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

def run_multiprocess_scenario(config, topology_links, source_node, dest_node, msg_payload):
    config_file = "temp_aodv_udp_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f)
        
    script = f"""
import sys, json, time, logging
from resqnet.backend.app.runtime.node import NodeRuntime

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(levelname)s] %(message)s')
node_id = sys.argv[1]
with open('{config_file}') as f:
    raw_config = json.load(f)
endpoint_config = {{k: (v[0], v[1]) for k, v in raw_config.items()}}

topology_links = {topology_links}

runtime = NodeRuntime(node_id, endpoint_config, topology_links=topology_links)
runtime.start()

if node_id == "{source_node}":
    time.sleep(2)
    logging.info(f"[{{node_id}}] Sending initial data to trigger RREQ...")
    runtime.send_data("{dest_node}", {msg_payload})
    time.sleep(2)
    logging.info(f"[{{node_id}}] Sending actual data over established route...")
    runtime.send_data("{dest_node}", {msg_payload})
    time.sleep(2)
else:
    time.sleep(6)

runtime.stop()
"""
    script_file = "temp_aodv_runner.py"
    with open(script_file, "w") as f:
        f.write(script)
        
    procs = {}
    outputs = {}
    try:
        # Start all nodes
        nodes = list(config.keys())
        for node in nodes:
            procs[node] = subprocess.Popen(
                [sys.executable, script_file, node], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True
            )
            
        for node in nodes:
            stdout, _ = procs[node].communicate(timeout=10)
            outputs[node] = stdout
            
        return outputs
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
        if os.path.exists(script_file):
            os.remove(script_file)

def test_aodv_route_discovery_and_data_delivery(test_config):
    """
    Test Phase 4.5 real AODV over UDP.
    A wants to send DATA to H.
    Should generate RREQ, propagate it, get RREP, and then send DATA.
    """
    topology_links = [("A", "B"), ("A", "D"), ("B", "C"), ("C", "D"), ("C", "H")]
    
    outputs = run_multiprocess_scenario(
        config=test_config, 
        topology_links=topology_links, 
        source_node="A", 
        dest_node="H", 
        msg_payload={"msg": "HELP REQUIRED"}
    )
            
    # 1. A should generate RREQ
    assert "RREQ_CREATED: node=A" in outputs["A"]
    
    # 2. H should generate RREP
    assert "RREP_GENERATED: node=H" in outputs["H"]
    
    # 3. C, B should forward RREP and install routes
    assert "FORWARD_ROUTE_INSTALLED: node=C dest=H" in outputs["C"]
    
    # B or D could install the route depending on which one was faster in the UDP race condition.
    assert ("FORWARD_ROUTE_INSTALLED: node=B dest=H" in outputs["B"]) or ("FORWARD_ROUTE_INSTALLED: node=D dest=H" in outputs["D"])
    
    assert "ROUTE_DISCOVERY_COMPLETED: node=A dest=H" in outputs["A"]
    
    # 4. DATA should reach H
    assert "PACKET DELIVERED" in outputs["H"]
    assert "HELP REQUIRED" in outputs["H"]


def test_aodv_alternate_path(test_config):
    """
    Test alternate path A-D-C-H by removing A-B link.
    """
    topology_links = [("A", "D"), ("B", "C"), ("C", "D"), ("C", "H")]
    
    outputs = run_multiprocess_scenario(
        config=test_config, 
        topology_links=topology_links, 
        source_node="A", 
        dest_node="H", 
        msg_payload={"msg": "ALT_HELP"}
    )
            
    # A generates RREQ
    assert "RREQ_CREATED: node=A" in outputs["A"]
    
    # B should NEVER see the packet because A-B is disconnected
    assert "FORWARD_ROUTE_INSTALLED" not in outputs["B"]
    
    # H generates RREP
    assert "RREP_GENERATED: node=H" in outputs["H"]
    
    # C and D MUST forward the RREP and install routes
    assert "FORWARD_ROUTE_INSTALLED: node=C dest=H" in outputs["C"]
    assert "FORWARD_ROUTE_INSTALLED: node=D dest=H" in outputs["D"]
    
    # A completes route discovery
    assert "ROUTE_DISCOVERY_COMPLETED: node=A dest=H" in outputs["A"]
    
    # DATA reaches H
    assert "PACKET DELIVERED" in outputs["H"]
    assert "ALT_HELP" in outputs["H"]

def test_aodv_no_route(test_config):
    """
    Test scenario where H is unreachable.
    """
    # C-H is removed, so H is isolated
    topology_links = [("A", "B"), ("A", "D"), ("B", "C"), ("C", "D")]
    
    outputs = run_multiprocess_scenario(
        config=test_config, 
        topology_links=topology_links, 
        source_node="A", 
        dest_node="H", 
        msg_payload={"msg": "HELP REQUIRED"}
    )
            
    # A generates RREQ
    assert "RREQ_CREATED: node=A" in outputs["A"]
    
    # H should NOT generate RREP
    assert "RREP_GENERATED: node=H" not in outputs["H"]
    
    # A does NOT complete route discovery
    assert "ROUTE_DISCOVERY_COMPLETED: node=A dest=H" not in outputs["A"]
    
    # DATA does NOT reach H
    assert "PACKET DELIVERED" not in outputs["H"]
