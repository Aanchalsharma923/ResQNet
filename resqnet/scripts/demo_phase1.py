from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.static_router import StaticRouter
from resqnet.backend.app.simulation.engine import SimulationEngine

def print_topology(nodes):
    print("\nNODE STATUS")
    print("-----------")
    for node_id, node in nodes.items():
        status = "ACTIVE" if node.is_active else "FAILED"
        name = ""
        if node_id == "A": name = "Rescue-A"
        elif node_id == "B": name = "Relay-B"
        elif node_id == "C": name = "Relay-C"
        elif node_id == "D": name = "Relay-D"
        elif node_id == "H": name = "Hospital"
        
        print(f"{node_id} {name:<11} {status}")
    print()

def print_packet_state(packet, engine):
    print(f"Source:        {packet.source_id}")
    print(f"Destination:   {packet.destination_id}")
    print(f"Current Node:  {packet.current_node}")
    print(f"Payload:       {packet.payload}")
    print(f"Route History: {' -> '.join(packet.route_history)}")
    print(f"Hop Count:     {packet.hop_count}")
    print(f"Status:        {packet.status.name}")
    print("\nEvents:")
    for event in engine.events:
        print(f" - {event}")
    print()

def main():
    print("==================================================")
    print(" RESQNET — DISASTER-RESILIENT NETWORK SIMULATION")
    print("==================================================")
    
    # 1. Construct Topology
    topo = NetworkTopology()
    nodes = {
        "A": Node("A", "192.168.1.10"),
        "B": Node("B", "192.168.1.11"),
        "C": Node("C", "192.168.1.12"),
        "D": Node("D", "192.168.1.13"),
        "H": Node("H", "192.168.1.14"),
    }
    for node in nodes.values():
        topo.add_node(node)
        
    topo.add_link(Link(nodes["A"], nodes["B"]))
    topo.add_link(Link(nodes["A"], nodes["D"]))
    topo.add_link(Link(nodes["B"], nodes["C"]))
    topo.add_link(Link(nodes["D"], nodes["C"]))
    topo.add_link(Link(nodes["C"], nodes["H"]))
    
    print("\nNETWORK TOPOLOGY")
    print("----------------")
    print("A Rescue-A   192.168.1.10")
    print("B Relay-B    192.168.1.11")
    print("C Relay-C    192.168.1.12")
    print("D Relay-D    192.168.1.13")
    print("H Hospital   192.168.1.14")
    
    print("\nACTIVE LINKS")
    print("------------")
    print("A <-> B")
    print("A <-> D")
    print("B <-> C")
    print("D <-> C")
    print("C <-> H")
    
    # 2. Configure Static Router
    route = ["A", "B", "C", "H"]
    routers = {
        node_id: StaticRouter(node_id, topo, route)
        for node_id in nodes
    }
    print("\nSTATIC ROUTE")
    print("------------")
    print(" -> ".join(route))
    
    # 3. Scenario 1
    print("\n--------------------------------------------------")
    print("SCENARIO 1: NORMAL COMMUNICATION")
    print("--------------------------------------------------")
    print_topology(nodes)
    
    engine = SimulationEngine(topo, routers)
    packet1 = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED")
    
    print("Message:")
    print(packet1.payload)
    print("\nForwarding (Engine logs):")
    engine.send_packet(packet1)
    
    if packet1.status.name == "DELIVERED":
        print("Packet delivered successfully.\n")
    else:
        print("Packet delivery failed.\n")
        
    print_packet_state(packet1, engine)
    
    # 4. Scenario 2
    print("--------------------------------------------------")
    print("SCENARIO 2: RELAY-B FAILURE")
    print("--------------------------------------------------")
    
    print("\nFAILURE EVENT")
    print("Relay-B (192.168.1.11) has FAILED.")
    nodes["B"].is_active = False
    
    print_topology(nodes)
    
    print("Configured route:")
    print(" -> ".join(route))
    
    print("\nAttempting to send:")
    print("HELP REQUIRED")
    
    # Reset engine for clean event log
    engine = SimulationEngine(topo, routers)
    packet2 = Packet(source_id="A", destination_id="H", payload="HELP REQUIRED")
    
    print("\nForwarding (Engine logs):")
    engine.send_packet(packet2)
    
    if packet2.status.name == "DELIVERED":
        print("Packet delivered successfully.\n")
    else:
        print("Packet delivery failed.\n")
        
    print("Failure:")
    print("Next hop B is unavailable.")
    
    print("\nAutomatic recovery:")
    print("NOT AVAILABLE IN PHASE 1")
    print("(No fallback to A -> D -> C -> H occurs)\n")
    
    print_packet_state(packet2, engine)

if __name__ == "__main__":
    main()
