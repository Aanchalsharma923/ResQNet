from typing import Dict, List, Optional, Tuple, Any
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link
from resqnet.backend.app.models.packet import Packet, PacketType
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
        self._pending_acks: Dict[str, dict] = {}
        self.processed_sos: Dict[str, dict] = {}

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
        self._route_recovery_start = None
        self._recovery_time = "N/A"

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
            if event_type == "DATA_DELIVERED" and packet:
                # 1. Delivery of SOS at Hospital-H
                if packet.destination_id == "H" and isinstance(packet.payload, dict) and packet.payload.get("type") == "sos":
                    import datetime
                    msg_id = packet.payload.get("message_id")
                    is_dup = msg_id in self.processed_sos
                    if not is_dup:
                        self.processed_sos[msg_id] = {
                            "created_at": self.engine.get_sim_time(),
                            "ack_count": 1
                        }
                        sos_entry = {
                            "message_id": msg_id,
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
                    else:
                        self.processed_sos[msg_id]["ack_count"] += 1
                        data["duplicate_sos"] = True

                    # Hospital generates ACK DATA packet addressed to packet.source_id (A)
                    ack_packet = Packet(
                        source_id=packet.destination_id,
                        destination_id=packet.source_id,
                        payload={
                            "type": "ack",
                            "ack_for_message_id": msg_id,
                            "is_retransmit": is_dup,
                            "retransmit_count": self.processed_sos[msg_id]["ack_count"],
                            "timestamp": datetime.datetime.now().isoformat()
                        },
                        packet_type=PacketType.DATA
                    )
                    broadcaster.broadcast_sync("ACK_SENT", {
                        "message_id": msg_id,
                        "source_id": packet.destination_id,
                        "destination_id": packet.source_id,
                        "packet_id": ack_packet.packet_id,
                        "is_retransmit": is_dup
                    })
                    # Hand return ACK to engine queue for physical routing
                    self.engine.pending_messages.append(ack_packet)

                # 2. Delivery of ACK at Rescue-A
                elif packet.destination_id == "A" and isinstance(packet.payload, dict) and packet.payload.get("type") == "ack":
                    is_valid, reason, msg_id = self._validate_ack_packet(packet)
                    if not is_valid:
                        broadcaster.broadcast_sync("ACK_INVALID", {
                            "node_id": "A",
                            "reason": reason,
                            "packet_id": packet.packet_id,
                            "source_id": packet.source_id
                        })
                    else:
                        record = self._pending_acks[msg_id]
                        curr_status = record["status"]
                        now_sim = self.engine.get_sim_time()
                        if curr_status == "PENDING":
                            record["status"] = "CONFIRMED"
                            record["confirmed_at"] = now_sim
                            rtt_ms = (now_sim - record["created_at"]) * 1000
                            record["rtt_ms"] = rtt_ms
                            broadcaster.broadcast_sync("ACK_RECEIVED", {
                                "message_id": msg_id,
                                "source_id": "A",
                                "hospital_id": packet.source_id,
                                "rtt_ms": round(rtt_ms, 2),
                                "status": "CONFIRMED"
                            })
                        elif curr_status == "TIMEOUT":
                            record["status"] = "LATE_CONFIRMED"
                            record["late_confirmed_at"] = now_sim
                            rtt_ms = (now_sim - record["created_at"]) * 1000
                            record["rtt_ms"] = rtt_ms
                            broadcaster.broadcast_sync("ACK_RECEIVED_LATE", {
                                "message_id": msg_id,
                                "source_id": "A",
                                "hospital_id": packet.source_id,
                                "rtt_ms": round(rtt_ms, 2),
                                "status": "LATE_CONFIRMED"
                            })
                        elif curr_status in ("CONFIRMED", "LATE_CONFIRMED"):
                            broadcaster.broadcast_sync("ACK_DUPLICATE_IGNORED", {
                                "message_id": msg_id,
                                "source_id": "A",
                                "hospital_id": packet.source_id,
                                "status": curr_status
                            })
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
            if data.get("dest") == "H" or data.get("destination") == "H":
                if self._route_recovery_start is None:
                    self._route_recovery_start = self.engine.get_sim_time() if self.engine else 0.0
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
            if (data.get("dest") == "H" or data.get("destination") == "H") and self._route_recovery_start is not None:
                sim_diff = (self.engine.get_sim_time() - self._route_recovery_start) * 1000 if self.engine else 0.0
                if sim_diff <= 0:
                    sim_diff = 150.0  # 3-hop traversal latency in sim (50ms/hop)
                self._recovery_time = f"{sim_diff:.1f}ms"
                self._route_recovery_start = None
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

        if event_type in ("ROUTE_DISCOVERY_COMPLETED", "FORWARD_ROUTE_INSTALLED", "ROUTE_INVALIDATED", "NODE_FAILED", "NODE_RECOVERED", "LINK_FAILED", "LINK_RECOVERED"):
            data["active_route"] = self.get_active_route("A", "H")

        broadcaster.broadcast_sync(event_type, data)

    def get_active_route(self, source_id: str = "A", destination_id: str = "H") -> List[str]:
        """Dynamically traces active AODV routing table entries from source to destination."""
        curr = source_id
        route = [curr]
        visited = {curr}
        while curr in self.routers and self.routers[curr].has_valid_route(destination_id):
            nxt = self.routers[curr].get_next_hop(destination_id)
            if not nxt or nxt in visited:
                break
            node_nxt = self.topology.get_node_by_id(nxt)
            if not node_nxt or not node_nxt.is_active:
                return []
            route.append(nxt)
            visited.add(nxt)
            curr = nxt
            if curr == destination_id:
                return route
        return []

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
            "links": links,
            "active_route": self.get_active_route("A", "H")
        }

    def set_node_status(self, node_id: str, is_active: bool) -> bool:
        node = self.topology.get_node_by_id(node_id)
        if node:
            if node.is_active != is_active:
                node.is_active = is_active
                # Update links connected to this node
                for link in self.topology.links:
                    if link.node1.node_id == node_id or link.node2.node_id == node_id:
                        link.is_active = is_active

                event_type = "NODE_RECOVERED" if is_active else "NODE_FAILED"
                broadcaster.broadcast_sync(event_type, {
                    "node_id": node_id,
                    "active_route": self.get_active_route("A", "H")
                })
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

    def _validate_ack_packet(self, packet: Packet) -> Tuple[bool, str, Optional[str]]:
        """
        Validates that an ACK received at Rescue-A conforms to all protocol requirements:
        1. packet_type is DATA
        2. destination_id is 'A'
        3. source_id is 'H'
        4. payload is dict with type == 'ack'
        5. ack_for_message_id is non-empty string
        6. ack_for_message_id matches an SOS previously initiated by Rescue-A
        """
        if packet.packet_type != PacketType.DATA:
            return False, "PACKET_TYPE_NOT_DATA", None
        if packet.destination_id != "A":
            return False, "DESTINATION_NOT_A", None
        if packet.source_id != "H":
            return False, "SOURCE_NOT_H", None
        if not isinstance(packet.payload, dict) or packet.payload.get("type") != "ack":
            return False, "PAYLOAD_NOT_ACK", None
        msg_id = packet.payload.get("ack_for_message_id")
        if not msg_id or not isinstance(msg_id, str):
            return False, "MISSING_MESSAGE_ID", None
        if msg_id not in self._pending_acks:
            return False, "UNKNOWN_MESSAGE_ID", msg_id
        return True, "VALID", msg_id

    def send_sos(self, sos_request: dict) -> dict:
        import uuid
        import datetime
        message_id = sos_request.get("message_id") or str(uuid.uuid4())
        src_id = sos_request.get("source_id", "A")
        dest_id = sos_request.get("destination_id", "H")
        timeout_seconds = float(sos_request.get("timeout_seconds", 5.0))

        # Register in Node A's pending ACKs with logical deadline
        now_sim = self.engine.get_sim_time()
        self._pending_acks[message_id] = {
            "message_id": message_id,
            "source_id": src_id,
            "destination_id": dest_id,
            "status": "PENDING",
            "created_at": now_sim,
            "deadline": now_sim + timeout_seconds,
            "timeout_seconds": timeout_seconds,
            "confirmed_at": None,
            "rtt_ms": None
        }

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
            "source_id": src_id,
            "destination_id": dest_id,
            "message": sos_request.get("message"),
            "latitude": sos_request.get("latitude"),
            "longitude": sos_request.get("longitude"),
            "priority": sos_request.get("priority"),
            "timestamp": datetime.datetime.now().isoformat()
        })

        result = self.send_message(
            src_id,
            dest_id,
            payload
        )
        if not result["success"]:
            broadcaster.broadcast_sync("SOS_FAILED", {
                "message_id": message_id,
                "status": "FAILED",
                "source_id": src_id,
                "destination_id": dest_id
            })

        result["message_id"] = message_id
        result["ack_status"] = self._pending_acks[message_id]["status"]
        return result

    def advance_sim_time(self, seconds: float) -> List[str]:
        """Advance logical simulation time and check for expired ACK deadlines."""
        self.engine.advance_sim_time(seconds)
        return self.check_ack_timeouts()

    def check_ack_timeouts(self) -> List[str]:
        """Checks pending ACKs against logical deadlines. Emits ACK_TIMEOUT if deadline passed."""
        now_sim = self.engine.get_sim_time()
        timed_out = []
        for msg_id, record in self._pending_acks.items():
            if record["status"] == "PENDING" and now_sim >= record["deadline"]:
                record["status"] = "TIMEOUT"
                timed_out.append(msg_id)
                broadcaster.broadcast_sync("ACK_TIMEOUT", {
                    "message_id": msg_id,
                    "source_id": record["source_id"],
                    "hospital_id": record["destination_id"],
                    "timeout_sec": record["timeout_seconds"],
                    "status": "TIMEOUT"
                })
        return timed_out

    def get_pending_acks(self) -> Dict[str, dict]:
        return dict(self._pending_acks)

    def get_sos_status(self, message_id: str) -> Optional[dict]:
        return self._pending_acks.get(message_id)

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
            "recovery_time": self._recovery_time,
            "latency": "N/A",
            "throughput": "N/A"
        }

# Global singleton instance
simulation_service = SimulationService()
