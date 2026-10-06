from fastapi.testclient import TestClient
from resqnet.backend.app.main import app
from resqnet.backend.app.services.simulation_service import simulation_service
from resqnet.backend.app.services.broadcaster import broadcaster

client = TestClient(app)

def test_websocket_network_initialized():
    simulation_service.reset()
    
    with client.websocket_connect("/api/ws/simulation") as websocket:
        # First message should be NETWORK_INITIALIZED
        data = websocket.receive_json()
        assert data["type"] == "NETWORK_INITIALIZED"
        assert "data" in data
        assert "nodes" in data["data"]
        assert "links" in data["data"]

def test_websocket_node_failure():
    simulation_service.reset()
    
    with client.websocket_connect("/api/ws/simulation") as websocket:
        # Consume INITIALIZED event
        websocket.receive_json()
        
        # Trigger node failure via REST API
        response = client.post("/api/nodes/A/fail")
        assert response.status_code == 200
        
        # Check websocket event
        event = websocket.receive_json()
        assert event["type"] == "NODE_FAILED"
        assert event["data"]["node_id"] == "A"

def test_websocket_packet_events():
    simulation_service.reset()
    
    with client.websocket_connect("/api/ws/simulation") as websocket:
        # Consume INITIALIZED event
        websocket.receive_json()
        
        # Send a message
        response = client.post("/api/messages/send", json={
            "source": "A",
            "destination": "B",
            "message": "Hello from A"
        })
        assert response.status_code == 200
        
        # We should receive multiple events over the websocket
        events_received = []
        # Receive a few events or break on timeout
        for _ in range(5):
            event = websocket.receive_json()
            events_received.append(event["type"])
            
        assert "PACKET_CREATED" in events_received or "DATA_CREATED" in events_received
        assert "RREQ_GENERATED" in events_received
