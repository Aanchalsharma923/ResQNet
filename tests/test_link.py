import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link

def test_link_creation_valid():
    """Test valid link creation with two distinct nodes."""
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    link = Link(node_a, node_b)
    
    assert link.node1 == node_a
    assert link.node2 == node_b
    assert link.is_active is True

def test_link_creation_invalid_types():
    """Test that link endpoints must be Node instances."""
    node_a = Node("A", "192.168.1.10")
    with pytest.raises(TypeError, match="Endpoints must be instances of Node"):
        Link(node_a, "not_a_node")
    with pytest.raises(TypeError, match="Endpoints must be instances of Node"):
        Link(None, node_a)

def test_link_creation_self_loop():
    """Test that a node cannot connect to itself."""
    node_a = Node("A", "192.168.1.10")
    with pytest.raises(ValueError, match="A link cannot connect a node to itself"):
        Link(node_a, node_a)

def test_link_equality_bidirectional():
    """Test that Link(A, B) is logically equivalent to Link(B, A)."""
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    
    link1 = Link(node_a, node_b)
    link2 = Link(node_b, node_a)
    
    # Must equate to True
    assert link1 == link2
    # Hashes must also match to allow using sets/dicts
    assert hash(link1) == hash(link2)

def test_link_connects():
    """Test the helper method to verify if an IP is part of the link."""
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    link = Link(node_a, node_b)
    
    assert link.connects("192.168.1.10") is True
    assert link.connects("192.168.1.11") is True
    assert link.connects("192.168.1.12") is False

def test_link_get_peer():
    """Test retrieving the peer node across the link."""
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    link = Link(node_a, node_b)
    
    assert link.get_peer("192.168.1.10") == node_b
    assert link.get_peer("192.168.1.11") == node_a
    
    with pytest.raises(ValueError, match="is not connected to this link"):
        link.get_peer("192.168.1.12")

def test_link_fail_and_recover():
    """Test failing and recovering a link."""
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    link = Link(node_a, node_b)
    
    assert link.is_active is True
    link.fail()
    assert link.is_active is False
    link.recover()
    assert link.is_active is True

def test_link_repr():
    """Test string representation of Link reflects its status."""
    node_a = Node("A", "192.168.1.10")
    node_b = Node("B", "192.168.1.11")
    link = Link(node_a, node_b)
    
    assert repr(link) == "Link(A <-> B, ACTIVE)"
    link.fail()
    assert repr(link) == "Link(A <-> B, FAILED)"
