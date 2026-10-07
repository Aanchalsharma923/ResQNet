import pytest
from fastapi.testclient import TestClient
from resqnet.backend.app.main import app

client = TestClient(app)

def test_e2e_normal_sos():
    client.post("/api/simulation/reset")
    
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Normal SOS",
        "latitude": 18.5,
        "longitude": 73.8,
        "priority": "LOW"
    }
    
    # 1. First attempt fails but starts RREQ
    resp1 = client.post("/api/sos", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["success"] is False
    
    # 2. Second attempt succeeds
    resp2 = client.post("/api/sos", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["success"] is True
    assert resp2.json()["packet"]["status"] == "DELIVERED"
    
    # Check metrics
    metrics = client.get("/api/metrics").json()
    assert metrics["packets_sent"] > 0
    assert metrics["packets_delivered"] > 0

def test_e2e_disaster_recovery():
    client.post("/api/simulation/reset")
    
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Disaster SOS",
        "latitude": 18.5,
        "longitude": 73.8,
        "priority": "HIGH"
    }
    
    # Setup initial route
    client.post("/api/sos", json=payload)
    resp2 = client.post("/api/sos", json=payload)
    
    intermediate_hop = resp2.json()["packet"]["route_history"][1]
    
    # Fail intermediate node
    client.post(f"/api/nodes/{intermediate_hop}/fail")
    
    # Attempt send - fails and generates RERR
    resp3 = client.post("/api/sos", json=payload)
    assert resp3.json()["success"] is False
    
    # Attempt send - triggers new RREQ
    resp4 = client.post("/api/sos", json=payload)
    assert resp4.json()["success"] is False
    
    # Attempt send - succeeds via alternate route
    resp5 = client.post("/api/sos", json=payload)
    assert resp5.json()["success"] is True
    assert intermediate_hop not in resp5.json()["packet"]["route_history"]

def test_e2e_link_failure():
    client.post("/api/simulation/reset")
    
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Link Fail SOS",
        "latitude": 18.5,
        "longitude": 73.8,
        "priority": "HIGH"
    }
    
    client.post("/api/sos", json=payload)
    resp2 = client.post("/api/sos", json=payload)
    
    route = resp2.json()["packet"]["route_history"]
    node_a = route[1]
    node_b = route[2]
    
    # Fail Link node_a-node_b
    client.post("/api/links/fail", json={"node_a": node_a, "node_b": node_b})
    
    # Attempt send - fails and generates RERR
    client.post("/api/sos", json=payload)
    
    # Attempt send - triggers new RREQ
    client.post("/api/sos", json=payload)
    
    # Attempt send - succeeds via alternate route
    resp5 = client.post("/api/sos", json=payload)
    assert resp5.json()["success"] is True
    
def test_e2e_unrecoverable_failure():
    client.post("/api/simulation/reset")
    
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Unrecoverable SOS",
        "latitude": 18.5,
        "longitude": 73.8,
        "priority": "CRITICAL"
    }
    
    # Fail both B and D to partition A from the rest of the network
    client.post("/api/nodes/B/fail")
    client.post("/api/nodes/D/fail")
    
    # First attempt - generates RREQ but no RREP will be received
    resp1 = client.post("/api/sos", json=payload)
    assert resp1.json()["success"] is False
    
    # Check metrics to ensure RREQ was sent but no RREP
    metrics = client.get("/api/metrics").json()
    assert metrics["rreq_count"] > 0
    
    # Next attempt should still fail since there's no path
    resp2 = client.post("/api/sos", json=payload)
    assert resp2.json()["success"] is False
