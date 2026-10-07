import pytest
from fastapi.testclient import TestClient
from resqnet.backend.app.main import app

client = TestClient(app)

def test_sos_disaster_recovery():
    # 1. Reset network
    client.post("/api/simulation/reset")

    # 2. Send SOS from A to H
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Emergency SOS from A",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH"
    }

    # First send triggers RREQ/RREP, DATA packet dropped
    resp1 = client.post("/api/sos", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["success"] is False # Because route was not yet established

    # Now the route is established, send again
    resp2 = client.post("/api/sos", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True
    assert data2["packet"]["status"] == "DELIVERED"
    
    intermediate_hop = data2["packet"]["route_history"][1]

    # Verify Hospital inbox contains it
    inbox = client.get("/api/hospital/inbox").json()
    assert len(inbox) > 0
    assert any(item["message"] == "Emergency SOS from A" for item in inbox)
    initial_inbox_count = len(inbox)

    # 6. Fail the intermediate node (B or D)
    client.post(f"/api/nodes/{intermediate_hop}/fail")

    # 7. Send another SOS from A to H (this will fail and trigger RERR)
    payload3 = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Second Emergency SOS from A",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH"
    }
    
    resp3 = client.post("/api/sos", json=payload3)
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["success"] is False
    
    events = client.get("/api/events").json()
    assert any("RERR_GENERATED" in e for e in events)

    # 8. Send SOS again to trigger route discovery
    resp4 = client.post("/api/sos", json=payload3)
    assert resp4.status_code == 200
    data4 = resp4.json()
    assert data4["success"] is False # Drops but initiates RREQ
    
    events2 = client.get("/api/events").json()
    assert any("ROUTE_DISCOVERY_COMPLETED" in e for e in events2)

    # 9. Send SOS a final time. Now the new route is active!
    resp5 = client.post("/api/sos", json=payload3)
    assert resp5.status_code == 200
    data5 = resp5.json()
    assert data5["success"] is True
    assert data5["packet"]["status"] == "DELIVERED"
    assert "B" not in data5["packet"]["route_history"]

    # Verify hospital inbox contains the new SOS
    inbox_final = client.get("/api/hospital/inbox").json()
    assert len(inbox_final) == initial_inbox_count + 1
    assert any(item["message"] == "Second Emergency SOS from A" for item in inbox_final)
