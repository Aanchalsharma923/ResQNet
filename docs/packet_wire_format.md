# Packet Wire Format & Serialization

This document describes the canonical wire format used to transmit ResQNet packets over physical/logical transports (Phase 4.2+).

## 1. Why Serialization is Needed
Prior to Phase 4.2, packets were passed by reference as Python objects entirely within the memory of the `SimulationEngine`. To allow ResQNet to operate over real network transports (like UDP sockets in Phase 4.3), packets must be serialized into a transport-independent, deterministic byte stream. This ensures boundaries between nodes strictly represent real network conditions without shared memory.

## 2. Packet Wire Format
We utilize JSON as the canonical wire format for simplicity, human-readability during demonstrations, and ease of debugging.
A serialized packet contains enough explicit state to reconstruct the original `Packet` object completely, without relying on external context, simulation state, or global topology knowledge.

### Generic Packet Structure
```json
{
  "version": 1,
  "packet_id": "uuid-string",
  "packet_type": "DATA | RREQ | RREP | RERR",
  "source_id": "string",
  "destination_id": "string",
  "sender_id": "string (the node that transmitted this specific hop)",
  "hop_count": 0,
  "ttl": 64,
  "status": "CREATED | IN_TRANSIT | DELIVERED | DROPPED | FAILED",
  "current_node": "string",
  "route_history": ["string", "..."],
  "payload": { ... }
}
```

## 3. Example Packet Types

### DATA Packet
Carries the actual application payload (e.g., SOS JSON).
```json
{
  "version": 1,
  "packet_id": "550e8400-e29b-41d4-a716-446655440000",
  "packet_type": "DATA",
  "source_id": "A",
  "destination_id": "H",
  "sender_id": "B",
  "hop_count": 2,
  "ttl": 62,
  "status": "IN_TRANSIT",
  "current_node": "C",
  "route_history": ["A", "B", "C"],
  "payload": {
    "msg": "Emergency SOS from A",
    "lat": 10.0,
    "priority": "HIGH"
  }
}
```

### RREQ (Route Request)
```json
{
  "version": 1,
  "packet_id": "123e4567-e89b-12d3-a456-426614174000",
  "packet_type": "RREQ",
  "source_id": "A",
  "destination_id": "H",
  "sender_id": "A",
  "hop_count": 0,
  "ttl": 64,
  "status": "IN_TRANSIT",
  "current_node": "A",
  "route_history": ["A"],
  "payload": {
    "source_id": "A",
    "destination_id": "H",
    "source_sequence_number": 2,
    "destination_sequence_number": 0,
    "broadcast_id": 1,
    "hop_count": 0
  }
}
```

### RREP (Route Reply)
```json
{
  "version": 1,
  "packet_id": "987e6543-e21b-12d3-a456-426614174111",
  "packet_type": "RREP",
  "source_id": "H",
  "destination_id": "A",
  "sender_id": "H",
  "hop_count": 0,
  "ttl": 64,
  "status": "IN_TRANSIT",
  "current_node": "H",
  "route_history": ["H"],
  "payload": {
    "destination_id": "H",
    "destination_sequence_number": 1,
    "originator_id": "A",
    "hop_count": 0
  }
}
```

### RERR (Route Error)
```json
{
  "version": 1,
  "packet_id": "111e6543-e21b-12d3-a456-426614174222",
  "packet_type": "RERR",
  "source_id": "B",
  "destination_id": "A",
  "sender_id": "B",
  "hop_count": 0,
  "ttl": 64,
  "status": "IN_TRANSIT",
  "current_node": "B",
  "route_history": ["B"],
  "payload": {
    "unreachable_destinations": [
      ["H", 2]
    ]
  }
}
```

## 4. Versioning & Validation Rules
- **Version**: Currently locked to `1`. `deserialize_packet` will reject unsupported versions.
- **Strict Parsing**: Any malformed JSON, missing top-level fields, or incomplete inner payloads will raise explicit `ValueError` exceptions immediately during deserialization.
- **Untrusted Input**: Deserialization explicitly plucks known fields and avoids executing arbitrary code (e.g., `pickle.loads` or `eval`), maintaining a strict security boundary for untrusted network input.
- **Sender Identification**: The `sender_id` must survive round-trip serialization identically. AODV and future UDP layers rely precisely on `sender_id` to determine the adjacent peer. Reconstructing `sender_id` from history/routing tables is strictly forbidden.

## 5. UDP Transport Integration (Phase 4.3)
In Phase 4.3, the architecture will look like this:

1. `AODVRouter` generates `Packet` locally.
2. `UDPTransport` receives `Packet` from the router.
3. `UDPTransport` calls `serialize_packet(packet)` to get `bytes`.
4. `UDPTransport` transmits `bytes` via UDP datagram to the next-hop IP.
5. Receiving `UDPTransport` reads bytes from UDP socket.
6. Receiving `UDPTransport` calls `deserialize_packet(bytes)` to get `Packet`.
7. Receiving `UDPTransport` hands `Packet` to its local `AODVRouter`.

Notice that neither the AODV layer nor the React Dashboard needs to know about this intermediate serialization step. 
Simulation Transport (`SimulationTransport`) may completely bypass serialization in testing or intentionally exercise it for validation.
