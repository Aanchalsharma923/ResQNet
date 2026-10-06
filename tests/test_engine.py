import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet, PacketStatus
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.static_router import StaticRouter
from resqnet.backend.app.simulation.engine import SimulationEngine

@pytest.fixture
def base_network():
    topo = NetworkTopology()
    nodes = {
        "A": Node("A", "192.168.1.10"),
        "B": Node("B", "192.168.1.11"),
        "C": Node("C", "192.168.1.12"),
        "D": Node("D", "192.168.1.13"),
        "H": Node("H", "192.168.1.14"),
    }
    for node in nodes.values():
        topo.add_node(node)
        
    topo.add_link(Link(nodes["A"], nodes["B"]))
    topo.add_link(Link(nodes["A"], nodes["D"]))
    topo.add_link(Link(nodes["B"], nodes["C"]))
    topo.add_link(Link(nodes["D"], nodes["C"]))
    topo.add_link(Link(nodes["C"], nodes["H"]))
    
    route = ["A", "B", "C", "H"]
    routers = {
        node_id: StaticRouter(node_id, topo, route)
        for node_id in nodes
    }
    
    engine = SimulationEngine(topo, routers)
    return engine, topo, nodes

def test_successful_forwarding_and_history(base_network):
    engine, topo, nodes = base_network
    
    packet = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED")
    engine.send_packet(packet)
    
    assert packet.status == PacketStatus.DELIVERED
    assert packet.current_node == "H"
    assert packet.hop_count == 3
    assert packet.route_history == ["A", "B", "C", "H"]
    assert packet.payload == "HELP REQUIRED"
    
    expected_events = [
        "PACKET_CREATED",
        "FORWARD A -> B",
        "FORWARD B -> C",
        "FORWARD C -> H",
        "PACKET_DELIVERED"
    ]
    assert engine.events == expected_events

def test_failed_intermediate_node(base_network):
    engine, topo, nodes = base_network
    
    # Fail B
    nodes["B"].is_active = False
    
    packet = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED")
    engine.send_packet(packet)
    
    assert packet.status == PacketStatus.DROPPED
    assert packet.current_node == "A"
    
    # Assert events show it couldn't find next hop
    assert "NEXT_HOP_UNAVAILABLE" in engine.events
    assert "PACKET_DROPPED" in engine.events
    
    # Ensure no automatic fallback to D
    assert "FORWARD A -> D" not in engine.events

def test_failed_link(base_network):
    engine, topo, nodes = base_network
    
    # Fail link B-C
    for link in topo.links:
        if (link.node1.node_id == "B" and link.node2.node_id == "C") or \
           (link.node1.node_id == "C" and link.node2.node_id == "B"):
            link.is_active = False
            
    packet = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED")
    engine.send_packet(packet)
    
    assert packet.status == PacketStatus.DROPPED
    assert packet.current_node == "B"  # Reached B, but couldn't go to C
    assert packet.route_history == ["A", "B"]

def test_ttl_prevents_indefinite_forwarding(base_network):
    engine, topo, nodes = base_network
    
    # Intentionally give a packet TTL of 1
    packet = Packet(source_id="A", destination_id="H", payload="TTL TEST", ttl=1)
    engine.send_packet(packet)
    
    assert packet.status == PacketStatus.DROPPED
    assert packet.current_node == "B" # TTL drops to 0 after first move to B
    assert packet.hop_count == 1
    assert "PACKET_DROPPED" in engine.events

def test_destination_stops_forwarding(base_network):
    engine, topo, nodes = base_network
    
    packet = Packet(source_id="H", destination_id="H", payload="LOCAL HELP")
    engine.send_packet(packet)
    
    assert packet.status == PacketStatus.DELIVERED
    assert packet.current_node == "H"
    assert packet.hop_count == 0
    assert engine.events == ["PACKET_CREATED", "PACKET_DELIVERED"]
    
def test_integration_static_route_no_recovery(base_network):
    engine, topo, nodes = base_network
    
    # Full scenario
    packet = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED")
    engine.send_packet(packet)
    assert packet.status == PacketStatus.DELIVERED
    
    # Reset engine events and packet
    engine.events = []
    
    # Now B fails
    nodes["B"].is_active = False
    
    packet2 = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED 2")
    engine.send_packet(packet2)
    
    assert packet2.status == PacketStatus.DROPPED
    assert packet2.current_node == "A"
    assert packet2.route_history == ["A"]
