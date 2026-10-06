import pytest
from resqnet.backend.app.models.node import Node

def test_node_creation_valid_ip():
    """Test that a Node can be created with a valid IPv4 address."""
    node = Node("A", "192.168.1.10")
    assert node.node_id == "A"
    assert node.ip_address == "192.168.1.10"
    assert node.is_active is True

def test_node_creation_invalid_ip():
    """Test that creating a Node with an invalid IPv4 address raises ValueError."""
    with pytest.raises(ValueError, match="Invalid IPv4 address: 999.999.999.999"):
        Node("B", "999.999.999.999")

    with pytest.raises(ValueError, match="Invalid IPv4 address: not_an_ip"):
        Node("C", "not_an_ip")
        
    with pytest.raises(ValueError, match="Invalid IPv4 address: 192.168.1"):
        Node("D", "192.168.1")
        
    # IPv6 should also fail since we only support IPv4 for this simulation
    with pytest.raises(ValueError):
        Node("E", "2001:0db8:85a3:0000:0000:8a2e:0370:7334")

def test_node_fail_and_recover():
    """Test the fail and recover state transitions of a Node."""
    node = Node("H", "192.168.1.14")
    assert node.is_active is True
    
    node.fail()
    assert node.is_active is False
    
    node.recover()
    assert node.is_active is True

def test_node_repr():
    """Test the string representation of the Node."""
    node = Node("Rescue-A", "192.168.1.10")
    assert repr(node) == "Node(Rescue-A, 192.168.1.10, active=True)"
