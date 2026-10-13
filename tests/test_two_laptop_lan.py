import os
import json
import time
import socket
import pytest
from resqnet.backend.app.config_loader import expand_env_vars, load_node_endpoints
from resqnet.backend.app.runtime.real_network_runtime import RealNetworkRuntime

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def test_expand_env_vars():
    # Test fallback when unset
    os.environ.pop("TEST_LAPTOP_IP", None)
    res = expand_env_vars("host: ${TEST_LAPTOP_IP:-127.0.0.1}")
    assert res == "host: 127.0.0.1"

    # Test override when set
    os.environ["TEST_LAPTOP_IP"] = "192.168.1.150"
    res = expand_env_vars("host: ${TEST_LAPTOP_IP:-127.0.0.1}")
    assert res == "host: 192.168.1.150"
    os.environ.pop("TEST_LAPTOP_IP", None)

def test_load_node_endpoints_two_laptops(tmp_path):
    config_file = str(tmp_path / "test_lan.json")
    raw = {
        "A": {"host": "${LAPTOP_1_IP:-10.0.0.1}", "port": 50010},
        "H": {"host": "${LAPTOP_2_IP:-10.0.0.2}", "port": 50014}
    }
    with open(config_file, "w") as f:
        json.dump(raw, f)

    # Default fallback
    os.environ.pop("LAPTOP_1_IP", None)
    os.environ.pop("LAPTOP_2_IP", None)
    endpoints = load_node_endpoints(config_file)
    assert endpoints["A"] == ("10.0.0.1", 50010)
    assert endpoints["H"] == ("10.0.0.2", 50014)

    # Custom LAN IPs
    os.environ["LAPTOP_1_IP"] = "192.168.1.42"
    os.environ["LAPTOP_2_IP"] = "192.168.1.99"
    endpoints_custom = load_node_endpoints(config_file)
    assert endpoints_custom["A"] == ("192.168.1.42", 50010)
    assert endpoints_custom["H"] == ("192.168.1.99", 50014)
    os.environ.pop("LAPTOP_1_IP", None)
    os.environ.pop("LAPTOP_2_IP", None)

def test_real_runtime_two_laptop_managed_nodes(tmp_path):
    """
    Verifies that Laptop 1 only launches processes for managed nodes (A, B, C, D)
    and treats Node H as a remote unmanaged node.
    """
    event_port = get_free_port()
    config_file = str(tmp_path / "lan_two_laptops.json")

    ports = {k: get_free_port() for k in ["A", "B", "C", "D", "H"]}
    raw_cfg = {k: {"host": "127.0.0.1", "port": ports[k]} for k in ports}
    with open(config_file, "w") as f:
        json.dump(raw_cfg, f)

    os.environ["RESQNET_MANAGED_NODES"] = "A,B,C,D"
    runtime = RealNetworkRuntime(config_path=config_file, event_port=event_port)

    assert runtime.managed_nodes == ["A", "B", "C", "D"]
    assert "H" in runtime.endpoint_config
    assert "H" not in runtime.managed_nodes

    try:
        # Start runtime (will only spawn A, B, C, D)
        runtime.start()
        time.sleep(0.5)

        # Check that only managed nodes have child processes
        assert "A" in runtime.processes
        assert "B" in runtime.processes
        assert "C" in runtime.processes
        assert "D" in runtime.processes
        assert "H" not in runtime.processes

        # Initially, remote node H is DOWN
        state = runtime.get_network_state()
        node_h = next(n for n in state["nodes"] if n["node_id"] == "H")
        assert node_h["is_active"] is False
        assert node_h["status"] == "DOWN"

    finally:
        runtime.stop()
        os.environ.pop("RESQNET_MANAGED_NODES", None)

def test_remote_event_ingestion_and_state_updates(tmp_path):
    """
    Simulates remote Node H on Laptop 2 sending UDP events across the network bridge.
    Verifies state updates, hospital inbox recording, and return ACK confirmation.
    """
    event_port = get_free_port()
    config_file = str(tmp_path / "lan_cfg.json")
    ports = {k: get_free_port() for k in ["A", "B", "C", "D", "H"]}
    raw_cfg = {k: {"host": "127.0.0.1", "port": ports[k]} for k in ports}
    with open(config_file, "w") as f:
        json.dump(raw_cfg, f)

    os.environ["RESQNET_MANAGED_NODES"] = "A,B,C,D"
    runtime = RealNetworkRuntime(config_path=config_file, event_port=event_port)

    try:
        # Start event listener without spawning child processes for this unit test
        runtime.is_running = True
        runtime._start_event_listener()
        time.sleep(0.1)

        # 1. Simulate remote Node H on Laptop 2 sending NODE_READY event over UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ready_ev = {
            "type": "NODE_READY",
            "data": {"node_id": "H", "status": "READY"}
        }
        s.sendto(json.dumps(ready_ev).encode("utf-8"), ("127.0.0.1", event_port))
        time.sleep(0.1)

        # Node H should now be marked UP in network state!
        state = runtime.get_network_state()
        node_h = next(n for n in state["nodes"] if n["node_id"] == "H")
        assert node_h["is_active"] is True
        assert node_h["status"] == "UP"

        # 2. Simulate remote Node H receiving SOS and emitting SOS_DELIVERED
        sos_ev = {
            "type": "SOS_DELIVERED",
            "data": {
                "message_id": "sos-lan-test-1",
                "source_id": "A",
                "destination_id": "H",
                "message": "CROSS_DEVICE_TEST",
                "priority": "CRITICAL"
            }
        }
        s.sendto(json.dumps(sos_ev).encode("utf-8"), ("127.0.0.1", event_port))
        time.sleep(0.1)

        inbox = runtime.get_hospital_inbox()
        assert len(inbox) == 1
        assert inbox[0]["message_id"] == "sos-lan-test-1"

        # 3. Simulate Node A receiving return ACK and confirming
        ack_ev = {
            "type": "ACK_RECEIVED",
            "data": {
                "message_id": "sos-lan-test-1",
                "source_id": "A",
                "hospital_id": "H",
                "rtt_ms": 42.5,
                "status": "CONFIRMED"
            }
        }
        s.sendto(json.dumps(ack_ev).encode("utf-8"), ("127.0.0.1", event_port))
        time.sleep(0.1)

        status_rec = runtime.get_sos_status("sos-lan-test-1")
        assert status_rec is not None
        assert status_rec["status"] == "CONFIRMED"

        # 4. Simulate neighbor failure detection for remote node H
        down_ev = {
            "type": "NEIGHBOR_DOWN",
            "data": {"node_id": "C", "neighbor_id": "H"}
        }
        s.sendto(json.dumps(down_ev).encode("utf-8"), ("127.0.0.1", event_port))
        time.sleep(0.1)

        state_after_fail = runtime.get_network_state()
        node_h_after = next(n for n in state_after_fail["nodes"] if n["node_id"] == "H")
        assert node_h_after["is_active"] is False
        assert node_h_after["status"] == "DOWN"
        link_ch = next(l for l in state_after_fail["links"] if (l["node_a_id"] == "C" and l["node_b_id"] == "H"))
        assert link_ch["is_active"] is False

        # 5. Simulate neighbor recovery for remote node H
        rec_ev = {
            "type": "NEIGHBOR_RECOVERED",
            "data": {"node_id": "C", "neighbor_id": "H"}
        }
        s.sendto(json.dumps(rec_ev).encode("utf-8"), ("127.0.0.1", event_port))
        time.sleep(0.1)

        state_after_rec = runtime.get_network_state()
        node_h_rec = next(n for n in state_after_rec["nodes"] if n["node_id"] == "H")
        assert node_h_rec["is_active"] is True
        assert node_h_rec["status"] == "UP"

        s.close()
    finally:
        runtime.stop()
        os.environ.pop("RESQNET_MANAGED_NODES", None)

def test_two_laptop_cross_process_end_to_end(tmp_path):
    """
    End-to-end test simulating actual 2-Laptop deployment:
    - Laptop 1 runs RealNetworkRuntime with managed_nodes = ["A", "B", "C", "D"]
    - Laptop 2 runs Node H as a separate standalone subprocess pointing to Laptop 1 event bridge
    - Tests route discovery, SOS delivery, return ACK confirmation, and clean shutdown.
    """
    import subprocess
    import sys

    event_port = get_free_port()
    config_file = str(tmp_path / "lan_two_laptops_test.json")
    ports = {k: get_free_port() for k in ["A", "B", "C", "D", "H"]}
    raw_cfg = {k: {"host": "127.0.0.1", "port": ports[k]} for k in ports}
    with open(config_file, "w") as f:
        json.dump(raw_cfg, f)

    # 1. Launch Laptop 1 runtime managing A, B, C, D
    os.environ["RESQNET_MANAGED_NODES"] = "A,B,C,D"
    runtime = RealNetworkRuntime(config_path=config_file, event_port=event_port)
    runtime.start()

    # 2. Launch Laptop 2 standalone process for Node H
    script_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../scripts/run_node.py")
    )
    ctrl_h_port = ports["H"] + 1000
    cmd_h = [
        sys.executable,
        script_path,
        "--node-id", "H",
        "--config", config_file,
        "--bind-host", "127.0.0.1",
        "--event-host", "127.0.0.1",
        "--event-port", str(event_port),
        "--control-port", str(ctrl_h_port)
    ]
    proc_h = subprocess.Popen(cmd_h)

    try:
        # Give nodes 2.5 seconds to start and exchange HELLO beacons
        time.sleep(2.5)

        # Verify all nodes are recognized as active
        state = runtime.get_network_state()
        active_ids = [n["node_id"] for n in state["nodes"] if n["is_active"]]
        assert "A" in active_ids
        assert "C" in active_ids
        assert "H" in active_ids

        # 3. Dispatch SOS from Rescue-A to Hospital-H
        sos_req = {
            "message_id": "sos-cross-device-001",
            "source_id": "A",
            "destination_id": "H",
            "message": "EMERGENCY TWO LAPTOP LAN TEST",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "CRITICAL",
            "timeout_seconds": 5.0
        }
        res = runtime.send_sos(sos_req)
        assert res.get("success") is True

        # Wait for AODV route discovery and forward traversal
        time.sleep(2.0)

        # If needed, send second confirmed packet along established route
        if not runtime.get_hospital_inbox():
            runtime.send_sos(sos_req)
            time.sleep(2.0)

        # 4. Verify Hospital-H on Laptop 2 received the SOS
        inbox = runtime.get_hospital_inbox()
        assert len(inbox) >= 1
        assert any(item.get("message_id") == "sos-cross-device-001" for item in inbox)

        # 5. Verify Rescue-A received and validated the return ACK from Hospital-H
        status_rec = runtime.get_sos_status("sos-cross-device-001")
        assert status_rec is not None
        assert status_rec.get("status") in ("CONFIRMED", "LATE_CONFIRMED")

    finally:
        # Clean shutdown of both laptops
        if proc_h.poll() is None:
            proc_h.terminate()
            try:
                proc_h.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc_h.kill()
        runtime.stop()
        os.environ.pop("RESQNET_MANAGED_NODES", None)
