import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.simulation.topology import NetworkTopology

def test_add_valid_node():
    """Test registering a valid node."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    topo.add_node(node_a)
    
    assert topo.get_node_by_id("A") == node_a
    assert topo.get_node_by_ip("192.168.1.10") == node_a

def test_add_duplicate_node_id():
    """Test that nodes with duplicate IDs are rejected."""
    topo = NetworkTopology()
    node_a1 = Node("A", "192.168.1.10")
    node_a2 = Node("A", "192.168.1.11")
    topo.add_node(node_a1)
    
    with pytest.raises(ValueError, match="already exists in topology"):
        topo.add_node(node_a2)

def test_add_duplicate_node_ip():
    """Test that nodes with duplicate IPs are rejected."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.10")
    topo.add_node(node_a)
    
    with pytest.raises(ValueError, match="already exists in topology"):
        topo.add_node(node_b)

def test_node_lookup_failures():
    """Test lookup errors for non-existent nodes."""
    topo = NetworkTopology()
    with pytest.raises(KeyError, match="not found"):
        topo.get_node_by_id("Missing")
    with pytest.raises(KeyError, match="not found"):
        topo.get_node_by_ip("192.168.1.99")

def test_add_valid_link():
    """Test adding a valid link between registered nodes."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    topo.add_node(node_b)
    
    link = Link(node_a, node_b)
    topo.add_link(link)
    
    assert topo.get_link("192.168.1.10", "192.168.1.11") == link

def test_add_link_unregistered_node():
    """Test that links cannot be added if endpoints aren't in topology."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    
    link = Link(node_a, node_b)
    with pytest.raises(ValueError, match="must be added to the topology first"):
        topo.add_link(link)

def test_add_duplicate_link():
    """Test that duplicate links (even if defined backward) are rejected."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    topo.add_node(node_b)
    
    link1 = Link(node_a, node_b)
    link2 = Link(node_b, node_a)
    
    topo.add_link(link1)
    with pytest.raises(ValueError, match="already exists in the topology"):
        topo.add_link(link2)

def test_active_neighbors_discovery():
    """Test finding healthy active neighbors."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    node_c = Node("C", "192.168.1.12")
    topo.add_node(node_a)
    topo.add_node(node_b)
    topo.add_node(node_c)
    
    topo.add_link(Link(node_a, node_b))
    topo.add_link(Link(node_a, node_c))
    
    neighbors_a = topo.get_active_neighbors("192.168.1.10")
    assert len(neighbors_a) == 2
    assert node_b in neighbors_a
    assert node_c in neighbors_a

def test_failed_node_excluded():
    """Test that failing a neighbor explicitly removes it from reachable neighbors."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    topo.add_node(node_b)
    topo.add_link(Link(node_a, node_b))
    
    node_b.fail()
    assert len(topo.get_active_neighbors("192.168.1.10")) == 0
    
    node_b.recover()
    assert len(topo.get_active_neighbors("192.168.1.10")) == 1

def test_failed_link_excluded():
    """Test that failing the physical link explicitly removes reachability."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    topo.add_node(node_b)
    
    link = Link(node_a, node_b)
    topo.add_link(link)
    
    link.fail()
    assert len(topo.get_active_neighbors("192.168.1.10")) == 0
    
    link.recover()
    assert len(topo.get_active_neighbors("192.168.1.10")) == 1

def test_self_failed_has_no_neighbors():
    """Test that if the requesting node is failed, it returns zero neighbors."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    topo.add_node(node_b)
    topo.add_link(Link(node_a, node_b))
    
    node_a.fail()
    assert len(topo.get_active_neighbors("192.168.1.10")) == 0

def test_bidirectional_neighbor_behavior():
    """Test that node reachability via links goes both ways."""
    topo = NetworkTopology()
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    topo.add_node(node_a)
    topo.add_node(node_b)
    topo.add_link(Link(node_a, node_b))
    
    assert node_b in topo.get_active_neighbors("192.168.1.10")
    assert node_a in topo.get_active_neighbors("192.168.1.11")

def test_invalid_type_addition():
    """Test preventing non-Node and non-Link objects from polluting the topology."""
    topo = NetworkTopology()
    with pytest.raises(TypeError, match="Must add a Node instance"):
        topo.add_node("Not a node")
    
    with pytest.raises(TypeError, match="Must add a Link instance"):
        topo.add_link("Not a link")
