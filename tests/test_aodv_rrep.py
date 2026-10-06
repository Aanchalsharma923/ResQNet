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
    
    topology.add_node(node_a)
    topology.add_node(node_b)
    topology.add_node(node_c)
    
    topology.add_link(Link(node_a, node_b))
    topology.add_link(Link(node_b, node_c))
    
    routers = {
        "A": AODVRouter("A", topology),
        "B": AODVRouter("B", topology),
        "C": AODVRouter("C", topology)
    }
    
    engine = SimulationEngine(topology, routers)
    return topology, routers, engine

def test_rrep_generation_at_destination():
    topology, routers, engine = build_test_network()

    rreq_packet = routers["A"].initiate_route_discovery("C")
    engine.send_packet(rreq_packet)

    events = engine.events

    # Destination C should have generated an RREP
    # And sent it to B
    assert "FORWARD C -> B" in events
    
def test_rrep_propagation():
    topology, routers, engine = build_test_network()

    rreq_packet = routers["A"].initiate_route_discovery("C")
    engine.send_packet(rreq_packet)

    events = engine.events

    # C sends RREP to B
    assert "FORWARD C -> B" in events
    # B forwards RREP to A
    assert "FORWARD B -> A" in events
    
    # We can check the route table at A to ensure RREP completed its job
    assert routers["A"].has_valid_route("C")
    
def test_forward_route_installation():
    topology, routers, engine = build_test_network()

    rreq_packet = routers["A"].initiate_route_discovery("C")
    engine.send_packet(rreq_packet)

    # A should now have a route to C
    route_at_a = routers["A"].routing_table.get_route("C")
    assert route_at_a is not None
    assert route_at_a.next_hop == "B"
    assert route_at_a.hop_count == 2
    
    # B should also have a forward route to C
    route_at_b = routers["B"].routing_table.get_route("C")
    assert route_at_b is not None
    assert route_at_b.next_hop == "C"
    assert route_at_b.hop_count == 1
    
def test_rrep_forwarding_fails_cleanly():
    topology, routers, engine = build_test_network()

    rreq_packet = routers["A"].initiate_route_discovery("C")
    engine.send_packet(rreq_packet)
    
    events = engine.events
    
    assert "FORWARD C -> B" in events
    
    # Let's break the link A-B, then send another RREQ (or fake a failure).
    # Since engine is synchronous, it already completed. Let's do it manually:
    topology, routers, engine = build_test_network()
    rreq_packet = routers["A"].initiate_route_discovery("C")
    
    # Broadcast A->B
    engine.send_packet(rreq_packet)
    
    # Before the RREP from B reaches A, let's say the route goes down?
    # Actually, let's just make B's next hop invalid.
    
    # In a new scenario, let C generate RREP, and B tries to forward it to A.
    # But A is down.
    node_a = topology.get_node_by_id("A")
    node_a.fail()
    
    from resqnet.backend.app.models.aodv_payloads import RREPPayload
    from resqnet.backend.app.models.packet import Packet, PacketType
    rrep_payload = RREPPayload("C", 1, "A", 0)
    rrep_packet = Packet("C", "A", rrep_payload, PacketType.RREP)
    rrep_packet.route_history.append("C")
    rrep_packet.route_history.append("B")
    
    routers["B"].routing_table.add_or_update_route("A", "A", 1, 1)
    
    engine.send_packet(rrep_packet)
    assert "NEXT_HOP_UNAVAILABLE" in engine.events or "PACKET_DROPPED" in engine.events
    # The forwarding from B -> A fails because A is failed.
