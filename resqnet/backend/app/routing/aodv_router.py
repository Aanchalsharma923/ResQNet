from typing import Optional, Set, Tuple

from resqnet.backend.app.routing.base import BaseRouter
from resqnet.backend.app.routing.table import RoutingTable
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.packet import Packet


class AODVRouter(BaseRouter):
    """
    Genuine AODV router implementation.
    Discovers routes on-demand using RREQ/RREP propagation.
    """
    def __init__(self, node_id: str, topology: NetworkTopology):
        super().__init__(node_id, topology)
        self.routing_table = RoutingTable()
        
        # AODV protocol state
        self.node_sequence_number: int = 1
        self.broadcast_id_counter: int = 0
        
        # Cache for duplicate RREQ detection (source_id, broadcast_id)
        self.seen_rreqs: Set[Tuple[str, int]] = set()

    def get_next_hop(self, destination_id: str) -> Optional[str]:
        """
        Consult the routing table for the next hop.
        Returns None if no valid route exists.
        """
        route = self.routing_table.get_route(destination_id)
        if route and route.is_valid:
            return route.next_hop
        return None

    def has_valid_route(self, destination_id: str) -> bool:
        """
        Check if a valid route to the destination exists.
        """
        return self.get_next_hop(destination_id) is not None

    def increment_sequence_number(self) -> int:
        """
        Increment and return the node's sequence number.
        """
        self.node_sequence_number += 1
        return self.node_sequence_number

    def get_next_broadcast_id(self) -> int:
        """
        Increment and return the next broadcast ID for a new RREQ.
        """
        self.broadcast_id_counter += 1
        return self.broadcast_id_counter

    def has_seen_rreq(self, source_id: str, broadcast_id: int) -> bool:
        """
        Check if an RREQ identity has already been processed.
        """
        return (source_id, broadcast_id) in self.seen_rreqs

    def record_rreq(self, source_id: str, broadcast_id: int):
        """
        Record an RREQ identity to prevent processing duplicates.
        """
        self.seen_rreqs.add((source_id, broadcast_id))

    def handle_packet(self, packet: Packet) -> list[str]:
        """
        Process an incoming packet and determine where it should be forwarded.
        """
        if packet.packet_type.name == "RREQ":
            return self._handle_rreq(packet)
        elif packet.packet_type.name == "RREP":
            return self._handle_rrep(packet)
        else:
            # Data packets use normal unicast forwarding
            next_hop = self.get_next_hop(packet.destination_id)
            if next_hop:
                return [next_hop]
            return []

    def _handle_rreq(self, packet: Packet) -> list[str]:
        from resqnet.backend.app.models.aodv_payloads import RREQPayload, RREPPayload
        from resqnet.backend.app.models.packet import PacketType
        
        payload: RREQPayload = packet.payload
        
        # 1. Duplicate detection
        if self.has_seen_rreq(payload.source_id, payload.broadcast_id):
            is_source_initiation = (self.node_id == payload.source_id and packet.hop_count == 0)
            if not is_source_initiation:
                return []
            
        # 2. Record it to prevent future duplicates
        self.record_rreq(payload.source_id, payload.broadcast_id)
        
        # 3. Setup reverse route to the source
        prev_hop = packet.route_history[-2] if len(packet.route_history) >= 2 else None
        
        if prev_hop:
            self.routing_table.add_or_update_route(
                destination_id=payload.source_id,
                next_hop=prev_hop,
                sequence_number=payload.source_sequence_number,
                hop_count=payload.hop_count + 1
            )
            
        # 4. Check if we are the destination
        if self.node_id == payload.destination_id:
            # Generate RREP
            self.node_sequence_number = max(self.node_sequence_number, payload.destination_sequence_number)
            
            rrep_payload = RREPPayload(
                destination_id=self.node_id,
                destination_sequence_number=self.node_sequence_number,
                originator_id=payload.source_id,
                hop_count=0
            )
            
            rrep_packet = Packet(
                source_id=self.node_id,
                destination_id=payload.source_id,
                payload=rrep_payload,
                packet_type=PacketType.RREP
            )
            
            self.generated_packets.append(rrep_packet)
            return []
            
        # 5. Increment RREQ protocol hop count (only at intermediate nodes)
        if self.node_id != payload.source_id:
            payload.hop_count += 1
            
        # 6. Broadcast to all active neighbors (excluding the one we just received it from)
        my_node = self.topology.get_node_by_id(self.node_id)
        active_neighbors = self.topology.get_active_neighbors(my_node.ip_address)
        
        next_hops = []
        for neighbor in active_neighbors:
            if neighbor.node_id != prev_hop:
                next_hops.append(neighbor.node_id)
                
        return next_hops

    def _handle_rrep(self, packet: Packet) -> list[str]:
        from resqnet.backend.app.models.aodv_payloads import RREPPayload
        payload: RREPPayload = packet.payload
        
        # 1. Setup forward route to the destination
        prev_hop = packet.route_history[-2] if len(packet.route_history) >= 2 else None
        
        if prev_hop:
            self.routing_table.add_or_update_route(
                destination_id=payload.destination_id,
                next_hop=prev_hop,
                sequence_number=payload.destination_sequence_number,
                hop_count=payload.hop_count + 1
            )
            
        # 2. Check if we are the RREQ source (RREP destination)
        if self.node_id == payload.originator_id:
            return []
            
        # 3. Increment RREP hop count (only at intermediate nodes)
        if self.node_id != payload.destination_id:
            payload.hop_count += 1
        
        # 4. Forward RREP along the reverse route back to the source
        next_hop = self.get_next_hop(payload.originator_id)
        if next_hop:
            return [next_hop]
            
        return []

    def initiate_route_discovery(self, destination_id: str) -> Packet:
        """
        Trigger AODV Route Discovery by generating an RREQ packet.
        Returns the generated RREQ Packet.
        """
        self.increment_sequence_number()
        broadcast_id = self.get_next_broadcast_id()
        
        # Record our own RREQ to prevent processing it if it loops back
        self.record_rreq(self.node_id, broadcast_id)
        
        from resqnet.backend.app.models.aodv_payloads import RREQPayload
        from resqnet.backend.app.models.packet import PacketType
        
        payload = RREQPayload(
            source_id=self.node_id,
            destination_id=destination_id,
            source_sequence_number=self.node_sequence_number,
            destination_sequence_number=0, # Unknown sequence number for destination initially
            broadcast_id=broadcast_id,
            hop_count=0
        )
        
        packet = Packet(
            source_id=self.node_id,
            destination_id=destination_id,
            payload=payload,
            packet_type=PacketType.RREQ
        )
        
        return packet
