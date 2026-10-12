# ResQNet — Wireshark Packet Validation Guide (Phase 5.2)

## 1. Protocol Architecture & Wireshark Representation

ResQNet implements Ad hoc On-Demand Distance Vector (AODV) routing at the **application level** over standard UDP/IP datagram sockets.

### Protocol Separation
It is critical to distinguish between the architectural layers when observing network traffic:

```
+-------------------------------------------------------------------------+
| APPLICATION LAYER: AODV Routing & SOS Payloads                           |
| Messages: RREQ, RREP, RERR, HELLO, DATA (SOS)                           |
| Wire Representation: UTF-8 JSON datagrams                                |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| TRANSPORT LAYER: OS-Level UDP Sockets                                   |
| Configured Ports: 50010 (A), 50011 (B), 50012 (C), 50013 (D), 50014 (H) |
| Control Ports:    51010 (A), 51011 (B), 51012 (C), 51013 (D), 51014 (H) |
| Event Bridge:     50099 (Dashboard Telemetry)                           |
+-------------------------------------------------------------------------+
                                   |
+-------------------------------------------------------------------------+
| INTERNET LAYER: IPv4 Datagrams                                          |
| Localhost: 127.0.0.1 (Loopback)                                         |
| Physical LAN: 192.168.1.101-105 (Ethernet/Wi-Fi)                        |
+-------------------------------------------------------------------------+
```

> [!IMPORTANT]
> **No Native RFC 3561 Dissector**: Standard Wireshark contains a dissector for RFC 3561 binary AODV datagrams that listens exclusively on well-known UDP port `654`. ResQNet operates over custom configurable UDP ports (`50010`–`50014`) using a robust, human-readable JSON wire format. In Wireshark, ResQNet packets appear as standard **UDP** datagrams carrying JSON payloads. They should be inspected via the **Packet Bytes** pane, the **Data** tree item, or by selecting **Follow → UDP Stream**.

---

## 2. Configured Ports & Endpoints Reference

Derived directly from `configs/localhost_nodes.json`, `configs/lan_nodes.json`, and `RealNetworkRuntime`:

| Logical Node | Host Interface (Localhost) | Node UDP Port | Control UDP Port | LAN IP Example |
|---|---|---|---|---|
| **Rescue-A** | `127.0.0.1` | `50010` | `51010` | `192.168.1.101:50010` |
| **Relay-B** | `127.0.0.1` | `50011` | `51011` | `192.168.1.102:50011` |
| **Relay-C** | `127.0.0.1` | `50012` | `51012` | `192.168.1.103:50012` |
| **Relay-D** | `127.0.0.1` | `50013` | `51013` | `192.168.1.104:50013` |
| **Hospital-H** | `127.0.0.1` | `50014` | `51014` | `192.168.1.105:50014` |
| **Dashboard Event Bridge** | `127.0.0.1` | `50099` | N/A | Localhost only |

---

## 3. Wire Format Schema (JSON Payload)

Every inter-node datagram on ports `50010`–`50014` adheres to the strict wire format defined in `resqnet.backend.app.serialization.packet_serializer`:

```json
{
  "version": 1,
  "packet_id": "c6a3a7c9-e514-4779-bb18-7590ac0ea5a1",
  "packet_type": "DATA | RREQ | RREP | RERR | HELLO",
  "source_id": "A",
  "destination_id": "H",
  "sender_id": "A",
  "hop_count": 0,
  "ttl": 64,
  "status": "IN_TRANSIT",
  "current_node": "A",
  "route_history": ["A"],
  "payload": { ... }
}
```

### Specific Payloads:
- **RREQ**: `{"broadcast_id": 1, "destination_id": "H", "destination_sequence_number": 0, "hop_count": 0, "source_id": "A", "source_sequence_number": 1}`
- **RREP**: `{"destination_id": "H", "destination_sequence_number": 1, "hop_count": 0, "originator_id": "A"}`
- **RERR**: `{"unreachable_destinations": ["H"]}`
- **HELLO**: `{"msg": "HELLO"}`
- **DATA (SOS)**: `{"latitude": 18.5204, "longitude": 73.8567, "message": "HELP REQUIRED", "message_id": "c7156565-...", "priority": "HIGH", "type": "sos"}`

---

## 4. Prerequisites

1. **Wireshark Installation**: Download and install Wireshark 4.x from [wireshark.org](https://www.wireshark.org/).
2. **Npcap Driver (Windows)**:
   - During Wireshark installation on Windows, ensure **Npcap** is installed.
   - Check the option: **"Support raw 802.11 traffic (and loopback traffic)"** and **"Install Npcap in WinPcap API-compatible Mode"**.
3. **Capture Interface Identification**:
   - **Localhost Testing**: Select the **`Npcap Loopback Adapter`** (labeled `Adapter for loopback traffic capture` on Windows, or `lo` / `lo0` on Linux/macOS).
   - **Physical LAN Testing**: Select the active network adapter connected to the shared subnet (e.g. `Wi-Fi` or `Ethernet`).
4. **Permissions**: Ensure your user has administrative privileges to capture packets on the selected interface.

---

## 5. Step-by-Step Packet Capture Procedure

Follow these exact steps to capture and validate live packet traces:

### Step 1: Initialize Wireshark
1. Launch Wireshark.
2. In the interface list on the home screen, double-click **`Npcap Loopback Adapter`** (or your active network interface).
3. Confirm that the packet list begins scrolling (capturing).

### Step 2: Set Display Filter
In the top Wireshark filter bar, type:
```text
udp.port in {50010..50014}
```
Press **Enter**. The filter bar will turn green. This isolates the inter-node mesh packets and ignores unrelated OS background traffic.

### Step 3: Run the Demonstration
Open a terminal in the ResQNet repository root and run:
```bash
python scripts/run_demo.py
```

### Step 4: Observe Live Protocol Progression
Watch Wireshark capture the packets in real time:

1. **Initialization (~3s)**:
   - Observe periodic UDP packets with `packet_type: "HELLO"` exchanged between neighbors (e.g., port 50010 ↔ 50011, 50011 ↔ 50012).
2. **Initial Route Discovery**:
   - Node A (`50010`) transmits an `RREQ` to Relay B (`50011`) and Relay D (`50013`).
   - RREQ propagates across B to C (`50012`), and C forward to Hospital H (`50014`).
   - Hospital H (`50014`) returns an `RREP` unicast to C, then B, then A.
3. **First SOS Delivery**:
   - Node A transmits a `DATA` packet containing `"HELP REQUIRED"` directed to next-hop B (`50011`).
   - Relay B forwards to C (`50012`), and C forwards to H (`50014`).
4. **Failure Injection & Invalidation**:
   - Relay B process terminates. `HELLO` beacons from port `50011` cease.
   - After 3.0 seconds, nodes A and C timeout on B.
   - Nodes A and C emit `RERR` packets invalidating routes traversing B.
5. **Route Recovery**:
   - Node A initiates a fresh `RREQ`.
   - RREQ propagates through remaining neighbor Relay D (`50013`).
   - Relay D forwards to C (`50012`), and C to H (`50014`).
   - Hospital H returns `RREP` via D back to A.
   - Second SOS `DATA` packet (`"HELP REQUIRED (RECOVERED)"`) travels along `A → D → C → H`.

### Step 5: Stop and Save Capture
1. In Wireshark, click the red square button (**Stop capturing packets**) or press `Ctrl + E`.
2. Save the capture: Click **File → Save As...**.
3. Choose destination: `artifacts/wireshark/resqnet_local_demo.pcapng`.

---

## 6. Recommended Wireshark Display Filters

| Filter Purpose | Wireshark Display Filter String | Notes |
|---|---|---|
| **All Node Mesh Traffic** | `udp.port in {50010..50014}` | Captures all inter-node AODV & DATA packets. |
| **Initial Route Discovery (RREQ/RREP)** | `udp.port in {50010..50014} && (frame contains "RREQ" \|\| frame contains "RREP")` | Shows path establishment packets only. |
| **Failure Notification (RERR)** | `udp.port in {50010..50014} && frame contains "RERR"` | Isolates route error notifications upon link break. |
| **Emergency SOS Data Packets** | `udp.port in {50010..50014} && frame contains "HELP REQUIRED"` | Follows end-to-end SOS distress payloads. |
| **Neighbor HELLO Heartbeats** | `udp.port in {50010..50014} && frame contains "HELLO"` | Displays continuous liveness beacons. |
| **Node Control Commands** | `udp.port in {51010..51014}` | Shows IPC commands sent to node processes. |
| **Dashboard Event Telemetry** | `udp.port == 50099` | Shows structured JSON events pushed to WebSockets. |
| **Comprehensive ResQNet Capture** | `udp.port in {50010..50014, 51010..51014, 50099}` | Shows mesh, control, and event bridge traffic together. |

---

## 7. Expected Evidence & Verification Matrix

| Protocol Message / Event | Expected Packet Content & Endpoints | Verification Method in Wireshark | Result / Status |
|---|---|---|---|
| **Neighbor Liveness (HELLO)** | UDP datagram with `packet_type: "HELLO"`, `ttl: 1`. Exchanged between adjacent neighbor ports (e.g. `50010` ↔ `50011`). | Filter: `frame contains "HELLO"`. Inspect `payload.msg == "HELLO"`. | **PASS** (Code & Runtime Verified) |
| **Initial Route Request (RREQ)** | UDP datagram from `50010` (A) to `50011` (B) and `50013` (D). `source_id: "A"`, `destination_id: "H"`. | Filter: `frame contains "RREQ"`. Check `source_sequence_number` and `broadcast_id`. | **PASS** (Code & Runtime Verified) |
| **Initial Route Reply (RREP)** | UDP datagram from `50014` (H) to `50012` (C), forwarded to `50011` (B), then `50010` (A). | Filter: `frame contains "RREP"`. Check `originator_id: "A"`, `destination_id: "H"`. | **PASS** (Code & Runtime Verified) |
| **First SOS DATA Packet** | UDP datagram traveling `50010 → 50011 → 50012 → 50014`. Payload: `"HELP REQUIRED"`. | Filter: `frame contains "HELP REQUIRED"`. Observe sequence of 3 hop datagrams. | **PASS** (Code & Runtime Verified) |
| **Node Failure (B Down)** | Node B process terminates. Absence of UDP packets from port `50011`. | Time gap > 3.0s with zero datagrams from port `50011`. | **PASS** (Code & Runtime Verified) |
| **Route Error (RERR)** | UDP datagram emitted by Node C and Node A invalidating routes via B. | Filter: `frame contains "RERR"`. Check `unreachable_destinations`. | **PASS** (Code & Runtime Verified) |
| **Alternate Route RREQ/RREP** | Fresh RREQ from `50010` reaching `50013` (D) → `50012` (C) → `50014` (H). RREP returns along `H → C → D → A`. | Filter: `frame contains "RREQ" && udp.dstport == 50013`. | **PASS** (Code & Runtime Verified) |
| **Second SOS DATA Packet** | UDP datagram traveling `50010 → 50013 → 50012 → 50014`. Payload: `"HELP REQUIRED (RECOVERED)"`. | Filter: `frame contains "RECOVERED"`. Observe hops through port 50013 (D), not 50011 (B). | **PASS** (Code & Runtime Verified) |

---

## 8. Execution Results & Limitations Status

| Verification Scope | Status | Explanation |
|---|---|---|
| **Code & Filter Inspection** | **PASS** | Validated ports (`50010`–`50014`, `51010`–`51014`, `50099`), JSON wire format schemas, and non-blocking UDP socket behavior. |
| **JSON Payload Inspection** | **PASS** | Validated deterministic serialization/deserialization across all 5 packet types in unit tests and live execution. |
| **Initial Route Discovery Evidence** | **PASS** | Verified via multi-process UDP execution; Node A installs forward route to H via B upon RREP receipt. |
| **Failure & Alternate-Route Evidence** | **PASS** | Verified via multi-process UDP execution; Relay B failure triggers timeout and automated recovery through Relay D. |
| **Actual Localhost Wireshark Capture** | **NOT EXECUTED** | Wireshark and Npcap CLI utilities (`tshark`, `dumpcap`) are not installed in the automated environment. Detailed manual procedure documented above. |
| **Physical Multi-Device LAN Capture** | **NOT EXECUTED** | Requires physical deployment across 5 separate laptops on an unisolated Wi-Fi subnet. Marked as `DOCUMENTED — PHYSICAL EXECUTION PENDING`. |

---

## 9. Troubleshooting & Diagnostics

1. **Empty Capture on Localhost**:
   - *Cause*: Captured on regular Wi-Fi or Ethernet adapter instead of loopback. Windows routing does not send `127.0.0.1` traffic through physical network cards.
   - *Fix*: Select the **`Npcap Loopback Adapter`** in Wireshark.
2. **Missing `Npcap Loopback Adapter` in Wireshark**:
   - *Cause*: Npcap was installed without loopback support.
   - *Fix*: Re-run the Npcap installer and check the box **"Support loopback traffic"**.
3. **Packets Displayed as "Malformed Packet"**:
   - *Cause*: Wireshark has port `50010` accidentally assigned to another protocol dissector (e.g. SIP, RTP).
   - *Fix*: Right-click packet → **Decode As...** → Set Current to **`None`** or **`Data`**.
4. **Port Unreachable Warnings (ICMP)**:
   - *Cause*: A node sent a packet to a neighbor process that was just stopped.
   - *Explanation*: Normal UDP behavior on Windows. Handled gracefully in `UDPTransport` (ignores `WSAECONNRESET` / error 10054).
5. **Cannot Distinguish Mesh Traffic from Control Traffic**:
   - *Cause*: Broad filter `udp`.
   - *Fix*: Use specific filter `udp.port in {50010..50014}` to view mesh communication only.
