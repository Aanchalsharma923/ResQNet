from typing import Dict, List
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.packet import Packet, PacketStatus
from resqnet.backend.app.routing.base import BaseRouter

class SimulationEngine:
    """
    Executes hop-by-hop packet forwarding through the topology.
    Coordinates between Packets, Topology, and Routers.
    """
    def __init__(self, topology: NetworkTopology, routers: Dict[str, BaseRouter]):
        """
        topology: The central NetworkTopology containing nodes and links.
        routers: A mapping from node_id to its corresponding BaseRouter instance.
        """
        self.topology = topology
        self.routers = routers
        self.events: List[str] = []

    def _log_event(self, event: str):
        self.events.append(event)
        
    def send_packet(self, packet: Packet):
        """
        Simulates the journey of a packet from its current_node to its destination_id.
        Continues forwarding until DELIVERED, DROPPED, or FAILED.
        """
        self._log_event("PACKET_CREATED")
        
        # If already at destination
        if packet.current_node == packet.destination_id:
            packet.mark_delivered()
            self._log_event("PACKET_DELIVERED")
            return
            
        while True:
            current = packet.current_node
            
            # 1. Determine the router for the current node
            router = self.routers.get(current)
            if not router:
                packet.mark_dropped()
                self._log_event("PACKET_DROPPED")
                break
                
            # 2. Ask the router for the next hop
            next_hop = router.get_next_hop(packet.destination_id)
            if not next_hop:
                packet.mark_dropped()
                self._log_event("NEXT_HOP_UNAVAILABLE")
                self._log_event("PACKET_DROPPED")
                break
                
            # 3. Verify that the next hop is an active neighbor in NetworkTopology
            current_node_obj = self.topology.get_node_by_id(current)
            active_neighbors = self.topology.get_active_neighbors(current_node_obj.ip_address)
            
            if not any(neighbor.node_id == next_hop for neighbor in active_neighbors):
                packet.mark_dropped()
                self._log_event("NEXT_HOP_UNAVAILABLE")
                self._log_event("PACKET_DROPPED")
                break
                
            # 4. Move the packet to that node
            self._log_event(f"FORWARD {current} -> {next_hop}")
            packet.move_to(next_hop)
            
            # Respect TTL behavior
            if packet.status == PacketStatus.DROPPED:
                self._log_event("PACKET_DROPPED")
                break
                
            # Stop forwarding if destination is reached
            if packet.current_node == packet.destination_id:
                packet.mark_delivered()
                self._log_event("PACKET_DELIVERED")
                break
