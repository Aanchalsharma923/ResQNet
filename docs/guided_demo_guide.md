# ResQNet Phase 3: Guided Live Disaster Demonstration Guide

## Overview

The ResQNet Guided Disaster Demonstration provides an interactive, repeatable, viva-ready presentation workflow designed for professors, examiners, and project evaluators. It systematically proves how an ad-hoc, multi-hop mesh network running the **Ad-hoc On-Demand Distance Vector (AODV)** routing protocol automatically adapts to node failures and maintains life-critical communication without central infrastructure.

---

## 1. How to Launch Backend and Frontend

### Prerequisites
- Python 3.10+ (with project dependencies installed: `fastapi`, `uvicorn`, `websockets`, `pydantic`, `pytest`)
- Node.js 18+ & npm
- Two PowerShell terminals in the repository root (e.g. `path/to/ResQNet`)

### Terminal 1 — Start FastAPI Backend
```powershell
python -m uvicorn resqnet.backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- WebSocket Stream: `ws://127.0.0.1:8000/api/ws/simulation` (alias: `ws://127.0.0.1:8000/ws`)

### Terminal 2 — Start React Frontend
```powershell
cd frontend
npm run dev
```
- Dashboard URL: `http://localhost:5173`

*(Optional CLI Mode)*
If presenting strictly via terminal without the web browser:
```powershell
python scripts/run_demo.py
```

---

## 2. Operating the Guided Demo

In the React Command Center dashboard (`http://localhost:5173`), the **Guided Disaster Demonstration Stepper** is prominently anchored at the top of the screen:

- **Launch Demo**: Click `▶ Launch Demo` to initiate Stage 1 from a verified clean state.
- **Stage Navigation**: Click `Next Stage ➔` or `◀ Back` to step manually through the stages at your presentation pace. Alternatively, click any completed stage chip (1 through 6) to jump directly.
- **Auto-Play Mode**: Toggle `▶ Auto-Play (7s)` to let the demonstration advance through the stages automatically with an animated progress countdown timer.
- **Reset**: Click `↺ Reset` to cleanly flush all messages, pending ACKs, and routing tables, returning all 5 nodes online.
- **Examiner Observation Guide**: Click `Examiner Observation Guide` on any stage to expand the technical briefing, network explanation, and protocol verification checklist.

---

## 3. The 6 Demonstration Stages in Computer Networks Terminology

| Stage | Title | CNT Protocol Actions | Expected Visual State |
| :--- | :--- | :--- | :--- |
| **Stage 1** | **Initial Network** | Initial node beaconing; baseline reactive route discovery; routing table population (`A -> B -> C -> H`). | All 5 nodes active (green); links active; route highlighted in emerald green; initial metrics baseline. |
| **Stage 2** | **Dispatch SOS** | Application-layer priority SOS wrapped in AODV `DATA` packet with UUID, GPS coords, and hop count. Forwarded hop-by-hop. | Packet traveling `A -> B -> C -> H`; status marked `DISPATCHED` / `FORWARDED` / `PENDING_ACK`. |
| **Stage 3** | **Hospital Receipt & ACK** | Destination packet delivery; hospital inbox insertion; generation of return `DATA` packet with `type: ack` and `ack_for_message_id`; reverse-path forwarding. | SOS arrives in hospital inbox; return ACK packet traverses `H -> C -> B -> A`; Rescue-A marks status `CONFIRMED` with measured RTT. |
| **Stage 4** | **Relay-B Failure** | Intermediate node crash; physical link disconnection; HELLO timeout or link-layer transmission error; route invalidation; `RERR` generation. | Relay-B turns red/offline; links to B severed; route indicator clears; recovery timer starts. |
| **Stage 5** | **Route Recovery** | Reactive route rediscovery via `RREQ` broadcast (`A -> D -> C -> H`); `RREP` unicast along reverse path; forward route installation; recovered SOS delivered; return ACK confirmed. | Node D routes packet; route re-established `A -> D -> C -> H`; new SOS delivered to hospital; ACK confirmed at A; recovery latency recorded. |
| **Stage 6** | **Results & Summary** | Protocol performance evaluation; PDR calculation; overhead quantification (RREQ/RREP/RERR counts); viva defense presentation. | Viva Defense Summary Card displays final statistics, delivery ratios, route history, and examiner talking points. |

---

## 4. Expected Observations and Metric Interpretation

### Primary Metrics
1. **Packet Delivery Ratio (PDR)**:
   $$\text{PDR} = \frac{\text{DATA Packets Delivered}}{\text{DATA Packets Dispatched}} \times 100\%$$
   In a normal run, PDR reflects the percentage of application DATA packets that reached their destination. If a packet was discarded while awaiting route discovery, the test harness accounts for it so that $\text{PDR} + \text{Loss} = 100.0\%$.
2. **Round-Trip Time (RTT)**:
   The elapsed duration between Rescue-A dispatching the original SOS and receiving the matching, validated return ACK DATA packet from Hospital-H.
   - In **Simulation Mode**: Calculated based on discrete-event logical clock (50ms per hop, typically ~300ms for 6 total hops).
   - In **Real UDP Mode**: Calculated from high-resolution OS monotonic timestamps over loopback sockets.
3. **Route Recovery Time**:
   The measured interval between the invalidation of the primary route through failed Relay-B and the completion of route rediscovery establishing the alternate path through Relay-D.
4. **Routing Protocol Overhead**:
   - `RREQ Count`: Number of Route Request broadcasts generated during initial route establishment and post-failure recovery.
   - `RREP Count`: Number of Route Reply unicasts sent by the destination to install the forward route.
   - `RERR Count`: Number of Route Error packets generated to notify neighbors of broken links.

---

## 5. Simulation Mode vs. Real UDP Mode

ResQNet supports two distinct operational runtimes. The demonstration panel clearly highlights the active mode:

### Simulation Mode (Discrete-Event)
- **Execution Model**: Single Python process using a logical simulation clock (`sim_time`).
- **Hop Latency**: Deterministic 50ms simulated link delay per transmission.
- **Evidence**: Events streamed synchronously to the dashboard via FastAPI WebSockets.
- **Use Case**: Reproducible classroom demonstrations and fast regression testing without network socket dependencies.

### Real UDP / LAN Mode (Multi-Process)
- **Execution Model**: 5 independent OS processes (`run_node.py`), one for each node (A, B, C, D, H).
- **Transport**: Real OS UDP sockets (`0.0.0.0:50010` to `50014`), transmitting serialized JSON datagrams.
- **Neighbor Detection**: Real 1.0s periodic UDP `HELLO` beacons; 3.0s loss threshold triggers neighbor failure.
- **Evidence**: Real loopback/network interface packet exchanges verifiable in Wireshark via display filter `udp.port in {50010..50014}`.

---

## 6. Known Limitations and Claims Policy

To maintain complete academic and engineering integrity during the viva evaluation:

1. **Physical LAN Execution Status**:
   - The multi-process UDP architecture and socket configuration support multi-device deployment across separate laptops on an unisolated Wi-Fi/Ethernet subnet (see `configs/lan_nodes.json` and `docs/lan_deployment.md`).
   - However, **physical multi-laptop execution on distinct physical machines is currently documented and architecture-ready, but was tested in development on localhost loopback UDP processes.** Do NOT claim physical 2-to-5 laptop Wi-Fi testing was conducted unless you personally execute the LAN deployment scripts during the viva.
2. **No Graph Shortcuts**:
   - ResQNet does not use Dijkstra, BFS, or centralized graph algorithms to compute paths. All routing state emerges exclusively from distributed AODV control packets (RREQ, RREP, RERR).
3. **Genuine Acknowledgment**:
   - Hospital receipt is never treated as ACK confirmation. Confirmation requires an explicit return DATA packet traversing from H to A and matching the pending message ID before deadline expiry.
