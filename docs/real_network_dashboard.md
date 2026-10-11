# ResQNet Phase 4.8: Real-Network Dashboard Integration

This document describes the complete architecture, data flow, and operation of the ResQNet React + FastAPI dashboard integrated with the real UDP/IP runtime.

---

## 1. Architectural Overview

ResQNet provides a unified control and observation interface for both deterministic simulation mode and real multi-process / multi-laptop UDP network mode.

```
                ┌───────────────────────────┐
                │      React Dashboard      │
                │  (Topology, SOS, Metrics) │
                └─────────────┬─────────────┘
                              │
                       REST / WebSocket
                              │
                ┌─────────────▼─────────────┐
                │       FastAPI API         │
                │ (/api/network, /api/ws)   │
                └─────────────┬─────────────┘
                              │
                ┌─────────────▼─────────────┐
                │      Runtime Manager      │
                │ (Mode Switch, Lifecycle)  │
                └─────────────┬─────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
┌─────────▼───────────────┐             ┌─────────▼───────────────┐
│   Simulation Runtime    │             │   Real Network Runtime  │
│   (SimulationEngine)    │             │    (Node Process IPC)   │
└─────────┬───────────────┘             └─────────┬───────────────┘
          │                                       │
┌─────────▼───────────────┐             ┌─────────▼───────────────┐
│   SimulationTransport   │             │     Node Processes      │
│  (In-memory packet bus) │             │ (A, B, C, D, H runtimes)│
└─────────────────────────┘             └─────────┬───────────────┘
                                                  │
                                        ┌─────────▼───────────────┐
                                        │       AODVRouter        │
                                        │  (Routing Intelligence) │
                                        └─────────┬───────────────┘
                                                  │
                                        ┌─────────▼───────────────┐
                                        │      UDPTransport       │
                                        │ (IPv4 UDP Sockets / LAN)│
                                        └─────────────────────────┘
```

---

## 2. Real Runtime Event & Command Bridge

The dashboard and real node processes communicate strictly through structured IPC channels without violating layer boundaries:

```
[Control Path]
React Dashboard ──(HTTP POST /api/sos)──> FastAPI ──> RuntimeManager ──> RealNetworkRuntime
                                                                               │
                                                                   (Local UDP Command)
                                                                               ▼
                                                                     Node A (Port 51010)
                                                                               │
                                                                      (AODV DATA / UDP)
                                                                               ▼
                                                                        LAN UDP Mesh
                                                                               │
                                                                               ▼
[Event Path]                                                         Node H (Delivery)
React Dashboard <──(WebSocket)── EventBroadcaster <── RealNetworkRuntime <──(Event UDP: 50099)
```

1. **Local Command Channel**: Each node process runs a loopback command listener (e.g., Node A on port 51010). When an operator triggers an SOS or message from the dashboard, FastAPI requests the local node process to generate and dispatch the packet.
2. **Local Event Bridge**: When routing events occur (`RREQ_GENERATED`, `RREP_FORWARDED`, `FORWARD_ROUTE_INSTALLED`, `DATA_DELIVERED`, `NEIGHBOR_DOWN`), the node process serializes a standardized JSON event and dispatches it over loopback UDP to `127.0.0.1:50099`.
3. **Broadcaster Integration**: `RealNetworkRuntime` receives these datagrams, extracts the payload, updates internal metrics, and broadcasts the event to all active WebSocket clients.

---

## 3. Strict Architectural Guarantees

- **React does NOT calculate routes**: React does not run Dijkstra, BFS, DFS, or A*. Link highlighting and packet animations are driven purely by backend state and event metadata.
- **React opens ZERO UDP sockets**: The browser interacts exclusively through standard HTTP REST and WebSocket connections to FastAPI.
- **FastAPI is NOT the routing brain**: FastAPI does not select next hops or manage routing tables. Routing decisions are made autonomously by `AODVRouter` instances inside individual node processes.
- **No hard-coded alternate routes**: Alternate routes (e.g. `A → D → C → H`) emerge naturally from AODV RREQ flood and sequence number evaluation following link/neighbor timeout.

---

## 4. Topology vs. Active Route Visualization

- **Logical Topology**: Represents configured physical neighborhood links (e.g. `A-B`, `A-D`, `B-C`, `D-C`, `C-H`).
- **Active Route**: Highlights only the links currently chosen by AODV for active forward communication (e.g. `A → B → C → H` displayed in glowing green).
- **Node Down State**: When a node process is stopped (e.g. Node B), its circle is marked red with a bold `DOWN` label. Inactive links remain visible as dashed red lines to convey network damage during disaster scenarios.

---

## 5. End-to-End Disaster Demonstration Flow

1. **Start System**:
   - Launch FastAPI (`uvicorn resqnet.backend.app.main:app --port 8000`).
   - Launch Frontend (`npm run dev`).
   - Switch mode in the Controls panel to **Real UDP / LAN Mode**.
   - Click **Start All Nodes** to launch processes A, B, C, D, H.
2. **Observe Steady-State**:
   - All 5 nodes report `UP (Running)`.
   - HELLO packets maintain healthy neighbor links.
3. **Issue Primary Distress Message**:
   - Select Node A in the SOS panel, enter `HELP REQUIRED`, click **Send SOS Distress**.
   - AODV discovers route `A → B → C → H`.
   - DATA packet travels across real UDP datagrams.
   - Hospital H delivers the packet; `HospitalPanel` displays the distress record.
   - The active route `A → B → C → H` is highlighted on the SVG topology.
4. **Simulate Real Relay Failure**:
   - In the Controls panel under Node Processes, click **Stop Process** on Node B.
   - Node B's process is terminated (`SIGTERM`).
   - HELLO packets from B cease.
   - Neighbor health monitors on A and C detect missed heartbeats after 3 seconds.
   - `NEIGHBOR_DOWN: B` and `ROUTE_INVALIDATED` events fire.
   - The dashboard updates Node B to `DOWN`, and clears the primary active route.
5. **Demonstrate Dynamic Route Recovery**:
   - Send another SOS distress from Node A.
   - Node A initiates AODV RREQ broadcast. Because link to B is down, RREQ propagates exclusively via `D`.
   - Node D forwards to C; Node C forwards to Hospital H.
   - Hospital H generates RREP; returns via C and D to A.
   - Node A installs alternate route `A → D → C → H`.
   - DATA packet delivers successfully to Hospital H.
   - The dashboard updates the active route to `A → D → C → H`.
6. **Demonstrate Node Recovery**:
   - Click **Start Process** on Node B.
   - Process restarts; UDP socket binds; HELLO exchanges resume.
   - Neighbors detect `NEIGHBOR_RECOVERED: B`. Node B transitions back to `UP`.

---

## 6. Viva & Technical Questions

**Q: Does React implement AODV?**
> **No.** React is purely a presentation layer. It listens for WebSocket events and renders SVG elements based on state sent by FastAPI.

**Q: Who chooses the next hop?**
> **AODVRouter.** Each node runs an independent routing table maintaining destination sequence numbers, hop counts, and next-hop pointers according to RFC 3561 principles.

**Q: What does UDPTransport do?**
> It translates logical next-hop node IDs into physical IP:Port socket destinations, serializing packets into binary JSON datagrams.

**Q: How does the dashboard know what happened?**
> Real node processes emit structured JSON events to an internal loopback UDP event socket (`127.0.0.1:50099`). `RealNetworkRuntime` receives these events and immediately broadcasts them through `EventBroadcaster` to the WebSocket client.

**Q: How is failure detected?**
> Application-level HELLO messages sent periodically over real UDP. If a neighbor fails to send a HELLO within `neighbor_timeout` (default 3.0s), the node marks the neighbor as `DOWN` and invalidates any routes passing through it.

**Q: Is this a custom wireless radio mesh?**
> **No.** It is an academic/software implementation demonstrating AODV routing and disaster recovery over commodity IP networks (Wi-Fi or Ethernet LAN) using standard UDP sockets.

---

## 7. Limitations & Operational Scope

1. **Common Network Requirement**: Multi-laptop deployment requires all participating laptops to share a common IPv4 subnet without AP client isolation.
2. **Firewall Access**: Inbound UDP on configured ports (e.g. 50010–50014) must be permitted by host firewalls.
3. **Application-Level Routing**: Logical topology is enforced at the software layer, rather than by hardware-level RF propagation limits.
