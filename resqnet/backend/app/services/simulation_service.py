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
        self.hospital_inbox = []
        
        # Metrics Tracking
        self.metrics = {
            "packets_sent": 0,
            "packets_delivered": 0,
            "packets_dropped": 0,
            "total_hop_count": 0,
            "rreq_count": 0,
            "rrep_count": 0,
            "rerr_count": 0
        }
        
        self._setup_default_network()

    def _setup_default_network(self):
        # 1. Construct Topology
        self.topology = NetworkTopology()
        nodes = {
            "A": Node("A", "192.168.1.10", latitude=18.5204, longitude=73.8567),
            "B": Node("B", "192.168.1.11", latitude=18.5210, longitude=73.8580),
            "C": Node("C", "192.168.1.12", latitude=18.5220, longitude=73.8600),
            "D": Node("D", "192.168.1.13", latitude=18.5190, longitude=73.8585),
            "H": Node("H", "192.168.1.14", latitude=18.5230, longitude=73.8620),
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
        broadcaster.broadcast_sync("INITIAL_STATE", self.get_network_state())

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
            if event_type == "DATA_DELIVERED" and packet.destination_id == "H":
                if isinstance(packet.payload, dict) and packet.payload.get("type") == "sos":
                    import datetime
                    sos_entry = {
                        "message_id": packet.payload.get("message_id"),
                        "source_id": packet.source_id,
                        "destination_id": packet.destination_id,
                        "message": packet.payload.get("message"),
                        "latitude": packet.payload.get("latitude"),
                        "longitude": packet.payload.get("longitude"),
                        "priority": packet.payload.get("priority"),
                        "status": "DELIVERED",
                        "packet_id": packet.packet_id,
                        "hop_count": packet.hop_count,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    self.hospital_inbox.append(sos_entry)
                    data["sos_data"] = sos_entry
                    broadcaster.broadcast_sync("SOS_DELIVERED", sos_entry)
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
        elif event_str.startswith("RREP_GENERATED:"):
            event_type = "RREP_GENERATED"
            parts = event_str.replace("RREP_GENERATED: ", "").split(" ")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=")
                    data[k] = v
        elif event_str.startswith("RREP_RECEIVED:"):
            event_type = "RREP_RECEIVED"
            parts = event_str.replace("RREP_RECEIVED: ", "").split(" ")
            for part in parts:
                if "=" in part:
                    k, v = part.split("=")
                    data[k] = v

        if event_type == "DATA_CREATED":
            self.metrics["packets_sent"] += 1
        elif event_type == "DATA_DELIVERED":
            self.metrics["packets_delivered"] += 1
            if packet:
                self.metrics["total_hop_count"] += packet.hop_count
        elif event_type == "DATA_DROPPED":
            self.metrics["packets_dropped"] += 1
        elif event_type == "RREQ_GENERATED":
            self.metrics["rreq_count"] += 1
        elif event_type == "RREP_GENERATED":
            self.metrics["rrep_count"] += 1
        elif event_type == "RERR_GENERATED":
            self.metrics["rerr_count"] += 1

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
                "is_active": node.is_active,
                "latitude": node.latitude,
                "longitude": node.longitude
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

    def send_sos(self, sos_request: dict) -> dict:
        import uuid
        import datetime
        message_id = str(uuid.uuid4())
        payload = {
            "type": "sos",
            "message_id": message_id,
            "message": sos_request.get("message"),
            "latitude": sos_request.get("latitude"),
            "longitude": sos_request.get("longitude"),
            "priority": sos_request.get("priority")
        }
        
        # We also want to emit an SOS_SENT event
        broadcaster.broadcast_sync("SOS_SENT", {
            "message_id": message_id,
            "source_id": sos_request.get("source_id"),
            "destination_id": sos_request.get("destination_id"),
            "message": sos_request.get("message"),
            "latitude": sos_request.get("latitude"),
            "longitude": sos_request.get("longitude"),
            "priority": sos_request.get("priority"),
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        result = self.send_message(
            sos_request.get("source_id"), 
            sos_request.get("destination_id"), 
            payload
        )
        if not result["success"]:
            broadcaster.broadcast_sync("SOS_FAILED", {
                "message_id": message_id,
                "status": "FAILED",
                "source_id": sos_request.get("source_id"),
                "destination_id": sos_request.get("destination_id")
            })
        return result

    def get_hospital_inbox(self) -> List[dict]:
        return self.hospital_inbox

    def get_events(self) -> List[str]:
        return list(self.engine.events)

    def get_metrics(self) -> dict:
        pdr = "0%"
        if self.metrics["packets_sent"] > 0:
            pdr = f"{(self.metrics['packets_delivered'] / self.metrics['packets_sent']) * 100:.1f}%"
            
        loss = "0%"
        if self.metrics["packets_sent"] > 0:
            loss = f"{(self.metrics['packets_dropped'] / self.metrics['packets_sent']) * 100:.1f}%"
            
        avg_hops = "0"
        if self.metrics["packets_delivered"] > 0:
            avg_hops = f"{(self.metrics['total_hop_count'] / self.metrics['packets_delivered']):.1f}"

        return {
            "packets_sent": self.metrics["packets_sent"],
            "packets_delivered": self.metrics["packets_delivered"],
            "packets_dropped": self.metrics["packets_dropped"],
            "pdr": pdr,
            "loss": loss,
            "avg_hop_count": avg_hops,
            "rreq_count": self.metrics["rreq_count"],
            "rrep_count": self.metrics["rrep_count"],
            "rerr_count": self.metrics["rerr_count"],
            "route_discovery_time": "N/A",
            "recovery_time": "N/A",
            "latency": "N/A",
            "throughput": "N/A"
        }

# Global singleton instance
simulation_service = SimulationService()
