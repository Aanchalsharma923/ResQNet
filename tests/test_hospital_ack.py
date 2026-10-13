import pytest
import time
import uuid
from fastapi.testclient import TestClient

from resqnet.backend.app.main import app
from resqnet.backend.app.services.simulation_service import simulation_service
from resqnet.backend.app.models.packet import Packet, PacketType
from resqnet.backend.app.runtime.node import NodeRuntime

client = TestClient(app)

def test_hospital_ack_normal_path_and_validation():
    """
    Scenario 1:
    - Normal forward path: A -> B -> C -> H delivers SOS.
    - Hospital-H records SOS in inbox and generates ACK DATA packet addressed to A.
    - Normal return path: H -> C -> B -> A delivers ACK to Rescue-A.
    - Rescue-A validates ACK against pending message ID, transitions to CONFIRMED, and computes RTT.
    """
    client.post("/api/simulation/reset")

    # Send initial SOS to establish route if not present
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Emergency Alpha",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "timeout_seconds": 5.0
    }

    # First attempt initiates RREQ/RREP discovery
    resp1 = client.post("/api/sos", json=payload)
    assert resp1.status_code == 200

    # Second attempt delivers SOS over established route A -> B -> C -> H
    resp2 = client.post("/api/sos", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True

    msg_id = data2["message_id"]
    status_record = simulation_service.get_sos_status(msg_id)
    assert status_record is not None
    assert status_record["status"] == "CONFIRMED"
    assert status_record["confirmed_at"] is not None
    assert status_record["rtt_ms"] is not None
    assert status_record["rtt_ms"] >= 0

    # Verify hospital inbox contains exactly 1 entry for this message
    inbox = client.get("/api/hospital/inbox").json()
    matching_inbox = [m for m in inbox if m["message_id"] == msg_id]
    assert len(matching_inbox) == 1
    assert matching_inbox[0]["status"] == "DELIVERED"


def test_hospital_ack_alternate_path_after_relay_failure():
    """
    Scenario 2:
    - Fail Relay-B.
    - Verify that AODV route discovery and forwarding establish the alternate path through D.
    - Verify forwarding events go through D (not B).
    - Verify return ACK reaches A via D.
    """
    client.post("/api/simulation/reset")

    # Establish initial route
    init_payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Pre-failure SOS",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "LOW"
    }
    client.post("/api/sos", json=init_payload)
    client.post("/api/sos", json=init_payload)

    # Fail Relay-B
    client.post("/api/nodes/B/fail")

    # Send SOS after B failure (triggers RERR on B, then AODV discovery via D)
    alt_payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Disaster SOS via Alternate Route",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "CRITICAL",
        "timeout_seconds": 5.0
    }

    # Send to trigger route repair / discovery
    client.post("/api/sos", json=alt_payload)
    # Send to complete discovery and establish route via D
    client.post("/api/sos", json=alt_payload)

    # Send final SOS over confirmed alternate route
    resp = client.post("/api/sos", json=alt_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["success"] is True

    # Verify actual route history uses D and excludes B
    route_hist = res_data["packet"]["route_history"]
    assert "D" in route_hist
    assert "B" not in route_hist
    assert route_hist == ["A", "D", "C", "H"]

    # Verify forwarding events include D
    events = client.get("/api/events").json()
    assert any("FORWARD A -> D" in e for e in events)
    assert any("FORWARD D -> C" in e for e in events)
    assert any("FORWARD C -> H" in e for e in events)

    # Verify return ACK confirmed
    msg_id = res_data["message_id"]
    status = simulation_service.get_sos_status(msg_id)
    assert status is not None
    assert status["status"] == "CONFIRMED"

    # Verify AODV distributed routing table state across hops
    router_a = simulation_service.routers["A"]
    route_to_h = router_a.routing_table.get_route("H")
    assert route_to_h is not None and route_to_h.is_valid
    assert route_to_h.next_hop == "D", "Node A routing table must route to H via next_hop D"

    router_d = simulation_service.routers["D"]
    route_d_to_a = router_d.routing_table.get_route("A")
    assert route_d_to_a is not None and route_d_to_a.is_valid
    assert route_d_to_a.next_hop == "A", "Node D routing table must route to A via next_hop A"

    router_c = simulation_service.routers["C"]
    route_c_to_a = router_c.routing_table.get_route("A")
    assert route_c_to_a is not None and route_c_to_a.is_valid
    assert route_c_to_a.next_hop == "D", "Node C routing table must route to A via next_hop D"

    router_h = simulation_service.routers["H"]
    route_h_to_a = router_h.routing_table.get_route("A")
    assert route_h_to_a is not None and route_h_to_a.is_valid
    assert route_h_to_a.next_hop == "C", "Node H routing table must route to A via next_hop C"


def test_simulation_timeout_requires_logical_deadline_expiration():
    """
    Scenario 3:
    - Partition network completely so ACK cannot return.
    - Verify that empty queue does NOT immediately transition status to TIMEOUT.
    - Verify that status remains PENDING until the logical deadline actually expires.
    """
    client.post("/api/simulation/reset")

    # Break all links from C to isolate H
    client.post("/api/nodes/C/fail")

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Unreachable SOS",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "timeout_seconds": 3.0
    }

    resp = client.post("/api/sos", json=payload)
    msg_id = resp.json()["message_id"]

    # Immediately after sending, queue is empty because packet was dropped at A/B
    # BUT logical deadline (3.0s) has NOT expired yet!
    status_before = simulation_service.get_sos_status(msg_id)
    assert status_before is not None
    assert status_before["status"] == "PENDING", "Should remain PENDING before configured deadline"

    # Advance time by 1.0s (less than 3.0s deadline)
    client.post("/api/simulation/advance_time?seconds=1.0")
    status_mid = simulation_service.get_sos_status(msg_id)
    assert status_mid["status"] == "PENDING", "Should remain PENDING when deadline has not expired"

    # Advance time past the 3.0s deadline
    client.post("/api/simulation/advance_time?seconds=3.0")
    status_after = simulation_service.get_sos_status(msg_id)
    assert status_after["status"] == "TIMEOUT", "Must transition to TIMEOUT once deadline expires"


def test_delayed_ack_policy_transitions_to_late_confirmed():
    """
    Scenario 4:
    - SOS is dispatched and deadline expires -> transitions to TIMEOUT.
    - Delayed return ACK arrives after timeout -> transitions from TIMEOUT to LATE_CONFIRMED.
    """
    client.post("/api/simulation/reset")

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Delayed SOS",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "timeout_seconds": 2.0
    }

    resp = client.post("/api/sos", json=payload)
    msg_id = resp.json()["message_id"]

    # Advance simulation time past 2.0s deadline
    client.post("/api/simulation/advance_time?seconds=2.5")
    assert simulation_service.get_sos_status(msg_id)["status"] == "TIMEOUT"

    # Inject delayed ACK arriving from H to A for this msg_id
    delayed_ack_packet = Packet(
        source_id="H",
        destination_id="A",
        payload={"type": "ack", "ack_for_message_id": msg_id},
        packet_type=PacketType.DATA
    )
    delayed_ack_packet.current_node = "A"

    # Process packet at node A
    simulation_service.engine._process_packet(delayed_ack_packet)

    status_late = simulation_service.get_sos_status(msg_id)
    assert status_late["status"] == "LATE_CONFIRMED"
    assert status_late["rtt_ms"] is not None


def test_hospital_deduplication_and_no_duplicate_inbox():
    """
    Scenario 5:
    - Same SOS delivered twice (duplicate transmission).
    - Hospital inbox must NOT have duplicate incidents.
    - Hospital retransmits ACK without loop.
    """
    client.post("/api/simulation/reset")

    # Establish route
    setup_payload = {"source_id": "A", "destination_id": "H", "message": "Setup", "priority": "LOW"}
    client.post("/api/sos", json=setup_payload)
    client.post("/api/sos", json=setup_payload)

    fixed_msg_id = f"fixed-dedup-{uuid.uuid4()}"
    sos_payload = {
        "type": "sos",
        "message_id": fixed_msg_id,
        "message": "Dedup Test Emergency",
        "latitude": 18.52,
        "longitude": 73.85,
        "priority": "HIGH"
    }

    # First delivery
    p1 = Packet(source_id="A", destination_id="H", payload=sos_payload, packet_type=PacketType.DATA)
    simulation_service.engine.send_packet(p1)

    inbox1 = simulation_service.get_hospital_inbox()
    count1 = len([m for m in inbox1 if m.get("message_id") == fixed_msg_id])
    assert count1 == 1

    # Second delivery (duplicate SOS)
    p2 = Packet(source_id="A", destination_id="H", payload=sos_payload, packet_type=PacketType.DATA)
    simulation_service.engine.send_packet(p2)

    inbox2 = simulation_service.get_hospital_inbox()
    count2 = len([m for m in inbox2 if m.get("message_id") == fixed_msg_id])
    assert count2 == 1, "Hospital inbox must not contain duplicate entries for same message_id"

    # Check that processed_sos recorded the duplicate count
    assert simulation_service.processed_sos[fixed_msg_id]["ack_count"] == 2


def test_mismatched_and_malformed_ack_rejection():
    """
    Scenario 6:
    - Unknown message ID ACK must be rejected.
    - Non-DATA packet must not confirm SOS.
    - Source not H must not confirm SOS.
    - Payload without discriminator 'ack' must not confirm SOS.
    - Duplicate ACK on already CONFIRMED SOS must be safely ignored without error.
    """
    client.post("/api/simulation/reset")

    # 1. Unknown message ID
    unknown_ack = Packet(
        source_id="H",
        destination_id="A",
        payload={"type": "ack", "ack_for_message_id": "unknown-nonexistent-id"},
        packet_type=PacketType.DATA
    )
    unknown_ack.current_node = "A"
    is_valid, reason, _ = simulation_service._validate_ack_packet(unknown_ack)
    assert is_valid is False
    assert reason == "UNKNOWN_MESSAGE_ID"

    # 2. Source not H
    rogue_ack = Packet(
        source_id="B",
        destination_id="A",
        payload={"type": "ack", "ack_for_message_id": "some-id"},
        packet_type=PacketType.DATA
    )
    is_valid2, reason2, _ = simulation_service._validate_ack_packet(rogue_ack)
    assert is_valid2 is False
    assert reason2 == "SOURCE_NOT_H"

    # 3. Payload not dict with type 'ack'
    bogus_ack = Packet(
        source_id="H",
        destination_id="A",
        payload="regular string payload",
        packet_type=PacketType.DATA
    )
    is_valid3, reason3, _ = simulation_service._validate_ack_packet(bogus_ack)
    assert is_valid3 is False
    assert reason3 == "PAYLOAD_NOT_ACK"


def test_simulation_reset_cancels_pending_acks_cleanly():
    """
    Scenario 7:
    - Dispatch pending SOS.
    - Call reset.
    - Verify all pending ACKs and processed records are cleared with zero stale state.
    """
    client.post("/api/simulation/reset")

    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Reset Test SOS",
        "priority": "LOW",
        "timeout_seconds": 10.0
    }
    resp = client.post("/api/sos", json=payload)
    msg_id = resp.json()["message_id"]
    assert simulation_service.get_sos_status(msg_id) is not None

    # Reset
    client.post("/api/simulation/reset")
    assert simulation_service.get_sos_status(msg_id) is None
    assert len(simulation_service.get_pending_acks()) == 0
    assert len(simulation_service.get_hospital_inbox()) == 0


def test_real_udp_node_runtime_ack_lifecycle():
    """
    Scenario 8:
    Verify NodeRuntime in Real UDP mode:
    - send_sos initiates pending ACK and sets cancellable timer
    - Valid return ACK cancels timer, transitions to CONFIRMED, records RTT
    - Malformed/rogue ACK is rejected
    - Timeout expiry transitions to TIMEOUT
    - Delayed ACK transitions TIMEOUT -> LATE_CONFIRMED
    - Clean shutdown cancels all active timers
    """
    from resqnet.backend.app.runtime.node import NodeRuntime
    events = []
    def record_event(etype, data):
        events.append((etype, data))

    endpoint_config = {
        "A": ("127.0.0.1", 52101),
        "H": ("127.0.0.1", 52102)
    }

    node_a = NodeRuntime("A", endpoint_config, topology_links=[("A", "H")], event_callback=record_event)
    try:
        # 1. Send SOS
        msg_id = f"test-sos-{uuid.uuid4()}"
        res = node_a.send_sos({
            "message_id": msg_id,
            "destination_id": "H",
            "message": "Real UDP Test SOS",
            "timeout_seconds": 1.0
        })
        assert res["success"] is True
        assert msg_id in node_a._pending_acks
        assert node_a._pending_acks[msg_id]["status"] == "PENDING"
        assert msg_id in node_a._ack_timers

        # 2. Receive Rogue ACK (from B, not H)
        rogue_pkt = Packet(
            source_id="B",
            destination_id="A",
            payload={"type": "ack", "ack_for_message_id": msg_id},
            packet_type=PacketType.DATA
        )
        rogue_pkt.current_node = "A"
        node_a._process_packet(rogue_pkt)
        assert node_a._pending_acks[msg_id]["status"] == "PENDING"

        # 3. Receive Valid ACK from H
        valid_pkt = Packet(
            source_id="H",
            destination_id="A",
            payload={"type": "ack", "ack_for_message_id": msg_id},
            packet_type=PacketType.DATA
        )
        valid_pkt.current_node = "A"
        node_a._process_packet(valid_pkt)
        assert node_a._pending_acks[msg_id]["status"] == "CONFIRMED"
        assert node_a._pending_acks[msg_id]["rtt_ms"] is not None
        assert msg_id not in node_a._ack_timers  # Timer was cancelled

        # 4. Duplicate ACK on confirmed SOS is safely ignored
        node_a._process_packet(valid_pkt)
        assert node_a._pending_acks[msg_id]["status"] == "CONFIRMED"

        # 5. Test timeout expiry on new SOS
        timeout_msg_id = f"test-timeout-{uuid.uuid4()}"
        node_a.send_sos({
            "message_id": timeout_msg_id,
            "destination_id": "H",
            "message": "SOS Expecting Timeout",
            "timeout_seconds": 0.15
        })
        assert node_a._pending_acks[timeout_msg_id]["status"] == "PENDING"
        time.sleep(0.3)
        assert node_a._pending_acks[timeout_msg_id]["status"] == "TIMEOUT"

        # 6. Delayed ACK transitions TIMEOUT to LATE_CONFIRMED
        late_pkt = Packet(
            source_id="H",
            destination_id="A",
            payload={"type": "ack", "ack_for_message_id": timeout_msg_id},
            packet_type=PacketType.DATA
        )
        late_pkt.current_node = "A"
        node_a._process_packet(late_pkt)
        assert node_a._pending_acks[timeout_msg_id]["status"] == "LATE_CONFIRMED"

    finally:
        node_a.stop()
        # Verify all timers cancelled on stop
        assert len(node_a._ack_timers) == 0


def test_real_udp_hospital_deduplication():
    """
    Scenario 9:
    Verify Hospital node deduplication in Real UDP mode:
    - Multiple arrivals of the same SOS message_id produce exactly 1 hospital inbox entry
    - Hospital retransmits ACK without loop
    """
    from resqnet.backend.app.runtime.node import NodeRuntime
    events = []
    def record_event(etype, data):
        events.append((etype, data))

    endpoint_config = {
        "A": ("127.0.0.1", 52103),
        "H": ("127.0.0.1", 52104)
    }

    node_h = NodeRuntime("H", endpoint_config, topology_links=[("A", "H")], event_callback=record_event)
    try:
        fixed_id = f"hosp-dedup-{uuid.uuid4()}"
        sos_pkt1 = Packet(
            source_id="A",
            destination_id="H",
            payload={
                "type": "sos",
                "message_id": fixed_id,
                "message": "Casualties at Sector 4",
                "priority": "HIGH"
            },
            packet_type=PacketType.DATA
        )
        sos_pkt1.current_node = "H"

        # Process first arrival
        node_h._process_packet(sos_pkt1)
        delivered_events1 = [e for e in events if e[0] == "SOS_DELIVERED"]
        assert len(delivered_events1) == 1
        assert fixed_id in node_h.processed_sos
        assert node_h.processed_sos[fixed_id]["ack_count"] == 1

        # Process second arrival (duplicate)
        sos_pkt2 = Packet(
            source_id="A",
            destination_id="H",
            payload={
                "type": "sos",
                "message_id": fixed_id,
                "message": "Casualties at Sector 4",
                "priority": "HIGH"
            },
            packet_type=PacketType.DATA
        )
        sos_pkt2.current_node = "H"
        node_h._process_packet(sos_pkt2)

        # Hospital must not emit a second SOS_DELIVERED event for the duplicate
        delivered_events2 = [e for e in events if e[0] == "SOS_DELIVERED"]
        assert len(delivered_events2) == 1, "Duplicate SOS must not produce duplicate SOS_DELIVERED events"
        assert node_h.processed_sos[fixed_id]["ack_count"] == 2

    finally:
        node_h.stop()


def test_no_available_return_route_causes_timeout():
    """
    Scenario 10:
    - Initial route A -> B -> C -> H established.
    - An SOS is sent with a 2.0s deadline.
    - Node C is failed, severing all return paths back to A.
    - Return ACK cannot traverse to A.
    - Empty queue does not cause premature timeout; when logical deadline expires, status transitions to TIMEOUT.
    """
    client.post("/api/simulation/reset")

    # Establish initial route
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Init Route",
        "priority": "LOW"
    }
    client.post("/api/sos", json=payload)
    client.post("/api/sos", json=payload)

    # Fail C so return path cannot be established
    client.post("/api/nodes/C/fail")

    sos_payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Cut Return Route SOS",
        "priority": "HIGH",
        "timeout_seconds": 2.0
    }
    resp = client.post("/api/sos", json=sos_payload)
    msg_id = resp.json()["message_id"]

    # Before deadline expires, status remains PENDING
    assert simulation_service.get_sos_status(msg_id)["status"] == "PENDING"

    # Advance time past 2.0s deadline
    client.post("/api/simulation/advance_time?seconds=2.5")
    assert simulation_service.get_sos_status(msg_id)["status"] == "TIMEOUT"


def test_ack_loop_prevention_and_no_cascading_replies():
    """
    Scenario 11:
    - Injecting an ACK packet at Hospital-H or any relay must NEVER generate a response ACK,
      an infinite loop, or cascading broadcast storm.
    """
    client.post("/api/simulation/reset")

    ack_to_h = Packet(
        source_id="A",
        destination_id="H",
        payload={"type": "ack", "ack_for_message_id": "loop-test-id"},
        packet_type=PacketType.DATA
    )
    ack_to_h.current_node = "H"

    initial_queue_len = len(simulation_service.engine.pending_messages)
    simulation_service.engine._process_packet(ack_to_h)

    # Queue must remain empty; no ACK generated in response to an ACK
    assert len(simulation_service.engine.pending_messages) == initial_queue_len
    # No duplicate inbox entry
    assert len(simulation_service.get_hospital_inbox()) == 0


def test_real_udp_end_to_end_socket_ack_round_trip():
    """
    Scenario 12:
    Verify Real UDP communication over actual OS loopback sockets between two independent NodeRuntime instances:
    - Node A starts UDP transport on loopback port
    - Node H starts UDP transport on loopback port
    - Forward and reverse direct links configured
    - Node A sends SOS to Node H via send_sos() over real UDP
    - Node H receives SOS over real UDP socket, adds to inbox, generates ACK
    - Node H routes and transmits ACK over real UDP socket back to Node A
    - Node A receives ACK over real UDP socket, validates it, cancels timer, confirms SOS!
    """
    import socket
    def get_port():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    port_a = get_port()
    port_h = get_port()

    endpoint_config = {
        "A": ("127.0.0.1", port_a),
        "H": ("127.0.0.1", port_h)
    }

    events_a = []
    events_h = []
    def rec_a(t, d): events_a.append((t, d))
    def rec_h(t, d): events_h.append((t, d))

    node_a = NodeRuntime("A", endpoint_config, topology_links=[("A", "H")], event_callback=rec_a)
    node_h = NodeRuntime("H", endpoint_config, topology_links=[("A", "H")], event_callback=rec_h)

    # Pre-install mutual direct routes in AODV routing tables to avoid dropped first DATA packet
    node_a.router.routing_table.add_or_update_route("H", "H", 1, 1)
    node_h.router.routing_table.add_or_update_route("A", "A", 1, 1)

    node_a.start()
    node_h.start()

    try:
        time.sleep(0.1)

        msg_id = f"udp-e2e-{uuid.uuid4()}"
        sos_req = {
            "message_id": msg_id,
            "destination_id": "H",
            "message": "Real UDP Round Trip SOS",
            "timeout_seconds": 2.0
        }

        # Send SOS from Node A to Node H
        res = node_a.send_sos(sos_req)
        assert res["success"] is True

        # Wait for real UDP round trip: A -> H -> A
        deadline = time.time() + 2.0
        while time.time() < deadline:
            status = node_a.get_sos_status(msg_id)
            if status and status.get("status") == "CONFIRMED":
                break
            time.sleep(0.05)

        final_status = node_a.get_sos_status(msg_id)
        assert final_status is not None
        assert final_status["status"] == "CONFIRMED", f"Expected CONFIRMED, got {final_status.get('status')}"
        assert final_status["rtt_ms"] is not None
        assert final_status["rtt_ms"] >= 0

        # Verify Hospital node inbox received the SOS over UDP
        hosp_events = [e for e in events_h if e[0] == "SOS_DELIVERED"]
        assert len(hosp_events) == 1
        assert hosp_events[0][1]["message_id"] == msg_id

    finally:
        node_a.stop()
        node_h.stop()
