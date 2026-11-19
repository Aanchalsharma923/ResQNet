import pytest
from fastapi.testclient import TestClient
from resqnet.backend.app.main import app
from resqnet.backend.app.services.simulation_service import simulation_service
from resqnet.backend.app.models.packet import Packet, PacketType

client = TestClient(app)

def test_1_successful_a_b_c_h_sos_and_hospital_inbox():
    """
    1. A successful A -> B -> C -> H SOS delivery and hospital inbox insertion.
    """
    reset_resp = client.post("/api/simulation/reset")
    assert reset_resp.status_code == 200

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "EMERGENCY: Immediate Evacuation Required",
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
    assert data["packet"]["route_history"] == ["A", "B", "C", "H"]
    assert data["ack_status"] == "CONFIRMED"

    # Verify hospital inbox
    inbox_resp = client.get("/api/hospital/inbox")
    assert inbox_resp.status_code == 200
    inbox = inbox_resp.json()
    assert len(inbox) >= 1
    found = [m for m in inbox if m["message_id"] == data["message_id"]]
    assert len(found) == 1
    assert found[0]["source_id"] == "A"
    assert found[0]["priority"] == "CRITICAL"
    assert found[0]["message"] == "EMERGENCY: Immediate Evacuation Required"

    # Verify network state active route
    net_resp = client.get("/api/network")
    assert net_resp.status_code == 200
    net_state = net_resp.json()
    assert net_state["active_route"] == ["A", "B", "C", "H"]


def test_2_correct_message_id_correlation_and_confirmed_ack():
    """
    2. Correct message-ID correlation and confirmed ACK.
    """
    client.post("/api/simulation/reset")
    unique_msg_id = "SOS-CORRELATION-TEST-001"

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "CORRELATION TEST PAYLOAD",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "message_id": unique_msg_id,
        "auto_discover": True
    }

    resp = client.post("/api/sos", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_id"] == unique_msg_id

    # Query status endpoint for this specific message_id
    status_resp = client.get(f"/api/sos/status/{unique_msg_id}")
    assert status_resp.status_code == 200
    ack_info = status_resp.json()
    assert ack_info["message_id"] == unique_msg_id
    assert ack_info["status"] == "CONFIRMED"
    assert ack_info["source_id"] == "A"
    assert ack_info["destination_id"] == "H"
    assert ack_info["rtt_ms"] is not None
    assert ack_info["rtt_ms"] >= 0.0

    # Query a non-existent message ID
    missing_resp = client.get("/api/sos/status/NON-EXISTENT-ID-999")
    assert missing_resp.status_code == 404 or missing_resp.json() is None


def test_3_delivery_event_does_not_falsely_confirm_ack():
    """
    3. A delivery event that does not falsely confirm an ACK.
    Verify that receiving a DATA packet or delivery event does not mark an unrelated or pending ACK as CONFIRMED.
    """
    client.post("/api/simulation/reset")

    # Manually register a pending ACK for message X
    fake_msg_id = "SOS-UNCONFIRMED-XYZ"
    simulation_service._pending_acks[fake_msg_id] = {
        "message_id": fake_msg_id,
        "source_id": "A",
        "destination_id": "H",
        "status": "PENDING",
        "created_at": 10.0,
        "deadline": 20.0,
        "timeout_seconds": 10.0,
        "confirmed_at": None,
        "rtt_ms": None
    }

    # Simulate arrival of an ordinary DATA packet (not an ACK)
    data_packet = Packet(
        source_id="A",
        destination_id="H",
        payload={"type": "ping", "content": "hello"}
    )
    simulation_service._on_simulation_event("DATA_DELIVERED", data_packet)

    # Confirm that fake_msg_id is STILL PENDING
    status = simulation_service.get_sos_status(fake_msg_id)
    assert status["status"] == "PENDING"
    assert status["confirmed_at"] is None

    # Simulate arrival of an ACK for a DIFFERENT message ID
    ack_packet_other = Packet(
        source_id="H",
        destination_id="A",
        payload={"type": "ack", "ack_for_message_id": "SOME-OTHER-ID", "timestamp": 12.0}
    )
    simulation_service._on_simulation_event("DATA_DELIVERED", ack_packet_other)

    # fake_msg_id must STILL be PENDING because the ACK was for SOME-OTHER-ID
    status_after = simulation_service.get_sos_status(fake_msg_id)
    assert status_after["status"] == "PENDING"
    assert status_after["confirmed_at"] is None


def test_4_dropped_packet_produces_accurate_metrics():
    """
    4. A dropped packet that does not produce misleading delivery metrics (e.g. 100% PDR when dropped).
    """
    client.post("/api/simulation/reset")

    # Sever all links out of A
    client.post("/api/links/fail", json={"node_a": "A", "node_b": "B"})
    client.post("/api/links/fail", json={"node_a": "A", "node_b": "D"})

    # Attempt to send message with auto_discover=False (no route can be found)
    send_resp = client.post("/api/messages/send", json={
        "source": "A",
        "destination": "H",
        "message": "This packet cannot be delivered"
    })
    assert send_resp.status_code == 200
    res_data = send_resp.json()
    assert res_data["success"] is False

    # Check metrics
    metrics_resp = client.get("/api/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()

    assert metrics["packets_sent"] >= 1
    assert metrics["packets_dropped"] >= 1
    assert metrics["packets_delivered"] == 0
    # Must NOT report 100.0% delivery
    assert metrics["pdr"] != "100.0%"
    assert metrics["loss"] == "100.0%"


def test_5_link_ab_failure_and_alternate_route_via_d():
    """
    5. A-B link failure followed by successful alternate-route delivery through A -> D -> C -> H.
    """
    client.post("/api/simulation/reset")

    # Initial delivery establishes A -> B -> C -> H
    resp1 = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "First SOS via primary",
        "auto_discover": True
    })
    assert resp1.status_code == 200
    assert resp1.json()["packet"]["route_history"] == ["A", "B", "C", "H"]

    # Verify active route in network state
    state1 = client.get("/api/network").json()
    assert state1["active_route"] == ["A", "B", "C", "H"]

    # Now sever link A-B
    fail_resp = client.post("/api/links/fail", json={"node_a": "A", "node_b": "B"})
    assert fail_resp.status_code == 200

    # Verify link A-B is inactive and active route is invalidated
    state_after_fail = client.get("/api/network").json()
    ab_link = next(l for l in state_after_fail["links"] if (l["node_a_id"] == "A" and l["node_b_id"] == "B") or (l["node_a_id"] == "B" and l["node_b_id"] == "A"))
    assert ab_link["is_active"] is False
    assert state_after_fail["active_route"] == []

    # Send second SOS with auto_discover=True
    resp2 = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Second SOS via alternate",
        "auto_discover": True
    })
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["success"] is True
    assert data2["packet"]["status"] == "DELIVERED"
    # Route history MUST be through D, not B!
    assert data2["packet"]["route_history"] == ["A", "D", "C", "H"]
    assert data2["ack_status"] == "CONFIRMED"

    # Verify active route now shows alternate path
    state_after_recover = client.get("/api/network").json()
    assert state_after_recover["active_route"] == ["A", "D", "C", "H"]

    # Verify hospital inbox contains both SOS messages in arrival order
    inbox = client.get("/api/hospital/inbox").json()
    assert len(inbox) == 2
    assert inbox[0]["message"] == "First SOS via primary"
    assert inbox[1]["message"] == "Second SOS via alternate"


def test_6_route_invalidation_and_restoration():
    """
    6. Route invalidation and restoration after failure/recovery.
    """
    client.post("/api/simulation/reset")

    # Discover route
    client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Pre-failure SOS",
        "auto_discover": True
    })
    assert client.get("/api/network").json()["active_route"] == ["A", "B", "C", "H"]

    # Fail Node B
    client.post("/api/nodes/B/fail")
    state = client.get("/api/network").json()
    node_b = next(n for n in state["nodes"] if n["node_id"] == "B")
    assert node_b["is_active"] is False
    # Route through B must be invalidated
    assert state["active_route"] == []

    # Recover Node B
    client.post("/api/nodes/B/recover")
    state_rec = client.get("/api/network").json()
    node_b_rec = next(n for n in state_rec["nodes"] if n["node_id"] == "B")
    assert node_b_rec["is_active"] is True


def test_7_repeated_reset_and_sos_dispatch_without_stale_state():
    """
    7. Repeated reset and SOS dispatch without stale state.
    """
    for cycle in range(3):
        # Reset
        client.post("/api/simulation/reset")
        inbox = client.get("/api/hospital/inbox").json()
        assert inbox == [], f"Inbox not empty in cycle {cycle}"

        metrics = client.get("/api/metrics").json()
        assert metrics["packets_sent"] == 0
        assert metrics["packets_delivered"] == 0
        assert metrics["packets_dropped"] == 0

        # Dispatch
        msg = f"Cycle {cycle} Emergency"
        res = client.post("/api/sos", json={
            "source_id": "A",
            "destination_id": "H",
            "message": msg,
            "auto_discover": True
        }).json()
        assert res["success"] is True

        inbox = client.get("/api/hospital/inbox").json()
        assert len(inbox) == 1
        assert inbox[0]["message"] == msg


def test_8_consistency_between_backend_api_and_dashboard_state():
    """
    8. Consistency between backend API responses and displayed dashboard state.
    """
    client.post("/api/simulation/reset")

    net = client.get("/api/network").json()
    metrics = client.get("/api/metrics").json()
    inbox = client.get("/api/hospital/inbox").json()

    assert net["active_route"] == []
    assert len(net["nodes"]) == 5
    assert len(net["links"]) == 5
    assert inbox == []
    assert metrics["pdr"] == "0%"

    # Dispatch SOS
    sos_res = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Consistency Test SOS",
        "auto_discover": True
    }).json()

    net_after = client.get("/api/network").json()
    metrics_after = client.get("/api/metrics").json()
    inbox_after = client.get("/api/hospital/inbox").json()

    # Net state route matches packet route
    assert net_after["active_route"] == sos_res["packet"]["route_history"]
    # Inbox contains exact message_id
    assert inbox_after[0]["message_id"] == sos_res["message_id"]
    # Metrics reflect exactly 1 sent and 1 delivered
    assert metrics_after["packets_sent"] == 1
    assert metrics_after["packets_delivered"] == 1
    assert metrics_after["pdr"] == "100.0%"
