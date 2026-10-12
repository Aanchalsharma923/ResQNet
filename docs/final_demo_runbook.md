# ResQNet — Final Demonstration Runbook (Phase 5.1)

## Executive Summary

This runbook provides complete, reproducible instructions for demonstrating **ResQNet**: an Ad hoc On-Demand Distance Vector (AODV) emergency ad-hoc mesh communication network demonstrating packet routing, heartbeat failure detection, dynamic route recovery, and real-time visualization.

This document records the mandatory pre-Phase-5.1 verification checks, exact commands for both web dashboard and terminal demonstrations, detailed step-by-step procedures, expected observations, troubleshooting steps, and the physical LAN acceptance criteria.

---

## Part 1: Mandatory Pre-Phase-5.1 Verification Checks

### Check 1 — Pytest Warning Audit

- **Original Report**: `146 passed, 1 warning in 49.28s`
- **Investigation**: Ran the complete backend test suite with warnings visible (`pytest -v -W default`).
- **Exact Warning Captured**:
  ```text
  fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa
  ```
- **Originating File and Line**: `fastapi/testclient.py`, Line 1 (imported by `starlette.testclient`).
- **Category**: `StarletteDeprecationWarning`.
- **Root Cause & Impact**:
  - The warning originates entirely within the third-party `fastapi` and `starlette` libraries installed in Python 3.12.
  - It advises that in future versions of Starlette, `starlette.testclient` may prefer `httpx2`.
  - It does **not** indicate a defect, resource leak, concurrency flaw, or invalid test assumption in ResQNet code.
  - An upstream fix depends on FastAPI releasing an update transitioning their internal re-exports to `httpx2`.
- **Policy**: Per strict audit rules, this warning is **not suppressed, filtered, ignored, or hidden**. It is acknowledged as a harmless third-party library deprecation notice.
- **Verification**: Verified via test suite run (`147 passed, 1 warning in 50.02s`).

---

### Check 2 — Active-Route Ownership & Architectural Separation

- **Files Inspected**:
  - `resqnet/backend/app/runtime/real_network_runtime.py`
  - `resqnet/backend/app/routing/aodv_router.py`
  - `resqnet/backend/app/routing/table.py`
  - `resqnet/backend/app/runtime/node.py`
  - `frontend/src/App.tsx`
  - `frontend/src/components/TopologyView.tsx`
  - `tests/test_real_network_dashboard.py`

- **Architectural Findings & Resolutions**:
  1. **AODV Authority**: AODV is the **sole authority** for packet forwarding decisions. Each independent node runs its own `AODVRouter` maintaining its own routing table.
  2. **Removal of Topology Fallback**: In `RealNetworkRuntime._recalculate_active_route()`, previous logic contained a heuristic fallback (`elif len(route) == 2: if candidate == destination_id or candidate == "C": nxt = candidate`). This was **completely removed**. The dashboard runtime now traces paths strictly through reported, installed AODV next-hop entries (`_routing_entries`).
  3. **Neighbor Constraint**: Every hop in the reconstructed display path must be a valid configured neighbor (`DEFAULT_LINKS`). Fabricated or non-neighbor hops are rejected.
  4. **Unreachable Destination Handling**: If no connected sequence of valid AODV routing entries spans from source to destination, `active_route` is set strictly to `[]` (empty). It is never guessed from graph topology.
  5. **No Packet-Driven Route Injection**: In `RealNetworkRuntime._handle_incoming_event()`, `DATA_FORWARDED` previously injected routes into `_routing_entries`. This was removed; `DATA_FORWARDED` is now strictly an event for UI animation, preventing data movement from mutating routing state.
  6. **Purging on Node Termination**: When a node process is stopped (`stop_node`), all routing table entries originating from or pointing to that node are purged, and `active_route` is cleared if the failed node was on the path.
  7. **Zero Client-Side Routing**: The React frontend (`App.tsx`) contains zero pathfinding algorithms (no Dijkstra, BFS, DFS, A*, or shortest-path calculation). It strictly receives and renders the authoritative `active_route` list delivered by the backend WebSocket.
  8. **Zero production pathfinding algorithms**: No graph algorithms (BFS, DFS, Dijkstra, A*, NetworkX) are used in production routing.

- **Regression Test Added**:
  - `tests/test_real_network_dashboard.py::test_route_ownership_strict_separation`
  - Verifies:
    - Injected non-neighbor entries are rejected.
    - Partial routes are not fabricated into full paths.
    - Invalidated routes clear the active path immediately.
    - Stopped nodes are never retained in active routes.
    - Unreachable destinations evaluate to `[]`.
  - Result: **5/5 tests passing**.

---

### Check 3 — Physical LAN Deployment Readiness & Checklist

- **Code & Configuration Readiness Verified**:
  - `configs/lan_nodes.json`: Clearly marked with example RFC 1918 private IPv4 addresses (`192.168.1.101`–`105`) and ports (`50010`–`50014`).
  - `configs/localhost_nodes.json`: Localhost loopback mappings (`127.0.0.1`, ports `50010`–`50014`).
  - `scripts/run_node.py`: Decouples bind address (`--bind-host 0.0.0.0`) from destination host in the JSON configuration. Independent logical IDs (`A`, `B`, `C`, `D`, `H`) map to physical UDP endpoints.
  - Socket Management: Clean startup and graceful SIGINT/SIGTERM shutdown.
  - Zero OS Manipulation: Zero network scanning, zero firewall modification, zero interface tampering.

- **Status**:
  ```text
  DOCUMENTED — PHYSICAL EXECUTION PENDING
  ```
  *(Automated multi-process UDP testing is fully validated on localhost; physical 5-laptop LAN execution requires dedicated physical hardware on a shared, non-isolated Wi-Fi/Ethernet subnet as detailed in the checklist below).*

#### Physical Acceptance Checklist (For Live Multi-Laptop Test)

| Step | Action | Verification |
|---|---|---|
| **1. Network Setup** | Connect 5 laptops to a shared Wi-Fi router or Ethernet switch. | Verify all devices have IP addresses on the same subnet (e.g., `192.168.1.0/24`). |
| **2. Client Isolation** | Ensure Wi-Fi Access Point / Router does **not** have AP/Client Isolation enabled. | Ping Laptop 2 (`B`) from Laptop 1 (`A`) to verify peer-to-peer ICMP reachability. |
| **3. Firewall Approval** | Permit inbound UDP traffic on ports `50010`–`50014` and control ports `51010`–`51014` on all host firewalls. | Administrator approved firewall rule applied. |
| **4. Configure Endpoints** | Record actual LAN IP of each laptop and edit `configs/lan_nodes.json`. | Each entry matches the physical IP of the corresponding node. |
| **5. Distribute Config** | Copy identical `configs/lan_nodes.json` to all 5 laptops. | File checksum or contents verified identical. |
| **6. Start Nodes** | Launch each node on its designated laptop:<br>`python scripts/run_node.py --node-id <ID> --config configs/lan_nodes.json --bind-host 0.0.0.0` | Console displays banner and `Status: READY`. |
| **7. Observe HELLO** | Watch console logs on all nodes. | Nodes log `NEIGHBOR_HELLO_SENT` and confirm neighbor liveness. |
| **8. Route Discovery** | Send SOS from Laptop 1 (`A`): Node A emits `RREQ`, destination `H` emits `RREP`. | Forward routes installed on A, B, C; route `A → B → C → H` active. |
| **9. SOS Delivery** | Node A dispatches `DATA` packet carrying SOS `HELP REQUIRED`. | Hospital `H` logs `PACKET DELIVERED: HELP REQUIRED`. |
| **10. Failure Injection** | Press `Ctrl+C` on Laptop 2 (`B`) to stop Relay-B. | Process terminates cleanly. |
| **11. Timeout & Invalidation** | Observe Laptop 1 (`A`) and Laptop 3 (`C`) logs for 3.0s. | `HELLO TIMEOUT: B` triggers; route invalidated; `RERR` emitted. |
| **12. Recovery Transmission** | Send second SOS from Laptop 1 (`A`). | Node A emits new `RREQ`; route discovered through `D` (`A → D → C → H`). |
| **13. Second SOS Receipt** | Verify delivery at Hospital `H`. | Hospital `H` logs `PACKET DELIVERED: HELP REQUIRED (RECOVERED)`. |
| **14. Clean Shutdown** | Stop all remaining node processes using `Ctrl+C`. | All sockets closed cleanly without dangling ports. |

---

## Part 2: Supported Demonstration Modes

ResQNet supports two primary demonstration modes:
1. **Mode A — Web Dashboard Demonstration**: Interactive SVG visualization with live WebSocket telemetry, SOS transmission, failure injection, and metric tracking.
2. **Mode B — CLI / Terminal Real UDP Demonstration**: Automated or manual multi-process execution showing raw AODV control packets, neighbor heartbeats, and delivery confirmations.

---

## Part 3: Mode A — Web Dashboard Demonstration

### Prerequisites
- Python 3.12+ with dependencies installed (`pip install -r resqnet/backend/requirements.txt`).
- Node.js 18+ and npm installed (`cd frontend && npm install`).
- Ports `8000` (FastAPI REST/WebSocket) and `5173` (Vite dev server) available.

### Step 1: Start Backend Server
Open **Terminal 1** in the repository root:
```bash
uvicorn resqnet.backend.app.main:app --host 127.0.0.1 --port 8000
```
- **Expected Output**:
  ```text
  INFO:     Started server process
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://127.0.0.1:8000
  ```

### Step 2: Start Frontend Dashboard
Open **Terminal 2** in the `frontend` directory:
```bash
cd frontend
npm run dev
```
- **Expected Output**:
  ```text
  VITE v8.3.3  ready in ... ms
  ➜  Local:   http://localhost:5173/
  ```

### Step 3: Open and Verify Dashboard
1. Open a browser and navigate to `http://localhost:5173`.
2. Verify:
   - Header shows **ResQNet Disaster Network Dashboard**.
   - Mode Toggle displays **Simulation Mode** and **Real UDP / LAN Mode**.
   - Node topology displays 5 nodes: **Rescue-A**, **Relay-B**, **Relay-C**, **Relay-D**, and **Hospital-H**.
   - Status indicator shows **Connected** (WebSocket active).

### Step 4: Switch to Real UDP / LAN Mode
1. Click the **Real UDP / LAN Mode** button in the header (or send `POST http://localhost:8000/api/runtime/mode` with `{"mode": "real"}`).
2. **Expected Behavior**:
   - Backend `RealNetworkRuntime` launches 5 independent OS subprocesses (`A`, `B`, `C`, `D`, `H`) using `configs/localhost_nodes.json`.
   - Node status indicators turn green (**UP**).
   - Event Log shows:
     - `[A] NODE_STARTED`
     - `[B] NODE_STARTED`
     - `[C] NODE_STARTED`
     - `[D] NODE_STARTED`
     - `[H] NODE_STARTED`
     - `[A] NEIGHBOR_HELLO_SENT` (and replies confirming neighbor health).

### Step 5: Send Initial SOS Distress Signal
1. In the **Send SOS Distress Signal** panel:
   - Message: `HELP REQUIRED`
   - Priority: `HIGH`
   - Latitude: `18.5204`, Longitude: `73.8567`
2. Click **Broadcast SOS Distress Signal**.
3. **Expected Behavior**:
   - Node A initiates AODV route discovery: `RREQ` broadcasts to neighbors.
   - Destination Hospital H generates `RREP`.
   - Forward routes install along `A → B → C → H`.
   - Active route turns **glowing green** along `A → B → C → H`.
   - Data packet delivers to Hospital H.
   - **Hospital Inbox** displays: `HELP REQUIRED` (Priority: HIGH).
   - Packet counters increment; PDR and Latency metrics update.

### Step 6: Simulate Failure of Relay-B
1. In the **Topology View** or node controls, click **Fail Node B** (or send `POST http://localhost:8000/api/real/nodes/B/stop`).
2. **Expected Behavior**:
   - Process for Relay-B is terminated. Node B turns red (**DOWN**).
   - Active route `A → B → C → H` is immediately invalidated and cleared.
   - After ~3.0 seconds, nodes A and C detect HELLO timeout:
     - Event log records `[A] HELLO TIMEOUT: B` and `[A] NEIGHBOR_DOWN: B`.
     - Route via B is invalidated; `RERR` packet generated.

### Step 7: Send Subsequent SOS (Failure Recovery)
1. Send another SOS message:
   - Message: `HELP REQUIRED (RECOVERED)`
2. Click **Broadcast SOS Distress Signal**.
3. **Expected Behavior**:
   - Node A initiates fresh `RREQ` broadcast.
   - Since B is down, RREQ propagates through remaining connected topology via **Relay-D** (`A → D → C → H`).
   - Hospital H responds with `RREP`.
   - Discovered active route turns glowing green along **`A → D → C → H`**.
   - Hospital Inbox displays second message: `HELP REQUIRED (RECOVERED)`.
   - Alternate route emerged **purely from AODV protocol logic** without any hardcoding!

### Step 8: Clean Shutdown
1. In Terminal 1 (Uvicorn), press `Ctrl+C`.
2. All subprocesses (`A`, `B`, `C`, `D`, `H`) and UDP sockets are terminated cleanly.
3. In Terminal 2 (Vite), press `Ctrl+C`.

---

## Part 4: Mode B — CLI / Terminal Reproducible Demonstration

For headless or automated validation, ResQNet provides the standalone demo launcher `scripts/run_demo.py`.

### Command
From the repository root:
```bash
python scripts/run_demo.py
```

### Execution Flow & Log Milestones
1. **[Step 1] Initializing Nodes**:
   - Launches independent subprocesses for `A`, `B`, `C`, `D`, `H`.
   - Binds UDP sockets on ports `50010`–`50014` and command listeners on `51010`–`51014`.
   - Verifies all 5 nodes report `READY`.
2. **[Step 2] Initial Route Discovery & Delivery**:
   - Node A creates `RREQ` for packet destined to H.
   - Hospital H generates `RREP`.
   - Forward routes install: `A → B → C → H`.
   - Packet delivered to Hospital: `HELP REQUIRED`.
3. **[Step 3] Failure Injection**:
   - Stops Relay-B process.
4. **[Step 4] Failure Detection**:
   - HELLO beacons from B cease.
   - At 3.0s, nodes C and A report `HELLO TIMEOUT: B`, `NEIGHBOR_DOWN: B`, and emit `RERR`.
   - Active route clears to `[]`.
5. **[Step 5] AODV Route Recovery**:
   - Node A transmits second SOS `HELP REQUIRED (RECOVERED)`.
   - New `RREQ` discovers alternate route through `D` (`A → D → C → H`).
   - Second packet delivered to Hospital: `HELP REQUIRED (RECOVERED)`.
6. **[Step 6] Clean Shutdown**:
   - Shuts down all processes and sockets cleanly.

---

## Part 5: Verification Evidence Summary

| Test Suite | Command | Result | Notes |
|---|---|---|---|
| **Full Backend Tests** | `python -m pytest -q` | **147 passed, 1 warning** (50.02s) | All unit, routing, transport, failure, and API tests passed. |
| **Dashboard Tests** | `python -m pytest tests/test_real_network_dashboard.py -v` | **5 passed, 1 warning** (1.35s) | Strict route ownership verified. |
| **Frontend Tests** | `npm test -- --run` (in `frontend/`) | **8 passed** across 3 test files | EventLog, App, TopologyView tests passed. |
| **Frontend Build** | `npm run build` (in `frontend/`) | **Exit code 0** (1.01s) | Production bundle compiled cleanly. |
| **Localhost UDP Demo** | `python scripts/run_demo.py` | **Exit code 0** (~15s) | 5 nodes, AODV RREQ/RREP, SOS delivery, B failure, D recovery. |

---

## Part 6: Wireshark Packet Inspection (Phase 5.2)

For low-level packet verification during the demonstration, Wireshark can be used to observe real UDP datagrams carrying ResQNet's JSON-serialized AODV and SOS packets.

- **Detailed Guide**: See [docs/wireshark_validation.md](file:///c:/Users/aanch/OneDrive/Desktop/Documents/CNT/ResQNet/docs/wireshark_validation.md) for full prerequisites, interface setup, payload schemas, and troubleshooting.
- **Recommended Interface**:
  - **Localhost**: Select `Npcap Loopback Adapter` (Windows) or `lo` (Linux/macOS).
  - **Physical LAN**: Select active `Wi-Fi` or `Ethernet` network card.
- **Key Display Filters**:
  - Inter-node mesh traffic: `udp.port in {50010..50014}`
  - RREQ / RREP route discovery: `udp.port in {50010..50014} && (frame contains "RREQ" || frame contains "RREP")`
  - Route error (RERR): `udp.port in {50010..50014} && frame contains "RERR"`
  - SOS distress data: `udp.port in {50010..50014} && frame contains "HELP REQUIRED"`
- **Protocol Note**: ResQNet runs application-level AODV over UDP ports `50010`–`50014`. Datagrams appear in Wireshark as UDP packets carrying JSON UTF-8 payloads, rather than binary RFC 3561 packets (port 654).

---

## Part 7: Troubleshooting & Common Issues

1. **Port Already in Use (`OSError: [Errno 10048] Address already in use`)**:
   - Cause: A previous test run or orphaned process is still holding UDP ports `50010`–`50014` or `50099`.
   - Solution (Windows PowerShell):
     ```powershell
     Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
     ```
2. **Missing `resqnet` Module in Python**:
   - Cause: Invoking a script from a subfolder without repository root in `PYTHONPATH`.
   - Solution: All scripts in `scripts/` automatically insert repository root to `sys.path`. Always run commands from the repository root.
3. **Browser WebSocket Disconnected**:
   - Cause: Backend server is not running on port `8000`.
   - Solution: Start backend with `uvicorn resqnet.backend.app.main:app --port 8000`.
4. **Physical Wi-Fi Communication Blocked**:
   - Cause: Wi-Fi Access Point has AP/Client isolation enabled.
   - Solution: Use a dedicated mobile hotspot or direct Ethernet switch where peer devices can communicate freely.
