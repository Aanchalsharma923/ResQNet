# ResQNet — Phase 2: Genuine Network-Level Hospital ACK Specification

## 1. Overview & Objectives

In ResQNet, emergency distress signaling must not rely on optimistic unidirectional delivery or simulated UI callbacks. Phase 2 introduces genuine, bidirectional, network-level acknowledgment (ACK) for high-priority SOS distress messages across both **Simulation Mode** and **Real UDP Mode**.

### Complete End-to-End Lifecycle:
1. **SOS Dispatch (Rescue-A)**: Rescue-A transmits a high-priority `DATA` packet containing an SOS payload with a unique `message_id`. Rescue-A registers the pending SOS with a configured logical/physical deadline and enters `PENDING` status.
2. **Forward AODV Traversal**: The SOS packet traverses the mesh using standard AODV on-demand routing (e.g. `A → B → C → H`, or alternate `A → D → C → H`).
3. **Hospital Delivery & Deduplication (Hospital-H)**: Hospital-H receives the SOS packet, verifies it, and delivers it to the hospital application inbox. Duplicate transmissions of the same `message_id` are identified and deduplicated so that no duplicate incidents are created in the inbox.
4. **Return ACK Generation (Hospital-H)**: Hospital-H generates an authentic `DATA` packet addressed to Rescue-A (`source_id='H'`, `destination_id='A'`, `packet_type=DATA`, `payload={'type': 'ack', 'ack_for_message_id': message_id}`).
5. **Reverse AODV Traversal**: The ACK packet traverses the existing routing and transport layer (e.g. `H → C → B → A` or `H → C → D → A`). No shortcuts or direct callbacks are used.
6. **Rescue-A Validation & Confirmation**: Rescue-A validates the incoming ACK against strict protocol criteria:
   - Packet type must be `DATA`.
   - Source node must be `H`.
   - Destination node must be `A`.
   - Payload must be a dictionary with discriminator `type == 'ack'`.
   - `ack_for_message_id` must match an active pending SOS.
7. **Terminal State & Timing Policy**:
   - On valid matching ACK before deadline: transitions `PENDING → CONFIRMED` and calculates round-trip time (RTT).
   - If deadline expires before ACK: transitions `PENDING → TIMEOUT`.
   - If delayed ACK arrives after timeout: transitions `TIMEOUT → LATE_CONFIRMED` and records late RTT.
   - Duplicate ACKs on already-confirmed records: safely ignored without error or loops.

---

## 2. Refined Architectural Constraints

### 1. Simulation Timeout Semantics
- **Rule**: Do NOT transition to `TIMEOUT` merely because the simulation packet queue is empty.
- **Implementation**: The simulation engine maintains a logical simulation clock (`sim_time`). Each successful hop traversal advances time by `hop_delay` (50ms). Deadlines are evaluated strictly by logical timestamp comparison (`sim_time >= deadline`). The backend exposes `advance_sim_time(seconds)` and `/api/simulation/advance_time` for deterministic testing.

### 2. ACK Validation at Rescue-A
- **Rule**: Unknown, rogue, or malformed packets must never confirm an SOS.
- **Validation Matrix**:
  - `packet.packet_type == PacketType.DATA`: Enforces transport and routing integrity.
  - `packet.destination_id == 'A'`: Must be addressed to the originating node.
  - `packet.source_id == 'H'`: Must originate strictly from Hospital-H.
  - `packet.payload.get('type') == 'ack'`: Explicit discriminator prevents conflating standard DATA with ACKs.
  - `packet.payload.get('ack_for_message_id') in pending_acks`: Must match an active SOS record.
  - Rejection emits structured telemetry (`ACK_INVALID`) with explicit rejection reason (`UNKNOWN_MESSAGE_ID`, `SOURCE_NOT_H`, `PAYLOAD_NOT_ACK`, etc.).

### 3. AODV Route Verification on Alternate Path
- **Rule**: When Relay-B fails, the return path through D must be verified through actual AODV discovery and hop forwarding events (`FORWARD A -> D`, `FORWARD D -> C`, `FORWARD C -> H`), not hardcoded or inferred solely from ACK arrival.
- **Implementation**: Tested in `tests/test_hospital_ack.py::test_hospital_ack_alternate_path_after_relay_failure`.

### 4. Hospital Deduplication & Loop Prevention
- **Rule**: Duplicate SOS packets must not create duplicate inbox incidents, and ACK retransmission must not trigger an ACK loop.
- **Implementation**:
  - Hospital tracks `processed_sos[message_id]`.
  - First delivery: appends to `hospital_inbox`, broadcasts `SOS_DELIVERED`, and sends ACK.
  - Subsequent deliveries: increments `ack_count`, retransmits return ACK, and does NOT append duplicate inbox entries.
  - Return ACKs have `payload['type'] == 'ack'`. Nodes never generate a response to an ACK packet, guaranteeing no ACK loops.

### 5. Mode Consistency without Forcing Shared Abstractions
- **Simulation Mode**: Uses deterministic discrete-event logical clock (`sim_time`), queue processing, and direct dictionary tracking.
- **Real UDP Mode**: Uses independent `NodeRuntime` processes over loopback UDP sockets, thread-safe `_ack_lock`, cancellable `threading.Timer` objects, and socket teardown on `stop()`.

---

## 3. Telemetry & Standardized Events

| Event Name | Source | Key Payload Fields | Description |
|---|---|---|---|
| `SOS_SENT` | Node A | `message_id`, `source_id`, `destination_id`, `priority` | SOS distress message injected into mesh. |
| `SOS_DELIVERED` | Node H | `message_id`, `source_id`, `hospital_id`, `hop_count` | SOS verified and appended to hospital inbox. |
| `ACK_SENT` | Node H | `message_id`, `source_id`, `destination_id`, `packet_id` | Hospital generated and queued return ACK. |
| `ACK_RECEIVED` | Node A | `message_id`, `source_id`, `hospital_id`, `rtt_ms`, `status` | Authentic return ACK confirmed within deadline. |
| `ACK_TIMEOUT` | Node A | `message_id`, `source_id`, `hospital_id`, `timeout_sec`, `status` | Configured deadline expired without valid ACK. |
| `ACK_RECEIVED_LATE` | Node A | `message_id`, `source_id`, `hospital_id`, `rtt_ms`, `status` | Delayed return ACK arrived after timeout. |
| `ACK_DUPLICATE_IGNORED` | Node A | `message_id`, `status` | Duplicate return ACK safely discarded. |
| `ACK_INVALID` | Node A | `reason`, `source_id`, `packet_id` | Rogue or malformed ACK rejected. |

---

## 4. Test Verification Suite

All 12 dedicated test scenarios in `tests/test_hospital_ack.py` pass:
1. `test_hospital_ack_normal_path_and_validation`: Verifies `A → B → C → H` SOS delivery, hospital inbox entry, `H → C → B → A` ACK return, confirmation, and RTT calculation.
2. `test_hospital_ack_alternate_path_after_relay_failure`: Fails Relay-B, triggers AODV alternate path discovery via D, verifies distributed AODV routing table entries across hops (`A`, `D`, `C`, `H`), forwarding events through D (`A → D → C → H`), and return ACK via D.
3. `test_simulation_timeout_requires_logical_deadline_expiration`: Verifies that an empty simulation queue does NOT cause premature timeout until logical simulation deadline expires.
4. `test_delayed_ack_policy_transitions_to_late_confirmed`: Verifies state progression `PENDING → TIMEOUT → LATE_CONFIRMED`.
5. `test_hospital_deduplication_and_no_duplicate_inbox`: Delivers multiple identical SOS packets; asserts exactly 1 hospital inbox entry and ACK retransmission.
6. `test_mismatched_and_malformed_ack_rejection`: Rejects unknown message IDs, non-DATA packets, source not H, and malformed payload discriminators.
7. `test_simulation_reset_cancels_pending_acks_cleanly`: Confirms all pending ACKs and processed records are cleared on reset.
8. `test_real_udp_node_runtime_ack_lifecycle`: Verifies Real UDP `NodeRuntime` thread-safe pending ACKs, cancellable timers, valid ACK confirmation, timeout expiry, and clean shutdown.
9. `test_real_udp_hospital_deduplication`: Verifies `NodeRuntime` deduplication on duplicate SOS arrivals.
10. `test_no_available_return_route_causes_timeout`: Verifies that when return routes are severed, empty queue does not trigger immediate timeout, and status transitions cleanly to TIMEOUT when the deadline expires.
11. `test_ack_loop_prevention_and_no_cascading_replies`: Injects an ACK packet at Hospital-H; verifies zero responding ACKs, zero RREQ storms, and zero queue proliferation.
12. `test_real_udp_end_to_end_socket_ack_round_trip`: Verifies end-to-end communication over actual operating system UDP sockets between independent `NodeRuntime` instances (`node_a` and `node_h`), with SOS transmission, inbox delivery, return ACK routing, and confirmation over loopback sockets.

---

## 5. Deployment & Physical LAN Status

- Localhost Simulation Mode: Fully verified (automated tests passing).
- Localhost Multi-Process Real UDP Mode: Fully verified (automated tests passing).
- **Two-Laptop / Multi-Laptop Physical LAN Testing**: Configured and documented in `docs/lan_deployment.md` and `docs/final_demo_runbook.md`; **physical execution pending on hardware**.
