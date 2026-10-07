# ResQNet LAN Deployment

## 1. LAN Architecture
ResQNet has evolved from a single-process simulation into a true multi-machine deployment capable of operating over physical IP networks (Wi-Fi or Ethernet) using UDP.
Each logical node (`A`, `B`, `C`, `D`, `H`) runs as an independent Python process, potentially on entirely different physical laptops, securely exchanging real serialized AODV packets.

## 2. Logical Node IDs vs. Physical IP Endpoints
ResQNet strongly decouples logical identity from physical addressing:
- **Logical Node IDs**: (e.g., `A`, `B`) used strictly by AODV for routing and topology tracking.
- **Physical Endpoints**: (e.g., `192.168.1.101:50010`) used strictly by `UDPTransport` to dispatch packets via the OS socket API.

## 3. Configuration
Endpoints are configured via JSON files. Nodes must be mapped to valid `host` and `port` addresses representing their true location on the LAN.

Example `configs/lan_nodes.json`:
```json
{
  "A": { "host": "192.168.1.101", "port": 50010 },
  "B": { "host": "192.168.1.102", "port": 50011 }
}
```

## 4. Bind Address vs. Destination Address
When launching a node, the application allows configuration of the **bind address** (the local interface to listen on). 
- **Bind Address:** Normally `0.0.0.0` to listen on all interfaces (or a specific LAN interface IP).
- **Destination Address:** The `host` defined in the configuration, indicating where UDP packets intended for this node should be physically sent.

## 5. Startup Procedure
To run a node on a physical machine:
```bash
python scripts/run_node.py --node-id A --config configs/lan_nodes.json --bind-host 0.0.0.0
```

## 6. Neighbor Health and Failure Recovery
Neighbors automatically exchange `HELLO` packets (TTL=1) via UDP. If a node physical stops or a Wi-Fi connection breaks, missing `HELLO` packets trigger a timeout.
The `NeighborHealthMonitor` will mark the neighbor as `DOWN`, invalidate local routes traversing that neighbor, and the `AODVRouter` will automatically spawn `RERR` packets and discover alternate paths via remaining healthy nodes.

## 7. Firewall and Wi-Fi Restrictions
- **Firewall:** Windows Defender or Linux firewalls must permit **Inbound UDP** traffic for the configured ports (e.g., 50010-50014).
- **Wi-Fi Client Isolation:** Public or corporate Wi-Fi networks often prevent devices from communicating directly with each other (AP/Client Isolation). ResQNet requires a network that permits direct peer-to-peer IP communication. Use a private hotspot if necessary.

## 8. Limitations
- Automatic network scanning (broadcast discovery) is out of scope; explicitly mapping nodes in JSON guarantees deterministic routing behavior for demonstration.
- Dashboard integration (React UI connected to multi-machine deployment) is deferred to Phase 4.8.
- ResQNet uses UDP/IP; it is not building a custom physical-layer radio mesh. It demonstrates AODV logical routing over IP.
