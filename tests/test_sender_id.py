import pytest
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.simulation.engine import SimulationEngine
from resqnet.backend.app.routing.base import BaseRouter

class DummyRouter(BaseRouter):
    def get_next_hop(self, destination_id: str):
        return None
        
    def handle_packet(self, packet: Packet) -> list[str]:
        # Track what sender_id we see
        if not hasattr(self, 'seen_senders'):
            self.seen_senders = []
        self.seen_senders.append(packet.sender_id)
        
        # Simple routing: A -> B -> C
        if self.node_id == "A":
            return ["B"]
        elif self.node_id == "B":
            return ["C"]
        elif self.node_id == "C":
            # Reached
            return []
        return []

def test_explicit_sender_id_tracking():
    topology = NetworkTopology()
    node_a = Node("A", "10.0.0.1")
    node_b = Node("B", "10.0.0.2")
    node_c = Node("C", "10.0.0.3")
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_node(node_c)
    
    topology.add_link(Link(node_a, node_b))
    topology.add_link(Link(node_b, node_c))
    
    router_a = DummyRouter("A", topology)
    router_b = DummyRouter("B", topology)
    router_c = DummyRouter("C", topology)
    
    engine = SimulationEngine(topology, {"A": router_a, "B": router_b, "C": router_c})
    
    packet = Packet(source_id="A", destination_id="D", payload="test_data")
    engine.send_packet(packet)
    
    # Verify sender_id seen by each router
    assert router_a.seen_senders == [None] # A generates it, sender is None when processed by A
    assert router_b.seen_senders == ["A"]  # B receives it from A
    assert router_c.seen_senders == ["B"]  # C receives it from B


def test_aodv_rerr_uses_sender_id():
    from resqnet.backend.app.routing.aodv_router import AODVRouter
    from resqnet.backend.app.models.aodv_payloads import RERRPayload
    
    topology = NetworkTopology()
    node_a = Node("A", "10.0.0.1")
    node_b = Node("B", "10.0.0.2")
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_link(Link(node_a, node_b))
    
    router_a = AODVRouter("A", topology)
    
    # Pre-populate A's routing table with a route to C via B
    router_a.routing_table.add_or_update_route("C", "B", 1, 1)
    route = router_a.routing_table.get_route("C")
    assert route.is_valid
    
    # Create an RERR from B saying C is unreachable
    payload = RERRPayload(unreachable_destinations=[("C", 2)])
    rerr_packet = Packet("B", "BROADCAST", payload, PacketType.RERR)
    
    # TAMPER WITH ROUTE HISTORY TO MAKE IT BOGUS!
    # If AODV relies on route_history, this will fail.
    rerr_packet.route_history = ["X", "Y", "Z"] 
    
    # But SET the correct sender_id
    rerr_packet.sender_id = "B"
    
    router_a.handle_packet(rerr_packet)
    
    # Because sender_id is "B", A should process the RERR and invalidate its route to C via B
    route = router_a.routing_table.get_route("C")
    assert not route.is_valid
    assert route.sequence_number == 2

