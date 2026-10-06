from typing import Dict, List, Optional
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.simulation.engine import SimulationEngine
from resqnet.backend.app.services.broadcaster import broadcaster

class SimulationService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SimulationService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.topology = NetworkTopology()
        self.routers = {}
        self.engine = None
        self._setup_default_network()

    def _setup_default_network(self):
        # 1. Construct Topology
        self.topology = NetworkTopology()
        nodes = {
            "A": Node("A", "192.168.1.10"),
            "B": Node("B", "192.168.1.11"),
            "C": Node("C", "192.168.1.12"),
            "D": Node("D", "192.168.1.13"),
            "H": Node("H", "192.168.1.14"),
        }
        for node in nodes.values():
            self.topology.add_node(node)
            
        self.topology.add_link(Link(nodes["A"], nodes["B"]))
        self.topology.add_link(Link(nodes["A"], nodes["D"]))
        self.topology.add_link(Link(nodes["B"], nodes["C"]))
        self.topology.add_link(Link(nodes["D"], nodes["C"]))
        self.topology.add_link(Link(nodes["C"], nodes["H"]))

        # 2. Configure AODV Routers
        self.routers = {
            node_id: AODVRouter(node_id, self.topology)
            for node_id in nodes
        }
        
        self.engine = SimulationEngine(self.topology, self.routers)
        self.engine.event_callback = self._on_simulation_event
        
        # Broadcast network initialized event
        broadcaster.broadcast_sync("NETWORK_INITIALIZED", self.get_network_state())

    def _on_simulation_event(self, event_str: str, packet: Packet = None):
        """Map SimulationEngine raw events to rich WebSocket events"""
        event_type = event_str
        data = {}
        
        if packet:
            data.update({
                "packet_id": packet.packet_id,
                "packet_type": packet.packet_type.name,
                "source_id": packet.source_id,
                "destination_id": packet.destination_id,
                "current_node": packet.current_node,
                "sender_id": packet.sender_id,
                "hop_count": packet.hop_count,
                "status": packet.status.name,
                "payload": packet.payload if isinstance(packet.payload, str) else str(packet.payload)
            })

        # Remap string events to standardized event types
        if event_str == "PACKET_CREATED":
            event_type = "DATA_CREATED" if packet and packet.packet_type.name == "DATA" else "PACKET_CREATED"
        elif event_str.startswith("RREQ_CREATED"):
            event_type = "RREQ_GENERATED"
        elif event_str == "PACKET_DELIVERED":
            event_type = "DATA_DELIVERED" if packet and packet.packet_type.name == "DATA" else "PACKET_DELIVERED"
        elif event_str == "RREQ_REACHED_DESTINATION":
            event_type = "RREQ_RECEIVED"
        elif event_str == "PACKET_DROPPED":
            event_type = "DATA_DROPPED" if packet and packet.packet_type.name == "DATA" else "PACKET_DROPPED"
        elif event_str.startswith("RREQ_BROADCAST"):
            event_type = "RREQ_FORWARDED"
            parts = event_str.split(" ")
            if len(parts) == 4:
                data["from_node"] = parts[1]
                data["to_node"] = parts[3]
        elif event_str.startswith("FORWARD "):
            # Could be DATA or RREP forwarding
            if packet and packet.packet_type.name == "RREP":
                event_type = "RREP_FORWARDED"
            elif packet and packet.packet_type.name == "RERR":
                event_type = "RERR_FORWARDED"
            else:
                event_type = "DATA_FORWARDED"
            parts = event_str.split(" ")
            if len(parts) == 4:
                data["from_node"] = parts[1]
                data["to_node"] = parts[3]
        elif event_str.startswith("ROUTE_INVALIDATED:"):
            event_type = "ROUTE_INVALIDATED"
            parts = event_str.replace("ROUTE_INVALIDATED: ", "").split(" ")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=")
                    data[k] = v
        elif event_str.startswith("FORWARD_ROUTE_INSTALLED:"):
            event_type = "FORWARD_ROUTE_INSTALLED"
            parts = event_str.replace("FORWARD_ROUTE_INSTALLED: ", "").split(" ")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=")
                    data[k] = v
        elif event_str.startswith("ROUTE_DISCOVERY_COMPLETED:"):
            event_type = "ROUTE_DISCOVERY_COMPLETED"
            parts = event_str.replace("ROUTE_DISCOVERY_COMPLETED: ", "").split(" ")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=")
                    data[k] = v
        elif event_str.startswith("RERR_GENERATED:"):
            event_type = "RERR_GENERATED"
            parts = event_str.replace("RERR_GENERATED: ", "").split(" ")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=")
                    data[k] = v

        broadcaster.broadcast_sync(event_type, data)

    def reset(self):
        self._initialize()
        broadcaster.broadcast_sync("SIMULATION_RESET", self.get_network_state())

    def get_network_state(self) -> dict:
        nodes = []
        for ip, node in self.topology.nodes_by_id.items():
            nodes.append({
                "node_id": node.node_id,
                "ip_address": node.ip_address,
                "is_active": node.is_active
            })
            
        links = []
        for link in self.topology.links:
            links.append({
                "node_a_id": link.node1.node_id,
                "node_b_id": link.node2.node_id,
                "is_active": link.is_active
            })
            
        return {
            "nodes": nodes,
            "links": links
        }

    def set_node_status(self, node_id: str, is_active: bool) -> bool:
        node = self.topology.get_node_by_id(node_id)
        if node:
            if node.is_active != is_active:
                node.is_active = is_active
                event_type = "NODE_RECOVERED" if is_active else "NODE_FAILED"
                broadcaster.broadcast_sync(event_type, {"node_id": node_id})
            return True
        return False

    def set_link_status(self, node_a_id: str, node_b_id: str, is_active: bool) -> bool:
        for link in self.topology.links:
            if (link.node1.node_id == node_a_id and link.node2.node_id == node_b_id) or \
               (link.node1.node_id == node_b_id and link.node2.node_id == node_a_id):
                if link.is_active != is_active:
                    link.is_active = is_active
                    event_type = "LINK_RECOVERED" if is_active else "LINK_FAILED"
                    broadcaster.broadcast_sync(event_type, {
                        "node_a_id": node_a_id, 
                        "node_b_id": node_b_id
                    })
                return True
        return False

    def send_message(self, source_id: str, destination_id: str, message: str) -> dict:
        packet = Packet(source_id=source_id, destination_id=destination_id, payload=message)
        
        # Clear engine events before sending
        self.engine.events.clear()
        
        self.engine.send_packet(packet)
        
        return {
            "success": packet.status.name == "DELIVERED",
            "events": list(self.engine.events),
            "packet": {
                "packet_id": packet.packet_id,
                "source_id": packet.source_id,
                "destination_id": packet.destination_id,
                "packet_type": packet.packet_type.name,
                "status": packet.status.name,
                "hop_count": packet.hop_count,
                "route_history": packet.route_history,
                "sender_id": packet.sender_id,
                "payload": packet.payload
            }
        }

    def get_events(self) -> List[str]:
        return list(self.engine.events)

    def get_metrics(self) -> dict:
        return {
            "total_events": len(self.engine.events),
            "total_packets_pending": len(self.engine.pending_messages)
        }

# Global singleton instance
simulation_service = SimulationService()
