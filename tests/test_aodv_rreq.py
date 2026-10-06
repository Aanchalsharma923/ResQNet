import pytest
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.simulation.engine import SimulationEngine
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import PacketStatus
from resqnet.backend.app.models.aodv_payloads import RREQPayload

def build_test_network():
    """
    Builds the test topology:
      B
     / \
    A   C -- H
     \ /
      D
    """
    topology = NetworkTopology()
    nodes = {
        "A": Node("A", "192.168.1.10"),
        "B": Node("B", "192.168.1.11"),
        "C": Node("C", "192.168.1.12"),
        "D": Node("D", "192.168.1.13"),
        "H": Node("H", "192.168.1.14")
    }
    for n in nodes.values():
        topology.add_node(n)

    topology.add_link(Link(nodes["A"], nodes["B"]))
    topology.add_link(Link(nodes["A"], nodes["D"]))
    topology.add_link(Link(nodes["B"], nodes["C"]))
    topology.add_link(Link(nodes["D"], nodes["C"]))
    topology.add_link(Link(nodes["C"], nodes["H"]))
    
    routers = {node_id: AODVRouter(node_id, topology) for node_id in nodes.keys()}
    engine = SimulationEngine(topology, routers)
    
    return topology, routers, engine

def test_rreq_broadcast_and_propagation():
    """RREQ is broadcasted to all active neighbors and propagates correctly."""
    topology, routers, engine = build_test_network()
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    events = engine.events
    
    # Assert A broadcasts to B and D
    assert "RREQ_BROADCAST A -> B" in events
    assert "RREQ_BROADCAST A -> D" in events
    
    # Assert RREQ reaches destination
    assert "RREQ_REACHED_DESTINATION" in events

def test_duplicate_rreq_suppression():
    """Duplicate RREQ is detected and dropped correctly."""
    topology, routers, engine = build_test_network()
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    # C should receive from both B and D, but it should only forward once to H
    # The second one from B/D should be suppressed.
    broadcasts_from_c = [e for e in engine.events if e.startswith("RREQ_BROADCAST C -> ")]
    assert len(broadcasts_from_c) == 2
    assert "RREQ_BROADCAST C -> H" in broadcasts_from_c

def test_hop_count_increases():
    """Hop count correctly increases on RREQ payload as it travels."""
    topology, routers, engine = build_test_network()
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    # Check the reverse routes added to routing tables to verify hop counts.
    # At B, distance to A is 1
    route_at_b = routers["B"].routing_table.get_route("A")
    assert route_at_b.hop_count == 1
    assert route_at_b.next_hop == "A"
    
    # At C, distance to A is 2
    route_at_c = routers["C"].routing_table.get_route("A")
    assert route_at_c.hop_count == 2
    assert route_at_c.next_hop in ["B", "D"] # Whichever arrived first
    
    # At H, distance to A is 3
    route_at_h = routers["H"].routing_table.get_route("A")
    assert route_at_h.hop_count == 3
    assert route_at_h.next_hop == "C"

def test_routing_table_stores_next_hop_only():
    """Routing table stores next_hop, not full path."""
    topology, routers, engine = build_test_network()
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    route_at_c = routers["C"].routing_table.get_route("A")
    # Path is not stored, just next hop
    assert isinstance(route_at_c.next_hop, str)
    assert len(route_at_c.next_hop) == 1

def test_failed_neighbor_excluded():
    """RREQ is not broadcast to failed neighbors."""
    topology, routers, engine = build_test_network()
    
    # Fail node D
    topology.get_node_by_id("D").fail()
    
    rreq_packet = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet)
    
    events = engine.events
    assert "RREQ_BROADCAST A -> B" in events
    assert "RREQ_BROADCAST A -> D" not in events
    assert "RREQ_REACHED_DESTINATION" in events # Still reaches via B

def test_different_broadcast_id_processed():
    """Same source but different broadcast ID is processed as a new RREQ."""
    topology, routers, engine = build_test_network()
    
    rreq_packet1 = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet1)
    events_count1 = engine.events.count("RREQ_REACHED_DESTINATION")
    assert events_count1 == 1
    
    # Clear events and initiate new RREQ
    engine.events.clear()
    rreq_packet2 = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet2)
    
    # Should propagate again
    events_count2 = engine.events.count("RREQ_REACHED_DESTINATION")
    assert events_count2 == 1

def test_different_source_processed():
    """Different source is processed as a new RREQ."""
    topology, routers, engine = build_test_network()
    
    rreq_packet1 = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet1)
    events_count1 = engine.events.count("RREQ_REACHED_DESTINATION")
    assert events_count1 == 1
    
    engine.events.clear()
    # Now B initiates
    rreq_packet2 = routers["B"].initiate_route_discovery("H")
    engine.send_packet(rreq_packet2)
    
    events_count2 = engine.events.count("RREQ_REACHED_DESTINATION")
    assert events_count2 == 1
