import pytest
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link

def setup_topology():
    topology = NetworkTopology()
    # Add nodes A and H
    node_a = Node("A", "192.168.1.10")
    node_h = Node("H", "192.168.1.20")
    topology.add_node(node_a)
    topology.add_node(node_h)
    return topology, node_a, node_h

def test_aodv_router_creation():
    """Router creation - AODVRouter can be created and has routing table."""
    topology, _, _ = setup_topology()
    router = AODVRouter("A", topology)
    assert router.node_id == "A"
    assert router.topology == topology
    assert router.routing_table is not None

def test_sequence_number():
    """Sequence number - initial is correct, increments correctly, multiple increments."""
    topology, _, _ = setup_topology()
    router = AODVRouter("A", topology)
    
    assert router.node_sequence_number == 1
    
    seq = router.increment_sequence_number()
    assert seq == 2
    assert router.node_sequence_number == 2
    
    seq2 = router.increment_sequence_number()
    assert seq2 == 3
    assert router.node_sequence_number == 3

def test_broadcast_id():
    """Broadcast ID - initial is correct, monotonically increases."""
    topology, _, _ = setup_topology()
    router = AODVRouter("A", topology)
    
    assert router.broadcast_id_counter == 0
    
    bid1 = router.get_next_broadcast_id()
    assert bid1 == 1
    assert router.broadcast_id_counter == 1
    
    bid2 = router.get_next_broadcast_id()
    assert bid2 == 2
    assert router.broadcast_id_counter == 2

def test_rreq_identity_tracking():
    """RREQ identity - record and check, seen -> duplicate."""
    topology, _, _ = setup_topology()
    router = AODVRouter("A", topology)
    
    # Not seen yet
    assert router.has_seen_rreq("B", 1) is False
    
    # Record
    router.record_rreq("B", 1)
    
    # Now seen (duplicate)
    assert router.has_seen_rreq("B", 1) is True
    
    # Other IDs not seen
    assert router.has_seen_rreq("B", 2) is False
    assert router.has_seen_rreq("C", 1) is False

def test_routing_table_integration_and_lookup():
    """Routing-table integration - delegates to routing table, no pathfinding."""
    topology, _, _ = setup_topology()
    router = AODVRouter("A", topology)
    
    # No route behavior
    assert router.has_valid_route("H") is False
    assert router.get_next_hop("H") is None
    
    # Inject a route into the routing table manually
    router.routing_table.add_or_update_route("H", "B", 3, 5)
    
    # Now has valid route
    assert router.has_valid_route("H") is True
    assert router.get_next_hop("H") == "B"

def test_no_hidden_pathfinding():
    """No hidden pathfinding - router must not discover topological paths silently."""
    topology, node_a, node_h = setup_topology()
    node_b = Node("B", "192.168.1.11")
    node_c = Node("C", "192.168.1.12")
    node_d = Node("D", "192.168.1.13")
    
    topology.add_node(node_b)
    topology.add_node(node_c)
    topology.add_node(node_d)
    
    topology.add_link(Link(node_a, node_b))
    topology.add_link(Link(node_b, node_c))
    topology.add_link(Link(node_c, node_h))
    topology.add_link(Link(node_a, node_d))
    topology.add_link(Link(node_d, node_c))
    
    router = AODVRouter("A", topology)
    
    # Despite topology having a path A->B->C->H and A->D->C->H,
    # AODVRouter should not know it without RREQ/RREP.
    assert router.has_valid_route("H") is False
    assert router.get_next_hop("H") is None

def test_route_discovery_initiation():
    """Route discovery initiates RREQ with correct values."""
    topology, _, _ = setup_topology()
    router = AODVRouter("A", topology)
    
    packet = router.initiate_route_discovery("H")
    
    assert packet.packet_type.name == "RREQ"
    assert packet.source_id == "A"
    assert packet.destination_id == "H"
    
    payload = packet.payload
    assert payload.source_id == "A"
    assert payload.destination_id == "H"
    assert payload.source_sequence_number == 2 # 1 incremented to 2
    assert payload.broadcast_id == 1
    assert payload.hop_count == 0
    
    # Verify the router recorded its own RREQ
    assert router.has_seen_rreq("A", 1) is True

