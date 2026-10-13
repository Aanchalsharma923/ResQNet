# ResQNet: Two-Laptop LAN Deployment & Viva Verification Guide

## Overview

This guide details the exact procedure to demonstrate **ResQNet's disaster-resilient AODV network across two physical laptops** on the same Local Area Network (Wi-Fi or Ethernet).

### Target Topology Across Machines

```text
       [ LAPTOP 1: Command Center & Mesh ]                  [ LAPTOP 2: Destination ]

            Rescue-A (port 50010)
                 /        \
    Relay-B (50011)     Relay-D (50013)
                 \        /
            Relay-C (port 50012)
                    |
      ========== PHYSICAL LAN / UDP ==========>
                    |
               Hospital-H (port 50014)
```

- **Laptop 1**: Hosts the React Emergency Command Center Dashboard, FastAPI Backend, Event Bridge, and Nodes **Rescue-A**, **Relay-B**, **Relay-C**, and **Relay-D**.
- **Laptop 2**: Hosts **Hospital-H**, running as an independent node process receiving real UDP datagrams, recording SOS in its local inbox, and transmitting network-level return ACKs back to Laptop 1.

---

## 1. Network Prerequisites & IP Discovery

Both laptops must be connected to the **same local network** (e.g., standard Wi-Fi, mobile phone hotspot, or Ethernet switch).
> [!IMPORTANT]
> **Client Isolation Warning**: Campus, public, or enterprise guest Wi-Fi networks frequently enable "AP Isolation" or "Client Isolation", which silently blocks UDP and TCP peer-to-peer communication between laptops. For an evaluation or viva, use a mobile phone hotspot or direct Ethernet connection to guarantee uninhibited peer-to-peer traffic.

### Step 1.1: Discover IP Addresses
Run this command in PowerShell on **both laptops**:
```powershell
ipconfig
```
Look for your active network adapter (e.g. `Wireless LAN adapter Wi-Fi` or `Ethernet adapter`):
- Find the **IPv4 Address**.
- *Example (Laptop 1)*: `192.168.1.150`
- *Example (Laptop 2)*: `192.168.1.180`

### Step 1.2: Test Basic IP Reachability (ICMP Ping)
From Laptop 1 PowerShell:
```powershell
ping <LAPTOP_2_IP>
```
From Laptop 2 PowerShell:
```powershell
ping <LAPTOP_1_IP>
```
If pings time out, check Windows Firewall settings (Step 2).

---

## 2. Windows Defender Firewall Configuration

Windows Defender Firewall blocks unsolicited incoming UDP and TCP packets by default. **Do NOT disable your firewall.** Instead, open the specific ports used by ResQNet.

Run PowerShell **as Administrator** on each laptop:

### On Laptop 1 (Administrator PowerShell)
```powershell
# 1. Allow Inbound UDP for ResQNet mesh nodes (Ports 50010 to 50013)
New-NetFirewallRule -DisplayName "ResQNet-UDP-Nodes" -Direction Inbound -LocalPort 50010-50013 -Protocol UDP -Action Allow

# 2. Allow Inbound UDP for ResQNet Event Bridge (Port 50099)
New-NetFirewallRule -DisplayName "ResQNet-UDP-EventBridge" -Direction Inbound -LocalPort 50099 -Protocol UDP -Action Allow

# 3. Allow Inbound TCP for FastAPI Backend (Port 8000)
New-NetFirewallRule -DisplayName "ResQNet-TCP-Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# 4. Allow Inbound TCP for Vite Frontend (Port 5173 - if viewed from Laptop 2)
New-NetFirewallRule -DisplayName "ResQNet-TCP-Frontend" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow
```

### On Laptop 2 (Administrator PowerShell)
```powershell
# 1. Allow Inbound UDP for Hospital-H (Port 50014)
New-NetFirewallRule -DisplayName "ResQNet-UDP-Hospital-H" -Direction Inbound -LocalPort 50014 -Protocol UDP -Action Allow
```

*(To remove these rules after your project evaluation, run: `Remove-NetFirewallRule -DisplayName "ResQNet-*"`)*

---

## 3. Configuration Setup

ResQNet includes `configs/lan_two_laptops.json` which supports environment variable expansion with safe fallbacks:

```json
{
  "A": { "host": "${LAPTOP_1_IP:-127.0.0.1}", "port": 50010 },
  "B": { "host": "${LAPTOP_1_IP:-127.0.0.1}", "port": 50011 },
  "C": { "host": "${LAPTOP_1_IP:-127.0.0.1}", "port": 50012 },
  "D": { "host": "${LAPTOP_1_IP:-127.0.0.1}", "port": 50013 },
  "H": { "host": "${LAPTOP_2_IP:-127.0.0.1}", "port": 50014 }
}
```

### Option A (Recommended): Using Environment Variables
You do NOT need to edit any files. Simply export the discovered IPs in your terminal sessions before running.

### Option B: Static JSON
Alternatively, you can edit `configs/lan_two_laptops.json` directly and fill in the literal IP addresses. Copy the identical configuration file to both laptops.

---

## 4. Exact Startup Commands

### Step 4.1: Laptop 1 (Backend, Nodes A/B/C/D, & Dashboard)

Open **Terminal 1** on Laptop 1:
```powershell
# Set Environment Variables (replace with your actual discovered IPs)
$env:LAPTOP_1_IP = "192.168.1.150"
$env:LAPTOP_2_IP = "192.168.1.180"
$env:RESQNET_CONFIG_PATH = "configs/lan_two_laptops.json"
$env:RESQNET_MANAGED_NODES = "A,B,C,D"
$env:RESQNET_EVENT_BIND_HOST = "0.0.0.0"

# Start the FastAPI Backend
python -m uvicorn resqnet.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **Terminal 2** on Laptop 1:
```powershell
# Start the React Frontend Dashboard
cd frontend
npm run dev -- --host 0.0.0.0
```
- Local URL: `http://localhost:5173`
- Network URL: `http://192.168.1.150:5173`

---

### Step 4.2: Laptop 2 (Hospital-H)

Open **Terminal 1** on Laptop 2:
```powershell
# Set Environment Variables (must match the same values used on Laptop 1)
$env:LAPTOP_1_IP = "192.168.1.150"
$env:LAPTOP_2_IP = "192.168.1.180"

# Start Node Hospital-H
python scripts/run_node.py --node-id H --config configs/lan_two_laptops.json --bind-host 0.0.0.0 --event-host 192.168.1.150 --event-port 50099
```

**Expected Console Output on Laptop 2:**
```text
========================================
RESQNET NODE
========================================
Node ID: H
Transport: UDP
Bind: 0.0.0.0:50014
Configured endpoint: 192.168.1.180:50014
Mode: LAN
Neighbors: C
Status: READY
========================================
```

---

## 5. Live Demonstration & Verification Procedure

### Test 1: Baseline Health & Connectivity
1. On Laptop 1, open `http://localhost:5173`.
2. Toggle the runtime selector to **Real UDP / LAN Mode**.
3. In the topology view, observe:
   - **Nodes A, B, C, D** are indicated **ACTIVE / UP** (green).
   - **Node H** is indicated **ACTIVE / UP** (green), recognized via UDP events received at `0.0.0.0:50099`.
   - Link `C — H` is indicated **ACTIVE**.

### Test 2: Cross-Device SOS Dispatch & Return ACK
1. On Laptop 1, navigate to the **Emergency SOS Dispatch** panel.
2. Select Priority `CRITICAL`, enter message `CASUALTY EVACUATION - SECTOR 4`, and click `DISPATCH SOS`.
3. **Observe the actual packet trajectory**:
   - `Rescue-A` creates DATA packet; sends over UDP to `Relay-B`.
   - `Relay-B` forwards to `Relay-C` (local loopback UDP).
   - `Relay-C` sends physical UDP datagram across Wi-Fi/LAN to `192.168.1.180:50014`.
   - **On Laptop 2 Terminal**, observe the immediate log:
     ```text
     [H] PACKET DELIVERED: {'message_id': '...', 'message': 'CASUALTY EVACUATION - SECTOR 4', 'type': 'sos'}
     [H] Generating return ACK packet for message_id ...
     ```
   - Hospital-H generates return `DATA` packet with `type: ack` and transmits it across the LAN to `Relay-C` (`192.168.1.150:50012`).
   - The ACK traverses `C -> B -> A`.
   - On Laptop 1, the SOS status transitions from `PENDING` to `CONFIRMED` with measured round-trip time (`RTT`).
   - The Hospital Inbox panel displays the delivered SOS.

### Test 3: Relay-B Failure & Autonomous AODV Recovery
1. In the **Network Controls** panel on Laptop 1, click `Fail Node` on **Relay-B**.
2. **Observe the network response**:
   - Relay-B process terminates.
   - Nodes A and C detect HELLO timeout ($3.0\text{s}$) and emit `NEIGHBOR_DOWN: B`.
   - The active route `A -> B -> C -> H` is invalidated.
   - The green route highlight clears.
3. Dispatch a second SOS from Rescue-A:
   - Rescue-A broadcasts an AODV `RREQ`.
   - `Relay-D` forwards the `RREQ` to `Relay-C`.
   - `Relay-C` forwards to `Hospital-H` on Laptop 2.
   - `Hospital-H` replies with `RREP` along the reverse path.
   - Forward route `A -> D -> C -> H` is installed.
   - The recovered SOS traverses `A -> D -> C -> (LAN) -> H`.
   - Hospital-H receives and records the recovered message.
   - Return ACK traverses back via D and confirms at Rescue-A!

### Test 4: Hospital-H Shutdown & Restart (Destination Recovery)
1. On Laptop 2, press `Ctrl+C` to terminate Hospital-H.
2. Observe on Laptop 1:
   - Node C detects neighbor loss; link `C — H` becomes red/DOWN.
   - Any new SOS dispatched from Rescue-A drops with `NO_ROUTE_AVAILABLE`.
3. Restart Hospital-H on Laptop 2:
   - Within 1 second, HELLO beacons exchange between H and C.
   - Node C emits `NEIGHBOR_RECOVERED: H`.
   - Link `C — H` turns green/UP.
   - New SOS messages succeed immediately.

---

## 6. Wireshark Capture: Localhost vs Physical LAN Traffic

A common point of confusion during CNT project vivas is **which network adapter to capture on in Wireshark**.

### 6.1 Understanding Traffic Paths

```text
[ Laptop 1 ]                                            [ Laptop 2 ]
A <-> B <-> C  (Localhost/Loopback adapter)
            C ================= (Physical Wi-Fi/Ethernet) ================> H (port 50014)
            ^ <---------------- (Physical Wi-Fi/Ethernet) ----------------- H (events -> 50099)
```

- Packets between **Rescue-A**, **Relay-B**, **Relay-C**, and **Relay-D** remain entirely on Laptop 1's virtual loopback interface.
- Only packets between **Relay-C and Hospital-H** (and event packets from H to port 50099) cross the physical LAN.

---

### 6.2 Wireshark Capture on Laptop 1

1. **Physical Interface Capture (Cross-Device Traffic)**:
   - Select your physical adapter in Wireshark (e.g., `Wi-Fi` or `Ethernet`).
   - Set Display Filter:
     ```text
     udp.port in {50012, 50014, 50099} or ip.addr == <LAPTOP_2_IP>
     ```
   - **What you will see**:
     - Periodic `HELLO` beacons between C and H.
     - Outgoing `RREQ` from C to H (destination port `50014`).
     - Incoming `RREP` from H to C (destination port `50012`).
     - Cross-device `DATA` packet carrying the SOS payload (`"type": "sos"`).
     - Cross-device `DATA` packet carrying the return ACK (`"type": "ack"`).
     - UDP Event datagrams from H to Laptop 1 on port `50099`.

2. **Loopback Adapter Capture (Intra-Machine Mesh Traffic)**:
   - Select the `Adapter for loopback traffic capture` (Npcap Loopback Adapter).
   - Set Display Filter:
     ```text
     udp.port in {50010, 50011, 50012, 50013}
     ```
   - **What you will see**:
     - Traffic between nodes A, B, C, D prior to leaving Laptop 1.

---

### 6.3 Wireshark Capture on Laptop 2

- Select the physical adapter (e.g., `Wi-Fi` or `Ethernet`).
- Set Display Filter:
  ```text
  udp.port == 50014 or udp.port == 50099
  ```
- **What you will see**:
  - Inbound SOS datagram arriving on port `50014` from Laptop 1 (`Relay-C`).
  - Outbound return ACK datagram leaving port `50014` bound for `Relay-C` (`port 50012`).
  - Outbound event reports (`NODE_STARTED`, `SOS_DELIVERED`, `ACK_GENERATED`) directed to Laptop 1's port `50099`.

---

### 6.4 Inspecting Packet Payloads in Wireshark
Click any captured UDP packet -> Expand **Data** in the packet details pane:
- Observe the genuine UTF-8 JSON payload:
  ```json
  {"type": "DATA", "source": "A", "destination": "H", "hop_count": 2, "sequence_number": 1, "payload": "{\"message_id\": \"...\", \"message\": \"CASUALTY EVACUATION\", \"type\": \"sos\"}"}
  ```
- Notice that the return ACK is also a real packet:
  ```json
  {"type": "DATA", "source": "H", "destination": "A", "hop_count": 0, "sequence_number": 1, "payload": "{\"message_id\": \"...\", \"ack_for_message_id\": \"...\", \"type\": \"ack\"}"}
  ```
- This confirms that acknowledgments are genuine routed network datagrams, not simulated UI state.

---

## 7. Troubleshooting & Diagnostics

### Distinguishing Firewall Issues from Application Issues

Use PowerShell's `Test-NetConnection` to test layer-3 and layer-4 connectivity before launching:

```powershell
# 1. Test ICMP Ping (Layer 3)
Test-NetConnection -ComputerName <TARGET_IP>

# 2. Test Backend TCP (Layer 4) from Laptop 2 to Laptop 1
Test-NetConnection -ComputerName <LAPTOP_1_IP> -Port 8000
```

- If `TcpTestSucceeded : True`: The IP route is intact and Windows Firewall allows TCP port 8000.
- If `PingSucceeded : True` but `TcpTestSucceeded : False`: Network routing works, but Windows Firewall or port binding is blocking port 8000.
- If both fail: The laptops are not on the same subnet or the Wi-Fi router has Client Isolation enabled.

### Common Symptoms & Solutions

| Symptom | Root Cause | Diagnosis Command / Fix |
| :--- | :--- | :--- |
| `ping` works, but `Test-NetConnection -Port 8000` fails | Firewall blocking TCP 8000 on Laptop 1 | Run `New-NetFirewallRule ... -LocalPort 8000 -Protocol TCP` on Laptop 1 as Admin. |
| Node H starts, but Laptop 1 dashboard never shows H | UDP event port 50099 blocked on Laptop 1 | Check Laptop 1 firewall rule `ResQNet-UDP-EventBridge`. Ensure `--event-host` is Laptop 1's exact LAN IP. |
| SOS sent from A, but C never forwards to H | UDP port 50014 blocked on Laptop 2 | Check Laptop 2 firewall rule `ResQNet-UDP-Hospital-H`. Ensure `--config` on Laptop 1 has H's correct IP. |
| Pings time out completely | Wi-Fi Client / AP Isolation enabled | Disconnect from campus Wi-Fi and connect both laptops to a mobile hotspot or direct Ethernet cable. |
| `WinError 10048: Only one usage of each socket address` | A previous node process is still running | Run `Get-Process python | Stop-Process` in PowerShell to kill orphaned background processes. |

---

## 8. Integrity & Viva Defense Disclosure

To preserve complete academic honesty during project evaluation:
- **Automated Cross-Process Testing**: Verified and passed 100% in automated integration test suite (`tests/test_two_laptop_lan.py` spins up independent processes simulating two machines over local sockets).
- **Physical Multi-Laptop LAN Testing**: Architecture, configuration loader, firewalls, and startup scripts are fully implemented and verified. Actual physical verification between two separate hardware laptops must be demonstrated live during evaluation on your Wi-Fi network. Do not claim physical multi-laptop execution until physically performed.
