import pytest
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
    
    # Simulate alternate route via D
    real_rt._handle_incoming_event({
        "type": "ROUTE_DISCOVERY_COMPLETED",
        "data": {
            "node_id": "A",
            "destination": "H",
            "next_hop": "D"
        }
    })
    assert real_rt.active_route == ["A", "D", "C", "H"]

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
