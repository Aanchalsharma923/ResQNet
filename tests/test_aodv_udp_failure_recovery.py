import pytest
import time
import subprocess
import sys
import socket
import json
import os

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture
def test_config():
    return {
        "A": ("127.0.0.1", get_free_port()),
        "B": ("127.0.0.1", get_free_port()),
        "C": ("127.0.0.1", get_free_port()),
        "D": ("127.0.0.1", get_free_port()),
        "H": ("127.0.0.1", get_free_port()),
    }

def test_aodv_failure_recovery(test_config):
    """
    Test Phase 4.6 real AODV over UDP failure and recovery.
    A -> H initially uses B.
    B fails. A detects neighbor down, invalidates route.
    A wants to send DATA to H again -> triggers RREQ -> RREP via D -> Alternate Route.
    """
    config_file = "temp_aodv_fail_config.json"
    with open(config_file, "w") as f:
        json.dump(test_config, f)
        
    script_a = f"""
import sys, json, time, logging
from resqnet.backend.app.runtime.node import NodeRuntime

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(levelname)s] %(message)s')
with open('{config_file}') as f:
    raw_config = json.load(f)
endpoint_config = {{k: (v[0], v[1]) for k, v in raw_config.items()}}
topology_links = [("A", "B"), ("A", "D"), ("B", "C"), ("C", "D"), ("C", "H")]

# Fast timeouts for testing
runtime = NodeRuntime("A", endpoint_config, topology_links=topology_links)
runtime.start()
runtime.health_monitor.heartbeat_interval = 0.5
runtime.health_monitor.neighbor_timeout = 1.5

time.sleep(2)
logging.info("[A] Sending initial data...")
runtime.send_data("H", {{"msg": "MSG1"}})
time.sleep(1)

logging.info("[A] Sending second data...")
runtime.send_data("H", {{"msg": "MSG2"}})

# Give it time to detect B failing
time.sleep(3)

logging.info("[A] Sending third data (after B failure)...")
runtime.send_data("H", {{"msg": "MSG3"}})

time.sleep(2)
logging.info("[A] Sending fourth data (after recovery)...")
runtime.send_data("H", {{"msg": "MSG4"}})

time.sleep(1)
runtime.stop()
"""

    script_other = f"""
import sys, json, time, logging
from resqnet.backend.app.runtime.node import NodeRuntime

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(levelname)s] %(message)s')
node_id = sys.argv[1]
with open('{config_file}') as f:
    raw_config = json.load(f)
endpoint_config = {{k: (v[0], v[1]) for k, v in raw_config.items()}}
topology_links = [("A", "B"), ("A", "D"), ("B", "C"), ("C", "D"), ("C", "H")]

runtime = NodeRuntime(node_id, endpoint_config, topology_links=topology_links)
if node_id != "D":
    runtime.start()
    runtime.health_monitor.heartbeat_interval = 0.5
    runtime.health_monitor.neighbor_timeout = 1.5

if node_id == "B":
    time.sleep(4)
    # Stop B to simulate failure
    logging.info("[B] STOPPING SIMULATING FAILURE")
    runtime.stop()
elif node_id == "D":
    # D is down initially, joins the network late
    time.sleep(3)
    runtime.start()
    runtime.health_monitor.heartbeat_interval = 0.5
    runtime.health_monitor.neighbor_timeout = 1.5
    time.sleep(6)
    runtime.stop()
else:
    time.sleep(9)
    runtime.stop()
"""
    
    script_a_file = "temp_runner_a.py"
    with open(script_a_file, "w") as f:
        f.write(script_a)
        
    script_other_file = "temp_runner_other.py"
    with open(script_other_file, "w") as f:
        f.write(script_other)
        
    procs = {}
    outputs = {}
    try:
        # Start all nodes
        procs["A"] = subprocess.Popen([sys.executable, script_a_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for node in ["B", "C", "D", "H"]:
            procs[node] = subprocess.Popen(
                [sys.executable, script_other_file, node], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True
            )
            
        for node in ["A", "B", "C", "D", "H"]:
            stdout, _ = procs[node].communicate(timeout=12)
            outputs[node] = stdout
            
    except subprocess.TimeoutExpired:
        for p in procs.values():
            p.kill()
        raise
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.kill()
        if os.path.exists(config_file):
            os.remove(config_file)
        if os.path.exists(script_a_file):
            os.remove(script_a_file)
        if os.path.exists(script_other_file):
            os.remove(script_other_file)
            
    # Validations
    print(outputs["A"])
    print(outputs["B"])
    print(outputs["H"])
    
    # 1. A should detect B failing
    assert "HELLO TIMEOUT: B" in outputs["A"]
    assert "NEIGHBOR_DOWN: B" in outputs["A"]
    
    # 2. A should invalidate the route
    assert "INVALIDATING ROUTE TO * VIA B" in outputs["A"]
    
    # 3. A should generate RERR
    assert "RERR_GENERATED: node=A" in outputs["A"]
    
    # 4. A should send MSG3, triggering new route discovery
    assert "RREQ_CREATED: node=A" in outputs["A"]
    
    # 5. H should receive MSG2 and MSG4
    assert "MSG2" in outputs["H"]
    assert "MSG4" in outputs["H"]
