import uuid
from enum import Enum, auto

class PacketType(Enum):
    """Types of packets that can flow through the network."""
    DATA = auto()
    # Future AODV types can be added here without redesigning the model
    RREQ = auto()
    RREP = auto()
    RERR = auto()

class PacketStatus(Enum):
    """Lifecycle states of a packet."""
    CREATED = auto()
    IN_TRANSIT = auto()
    DELIVERED = auto()
    DROPPED = auto()
    FAILED = auto()

from typing import Any

class Packet:
    """
    Represents a discrete message/data chunk traveling through the network.
    Records its actual movement across nodes.
    """
    def __init__(self, source_id: str, destination_id: str, payload: Any, packet_type: PacketType = PacketType.DATA, ttl: int = 64):
        if not source_id or not destination_id:
            raise ValueError("Source and destination identifiers must be provided.")
        if packet_type == PacketType.DATA and not payload:
            raise ValueError("Payload cannot be empty for DATA packets.")
        
        self.packet_id = str(uuid.uuid4())
        self.source_id = source_id
        self.destination_id = destination_id
        self.payload = payload
        self.packet_type = packet_type
        
        self.current_node = source_id
        self.sender_id: str | None = None
        self.hop_count = 0
        # Route history strictly records ACTUAL movement, never pre-calculated routes
        self.route_history = [source_id]
        self.status = PacketStatus.CREATED
        self.ttl = ttl

    def move_to(self, next_node_id: str):
        """
        Records the packet physically/logically moving to a new node.
        Updates location, hop count, route history, and TTL.
        """
        if not next_node_id:
            raise ValueError("Next node identifier cannot be empty.")
            
        if self.status in [PacketStatus.DELIVERED, PacketStatus.DROPPED, PacketStatus.FAILED]:
            raise ValueError(f"Cannot move packet with status {self.status.name}")

        self.current_node = next_node_id
        self.hop_count += 1
        self.ttl -= 1
        self.route_history.append(next_node_id)
        
        # If TTL expires, explicitly drop the packet to prevent infinite loops
        if self.ttl <= 0:
            self.status = PacketStatus.DROPPED
        else:
            self.status = PacketStatus.IN_TRANSIT

    def clone(self) -> 'Packet':
        """
        Create a clone of the packet (e.g., for broadcasting).
        The clone has a new packet_id, but retains the same payload, route history, and hop count.
        """
        import copy
        new_packet = Packet(
            source_id=self.source_id,
            destination_id=self.destination_id,
            payload=copy.deepcopy(self.payload),
            packet_type=self.packet_type,
            ttl=self.ttl
        )
        new_packet.current_node = self.current_node
        new_packet.sender_id = self.sender_id
        new_packet.hop_count = self.hop_count
        new_packet.route_history = list(self.route_history)
        new_packet.status = self.status
        return new_packet

    def mark_delivered(self):
        """Mark the packet successfully delivered to its destination."""
        self.status = PacketStatus.DELIVERED

    def mark_dropped(self):
        """Mark the packet dropped (e.g. queue full, route lost)."""
        self.status = PacketStatus.DROPPED

    def mark_failed(self):
        """Mark the packet as completely failed."""
        self.status = PacketStatus.FAILED

    def __repr__(self) -> str:
        return f"Packet({self.packet_type.name}, {self.source_id} -> {self.destination_id}, curr={self.current_node}, hops={self.hop_count}, stat={self.status.name})"
