import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.engine import SimulationEngine

def build_test_network():
    topology = NetworkTopology()
    
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    node_c = Node("C", "192.168.1.12")
    node_h = Node("H", "192.168.1.14")
    
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_node(node_c)
    topology.add_node(node_h)
    
    topology.add_link(Link(node_a, node_b))
    topology.add_link(Link(node_b, node_c))
    topology.add_link(Link(node_c, node_h))
    
    routers = {
        "A": AODVRouter("A", topology),
        "B": AODVRouter("B", topology),
        "C": AODVRouter("C", topology),
        "H": AODVRouter("H", topology)
    }
    
    engine = SimulationEngine(topology, routers)
    return topology, routers, engine

def setup_routes(routers, engine):
    """Sets up AODV routes from A to H organically via RREQ/RREP."""
    rreq = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq)

def test_data_forwarding_end_to_end():
    topology, routers, engine = build_test_network()
    setup_routes(routers, engine)
    
    # Send DATA packet
    data_packet = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet)
    
    assert data_packet.status == PacketStatus.DELIVERED
    assert data_packet.current_node == "H"
    assert data_packet.hop_count == 3
    assert data_packet.route_history == ["A", "B", "C", "H"]
    
def test_data_forwarding_fails_no_route():
    topology, routers, engine = build_test_network()
    # Don't setup routes
    
    data_packet = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet)
    
    assert data_packet.status == PacketStatus.DROPPED
    assert data_packet.current_node == "A"
    assert "NEXT_HOP_UNAVAILABLE" in engine.events or "ROUTE_UNAVAILABLE" in engine.events
    
def test_data_forwarding_respects_link_failure():
    topology, routers, engine = build_test_network()
    setup_routes(routers, engine)
    
    # Fail link B<->C
    b = topology.get_node_by_id("B")
    c = topology.get_node_by_id("C")
    link_bc = topology.get_link(b.ip_address, c.ip_address)
    assert link_bc is not None
    link_bc.is_active = False
    
    data_packet = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet)
    
    # Packet makes it to B, but B cannot forward it because link to C is down
    assert data_packet.status == PacketStatus.DROPPED
    assert data_packet.current_node == "B"
    
def test_data_forwarding_respects_ttl():
    topology, routers, engine = build_test_network()
    setup_routes(routers, engine)
    
    data_packet = Packet("A", "H", "HELP REQUIRED", PacketType.DATA, ttl=2)
    engine.send_packet(data_packet)
    
    # A->B uses 1 TTL (ttl goes from 2 to 1)
    # B->C uses 1 TTL (ttl goes from 1 to 0) -> dropped at C
    assert data_packet.status == PacketStatus.DROPPED
    assert data_packet.current_node == "C"
    assert data_packet.hop_count == 2
