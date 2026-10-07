# Real UDP Transport (Phase 4.3)

## 1. Why UDP is Introduced
Previously, ResQNet utilized a `SimulationTransport` where packets moved logically between nodes by instantly resolving direct memory references based on a central mock `NetworkTopology`. 
To transform ResQNet into a real-world mesh networking application, packets must be physically transmitted across actual network interfaces. The `UDPTransport` encapsulates standard User Datagram Protocol (UDP) sockets to transmit our custom AODV and DATA packets using real OS-level networking. 

## 2. Simulation vs Real Networking
- **Simulation**: Node A directly checks if Link(A,B) is active via central state and immediately executes `packet.move_to(B)`.
- **Real Networking**: Node A serializes the `Packet`, looks up the mapped UDP Endpoint for Node B, sends a datagram over the real `127.0.0.1` network stack, and B asynchronously receives and deserializes the datagram before feeding it to its routing brain.

## 3. UDPTransport Responsibility
The `UDPTransport` strictly implements the `BaseTransport` interface. It is exclusively responsible for delivering packets directly to endpoints designated by the routing engine.
- **It DOES NOT** calculate routes.
- **It DOES NOT** parse the topology.
- **It DOES NOT** know about routing tables or AODV logic.

## 4. Node Endpoint Mapping
Each logical ResQNet `node_id` is mapped explicitly to a UDP address/port via an `endpoint_config` dictionary injected during transport initialization.
```python
endpoint_config = {
    "A": ("127.0.0.1", 50010),
    "B": ("127.0.0.1", 50011)
}
```

## 5. Packet Send Flow
1. AODV determines the physical next-hop (e.g. `B`).
2. AODV passes `send(packet, ["B"])` to the `UDPTransport`.
3. Transport invokes `serialize_packet(packet)`.
4. Transport checks `endpoint_config` for `B`.
5. Transport executes `socket.sendto(bytes, ("127.0.0.1", 50011))`.

## 6. Packet Receive Flow
1. `UDPTransport` background thread executes `socket.recvfrom()`.
2. Raw bytes are captured.
3. Transport invokes `deserialize_packet(bytes)`.
4. The exact `Packet` object is recovered, crucially preserving `sender_id`.
5. Transport passes `Packet` up to AODV via the `_receive_callback`.

## 7. Socket Lifecycle
- **start()**: Opens an `AF_INET`, `SOCK_DGRAM` socket. Binds to the designated port. Spins up a `_receive_thread` to asynchronously drain datagrams.
- **stop()**: Flips running flag, joins the thread, and explicitly closes the OS socket preventing orphaned ports and thread leaks.

## 8. Failure Semantics
- A malformed datagram strictly catches `ValueError` parsing exceptions, logs a warning, drops the garbage data, and safely keeps listening. It will not crash the node.
- A `sendto()` attempting to reach a stopped endpoint will logically succeed from the transport's perspective (fire and forget), but the packet will be physically lost, identically mirroring actual WiFi/Radio characteristics.

## 9. Why UDP Send != Guaranteed Delivery
Executing `socket.sendto` successfully guarantees only that the host OS accepted the buffer. It guarantees nothing about destination reachability, application status, or successful deserialization. AODV remains the authoritative layer for tracking lost links (via RREQ timeouts, or future heartbeat mechanisms) and establishing end-to-end reliability.

## 10. Current Localhost Limitations
Currently, all UDP tests and nodes target `127.0.0.1` (localhost). They are independent UDP bindings on different ports simulating multiple devices.

## 11. Future LAN Usage
By modifying `endpoint_config`, UDP transports can natively dispatch across physical boundaries (e.g., Laptop A `192.168.1.10:50000` → Laptop B `192.168.1.20:50000`).

## 12. Why AODV Remains Separate
Preserving the AODV routing brain separately from Transport allows identical routing logic to be verified instantly using `SimulationTransport` and organically executed on real networks via `UDPTransport` without divergence.

## 13. Neighbor Health is Deferred (Phase 4.6)
We do not currently detect broken links purely from UDP errors. In Phase 4.6, explicit UDP Hello/Heartbeat messages will be established to declare links DEAD and trigger local AODV `RERR` packets organically. Until then, `UDPTransport` silently drops packets for broken physical connections, and AODV fails out on initial requests.
