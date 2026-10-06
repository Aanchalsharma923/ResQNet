import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.engine import SimulationEngine

def build_test_network():
    topology = NetworkTopology()
    
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    node_c = Node("C", "192.168.1.12")
    node_d = Node("D", "192.168.1.13")
    node_h = Node("H", "192.168.1.14")
    
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_node(node_c)
    topology.add_node(node_d)
    topology.add_node(node_h)
    
    topology.add_link(Link(node_a, node_b))
    topology.add_link(Link(node_b, node_c))
    topology.add_link(Link(node_c, node_h))
    
    # Another path A->D->C
    topology.add_link(Link(node_a, node_d))
    topology.add_link(Link(node_d, node_c))
    
    routers = {
        "A": AODVRouter("A", topology),
        "B": AODVRouter("B", topology),
        "C": AODVRouter("C", topology),
        "D": AODVRouter("D", topology),
        "H": AODVRouter("H", topology)
    }
    
    engine = SimulationEngine(topology, routers)
    return topology, routers, engine

def test_forward_route_installation_and_events():
    topology, routers, engine = build_test_network()

    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)

    events = engine.events

    # C should have installed a route to H (next hop H, hop count 1)
    assert any("FORWARD_ROUTE_INSTALLED: node=C dest=H next=H hops=1" in e for e in events)
    
    # B or D should have installed a route to H (next hop C, hop count 2)
    assert any("FORWARD_ROUTE_INSTALLED: node=B dest=H next=C hops=2" in e for e in events) or \
           any("FORWARD_ROUTE_INSTALLED: node=D dest=H next=C hops=2" in e for e in events)
           
    # A should have installed a route to H
    assert any("ROUTE_DISCOVERY_COMPLETED: node=A dest=H" in e for e in events)
    
    # Verify exact route entries in the tables
    route_c = routers["C"].routing_table.get_route("H")
    assert route_c is not None
    assert route_c.next_hop == "H"
    assert route_c.hop_count == 1
    
    # A's route
    route_a = routers["A"].routing_table.get_route("H")
    assert route_a is not None
    assert route_a.hop_count == 3
    # Next hop is either B or D
    assert route_a.next_hop in ["B", "D"]
    assert routers["A"].get_next_hop("H") in ["B", "D"]

def test_sequence_number_update():
    topology, routers, engine = build_test_network()
    
    # Pretend A already has an old route to H
    routers["A"].routing_table.add_or_update_route("H", "B", 4, 10)
    
    # H has sequence number 15
    routers["H"].node_sequence_number = 15
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    route_a = routers["A"].routing_table.get_route("H")
    assert route_a is not None
    assert route_a.sequence_number == 15
    assert route_a.hop_count == 3
    
def test_no_worse_route_installed():
    topology, routers, engine = build_test_network()
    
    # Give A an excellent valid route with same sequence number
    routers["A"].routing_table.add_or_update_route("H", "X", 1, 15)
    
    routers["H"].node_sequence_number = 15
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    route_a = routers["A"].routing_table.get_route("H")
    # It should not have been overwritten by the 3-hop route because 3 > 1
    assert route_a is not None
    assert route_a.next_hop == "X"
    assert route_a.hop_count == 1
