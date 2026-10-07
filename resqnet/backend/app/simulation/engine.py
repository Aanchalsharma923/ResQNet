from typing import Dict, List, Optional
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.packet import Packet, PacketStatus
from resqnet.backend.app.routing.base import BaseRouter
from resqnet.backend.app.transport.base import BaseTransport

class SimulationEngine:
    """
    Executes hop-by-hop packet forwarding through the topology.
    Coordinates between Packets, Topology, Routers, and Transport.
    """
    def __init__(self, topology: NetworkTopology, routers: Dict[str, BaseRouter], transport: Optional[BaseTransport] = None):
        """
        topology: The central NetworkTopology containing nodes and links.
        routers: A mapping from node_id to its corresponding BaseRouter instance.
        transport: The transport layer mechanism. Defaults to SimulationTransport if None.
        """
        self.topology = topology
        self.routers = routers
        self.events: List[str] = []
        self.pending_messages: List[Packet] = []
        
        if transport is None:
            from resqnet.backend.app.transport.simulation import SimulationTransport
            self.transport = SimulationTransport(topology, event_logger=self._log_event)
        else:
            self.transport = transport
            
        self.transport.set_receive_callback(self._on_packet_received_from_transport)
        self.transport.start()

    def _on_packet_received_from_transport(self, packet: Packet):
        self.pending_messages.append(packet)

    def _log_event(self, event: str, packet: Packet = None):
        self.events.append(event)
        if hasattr(self, 'event_callback') and self.event_callback:
            self.event_callback(event, packet)
        
    def send_packet(self, packet: Packet):
        """
        Simulates the journey of a packet from its current_node to its destination_id.
        Adds to pending messages queue and processes until empty.
        """
        self._log_event("PACKET_CREATED", packet)
        if packet.packet_type.name == "RREQ":
            self._log_event("RREQ_CREATED", packet)
            
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
                self._log_event("PACKET_DELIVERED", packet)
                return
            elif packet.packet_type.name == "RREQ":
                packet.mark_delivered()
                self._log_event("RREQ_REACHED_DESTINATION", packet)
                # AODV routers need to process the RREQ to install reverse routes
                # and generate RREPs.
                pass
                
        # 2. Determine the router for the current node
        router = self.routers.get(current)
        if not router:
            packet.mark_dropped()
            self._log_event("PACKET_DROPPED", packet)
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
                self._log_event(event, packet)
            router.events.clear()
            
        if not next_hops:
            if packet.status not in [PacketStatus.DELIVERED, PacketStatus.DROPPED, PacketStatus.FAILED]:
                packet.mark_dropped()
                # For static router tests compatibility
                if packet.packet_type.name not in ["RREQ", "RERR"]:
                    self._log_event("NEXT_HOP_UNAVAILABLE", packet)
                self._log_event("PACKET_DROPPED", packet)
            return
            
        # 4 & 5. Use Transport to send the packet to next_hops
        success = self.transport.send(packet, next_hops)
        
        if not success:
            packet.mark_dropped()
            if packet.packet_type.name not in ["RREQ", "RERR"]:
                self._log_event("NEXT_HOP_UNAVAILABLE", packet)
            self._log_event("PACKET_DROPPED", packet)
            return
