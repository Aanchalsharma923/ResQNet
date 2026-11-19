import pytest
from fastapi.testclient import TestClient
from resqnet.backend.app.main import app
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.engine import SimulationEngine
from resqnet.backend.app.services.simulation_service import SimulationService

client = TestClient(app)

def create_topology_and_engine():
    r"""
    Standard ResQNet 5-node topology:
    A -- B -- C -- H
     [ \       / ]
      -- D --
    """
    topology = NetworkTopology()
    nodes = {
        "A": Node("A", "192.168.1.10"),
        "B": Node("B", "192.168.1.11"),
        "C": Node("C", "192.168.1.12"),
        "D": Node("D", "192.168.1.13"),
        "H": Node("H", "192.168.1.14"),
    }
    for n in nodes.values():
        topology.add_node(n)

    topology.add_link(Link(nodes["A"], nodes["B"]))
    topology.add_link(Link(nodes["A"], nodes["D"]))
    topology.add_link(Link(nodes["B"], nodes["C"]))
    topology.add_link(Link(nodes["D"], nodes["C"]))
    topology.add_link(Link(nodes["C"], nodes["H"]))

    routers = {nid: AODVRouter(nid, topology) for nid in nodes}
    engine = SimulationEngine(topology, routers)
    return topology, nodes, routers, engine


# =========================================================================
# 1. SCENARIO 1: Normal A-to-H Delivery (Primary Route: A -> B -> C -> H)
# =========================================================================
def test_scenario_1_normal_delivery():
    client.post("/api/simulation/reset")
    payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Scenario 1: Normal Emergency Delivery",
        "priority": "CRITICAL",
        "auto_discover": True
    }
    resp = client.post("/api/sos", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["success"] is True
    assert data["packet"]["status"] == "DELIVERED"
    assert data["packet"]["route_history"] == ["A", "B", "C", "H"]
    assert data["ack_status"] == "CONFIRMED"

    net_resp = client.get("/api/network").json()
    assert net_resp["active_route"] == ["A", "B", "C", "H"]


# =========================================================================
# 2. SCENARIO 2: Node B Failure & Dynamic Failover (A -> D -> C -> H)
# =========================================================================
def test_scenario_2_node_b_failover_to_d():
    client.post("/api/simulation/reset")
    # Step 1: Establish baseline route
    client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Baseline SOS",
        "auto_discover": True
    })
    assert client.get("/api/network").json()["active_route"] == ["A", "B", "C", "H"]

    # Step 2: Fail Node B
    fail_resp = client.post("/api/nodes/B/fail")
    assert fail_resp.status_code == 200

    # Step 3: Dispatch subsequent SOS - AODV autonomously rediscovers via D
    resp2 = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Failover SOS via D",
        "auto_discover": True
    })
    assert resp2.status_code == 200
    data2 = resp2.json()

    assert data2["success"] is True
    assert data2["packet"]["route_history"] == ["A", "D", "C", "H"]
    assert data2["ack_status"] == "CONFIRMED"

    net_state = client.get("/api/network").json()
    assert net_state["active_route"] == ["A", "D", "C", "H"]


# =========================================================================
# 3. SCENARIO 3: Node C Failure (Junction Loss, Unreachable Destination)
# =========================================================================
def test_scenario_3_node_c_failure_bottleneck():
    client.post("/api/simulation/reset")
    client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Before C loss",
        "auto_discover": True
    })

    # Fail bottleneck Node C
    client.post("/api/nodes/C/fail")

    # Attempt SOS transmission to H - must fail gracefully without crash
    resp = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Unreachable SOS",
        "auto_discover": True
    })
    data = resp.json()
    assert data["success"] is False
    assert client.get("/api/network").json()["active_route"] == []

    metrics = client.get("/api/metrics").json()
    assert metrics["packets_dropped"] >= 1


# =========================================================================
# 4. SCENARIO 4: Node D Failure while on Primary Route
# =========================================================================
def test_scenario_4_node_d_fail_isolated():
    client.post("/api/simulation/reset")
    # Ensure primary path A -> B -> C -> H is established
    client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Initial",
        "auto_discover": True
    })
    assert client.get("/api/network").json()["active_route"] == ["A", "B", "C", "H"]

    # Fail unused standby Node D
    client.post("/api/nodes/D/fail")

    # Active route must remain intact and subsequent packets deliver
    resp = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "During D outage",
        "auto_discover": True
    })
    data = resp.json()
    assert data["success"] is True
    assert data["packet"]["route_history"] == ["A", "B", "C", "H"]
    assert client.get("/api/network").json()["active_route"] == ["A", "B", "C", "H"]


# =========================================================================
# 5. SCENARIO 5: Active Link Failure (Link B-C Fails)
# =========================================================================
def test_scenario_5_active_link_failure():
    client.post("/api/simulation/reset")
    client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Before link fail",
        "auto_discover": True
    })
    assert client.get("/api/network").json()["active_route"] == ["A", "B", "C", "H"]

    # Fail specific link B-C
    fail_link = client.post("/api/links/fail", json={"node_a": "B", "node_b": "C"})
    assert fail_link.status_code == 200

    # Next message detects link loss and discovers A -> D -> C -> H
    resp = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "After B-C link fail",
        "auto_discover": True
    })
    data = resp.json()
    assert data["success"] is True
    assert data["packet"]["route_history"] == ["A", "D", "C", "H"]
    assert client.get("/api/network").json()["active_route"] == ["A", "D", "C", "H"]


# =========================================================================
# 6. SCENARIO 6: Destination Node H Offline
# =========================================================================
def test_scenario_6_destination_h_offline():
    client.post("/api/simulation/reset")
    # Fail Destination H
    client.post("/api/nodes/H/fail")

    resp = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "SOS to offline hospital",
        "auto_discover": True
    })
    data = resp.json()
    assert data["success"] is False
    assert client.get("/api/network").json()["active_route"] == []


# =========================================================================
# 7. SCENARIO 7: All Routes Disconnected (Network Partition)
# =========================================================================
def test_scenario_7_all_routes_disconnected():
    client.post("/api/simulation/reset")
    # Fail both intermediate relays B and D
    client.post("/api/nodes/B/fail")
    client.post("/api/nodes/D/fail")

    resp = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Partitioned network SOS",
        "auto_discover": True
    })
    data = resp.json()
    assert data["success"] is False
    assert client.get("/api/network").json()["active_route"] == []

    metrics = client.get("/api/metrics").json()
    assert metrics["packets_dropped"] >= 1


# =========================================================================
# 8. SCENARIO 8: Node Recovery
# =========================================================================
def test_scenario_8_node_recovery():
    client.post("/api/simulation/reset")
    # Fail B
    client.post("/api/nodes/B/fail")
    node_b = [n for n in client.get("/api/network").json()["nodes"] if n["node_id"] == "B"][0]
    assert not node_b["is_active"]

    # Recover B
    rec_resp = client.post("/api/nodes/B/recover")
    assert rec_resp.status_code == 200
    node_b_rec = [n for n in client.get("/api/network").json()["nodes"] if n["node_id"] == "B"][0]
    assert node_b_rec["is_active"]


# =========================================================================
# 9. SCENARIO 9: Route Rediscovery after Failover & Recovery
# =========================================================================
def test_scenario_9_route_rediscovery():
    topo, nodes, routers, engine = create_topology_and_engine()

    # Initial route discovery
    engine.send_packet(routers["A"].initiate_route_discovery("H"))
    assert routers["A"].routing_table.get_route("H") is not None
    assert routers["A"].routing_table.get_route("H").is_valid

    # Break active route
    r_a = routers["A"].routing_table.get_route("H")
    active_nh = r_a.next_hop
    topo.get_link(nodes["A"].ip_address, nodes[active_nh].ip_address).is_active = False

    # Trigger local route invalidation
    routers["A"].routing_table.invalidate_route("H")
    assert not routers["A"].routing_table.get_route("H").is_valid

    # Rediscover route
    engine.send_packet(routers["A"].initiate_route_discovery("H"))
    new_route = routers["A"].routing_table.get_route("H")
    assert new_route is not None and new_route.is_valid
    assert new_route.next_hop != active_nh


# =========================================================================
# 10. SCENARIO 10: Post-Recovery Communication & Verified ACK
# =========================================================================
def test_scenario_10_post_recovery_communication():
    client.post("/api/simulation/reset")

    # Step 1: Send baseline SOS with ACK
    res1 = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Pre-failure emergency",
        "auto_discover": True
    }).json()
    assert res1["success"] is True
    assert res1["ack_status"] == "CONFIRMED"

    # Step 2: Disrupt network (fail B)
    client.post("/api/nodes/B/fail")

    # Step 3: Send SOS over alternate route
    res2 = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Emergency during failover",
        "auto_discover": True
    }).json()
    assert res2["success"] is True
    assert res2["ack_status"] == "CONFIRMED"

    # Step 4: Recover Node B
    client.post("/api/nodes/B/recover")

    # Step 5: Post-recovery transmission
    res3 = client.post("/api/sos", json={
        "source_id": "A",
        "destination_id": "H",
        "message": "Post-recovery all systems operational",
        "auto_discover": True
    }).json()
    assert res3["success"] is True
    assert res3["ack_status"] == "CONFIRMED"

    # Step 6: Verify hospital inbox contains all delivered messages
    inbox = client.get("/api/hospital/inbox").json()
    assert len(inbox) >= 3
    messages = [m["message"] for m in inbox]
    assert "Pre-failure emergency" in messages
    assert "Emergency during failover" in messages
    assert "Post-recovery all systems operational" in messages
