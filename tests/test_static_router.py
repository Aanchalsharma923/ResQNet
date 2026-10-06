import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.static_router import StaticRouter

@pytest.fixture
def base_topology():
    topo = NetworkTopology()
    nodes = {
        "A": Node("A", "10.0.0.1"),
        "B": Node("B", "10.0.0.2"),
        "C": Node("C", "10.0.0.3"),
        "D": Node("D", "10.0.0.4"),
        "H": Node("H", "10.0.0.5"),
    }
    for node in nodes.values():
        topo.add_node(node)
        
    topo.add_link(Link(nodes["A"], nodes["B"]))
    topo.add_link(Link(nodes["B"], nodes["C"]))
    topo.add_link(Link(nodes["C"], nodes["H"]))
    topo.add_link(Link(nodes["A"], nodes["D"]))
    topo.add_link(Link(nodes["D"], nodes["C"]))
    return topo, nodes

def test_static_route_creation(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    router = StaticRouter("A", topo, route)
    assert router.node_id == "A"
    assert router.route == route

def test_valid_next_hop_lookup(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    
    router_a = StaticRouter("A", topo, route)
    assert router_a.get_next_hop("H") == "B"

def test_correct_sequence(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    
    router_a = StaticRouter("A", topo, route)
    router_b = StaticRouter("B", topo, route)
    router_c = StaticRouter("C", topo, route)
    router_h = StaticRouter("H", topo, route)
    
    assert router_a.get_next_hop("H") == "B"
    assert router_b.get_next_hop("H") == "C"
    assert router_c.get_next_hop("H") == "H"
    assert router_h.get_next_hop("H") is None  # We are the destination

def test_invalid_nonexistent_route(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    router_a = StaticRouter("A", topo, route)
    
    # Destination not in route
    assert router_a.get_next_hop("X") is None
    
    # Node not in route
    router_d = StaticRouter("D", topo, route)
    assert router_d.get_next_hop("H") is None

def test_failed_node_handling(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    router_a = StaticRouter("A", topo, route)
    
    # Next hop is B, let's fail B
    nodes["B"].is_active = False
    
    assert router_a.get_next_hop("H") is None

def test_failed_link_handling(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    router_b = StaticRouter("B", topo, route)
    
    # Next hop from B is C. Let's fail the link B-C
    # We find the link and fail it
    for link in topo.links:
        if (link.node1.node_id == "B" and link.node2.node_id == "C") or \
           (link.node1.node_id == "C" and link.node2.node_id == "B"):
            link.is_active = False
            
    assert router_b.get_next_hop("H") is None

def test_no_automatic_alternate_route(base_topology):
    topo, nodes = base_topology
    route = ["A", "B", "C", "H"]
    router_a = StaticRouter("A", topo, route)
    
    # Node D provides an alternate physical path (A -> D -> C -> H)
    # But if B fails, StaticRouter should not automatically switch to D
    nodes["B"].is_active = False
    
    assert router_a.get_next_hop("H") is None
