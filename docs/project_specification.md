# ResQNet: Project Specification

## 1. Project Vision
ResQNet is an academic simulation of a disaster-resilient ad-hoc communication network. Its primary goal is to demonstrate how AODV (Ad hoc On-Demand Distance Vector) routing can dynamically discover routes, maintain communication, and recover from node or link failures during disaster scenarios (e.g., between rescue teams and critical infrastructure).

This project emphasizes **Computer Networks (CNT) fundamentals**. It is not merely a web application displaying a graph; the core is a technically defensible Python networking engine that accurately models IPs, nodes, links, topology, packet forwarding, routing tables, and the AODV routing protocol logic (RFC 3561).

## 2. Scope

### In Scope
- **Network Fundamentals**: Simulation of nodes, IP addressing, links, and topology.
- **Packet Lifecycle**: Creation, propagation, hop-by-hop forwarding, delivery, and loss.
- **Routing**: Routing tables, next-hop forwarding, static routing (as an initial baseline).
- **AODV Protocol**:
  - Route Requests (RREQ) and Route Replies (RREP).
  - Route Errors (RERR) and route invalidation.
  - Sequence numbers, broadcast IDs, forward and reverse routes.
  - Handling duplicate RREQs and route expirations.
- **Failure Simulation**: Node failures, link failures, and dynamic alternate route discovery.
- **Metrics Engine**: Packet Delivery Ratio (PDR), latency, throughput, hop count, route discovery/recovery times, and resilience tracking.
- **Demonstration Scenario**: A specific 5-node topology (Rescue-A, Relays B/C/D, Hospital H) demonstrating AODV's ability to reroute traffic when Relay-B fails.

### Eventual Scope (Later Phases)
- **Transport Layer**: UDP/TCP integration over standard Python sockets.
- **API Layer**: FastAPI backend exposing simulation state and controls.
- **Real-time Observability**: WebSockets streaming simulation events.
- **Frontend Visualization**: React-based UI to visually represent the network, packet movement, failures, and metrics.
- **Validation**: Wireshark capture of generated transport traffic.
- **Persistence**: Optional MySQL database for recording simulation runs and metrics (if justified).

## 3. Non-Goals (Out of Scope for Initial Engine)
- UI-first development (React must come last).
- Hard-coded routing shortcuts (e.g., using BFS, Dijkstra, NetworkX `shortest_path` and calling it AODV).
- Faked AODV control messages for visualization purposes.
- Kubernetes, Docker, microservices, cloud deployments, or enterprise-scale infrastructure.
- Authentication, authorization, or complex user management.
- Real physical MANET hardware deployments.

## 4. Technical Constraints & Architecture
- **Language**: Python (Core Engine).
- **Architecture Principle**: "Build the networking engine first. Build the UI last."
- **AODV Fidelity**: The routing engine must logically execute the AODV process—RREQ propagation, reverse route creation, RREP back-propagation, and data forwarding via routing tables.
- **Modularity**: Code must be separated cleanly into models (Node, Link, Packet), simulation (Topology, Engine), routing (Base, Static, AODV), and eventual API/UI layers.
- **Empirical Verification**: All behaviors must be proven through automated tests (e.g., `pytest`) and empirical command output, not just assumed correct.

## 5. Acceptance Criteria (Milestone 1 - Baseline Network)
- A network topology of 5 nodes is successfully instantiated:
  - Nodes: A (192.168.1.10), B (192.168.1.11), C (192.168.1.12), D (192.168.1.13), H (192.168.1.14)
  - Links: A↔B, A↔D, B↔C, D↔C, C↔H
- A packet is created at Node A destined for Node H with payload "HELP REQUIRED".
- Using a baseline routing mechanism (pre-AODV StaticRouter), the packet successfully traverses A → B → C → H and is delivered.
- If Node B is marked as failed, the packet is correctly dropped and cannot traverse B.
- Note: Automatic route recovery (A → D → C → H) is NOT expected in Milestone 1; it proves the baseline failure condition before AODV is introduced.
