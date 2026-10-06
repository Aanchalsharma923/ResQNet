import pytest
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.engine import SimulationEngine

def build_test_network():
    """
    Initial topology:
    A -- B -- C -- H
     \       /
      -- D --
    """
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
    topology.add_link(Link(node_a, node_d))
    topology.add_link(Link(node_b, node_c))
    topology.add_link(Link(node_d, node_c))
    topology.add_link(Link(node_c, node_h))
    
    routers = {
        "A": AODVRouter("A", topology),
        "B": AODVRouter("B", topology),
        "C": AODVRouter("C", topology),
        "D": AODVRouter("D", topology),
        "H": AODVRouter("H", topology)
    }
    
    engine = SimulationEngine(topology, routers)
    return topology, routers, engine

def test_aodv_disaster_recovery():
    topology, routers, engine = build_test_network()
    
    # Step 1-3: Route Discovery A -> H
    rreq = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq)
    
    route_a = routers["A"].routing_table.get_route("H")
    assert route_a is not None
    assert route_a.is_valid
    
    # It might pick B or D depending on simulation order, usually B if it's processed first.
    # We will break the specific active route.
    active_next_hop = route_a.next_hop
    
    # Step 4-5: Send DATA
    data_packet1 = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet1)
    
    assert data_packet1.status == PacketStatus.DELIVERED
    assert data_packet1.current_node == "H"
    
    # Step 6: Break the active route (Next Hop -> C)
    # The active route goes A -> (B or D) -> C -> H. Let's break the active_next_hop -> C link
    intermediate_node = topology.get_node_by_id(active_next_hop)
    node_c = topology.get_node_by_id("C")
    
    link_to_break = topology.get_link(intermediate_node.ip_address, node_c.ip_address)
    link_to_break.is_active = False
    
    engine.events.clear()
    
    # Step 7: Attempt communication again
    data_packet2 = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet2)
    
    # Step 8: The stale route must fail
    assert data_packet2.status == PacketStatus.DROPPED
    assert data_packet2.current_node == intermediate_node.node_id
    
    # Step 9: RERR/invalidation occurs
    # Intermediate node detected link is down, generated RERR, A received it and invalidated route
    assert any("RERR_GENERATED" in e for e in engine.events)
    assert any("ROUTE_INVALIDATED: node=A dest=H" in e for e in engine.events)
    
    assert not routers["A"].routing_table.get_route("H").is_valid
    
    # Step 10: Route rediscovery
    # We either manually trigger initiate_route_discovery, or if A's handle_packet triggers it automatically on DATA 
    # when no route, we could just send DATA again. Let's send DATA again and ensure it triggers discovery and drops.
    # Wait, the prompt says "Attempt communication again -> stale route fails -> RERR -> route invalid. New RREQ occurs."
    # We will trigger the new RREQ by sending a DATA packet, which will drop and generate RREQ.
    
    engine.events.clear()
    data_packet3 = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet3)
    
    # It should have generated an RREQ and processed it
    assert data_packet3.status == PacketStatus.DROPPED
    assert data_packet3.current_node == "A"
    assert any("RREQ_CREATED" in e or "RREQ_BROADCAST" in e for e in engine.events)
    
    # Verify new route is established
    new_route_a = routers["A"].routing_table.get_route("H")
    assert new_route_a.is_valid
    assert new_route_a.next_hop != active_next_hop # Must use the alternate!
    
    # Step 12-13: Send DATA again
    data_packet4 = Packet("A", "H", "HELP REQUIRED AGAIN", PacketType.DATA)
    engine.send_packet(data_packet4)
    
    # Step 14: H receives it
    assert data_packet4.status == PacketStatus.DELIVERED
    assert data_packet4.current_node == "H"
    assert data_packet4.route_history[1] == new_route_a.next_hop

def test_aodv_node_failure_recovery():
    topology, routers, engine = build_test_network()
    
    # Discovery
    rreq = routers["A"].initiate_route_discovery("H")
    engine.send_packet(rreq)
    
    route_a = routers["A"].routing_table.get_route("H")
    active_next_hop = route_a.next_hop
    
    data_packet1 = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet1)
    
    # Fail the intermediate node entirely
    intermediate_node = topology.get_node_by_id(active_next_hop)
    intermediate_node.is_active = False
    
    engine.events.clear()
    
    # Attempt communication again
    data_packet2 = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet2)
    
    assert data_packet2.status == PacketStatus.DROPPED
    assert any("ROUTE_INVALIDATED: node=A dest=H" in e for e in engine.events)
    
    # Rediscovery
    engine.events.clear()
    data_packet3 = Packet("A", "H", "HELP REQUIRED", PacketType.DATA)
    engine.send_packet(data_packet3)
    
    new_route_a = routers["A"].routing_table.get_route("H")
    assert new_route_a.is_valid
    assert new_route_a.next_hop != active_next_hop
    
    data_packet4 = Packet("A", "H", "HELP REQUIRED AGAIN", PacketType.DATA)
    engine.send_packet(data_packet4)
    assert data_packet4.status == PacketStatus.DELIVERED
