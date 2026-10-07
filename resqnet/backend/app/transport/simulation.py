from typing import List, Callable, Optional
from resqnet.backend.app.transport.base import BaseTransport
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.packet import Packet, PacketStatus

class SimulationTransport(BaseTransport):
    """
    Simulates packet delivery by instantly moving the packet to the next hop
    if the topology dictates that they are valid, active neighbors.
    """
    def __init__(self, topology: NetworkTopology, event_logger: Optional[Callable] = None):
        super().__init__()
        self.topology = topology
        self.event_logger = event_logger

    def send(self, packet: Packet, next_hops: List[str]) -> bool:
        if not self.is_running:
            return False

        current = packet.current_node
        current_node_obj = self.topology.get_node_by_id(current)
        
        if not current_node_obj:
            return False

        active_neighbors = self.topology.get_active_neighbors(current_node_obj.ip_address)
        active_neighbor_ids = [n.node_id for n in active_neighbors]
        
        valid_next_hops = [hop for hop in next_hops if hop in active_neighbor_ids]
        
        if not valid_next_hops:
            return False

        original_packet = packet.clone()
        
        for i, hop in enumerate(valid_next_hops):
            # For the last hop, we can use the original packet to avoid an extra clone
            out_packet = packet if i == len(valid_next_hops) - 1 else original_packet.clone()
            
            # Replicate exact logging behavior from SimulationEngine
            if self.event_logger:
                if out_packet.packet_type.name == "RREQ":
                    self.event_logger(f"RREQ_BROADCAST {current} -> {hop}", out_packet)
                else:
                    self.event_logger(f"FORWARD {current} -> {hop}", out_packet)
                    
            out_packet.sender_id = current
            out_packet.move_to(hop)
            
            if out_packet.status == PacketStatus.DROPPED:
                if self.event_logger:
                    self.event_logger("PACKET_DROPPED", out_packet)
            else:
                if self._receive_callback:
                    self._receive_callback(out_packet)

        return True
