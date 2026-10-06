# ResQNet: Roadmap

This roadmap follows an incremental, engine-first methodology. Each phase represents a deployable and verifiable milestone.

## Phase 1: Core Network Engine (Current)
*Goal: Establish the basic primitives of a simulated network without dynamic routing.*
- **Tasks**:
  - Implement `Node` and IP address assignment.
  - Implement `Link` and connectivity state.
  - Implement `Topology` manager.
  - Implement `Packet` structure.
  - Implement basic hop-by-hop forwarding mechanism.
  - Implement a `StaticRouter` (temporary, for baseline validation).
  - Implement basic node/link failure validation (packet drop).
- **Verification**: 
  - `pytest` suite for models.
  - CLI script proving a packet can travel `A → B → C → H` and fails when `B` is down.

## Phase 2: AODV Route Discovery
*Goal: Implement RFC 3561 compliant AODV route discovery logic.*
- **Tasks**:
  - Implement `RoutingTable` and entries.
  - Implement `AODVRouter` extending base router.
  - Implement `RREQ` message generation, propagation, and duplicate detection.
  - Implement reverse route establishment.
  - Implement `RREP` message generation and back-propagation.
  - Implement forward route establishment and sequence numbers.
- **Verification**:
  - `A` has no initial route to `H`.
  - `A` initiates `RREQ` → `H` replies with `RREP` → `A` forwards `DATA` via discovered route.

## Phase 3: Failure & Route Recovery
*Goal: Make the network disaster-resilient.*
- **Tasks**:
  - Implement Node/Link failure detection during forwarding.
  - Implement `RERR` generation and route invalidation.
  - Trigger local repair or source route rediscovery.
  - Successfully establish alternate routes.
- **Verification**:
  - Hero Scenario: `A → B → C → H` is active. `B` fails. `AODV` detects failure, triggers RREQ, discovers `A → D → C → H`, and restores communication.

## Phase 4: Metrics & Observability
*Goal: Quantify network performance and resilience.*
- **Tasks**:
  - Implement metrics collection for PDR (Packet Delivery Ratio), packet loss, and hop count.
  - Measure latency and throughput.
  - Measure route discovery and recovery times.
  - Implement structured event logging.

## Phase 5: Transport Layer Integration
*Goal: Bridge simulation with actual OS-level networking.*
- **Tasks**:
  - Integrate actual Python UDP/TCP sockets.
  - Separate simulated routing decisions from physical transport payload delivery.
- **Verification**:
  - Wireshark captures showing actual packets matching the simulation's intent.

## Phase 6: FastAPI & WebSocket Backend
*Goal: Expose the engine via standard web protocols.*
- **Tasks**:
  - Create REST endpoints for topology management, simulation control, and metrics.
  - Create WebSocket endpoints to stream live events (RREQ, failures, packet movement).

## Phase 7: React Frontend Visualization
*Goal: Visually demonstrate the network.*
- **Tasks**:
  - Build React dashboard consuming FastAPI and WebSockets.
  - Visualize topology, nodes, links, and real-time packet flow.
  - Visualize metrics and failure/recovery scenarios.

## Phase 8: Optional Persistence
*Goal: Record simulation history.*
- **Tasks**:
  - Evaluate need for MySQL.
  - If justified, implement ORM models and save simulation runs, metrics, and events.
