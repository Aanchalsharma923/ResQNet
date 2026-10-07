import pytest
from resqnet.backend.app.transport.simulation import SimulationTransport
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet

def test_simulation_transport_lifecycle():
    topology = NetworkTopology()
    transport = SimulationTransport(topology)
    
    assert transport.is_running is False
    transport.start()
    assert transport.is_running is True
    transport.stop()
    assert transport.is_running is False

def test_simulation_transport_delivery():
    topology = NetworkTopology()
    node_a = Node("A", "10.0.0.1")
    node_b = Node("B", "10.0.0.2")
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_link(Link(node_a, node_b))
    
    transport = SimulationTransport(topology)
    
    # Needs to be running to send
    packet = Packet(source_id="A", destination_id="B", payload="test")
    assert transport.send(packet, ["B"]) is False
    
    transport.start()
    
    received_packets = []
    def on_receive(pkt):
        received_packets.append(pkt)
        
    transport.set_receive_callback(on_receive)
    
    # Send packet
    success = transport.send(packet, ["B"])
    assert success is True
    assert len(received_packets) == 1
    
    delivered_packet = received_packets[0]
    assert delivered_packet.current_node == "B"
    assert delivered_packet.sender_id == "A"
    
def test_simulation_transport_delivery_failure():
    topology = NetworkTopology()
    node_a = Node("A", "10.0.0.1")
    node_b = Node("B", "10.0.0.2")
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_link(Link(node_a, node_b))
    
    transport = SimulationTransport(topology)
    transport.start()
    
    packet = Packet(source_id="A", destination_id="C", payload="test")
    # "C" is not a neighbor, nor does it exist
    success = transport.send(packet, ["C"])
    assert success is False
    
    # Now try sending to a failed node
    node_b.is_active = False
    success2 = transport.send(packet, ["B"])
    assert success2 is False
