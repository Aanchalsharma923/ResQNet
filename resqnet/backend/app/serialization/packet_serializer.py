import json
from typing import Any

from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.models.aodv_payloads import RREQPayload, RREPPayload, RERRPayload

CURRENT_VERSION = 1

def serialize_packet(packet: Packet) -> bytes:
    """
    Serializes a Packet object into a stable JSON byte representation.
    """
    payload_data = None
    
    if packet.packet_type == PacketType.RREQ:
        req: RREQPayload = packet.payload
        payload_data = {
            "source_id": req.source_id,
            "destination_id": req.destination_id,
            "source_sequence_number": req.source_sequence_number,
            "destination_sequence_number": req.destination_sequence_number,
            "broadcast_id": req.broadcast_id,
            "hop_count": req.hop_count
        }
    elif packet.packet_type == PacketType.RREP:
        rep: RREPPayload = packet.payload
        payload_data = {
            "destination_id": rep.destination_id,
            "destination_sequence_number": rep.destination_sequence_number,
            "originator_id": rep.originator_id,
            "hop_count": rep.hop_count
        }
    elif packet.packet_type == PacketType.RERR:
        err: RERRPayload = packet.payload
        payload_data = {
            "unreachable_destinations": err.unreachable_destinations
        }
    elif packet.packet_type == PacketType.DATA:
        # DATA payload is expected to be JSON serializable (dict, string, etc.)
        payload_data = packet.payload
    elif packet.packet_type == PacketType.HELLO:
        payload_data = packet.payload
    else:
        raise ValueError(f"Unknown packet type for serialization: {packet.packet_type}")
        
    wire_dict = {
        "version": CURRENT_VERSION,
        "packet_id": packet.packet_id,
        "packet_type": packet.packet_type.name,
        "source_id": packet.source_id,
        "destination_id": packet.destination_id,
        "sender_id": packet.sender_id,
        "hop_count": packet.hop_count,
        "ttl": packet.ttl,
        "status": packet.status.name,
        "current_node": packet.current_node,
        "route_history": packet.route_history,
        "payload": payload_data
    }
    
    # Sort keys for deterministic output
    return json.dumps(wire_dict, sort_keys=True).encode("utf-8")

def deserialize_packet(data: bytes | str) -> Packet:
    """
    Deserializes a JSON byte/string representation into a Packet object.
    Performs validation on untrusted network input.
    """
    try:
        wire_dict = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON data: {str(e)}")
        
    if not isinstance(wire_dict, dict):
        raise ValueError("Serialized packet must be a JSON object")
        
    version = wire_dict.get("version")
    if version != CURRENT_VERSION:
        raise ValueError(f"Unsupported packet version: {version}")
        
    # Extract basic fields
    try:
        packet_type_str = wire_dict["packet_type"]
        packet_id = wire_dict["packet_id"]
        source_id = wire_dict["source_id"]
        destination_id = wire_dict["destination_id"]
        payload_data = wire_dict["payload"]
    except KeyError as e:
        raise ValueError(f"Missing required field in packet: {e.args[0]}")
        
    try:
        packet_type = PacketType[packet_type_str]
    except KeyError:
        raise ValueError(f"Unknown packet_type: {packet_type_str}")
        
    # Reconstruct payload based on type
    reconstructed_payload: Any = None
    if packet_type == PacketType.RREQ:
        try:
            reconstructed_payload = RREQPayload(
                source_id=payload_data["source_id"],
                destination_id=payload_data["destination_id"],
                source_sequence_number=payload_data["source_sequence_number"],
                destination_sequence_number=payload_data["destination_sequence_number"],
                broadcast_id=payload_data["broadcast_id"],
                hop_count=payload_data["hop_count"]
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Malformed RREQ payload: {str(e)}")
            
    elif packet_type == PacketType.RREP:
        try:
            reconstructed_payload = RREPPayload(
                destination_id=payload_data["destination_id"],
                destination_sequence_number=payload_data["destination_sequence_number"],
                originator_id=payload_data["originator_id"],
                hop_count=payload_data["hop_count"]
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Malformed RREP payload: {str(e)}")
            
    elif packet_type == PacketType.RERR:
        try:
            # Ensure format is correct: list[list[str, int]] which comes back from JSON instead of tuple
            unreachable_destinations = []
            for dest in payload_data["unreachable_destinations"]:
                unreachable_destinations.append((dest[0], dest[1]))
            reconstructed_payload = RERRPayload(
                unreachable_destinations=unreachable_destinations
            )
        except (KeyError, TypeError, ValueError, IndexError) as e:
            raise ValueError(f"Malformed RERR payload: {str(e)}")
            
    elif packet_type == PacketType.DATA or packet_type == PacketType.HELLO:
        reconstructed_payload = payload_data
        
    # Build Packet
    try:
        ttl = wire_dict.get("ttl", 64)
        packet = Packet(
            source_id=source_id,
            destination_id=destination_id,
            payload=reconstructed_payload,
            packet_type=packet_type,
            ttl=ttl
        )
    except ValueError as e:
        raise ValueError(f"Failed to instantiate packet: {str(e)}")
        
    # Restore explicit state exactly as it was
    packet.packet_id = packet_id
    packet.sender_id = wire_dict.get("sender_id")
    packet.hop_count = wire_dict.get("hop_count", 0)
    packet.current_node = wire_dict.get("current_node", source_id)
    packet.route_history = wire_dict.get("route_history", [source_id])
    
    try:
        status_str = wire_dict.get("status", "CREATED")
        packet.status = PacketStatus[status_str]
    except KeyError:
        raise ValueError(f"Unknown status: {wire_dict.get('status')}")
        
    return packet
