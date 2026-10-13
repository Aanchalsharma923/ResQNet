import pytest
import time
from fastapi.testclient import TestClient
from resqnet.backend.app.main import app
from resqnet.backend.app.services.demo_service import demo_service
from resqnet.backend.app.services.runtime_manager import runtime_manager

client = TestClient(app)

def test_demo_stage_1_initialization():
    """
    Stage 1: Verify clean network initialization and initial AODV route discovery.
    """
    resp = client.post("/api/demo/start")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_stage"] == 1
    assert data["status"] in ("running", "ready")
    assert len(data["active_nodes"]) == 5
    assert set(data["active_nodes"]) == {"A", "B", "C", "D", "H"}
    assert data["active_route"] == ["A", "B", "C", "H"]
    assert "concept" in data["stage_info"]
    assert len(data["stage_info"]["observations"]) >= 3


def test_demo_stage_2_sos_dispatch():
    """
    Stage 2: Verify dispatch of genuine SOS DATA packet with unique message ID.
    """
    client.post("/api/demo/start")
    resp = client.post("/api/demo/step/2")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_stage"] == 2
    last_res = data["last_action_result"]
    assert last_res["success"] is True
    assert last_res["message_id"] == "sos-demo-stage2"


def test_demo_stage_3_hospital_ack():
    """
    Stage 3: Verify authenticated delivery at Hospital-H and ACK confirmation at Rescue-A with RTT.
    """
    client.post("/api/demo/start")
    client.post("/api/demo/step/2")
    resp = client.post("/api/demo/step/3")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_stage"] == 3
    last_res = data["last_action_result"]
    assert last_res["success"] is True
    assert last_res["delivered_to_hospital"] is True
    assert last_res["ack_confirmed"] is True
    assert last_res["rtt_ms"] is not None
    assert last_res["rtt_ms"] >= 0

    # Check hospital inbox directly
    inbox = client.get("/api/hospital/inbox").json()
    matching = [m for m in inbox if m["message_id"] == "sos-demo-stage2"]
    assert len(matching) == 1
    assert matching[0]["status"] == "DELIVERED"


def test_demo_stage_4_relay_failure():
    """
    Stage 4: Inject failure of Relay-B, verify link breakage and active route invalidation.
    """
    client.post("/api/demo/start")
    client.post("/api/demo/step/2")
    client.post("/api/demo/step/3")
    resp = client.post("/api/demo/step/4")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_stage"] == 4
    last_res = data["last_action_result"]
    assert last_res["success"] is True
    assert last_res["failed_node"] == "B"
    assert "B" not in data["active_nodes"]
    assert data["active_route"] == []  # Route invalidated


def test_demo_stage_5_alternate_route_recovery():
    """
    Stage 5: Autonomous AODV rediscovery establishes alternate route through Relay-D.
    """
    client.post("/api/demo/start")
    client.post("/api/demo/step/2")
    client.post("/api/demo/step/3")
    client.post("/api/demo/step/4")
    resp = client.post("/api/demo/step/5")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_stage"] == 5
    last_res = data["last_action_result"]
    assert last_res["success"] is True
    assert last_res["traverses_alternate_relay"] is True
    assert data["active_route"] == ["A", "D", "C", "H"]
    assert last_res["ack_confirmed"] is True
    assert last_res["recovery_time"] != "N/A"


def test_demo_stage_6_summary_metrics():
    """
    Stage 6: Comprehensive summary metrics report with genuine measurements.
    """
    client.post("/api/demo/start")
    client.post("/api/demo/step/2")
    client.post("/api/demo/step/3")
    client.post("/api/demo/step/4")
    client.post("/api/demo/step/5")
    resp = client.post("/api/demo/step/6")
    assert resp.status_code == 200
    data = resp.json()

    assert data["current_stage"] == 6
    assert data["status"] == "completed"
    assert data["summary"] is not None
    summary = data["summary"]

    assert summary["sos_delivered"] == 2
    assert summary["acks_confirmed"] == 2
    assert summary["packets_dropped"] >= 0
    assert summary["pdr"] != "0%"
    assert summary["active_route_at_conclusion"] == ["A", "D", "C", "H"]
    assert summary["recovery_time"] != "N/A"
    assert "mode_explanation" in summary


def test_demo_sequential_navigation():
    """
    Test next, prev, and status endpoints across stage sequence.
    """
    client.post("/api/demo/reset")

    # Check status
    s0 = client.get("/api/demo/status").json()
    assert s0["current_stage"] == 1

    # Advance via next
    s1 = client.post("/api/demo/next").json()
    assert s1["current_stage"] == 2

    s2 = client.post("/api/demo/next").json()
    assert s2["current_stage"] == 3

    # Step backwards
    p1 = client.post("/api/demo/prev").json()
    assert p1["current_stage"] == 2


def test_demo_repeatability_and_clean_reset():
    """
    Run through stages, reset, and run again. Verify zero stale state and clean repeatability.
    """
    # Run 1
    client.post("/api/demo/start")
    client.post("/api/demo/step/2")
    client.post("/api/demo/step/3")
    client.post("/api/demo/step/4")
    client.post("/api/demo/step/5")
    client.post("/api/demo/step/6")

    inbox1 = client.get("/api/hospital/inbox").json()
    assert len(inbox1) == 2

    # Reset
    reset_resp = client.post("/api/demo/reset")
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["current_stage"] == 1

    inbox_reset = client.get("/api/hospital/inbox").json()
    assert len(inbox_reset) == 0

    # Run 2
    client.post("/api/demo/step/2")
    client.post("/api/demo/step/3")
    inbox2 = client.get("/api/hospital/inbox").json()
    assert len(inbox2) == 1
    assert inbox2[0]["message_id"] == "sos-demo-stage2"


def test_demo_failure_when_no_route_possible():
    """
    Verify that when both Relay-B and Relay-D are down, SOS delivery fails gracefully
    without fabricating delivery or ACK confirmation.
    """
    client.post("/api/demo/reset")

    # Fail both B and D
    client.post("/api/nodes/B/fail")
    client.post("/api/nodes/D/fail")

    # Send SOS
    resp = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "ISOLATED SOS",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH"
    })
    assert resp.status_code == 200
    data = resp.json()

    # Hospital inbox must NOT receive this message
    inbox = client.get("/api/hospital/inbox").json()
    assert not any(m.get("message") == "ISOLATED SOS" for m in inbox)

    # SOS status at Rescue-A must NOT be confirmed
    msg_id = data["message_id"]
    status_resp = client.get(f"/api/sos/status/{msg_id}").json()
    assert status_resp["status"] != "CONFIRMED"
