from fastapi.testclient import TestClient
from resqnet.backend.app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ResQNet"}

def test_get_network():
    response = client.get("/api/network")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) == 5
    assert len(data["links"]) == 5

def test_simulation_reset():
    # Fail a node first
    client.post("/api/nodes/B/fail")
    response = client.get("/api/network")
    node_b = next(n for n in response.json()["nodes"] if n["node_id"] == "B")
    assert node_b["is_active"] is False

    # Reset
    response = client.post("/api/simulation/reset")
    assert response.status_code == 200

    # Check node is recovered
    response = client.get("/api/network")
    node_b = next(n for n in response.json()["nodes"] if n["node_id"] == "B")
    assert node_b["is_active"] is True

def test_node_failure_and_recovery():
    # Fail
    response = client.post("/api/nodes/C/fail")
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    response = client.get("/api/network")
    node_c = next(n for n in response.json()["nodes"] if n["node_id"] == "C")
    assert node_c["is_active"] is False

    # Recover
    response = client.post("/api/nodes/C/recover")
    assert response.status_code == 200
    assert response.json()["is_active"] is True

    response = client.get("/api/network")
    node_c = next(n for n in response.json()["nodes"] if n["node_id"] == "C")
    assert node_c["is_active"] is True

def test_link_failure_and_recovery():
    payload = {"node_a": "A", "node_b": "B"}
    
    # Fail
    response = client.post("/api/links/fail", json=payload)
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    response = client.get("/api/network")
    link = next(l for l in response.json()["links"] if l["node_a_id"] == "A" and l["node_b_id"] == "B")
    assert link["is_active"] is False

    # Recover
    response = client.post("/api/links/recover", json=payload)
    assert response.status_code == 200
    assert response.json()["is_active"] is True

    response = client.get("/api/network")
    link = next(l for l in response.json()["links"] if l["node_a_id"] == "A" and l["node_b_id"] == "B")
    assert link["is_active"] is True

def test_send_message_integration():
    # Ensure fresh state
    client.post("/api/simulation/reset")

    payload = {
        "source": "A",
        "destination": "H",
        "message": "SOS"
    }

    # First send will trigger RREQ/RREP discovery and the original DATA packet will be dropped
    response1 = client.post("/api/messages/send", json=payload)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["success"] is False
    assert data1["packet"]["status"] == "DROPPED"
    
    # But route discovery should have succeeded in the background
    events = client.get("/api/events").json()
    assert any("RREQ_CREATED" in e for e in events)
    assert any("ROUTE_DISCOVERY_COMPLETED" in e for e in events)

    # Second send should succeed
    response2 = client.post("/api/messages/send", json=payload)
    assert response2.status_code == 200
    data2 = response2.json()
    
    assert data2["success"] is True
    assert data2["packet"]["payload"] == "SOS"
    assert data2["packet"]["destination_id"] == "H"
    assert data2["packet"]["status"] == "DELIVERED"
    
    metrics = client.get("/api/metrics").json()
    assert metrics["packets_sent"] > 0
    assert metrics["packets_delivered"] > 0
