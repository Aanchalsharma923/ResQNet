import time
import pytest
from fastapi.testclient import TestClient
from resqnet.backend.app.main import app
from resqnet.backend.app.services.simulation_service import simulation_service
from resqnet.backend.app.runtime.real_network_runtime import RealNetworkRuntime

client = TestClient(app)

def test_scenario_1_basic_sos_with_auto_discover():
    """
    Scenario 1:
    1. Reset the network.
    2. Verify all five nodes and links are active.
    3. Send an SOS from A to H with auto_discover=True.
    4. Perform AODV route discovery and forward over engine-managed path.
    5. Verify delivery into the hospital inbox on the first dispatch.
    6. Verify corresponding acknowledgement and source-side status.
    """
    reset_resp = client.post("/api/simulation/reset")
    assert reset_resp.status_code == 200
    state = client.get("/api/network").json()
    assert len(state["nodes"]) == 5
    assert all(n["is_active"] for n in state["nodes"])
    assert len(state["links"]) == 5
    assert all(l["is_active"] for l in state["links"])

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "EMERGENCY: Scenario 1 Basic SOS",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "auto_discover": True
    }

    resp = client.post("/api/sos", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["packet"]["status"] == "DELIVERED"
    assert data["packet"]["route_history"] == ["A", "B", "C", "H"]
    assert data["packet"]["destination_id"] == "H"
    msg_id = data["message_id"]

    # Verify hospital inbox
    inbox_resp = client.get("/api/hospital/inbox")
    assert inbox_resp.status_code == 200
    inbox = inbox_resp.json()
    assert any(entry.get("message_id") == msg_id for entry in inbox)

    # Verify source-side ACK status
    ack_resp = client.get(f"/api/sos/status/{msg_id}")
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["status"] == "CONFIRMED"
    assert ack_data["rtt_ms"] is not None

def test_scenario_2_alternate_route_after_link_failure():
    """
    Scenario 2:
    1. Reset the network.
    2. Disable link A <-> B.
    3. Send an SOS from A to H with auto_discover=True.
    4. Verify the route uses A -> D -> C -> H.
    5. Verify hospital delivery and acknowledgement.
    """
    client.post("/api/simulation/reset")

    # Disable link A <-> B
    fail_resp = client.post("/api/links/fail", json={"node_a": "A", "node_b": "B"})
    assert fail_resp.status_code == 200

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "EMERGENCY: Scenario 2 Alternate Route",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "CRITICAL",
        "auto_discover": True
    }

    resp = client.post("/api/sos", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["packet"]["status"] == "DELIVERED"
    assert data["packet"]["route_history"] == ["A", "D", "C", "H"]
    assert "B" not in data["packet"]["route_history"]
    msg_id = data["message_id"]

    # Hospital inbox verification
    inbox = client.get("/api/hospital/inbox").json()
    assert any(entry.get("message_id") == msg_id for entry in inbox)

    # ACK verification
    ack_data = client.get(f"/api/sos/status/{msg_id}").json()
    assert ack_data["status"] == "CONFIRMED"

def test_scenario_3_node_failure_and_recovery():
    """
    Scenario 3:
    1. Establish successful A-to-H communication.
    2. Fail node B on the primary route.
    3. Verify that old route is invalidated.
    4. Verify that AODV discovers valid alternate route via D.
    5. Verify delivery over alternate route.
    6. Recover node B and verify state is restored.
    """
    client.post("/api/simulation/reset")

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "EMERGENCY: Initial primary path",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "auto_discover": True
    }
    resp1 = client.post("/api/sos", json=payload)
    assert resp1.json()["success"] is True
    assert resp1.json()["packet"]["route_history"] == ["A", "B", "C", "H"]

    # Fail Node B
    fail_node_resp = client.post("/api/nodes/B/fail")
    assert fail_node_resp.status_code == 200

    # Dispatch second SOS; B is dead so AODV discovers A -> D -> C -> H
    payload2 = {
        "source_id": "A",
        "destination_id": "H",
        "message": "EMERGENCY: Scenario 3 After B Fail",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "CRITICAL",
        "auto_discover": True
    }
    resp2 = client.post("/api/sos", json=payload2)
    assert resp2.json()["success"] is True
    assert resp2.json()["packet"]["route_history"] == ["A", "D", "C", "H"]

    # Recover Node B
    rec_resp = client.post("/api/nodes/B/recover")
    assert rec_resp.status_code == 200
    state = client.get("/api/network").json()
    node_b = next(n for n in state["nodes"] if n["node_id"] == "B")
    assert node_b["is_active"] is True

def test_scenario_4_all_source_nodes_to_hospital():
    """
    Scenario 4:
    Test SOS delivery to H from A, B, C, and D where a valid path exists.
    Verify that ACK and inbox tracking work for all sources (not hardcoded to 'A').
    """
    for src in ["A", "B", "C", "D"]:
        client.post("/api/simulation/reset")
        payload = {
            "source_id": src,
            "destination_id": "H",
            "message": f"SOS from node {src}",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "HIGH",
            "auto_discover": True
        }
        resp = client.post("/api/sos", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True, f"Failed for source {src}"
        assert data["packet"]["status"] == "DELIVERED"
        assert data["packet"]["destination_id"] == "H"
        assert data["packet"]["route_history"][0] == src
        assert data["packet"]["route_history"][-1] == "H"

        msg_id = data["message_id"]
        inbox = client.get("/api/hospital/inbox").json()
        matching = [e for e in inbox if e.get("message_id") == msg_id]
        assert len(matching) == 1
        assert matching[0]["source_id"] == src

        ack_data = client.get(f"/api/sos/status/{msg_id}").json()
        assert ack_data["status"] == "CONFIRMED"
        assert ack_data["source_id"] == src

def test_scenario_5_reset_and_repeat():
    """
    Scenario 5:
    Run the basic SOS workflow repeatedly.
    Ensure second and third runs behave like the first without stale state leaking.
    """
    for iteration in range(3):
        client.post("/api/simulation/reset")
        inbox = client.get("/api/hospital/inbox").json()
        assert len(inbox) == 0, f"Inbox not empty after reset on iter {iteration}"

        metrics = client.get("/api/metrics").json()
        assert metrics["packets_sent"] == 0
        assert metrics["packets_delivered"] == 0

        payload = {
            "source_id": "A",
            "destination_id": "H",
            "message": f"Repeat SOS #{iteration}",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "HIGH",
            "auto_discover": True
        }
        resp = client.post("/api/sos", json=payload)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["packet"]["route_history"] == ["A", "B", "C", "H"]

        inbox_after = client.get("/api/hospital/inbox").json()
        assert len(inbox_after) == 1

def test_real_network_runtime_reset_method():
    """
    Verifies that RealNetworkRuntime.reset() cleanly clears inboxes,
    recent events, active routes, routing entries, and metrics.
    """
    rt = RealNetworkRuntime()
    rt.hospital_inbox.append({"message_id": "test-msg-123", "message": "Test"})
    rt.recent_events.append("DATA_FORWARDED A -> B")
    rt.active_route = ["A", "B", "C", "H"]
    rt.metrics["packets_sent"] = 5
    rt.metrics["packets_delivered"] = 5

    rt.reset()

    assert rt.hospital_inbox == []
    assert rt.recent_events == []
    assert rt.active_route == []
    assert rt.metrics["packets_sent"] == 0
    assert rt.metrics["packets_delivered"] == 0
