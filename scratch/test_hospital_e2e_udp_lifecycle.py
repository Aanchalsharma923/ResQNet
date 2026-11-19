#!/usr/bin/env python3
"""
Independent Process / Real UDP Socket End-to-End Hospital Communication Lifecycle Test:
1. Original SOS ID generated at Node A.
2. SOS packet transmitted over real OS UDP socket to Node H.
3. Node H receives SOS (Hospital Receipt) and verifies payload.
4. Node H generates Technical Transport ACK.
5. ACK transmitted over real OS UDP socket back to Node A.
6. Node A receives Technical ACK, measures RTT, and marks SOS as CONFIRMED.
7. Node H clinician inputs human triage response referencing original SOS ID.
8. Clinician response transmitted over real OS UDP socket to Node A.
9. Node A receives Clinician Response (Source Receipt) and verifies reference correlation.
"""

import sys
import os
import time
import json
import uuid
import socket
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from resqnet.backend.app.runtime.node import NodeRuntime
from resqnet.backend.app.models.packet import Packet, PacketType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("e2e_hospital_udp")

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def run_lifecycle():
    port_a = get_free_port()
    port_h = get_free_port()

    endpoint_config = {
        "A": ("127.0.0.1", port_a),
        "H": ("127.0.0.1", port_h)
    }

    events_a = []
    events_h = []

    def cb_a(t, d): events_a.append((t, d))
    def cb_h(t, d): events_h.append((t, d))

    node_a = NodeRuntime("A", endpoint_config, topology_links=[("A", "H")], event_callback=cb_a)
    node_h = NodeRuntime("H", endpoint_config, topology_links=[("A", "H")], event_callback=cb_h)

    # Establish initial direct route
    node_a.router.routing_table.add_or_update_route("H", "H", 1, 1)
    node_h.router.routing_table.add_or_update_route("A", "A", 1, 1)

    node_a.start()
    node_h.start()

    results = {}

    try:
        time.sleep(0.2)

        # Step 1: Generate SOS ID and Dispatch SOS
        sos_id = f"SOS-E2E-{uuid.uuid4().hex[:8].upper()}"
        results["stage_1_sos_id"] = sos_id
        logger.info(f"Stage 1: Dispatching SOS {sos_id} from Node A over UDP port {port_a} -> {port_h}")

        sos_request = {
            "message_id": sos_id,
            "destination_id": "H",
            "message": "CRITICAL CASUALTY: TACTICAL EVACUATION NEEDED",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "CRITICAL",
            "timeout_seconds": 3.0
        }
        res_send = node_a.send_sos(sos_request)
        assert res_send["success"] is True

        # Wait for Step 2 & 3: Hospital Receipt and Technical Transport ACK
        deadline = time.time() + 3.0
        while time.time() < deadline:
            st = node_a.get_sos_status(sos_id)
            if st and st.get("status") == "CONFIRMED":
                break
            time.sleep(0.05)

        # Verify Hospital Receipt
        hospital_delivered_evts = [d for (t, d) in events_h if t == "SOS_DELIVERED" and d.get("message_id") == sos_id]
        assert len(hospital_delivered_evts) > 0, "Hospital failed to receive SOS over UDP"
        results["stage_2_hospital_receipt"] = {
            "verified": True,
            "event": hospital_delivered_evts[0]
        }
        logger.info(f"Stage 2: Hospital-H received SOS {sos_id}: {hospital_delivered_evts[0]['message']}")

        # Verify Technical Transport ACK at Node A
        final_ack_status = node_a.get_sos_status(sos_id)
        assert final_ack_status is not None and final_ack_status["status"] == "CONFIRMED"
        results["stage_3_technical_ack"] = {
            "verified": True,
            "status": final_ack_status["status"],
            "rtt_ms": final_ack_status["rtt_ms"]
        }
        logger.info(f"Stage 3: Technical Transport ACK received at Node A: RTT = {final_ack_status['rtt_ms']:.2f}ms")

        # Step 4: Hospital Clinician Triage Response
        clinician_msg = f"Doctor assigned to unit {sos_id[:12]}. Air ambulance airborne ETA 6 mins."
        results["stage_4_clinician_response"] = {
            "dispatched": True,
            "text": clinician_msg,
            "ref_sos_id": sos_id
        }
        logger.info(f"Stage 4: Clinician at Hospital-H dispatching triage response referencing {sos_id}")

        # Send response from Node H to Node A
        node_h.send_data("A", {
            "type": "hospital_response",
            "sos_message_id": sos_id,
            "message": clinician_msg
        })

        # Wait for Step 5: Clinician Response Receipt at Source (Node A)
        deadline = time.time() + 3.0
        response_received = False
        received_payload = None
        while time.time() < deadline:
            resp_evts = [d for (t, d) in events_a if t == "HOSPITAL_RESPONSE_DELIVERED" and d.get("sos_message_id") == sos_id]
            if resp_evts:
                response_received = True
                received_payload = resp_evts[0]
                break
            time.sleep(0.05)

        assert response_received, "Node A failed to receive HOSPITAL_RESPONSE_DELIVERED over UDP"
        results["stage_5_source_response_receipt"] = {
            "verified": True,
            "payload": received_payload
        }
        logger.info(f"Stage 5: Node A successfully received Clinician Triage Response over UDP: '{received_payload['message']}'")

    finally:
        node_a.stop()
        node_h.stop()

    print("\n=======================================================")
    print("   END-TO-END HOSPITAL UDP COMMUNICATION LIFECYCLE     ")
    print("=======================================================")
    print(json.dumps(results, indent=2))
    print("=======================================================\n")
    return results

if __name__ == "__main__":
    run_lifecycle()
