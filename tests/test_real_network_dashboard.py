import pytest
import time
from fastapi.testclient import TestClient

from resqnet.backend.app.main import app
from resqnet.backend.app.services.runtime_manager import runtime_manager
from resqnet.backend.app.runtime.real_network_runtime import RealNetworkRuntime

client = TestClient(app)

def setup_function():
    # Ensure mode starts in simulation for test isolation
    runtime_manager.set_mode("simulation")

def teardown_function():
    # Restore simulation mode and ensure real runtime processes stopped
    runtime_manager.set_mode("simulation")
    if runtime_manager.real_runtime.is_running:
        runtime_manager.real_runtime.stop()

def test_runtime_manager_mode_switching():
    assert runtime_manager.get_mode() == "simulation"
    
    # Switch to real
    res = runtime_manager.set_mode("real")
    assert res["status"] == "success"
    assert runtime_manager.get_mode() == "real"
    
    # State reflects real mode
    state = runtime_manager.get_network_state()
    assert state["mode"] == "real"
    assert "nodes" in state
    assert "links" in state
    assert "active_route" in state
    
    # Invalid mode
    with pytest.raises(ValueError):
        runtime_manager.set_mode("invalid_mode")
        
    # Switch back to simulation
    runtime_manager.set_mode("simulation")
    assert runtime_manager.get_mode() == "simulation"
    sim_state = runtime_manager.get_network_state()
    assert sim_state["mode"] == "simulation"

def test_api_runtime_mode_endpoints():
    # GET mode
    res = client.get("/api/runtime/mode")
    assert res.status_code == 200
    assert res.json()["mode"] == "simulation"
    
    # POST mode -> real
    res = client.post("/api/runtime/mode", json={"mode": "real"})
    assert res.status_code == 200
    assert res.json()["mode"] == "real"
    
    # GET status
    res = client.get("/api/runtime/status")
    assert res.status_code == 200
    status_data = res.json()
    assert status_data["mode"] == "real"
    assert "real_nodes" in status_data
    
    # GET network in real mode
    res = client.get("/api/network")
    assert res.status_code == 200
    net_data = res.json()
    assert net_data["mode"] == "real"
    assert len(net_data["nodes"]) >= 5
    
    # POST mode -> invalid
    res = client.post("/api/runtime/mode", json={"mode": "unknown"})
    assert res.status_code == 400
    
    # Restore simulation
    client.post("/api/runtime/mode", json={"mode": "simulation"})

def test_real_network_runtime_event_handling():
    real_rt = RealNetworkRuntime()
    
    # Simulate incoming RREQ_GENERATED event
    real_rt._handle_incoming_event({
        "type": "RREQ_GENERATED",
        "data": {
            "node_id": "A",
            "source_id": "A",
            "destination_id": "H",
            "packet_id": "pkt-1"
        }
    })
    assert real_rt.metrics["rreq_count"] == 1
    
    # Simulate distributed AODV RREP propagation and forward route installation
    real_rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "C", "dest": "H", "next": "H", "hops": "1"}
    })
    real_rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "B", "dest": "H", "next": "C", "hops": "2"}
    })
    real_rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "A", "dest": "H", "next": "B", "hops": "3"}
    })
    
    # Simulate ROUTE_DISCOVERY_COMPLETED at node A
    real_rt._handle_incoming_event({
        "type": "ROUTE_DISCOVERY_COMPLETED",
        "data": {
            "node_id": "A",
            "destination": "H",
            "next_hop": "B"
        }
    })
    assert real_rt.active_route == ["A", "B", "C", "H"]
    
    # Simulate DATA_CREATED and DATA_DELIVERED
    real_rt._handle_incoming_event({
        "type": "DATA_CREATED",
        "data": {
            "node_id": "A",
            "packet_id": "data-1",
            "source_id": "A",
            "destination_id": "H"
        }
    })
    assert real_rt.metrics["packets_sent"] == 1
    
    real_rt._handle_incoming_event({
        "type": "DATA_DELIVERED",
        "data": {
            "node_id": "H",
            "packet_id": "data-1",
            "hop_count": 3
        }
    })
    assert real_rt.metrics["packets_delivered"] == 1
    assert real_rt.metrics["total_hop_count"] == 3
    
    # Simulate SOS_DELIVERED
    sos_data = {
        "message_id": "sos-123",
        "source_id": "A",
        "destination_id": "H",
        "message": "HELP REQUIRED",
        "status": "DELIVERED"
    }
    real_rt._handle_incoming_event({
        "type": "SOS_DELIVERED",
        "data": sos_data
    })
    assert len(real_rt.get_hospital_inbox()) == 1
    assert real_rt.get_hospital_inbox()[0]["message_id"] == "sos-123"
    
    # Simulate NEIGHBOR_DOWN for B
    real_rt._handle_incoming_event({
        "type": "NEIGHBOR_DOWN",
        "data": {
            "node_id": "A",
            "neighbor_id": "B"
        }
    })
    # Active route containing B should be invalidated
    assert real_rt.active_route == []
    assert real_rt.neighbor_health["A"]["B"] == "DOWN"
    
    # Incomplete route: only A reported next_hop=D, but D has not yet installed forward route to H
    real_rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "A", "dest": "H", "next": "D", "hops": "3"}
    })
    real_rt._handle_incoming_event({
        "type": "ROUTE_DISCOVERY_COMPLETED",
        "data": {
            "node_id": "A",
            "destination": "H",
            "next_hop": "D"
        }
    })
    # Since D has not installed route to H, route must NOT be fabricated!
    assert real_rt.active_route == []

    # Now D receives RREP and installs forward route to H via C
    real_rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "D", "dest": "H", "next": "C", "hops": "2"}
    })
    # Now all hops (A->D, D->C, C->H) are supported by actual AODV routing state
    assert real_rt.active_route == ["A", "D", "C", "H"]


def test_route_ownership_strict_separation():
    """
    Verifies that:
    1. A route is displayed only when supported by actual AODV routing table entries.
    2. Displayed consecutive nodes must be valid configured neighbors.
    3. Invalidated routes and failed nodes are not displayed as active.
    4. An unreachable destination is represented as unreachable, not fabricated.
    5. Reconstructed path cannot alter node forwarding decisions.
    """
    from resqnet.backend.app.runtime.real_network_runtime import RealNetworkRuntime
    rt = RealNetworkRuntime()
    assert rt.active_route == []

    # Case 1: Non-neighbor link injection (e.g. A->H directly) must be rejected
    rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "A", "dest": "H", "next": "H", "hops": "1"}
    })
    # A and H are not direct neighbors in DEFAULT_LINKS, so must not display as active route
    assert rt.active_route == []

    # Case 2: Partial path (C->H only, A->H unknown) -> no active route from A
    rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "C", "dest": "H", "next": "H", "hops": "1"}
    })
    assert rt.active_route == []

    # Case 3: Proper full path established via B (C->H, B->C, A->B)
    rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "B", "dest": "H", "next": "C", "hops": "2"}
    })
    rt._handle_incoming_event({
        "type": "FORWARD_ROUTE_INSTALLED",
        "data": {"node_id": "A", "dest": "H", "next": "B", "hops": "3"}
    })
    assert rt.active_route == ["A", "B", "C", "H"]

    # Case 4: Route invalidation at node B -> active route cleared immediately
    rt._handle_incoming_event({
        "type": "ROUTE_INVALIDATED",
        "data": {"node_id": "B", "destination": "H"}
    })
    assert rt.active_route == []

    # Case 5: Node failure (B DOWN) -> active route remains cleared
    rt._handle_incoming_event({
        "type": "NEIGHBOR_DOWN",
        "data": {"node_id": "A", "neighbor_id": "B"}
    })
    assert rt.active_route == []
    assert rt.neighbor_health["A"]["B"] == "DOWN"

    # Case 6: Unreachable destination -> when destination cannot be reached, no route fabricated
    rt._handle_incoming_event({
        "type": "ROUTE_INVALIDATED",
        "data": {"node_id": "C", "destination": "H"}
    })
    assert rt.active_route == []

def test_websocket_initial_state_contract():
    with client.websocket_connect("/api/ws/simulation") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "INITIAL_STATE"
        assert "event_id" in msg
        assert "timestamp" in msg
        assert "data" in msg
        data = msg["data"]
        assert "nodes" in data
        assert "links" in data
        assert "mode" in data


def test_metric_consistency_pdr_and_loss_reconciliation():
    """
    Phase 5.3: Verify that PDR and Loss use consistent denominators and reconcile mathematically:
    packets_sent = packets_delivered + packets_dropped -> PDR + Loss = 100.0%.
    """
    rt = RealNetworkRuntime()
    assert rt.get_metrics()["pdr"] == "0%"
    assert rt.get_metrics()["loss"] == "0%"
    assert rt.get_metrics()["latency"] == "N/A"
    assert rt.get_metrics()["throughput"] == "N/A"

    # Simulate 4 packets sent: 2 delivered, 2 dropped
    rt._handle_incoming_event({"type": "DATA_CREATED", "data": {"packet_id": "p1"}})
    rt._handle_incoming_event({"type": "DATA_DROPPED", "data": {"packet_id": "p1", "reason": "NO_ROUTE"}})

    rt._handle_incoming_event({"type": "DATA_CREATED", "data": {"packet_id": "p2"}})
    rt._handle_incoming_event({"type": "DATA_DELIVERED", "data": {"packet_id": "p2", "hop_count": 3, "payload": "HELP"}})

    rt._handle_incoming_event({"type": "DATA_CREATED", "data": {"packet_id": "p3"}})
    rt._handle_incoming_event({"type": "DATA_DROPPED", "data": {"packet_id": "p3", "reason": "NO_ROUTE"}})

    rt._handle_incoming_event({"type": "DATA_CREATED", "data": {"packet_id": "p4"}})
    rt._handle_incoming_event({"type": "DATA_DELIVERED", "data": {"packet_id": "p4", "hop_count": 3, "payload": "RECOVERED"}})

    metrics = rt.get_metrics()
    assert metrics["packets_sent"] == 4
    assert metrics["packets_delivered"] == 2
    assert metrics["packets_dropped"] == 2
    assert metrics["pdr"] == "50.0%"
    assert metrics["loss"] == "50.0%"
    assert metrics["avg_hop_count"] == "3.0"


def test_route_recovery_time_and_discovery_time_measurement():
    """
    Phase 5.3: Verify route discovery and route recovery timers.
    """
    import time
    rt = RealNetworkRuntime()
    assert rt.metrics["route_discovery_time"] == "N/A"
    assert rt.metrics["recovery_time"] == "N/A"

    # 1. Route Discovery Time
    rt._handle_incoming_event({"type": "RREQ_GENERATED", "data": {"node_id": "A", "destination_id": "H"}})
    assert rt._route_discovery_start is not None
    time.sleep(0.01)

    rt._handle_incoming_event({
        "type": "ROUTE_DISCOVERY_COMPLETED",
        "data": {"node_id": "A", "dest": "H", "next_hop": "B"}
    })
    assert rt.metrics["route_discovery_time"] != "N/A"
    assert "ms" in rt.metrics["route_discovery_time"]
    assert rt._route_discovery_start is None

    # 2. Recovery Time
    # Invalidate route
    rt._handle_incoming_event({
        "type": "ROUTE_INVALIDATED",
        "data": {"node_id": "A", "dest": "H"}
    })
    assert rt._route_recovery_start is not None
    time.sleep(0.01)

    rt._handle_incoming_event({
        "type": "ROUTE_DISCOVERY_COMPLETED",
        "data": {"node_id": "A", "dest": "H", "next_hop": "D"}
    })
    assert rt.metrics["recovery_time"] != "N/A"
    assert "ms" in rt.metrics["recovery_time"]
    assert rt._route_recovery_start is None


def test_node_runtime_emits_data_dropped_on_no_route():
    """
    Phase 5.3: NodeRuntime must emit DATA_DROPPED when a DATA packet has no route.
    """
    from resqnet.backend.app.runtime.node import NodeRuntime
    events = []
    def record_event(etype, data):
        events.append((etype, data))

    endpoint_config = {
        "A": ("127.0.0.1", 52010),
        "H": ("127.0.0.1", 52014)
    }
    # No links connected between A and H
    runtime = NodeRuntime("A", endpoint_config, topology_links=[], event_callback=record_event)
    runtime.start()
    try:
        runtime.send_data("H", "TEST_PAYLOAD")
        time.sleep(0.1)

        event_types = [e[0] for e in events]
        assert "DATA_CREATED" in event_types
        assert "DATA_DROPPED" in event_types
        drop_data = [e[1] for e in events if e[0] == "DATA_DROPPED"][0]
        assert drop_data["node_id"] == "A"
        assert drop_data["reason"] == "NO_ROUTE_AVAILABLE"
    finally:
        runtime.stop()


def test_duplicate_sos_message_id_deduplication():
    """
    Phase 5.3: Hospital inbox de-duplicates identical message_ids while preserving distinct messages.
    """
    rt = RealNetworkRuntime()
    sos_1 = {
        "message_id": "sos-msg-1",
        "source_id": "A",
        "destination_id": "H",
        "message": "HELP REQUIRED",
        "status": "DELIVERED"
    }
    # Deliver initial SOS
    rt._handle_incoming_event({"type": "SOS_DELIVERED", "data": sos_1})
    assert len(rt.get_hospital_inbox()) == 1

    # Deliver duplicate of initial SOS (e.g. transport retry)
    rt._handle_incoming_event({"type": "SOS_DELIVERED", "data": dict(sos_1)})
    assert len(rt.get_hospital_inbox()) == 1

    # Deliver second distinct SOS (recovered SOS)
    sos_2 = {
        "message_id": "sos-msg-2",
        "source_id": "A",
        "destination_id": "H",
        "message": "HELP REQUIRED (RECOVERED)",
        "status": "DELIVERED"
    }
    rt._handle_incoming_event({"type": "SOS_DELIVERED", "data": sos_2})
    assert len(rt.get_hospital_inbox()) == 2
    assert [m["message"] for m in rt.get_hospital_inbox()] == ["HELP REQUIRED", "HELP REQUIRED (RECOVERED)"]

