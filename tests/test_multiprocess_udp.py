import pytest
import time
import subprocess
import sys
import socket
import json
import os
from resqnet.backend.app.runtime.node import NodeRuntime
from resqnet.backend.app.models.packet import Packet, PacketType

# Free port helper
def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture
def test_endpoints():
    return {
        "A": ("127.0.0.1", get_free_port()),
        "B": ("127.0.0.1", get_free_port()),
        "C": ("127.0.0.1", get_free_port())
    }

def test_node_runtime_lifecycle(test_endpoints):
    """UNIT: NodeRuntime construction and clean shutdown."""
    runtime = NodeRuntime("A", test_endpoints)
    assert not runtime.is_running
    
    runtime.start()
    assert runtime.is_running
    
    runtime.stop()
    assert not runtime.is_running

def test_multiprocess_ab_real_udp(test_endpoints):
    """MULTI-PROCESS: A -> B real UDP communication across OS processes."""
    # Write config to a temporary file
    config_file = "temp_test_config.json"
    with open(config_file, "w") as f:
        json.dump(test_endpoints, f)
        
    script = """
import sys, json, time, logging
from resqnet.backend.app.runtime.node import NodeRuntime
from resqnet.backend.app.models.packet import Packet, PacketType

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
node_id = sys.argv[1]
with open('temp_test_config.json') as f:
    config = json.load(f)
# Convert tuple ports back to tuple
config = {k: (v[0], v[1]) for k, v in config.items()}

runtime = NodeRuntime(node_id, config)
runtime.start()

if node_id == "A":
    # Wait for B to start
    time.sleep(1)
    # First send triggers Route Discovery (RREQ) because A doesn't have a route to B.
    # The packet itself is not queued by this basic AODV implementation.
    runtime.send_data("B", {"msg": "hello from A"})
    # Wait for RREP to come back
    time.sleep(1)
    # Second send uses the established route
    runtime.send_data("B", {"msg": "hello from A"})
    time.sleep(1)
    runtime.stop()
else:
    # Just listen
    time.sleep(3)
    runtime.stop()
"""
    script_file = "temp_runner.py"
    with open(script_file, "w") as f:
        f.write(script)
        
    try:
        proc_b = subprocess.Popen([sys.executable, script_file, "B"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc_a = subprocess.Popen([sys.executable, script_file, "A"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        try:
            stdout_a, _ = proc_a.communicate(timeout=5)
            stdout_b, _ = proc_b.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc_a.kill()
            proc_b.kill()
            stdout_a, stderr_a = proc_a.communicate()
            stdout_b, stderr_b = proc_b.communicate()
            print("A stdout:", stdout_a)
            print("A stderr:", stderr_a)
            print("B stdout:", stdout_b)
            print("B stderr:", stderr_b)
            raise
        
        # B should have received the packet and logged it as delivered
        assert b"PACKET DELIVERED" in stdout_b
        assert b"hello from A" in stdout_b
        
    finally:
        for p in [proc_a, proc_b]:
            if p.poll() is None:
                p.kill()
        if os.path.exists(config_file):
            os.remove(config_file)
        if os.path.exists(script_file):
            os.remove(script_file)

def test_multiprocess_process_isolation(test_endpoints):
    """MULTI-PROCESS: stopping B does not crash A or C."""
    config_file = "temp_test_config_iso.json"
    with open(config_file, "w") as f:
        json.dump(test_endpoints, f)
        
    script = """
import sys, json, time
from resqnet.backend.app.runtime.node import NodeRuntime

node_id = sys.argv[1]
with open('temp_test_config_iso.json') as f:
    config = json.load(f)
config = {k: (v[0], v[1]) for k, v in config.items()}

runtime = NodeRuntime(node_id, config)
runtime.start()

try:
    if node_id == "B":
        # Die early
        time.sleep(1)
        runtime.stop()
        sys.exit(0)
    else:
        # A and C stay alive
        time.sleep(3)
        runtime.stop()
except Exception:
    sys.exit(1)
"""
    script_file = "temp_runner_iso.py"
    with open(script_file, "w") as f:
        f.write(script)
        
    try:
        procs = {
            "A": subprocess.Popen([sys.executable, script_file, "A"]),
            "B": subprocess.Popen([sys.executable, script_file, "B"]),
            "C": subprocess.Popen([sys.executable, script_file, "C"])
        }
        
        # Wait for B to exit
        procs["B"].wait(timeout=3)
        assert procs["B"].returncode == 0
        
        # A and C should still be running
        assert procs["A"].poll() is None
        assert procs["C"].poll() is None
        
        procs["A"].wait(timeout=5)
        procs["C"].wait(timeout=5)
        
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.kill()
        if os.path.exists(config_file):
            os.remove(config_file)
        if os.path.exists(script_file):
            os.remove(script_file)

def test_port_collision(test_endpoints):
    """UNIT/MULTI: Port collisions are handled explicitly."""
    # Start runtime A
    runtime_a = NodeRuntime("A", test_endpoints)
    runtime_a.start()
    
    # Try starting another runtime A on the same port in the same process space
    runtime_a2 = NodeRuntime("A", test_endpoints)
    with pytest.raises(RuntimeError, match="Failed to bind UDP socket"):
        runtime_a2.start()
        
    runtime_a.stop()

def test_malformed_packet_resilience(test_endpoints):
    """MULTI-PROCESS: Node survives malformed datagrams."""
    runtime_b = NodeRuntime("B", test_endpoints)
    runtime_b.start()
    
    # Send garbage UDP
    dest = test_endpoints["B"]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(b"totally invalid json data", dest)
        
    time.sleep(0.1)
    
    # B should still be running
    assert runtime_b.is_running
    
    runtime_b.stop()
