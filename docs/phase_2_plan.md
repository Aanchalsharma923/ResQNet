# Phase 2: Genuine AODV Routing - Implementation Plan

## Overview
Phase 2 implements a genuine Ad hoc On-Demand Distance Vector (AODV) routing protocol on top of the Phase 1 network primitives. It explicitly avoids precomputed paths, centralized graph algorithms (like Dijkstra or BFS), and hard-coded routes. Instead, routes will organically emerge through the distributed propagation of Route Requests (RREQs) and Route Replies (RREPs).

## Architectural Decisions & Enhancements
1. **Separation of Routing Tables**: AODV requires dynamic state (sequence numbers, expiration). We will introduce a strict `RoutingTable` abstraction inside the `AODVRouter`, keeping it entirely separate from the baseline `StaticRouter`.
2. **Packet Architecture**: The Phase 1 `Packet` model will act as the generic carrier (similar to an IP frame). AODV-specific fields (like `broadcast_id`, `destination_sequence_number`) will be encapsulated in dedicated payload objects (`RREQPayload`, `RREPPayload`). This prevents polluting the generic packet with protocol-specific fields.
3. **Engine Message-Passing (Architectural Conflict Resolution)**: The Phase 1 `SimulationEngine` is currently a linear `while True` loop that tracks a single packet's hop-by-hop traversal. Because RREQs require **broadcasting** (one packet duplicating to multiple neighbors), the engine must be refactored into a queue-based message-passing loop. Routers will "process" an incoming packet and emit 0 or more outgoing packets back to the engine queue.

---

## Task Breakdown

### Task 1: AODV Routing Table
- **Objective**: Design the AODV routing table and entry abstraction.
- **Files Affected**: `resqnet/backend/app/routing/table.py`, `tests/test_routing_table.py`
- **Dependencies**: None
- **Implementation Details**:
  - `RouteEntry` class with fields: `destination_id`, `next_hop`, `hop_count`, `sequence_number`, `is_valid`.
  - `RoutingTable` class mapping destinations to `RouteEntry` objects, with methods to add, update (based on newer sequence numbers or better hop counts), and invalidate routes.
- **Acceptance Criteria**: Entries can be correctly added, updated according to AODV sequence number rules (higher seq num wins, or same seq num with lower hop count wins), and retrieved.
- **Verification Command**: `pytest tests/test_routing_table.py -v`
- **Git Commit Boundary**: Yes.

### Task 2: AODV Control Packet Payloads
- **Objective**: Define structured payloads for AODV control messages.
- **Files Affected**: `resqnet/backend/app/models/aodv_payloads.py`, `resqnet/backend/app/models/packet.py`, `tests/test_aodv_payloads.py`
- **Dependencies**: Task 1
- **Implementation Details**:
  - Extend `PacketType` to include `RREQ`, `RREP`, `RERR`.
  - Create `RREQPayload`: `source_id`, `destination_id`, `source_seq_num`, `dest_seq_num`, `broadcast_id`, `hop_count`.
  - Create `RREPPayload`: `source_id`, `destination_id`, `dest_seq_num`, `hop_count`.
- **Acceptance Criteria**: Payloads correctly initialize and can be embedded in the `Packet` payload field.
- **Verification Command**: `pytest tests/test_aodv_payloads.py -v`
- **Git Commit Boundary**: Yes.

### Task 3: SimulationEngine Event-Queue Refactoring
- **Objective**: Refactor the engine to support one-to-many packet generation (broadcasting) required by RREQs.
- **Files Affected**: `resqnet/backend/app/simulation/engine.py`, `resqnet/backend/app/routing/base.py`, `tests/test_engine.py`
- **Dependencies**: None (Refactoring)
- **Implementation Details**:
  - Introduce an internal `deque` of packets in `SimulationEngine`.
  - Add a `receive_packet(packet)` method to `BaseRouter` (default behavior: just forward or drop).
  - The engine loop pops a packet, moves it to the `current_node`, asks the local router to process it, and enqueues any resulting emitted packets (like broadcasts).
- **Acceptance Criteria**: Phase 1 integration tests (`A -> B -> C -> H` static routing) remain passing using the new queue-based engine.
- **Verification Command**: `pytest tests/test_engine.py -v`
- **Git Commit Boundary**: Yes.

### Task 4: AODV Router Base & Duplicate RREQ Detection
- **Objective**: Implement the `AODVRouter` skeleton, sequence numbers, and duplicate detection.
- **Files Affected**: `resqnet/backend/app/routing/aodv_router.py`, `tests/test_aodv_router.py`
- **Dependencies**: Task 1, 2, 3
- **Implementation Details**:
  - `AODVRouter` extends `BaseRouter`.
  - State variables: `node_sequence_number`, `broadcast_id_counter`, `seen_rreqs` (set of `(source_id, broadcast_id)`).
  - `process_rreq()` skeleton: If duplicate, drop. If new, record in `seen_rreqs`.
- **Acceptance Criteria**: Router successfully identifies and drops duplicate RREQs.
- **Verification Command**: `pytest tests/test_aodv_router.py -v`
- **Git Commit Boundary**: Yes.

### Task 5: Reverse Route Establishment & RREQ Propagation
- **Objective**: Implement RREQ processing and reverse route creation.
- **Files Affected**: `resqnet/backend/app/routing/aodv_router.py`, `tests/test_aodv_router_rreq.py`
- **Dependencies**: Task 4
- **Implementation Details**:
  - When an RREQ is accepted as new, extract the previous hop (sender).
  - Create/update a routing table entry for the RREQ's `source_id` (the reverse route) pointing to the sender.
  - Increment the RREQ `hop_count`.
  - If the node is NOT the destination, emit cloned RREQ packets to all active neighbors via the engine.
- **Acceptance Criteria**: RREQs successfully flood the network without infinite loops (due to duplicate detection), and intermediate nodes successfully build reverse routes back to the source.
- **Verification Command**: `pytest tests/test_aodv_router_rreq.py -v`
- **Git Commit Boundary**: Yes.

### Task 6: RREP Generation & Forward Route Installation
- **Objective**: Generate RREPs at the destination and install forward routes.
- **Files Affected**: `resqnet/backend/app/routing/aodv_router.py`, `tests/test_aodv_router_rrep.py`
- **Dependencies**: Task 5
- **Implementation Details**:
  - If RREQ reaches the destination, the destination generates an RREP.
  - The RREP is unicast back to the RREQ source using the established reverse route.
  - As intermediate nodes receive the RREP, they install/update a forward route to the destination pointing to the node that sent the RREP.
  - They then forward the RREP to the next hop on the reverse route.
- **Acceptance Criteria**: RREP successfully traverses the reverse route, establishing valid forward routes at all intermediate nodes back to the source.
- **Verification Command**: `pytest tests/test_aodv_router_rrep.py -v`
- **Git Commit Boundary**: Yes.

### Task 7: On-Demand Route Discovery & DATA Forwarding
- **Objective**: Trigger route discovery automatically for DATA packets without routes, and forward them when routes are established.
- **Files Affected**: `resqnet/backend/app/routing/aodv_router.py`, `tests/test_aodv_data.py`
- **Dependencies**: Task 6
- **Implementation Details**:
  - If `AODVRouter` receives a DATA packet originating locally, and no route exists, queue the DATA packet and initiate an RREQ broadcast.
  - When the RREP arrives at the source, dequeue the DATA packet and forward it using the newly established forward route.
  - Intermediate nodes seamlessly forward the DATA packet using their routing tables.
- **Acceptance Criteria**: A locally generated DATA packet triggers the full RREQ -> RREP cycle, and is subsequently successfully delivered.
- **Verification Command**: `pytest tests/test_aodv_data.py -v`
- **Git Commit Boundary**: Yes.

### Task 8: End-to-End AODV Integration & Multiple Route Validation
- **Objective**: Prove AODV operates correctly over the full ResQNet Phase 1 topology.
- **Files Affected**: `tests/test_aodv_integration.py`
- **Dependencies**: Task 7
- **Implementation Details**:
  - Integration test over the `A-B-C-H` and `A-D-C-H` redundant topology.
  - Prove that `A -> H` communication succeeds via dynamically discovered routes.
  - Prove that the discovered route emerges purely from protocol propagation, not hard-coded lists.
- **Acceptance Criteria**: The integration test passes, proving dynamic route discovery. Full regression suite passes.
- **Verification Command**: `pytest -v`
- **Git Commit Boundary**: Yes.

### Task 9: Phase 2 Documentation and Review (Completed)
- **Objective**: Update all documentation reflecting the new AODV capability.
- **Files Affected**: `README.md`, `docs/roadmap.md`, `docs/phase_2_plan.md`, `.project_state.md`
- **Implementation Details**: Document how the AODV implementation works, how to test it, and how it differentiates from the StaticRouter. Ensure Phase 2 boundary definitions are respected.

### Task 10: Disaster Resilience & RERR (Completed)
- **Objective**: Implement disaster resilience via route invalidation, RERR generation/propagation, and organic route rediscovery.
- **Implementation Details**: Handle node and link failures gracefully by invalidating broken routes and triggering a new sequence of AODV discovery using the correct sequence numbers.

### Task 11: Architectural Hardening & Final Audit (Completed)
- **Objective**: Freeze the networking core by ensuring no reliance on explicit route history, passing all disaster recovery test suites, and confirming strict adherence to no-cheating protocol constraints.
- **Implementation Details**: `sender_id` semantics replaced `route_history` for routing logic. Validated isolation of node failures and link failures. Audit confirmed ZERO usage of shortest-path algorithms.

---

## Architectural Guardrails
- **No Pathfinding Algorithms**: Absolutely zero usage of Dijkstra, BFS, DFS, A*, or NetworkX. Routes emerge exclusively from RREQ/RREP packet processing.
- **No Hard-coding**: `["A", "B", "C", "H"]` will never exist in the AODVRouter.
- **Disaster Resilience**: Fully integrated RERR payload and node/link failure rediscovery mechanisms to ensure genuine AODV healing capabilities without centralized graph evaluation.

