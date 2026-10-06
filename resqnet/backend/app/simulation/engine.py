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
        self.pending_messages: List[Packet] = []

    def _log_event(self, event: str):
        self.events.append(event)
        
    def send_packet(self, packet: Packet):
        """
        Simulates the journey of a packet from its current_node to its destination_id.
        Adds to pending messages queue and processes until empty.
        """
        self._log_event("PACKET_CREATED")
        if packet.packet_type.name == "RREQ":
            self._log_event("RREQ_CREATED")
            
        self.pending_messages.append(packet)
        self._process_queue()

    def _process_queue(self):
        """
        Process all pending messages until the queue is empty.
        """
        while self.pending_messages:
            packet = self.pending_messages.pop(0)
            self._process_packet(packet)

    def _process_packet(self, packet: Packet):
        """
        Process a single packet at its current node.
        """
        current = packet.current_node
        
        # 1. Check if destination is reached (but still process it via router for control packets)
        if current == packet.destination_id:
            if packet.packet_type.name == "DATA":
                packet.mark_delivered()
                self._log_event("PACKET_DELIVERED")
                return
            elif packet.packet_type.name == "RREQ":
                packet.mark_delivered()
                self._log_event("RREQ_REACHED_DESTINATION")
                # AODV routers need to process the RREQ to install reverse routes
                # and generate RREPs.
                pass
                
        # 2. Determine the router for the current node
        router = self.routers.get(current)
        if not router:
            packet.mark_dropped()
            self._log_event("PACKET_DROPPED")
            return
            
        # 3. Ask the router for the next hops
        next_hops = router.handle_packet(packet)
        
        # 3.5 Check if the router generated any new packets (e.g., RREP in response to RREQ)
        if hasattr(router, 'generated_packets') and router.generated_packets:
            for new_packet in router.generated_packets:
                self.pending_messages.append(new_packet)
            router.generated_packets.clear()
            
        if hasattr(router, 'events') and router.events:
            for event in router.events:
                self._log_event(event)
            router.events.clear()
            
        if not next_hops:
            if packet.status not in [PacketStatus.DELIVERED, PacketStatus.DROPPED, PacketStatus.FAILED]:
                packet.mark_dropped()
                # For static router tests compatibility
                if packet.packet_type.name not in ["RREQ", "RERR"]:
                    self._log_event("NEXT_HOP_UNAVAILABLE")
                self._log_event("PACKET_DROPPED")
            return
            
        # 4. Verify that the next hops are active neighbors in NetworkTopology
        current_node_obj = self.topology.get_node_by_id(current)
        active_neighbors = self.topology.get_active_neighbors(current_node_obj.ip_address)
        active_neighbor_ids = [n.node_id for n in active_neighbors]
        
        valid_next_hops = [hop for hop in next_hops if hop in active_neighbor_ids]
        
        if not valid_next_hops:
            packet.mark_dropped()
            if packet.packet_type.name not in ["RREQ", "RERR"]:
                self._log_event("NEXT_HOP_UNAVAILABLE")
            self._log_event("PACKET_DROPPED")
            return
            
        # 5. Move the packet to those nodes
        original_packet = packet.clone() # Keep a pristine copy if we need to modify packet
        
        for i, hop in enumerate(valid_next_hops):
            # For the last hop, we can just use the original packet to avoid an extra clone
            out_packet = packet if i == len(valid_next_hops) - 1 else original_packet.clone()
            
            if out_packet.packet_type.name == "RREQ":
                self._log_event(f"RREQ_BROADCAST {current} -> {hop}")
            else:
                self._log_event(f"FORWARD {current} -> {hop}")
                
            out_packet.move_to(hop)
            
            if out_packet.status == PacketStatus.DROPPED:
                self._log_event("PACKET_DROPPED")
            else:
                self.pending_messages.append(out_packet)
