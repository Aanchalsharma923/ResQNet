import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Callable, Any, List

from resqnet.backend.app.models.packet import Packet, PacketStatus, PacketType
from resqnet.backend.app.routing.aodv_router import AODVRouter
from resqnet.backend.app.transport.udp_transport import UDPTransport
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link

logger = logging.getLogger(__name__)

class NodeRuntime:
    """
    Represents a single ResQNet node running as an independent process.
    Binds an AODVRouter to a UDPTransport.
    """
    def __init__(
        self,
        node_id: str,
        endpoint_config: Dict[str, Tuple[str, int]],
        topology_links: Optional[list[Tuple[str, str]]] = None,
        bind_host: str = "0.0.0.0",
        event_callback: Optional[Callable[[str, dict], None]] = None,
        event_host: str = "127.0.0.1",
        event_port: Optional[int] = None,
        control_port: Optional[int] = None
    ):
        self.node_id = node_id
        self.endpoint_config = endpoint_config
        self.topology_links = topology_links
        self.bind_host = bind_host
        self.event_callback = event_callback
        self.event_host = event_host
        self.event_port = event_port
        self.control_port = control_port
        self.is_running = False

        self._control_sock: Optional[socket.socket] = None
        self._control_thread: Optional[threading.Thread] = None

        # ACK tracking & deduplication state
        self._pending_acks: Dict[str, dict] = {}
        self._ack_timers: Dict[str, threading.Timer] = {}
        self._ack_lock = threading.Lock()
        self.processed_sos: Dict[str, dict] = {}

        # Build a virtual topology for the AODV router to query neighbors
        self.topology = self._build_virtual_topology()
        
        self.router = AODVRouter(self.node_id, self.topology)
        self.transport = UDPTransport(self.node_id, self.endpoint_config, bind_host=self.bind_host)
        self.transport.set_receive_callback(self._on_packet_received)

    def _build_virtual_topology(self) -> NetworkTopology:
        """
        Creates a NetworkTopology containing nodes so AODV can determine its active neighbors.
        """
        topology = NetworkTopology()
        
        # Add all nodes
        for nid in self.endpoint_config:
            ip = f"192.168.1.{ord(nid[0])}"  # Fake IP just for topology objects
            topology.add_node(Node(nid, ip))
            
        # Add standard links if nodes exist
        links_to_add = self.topology_links if self.topology_links is not None else [("A", "B"), ("A", "D"), ("B", "C"), ("C", "D"), ("C", "H")]
        for n1_id, n2_id in links_to_add:
            if n1_id in self.endpoint_config and n2_id in self.endpoint_config:
                node1 = topology.get_node_by_id(n1_id)
                node2 = topology.get_node_by_id(n2_id)
                topology.add_link(Link(node1, node2))
                
        return topology

    def _emit_event(self, event_type: str, data: Optional[dict] = None):
        """Dispatches structured events to the local callback and/or remote event port."""
        if data is None:
            data = {}
        data.setdefault("node_id", self.node_id)
        
        event_obj = {
            "event_id": str(uuid.uuid4()),
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }

        # 1. Local in-process callback
        if self.event_callback:
            try:
                self.event_callback(event_type, data)
            except Exception as e:
                logger.error(f"[{self.node_id}] Error in event_callback: {e}")

        # 2. Remote UDP event port (for IPC with dashboard/runtime manager)
        if self.event_port:
            try:
                msg = json.dumps(event_obj).encode("utf-8")
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.sendto(msg, (self.event_host, self.event_port))
                s.close()
            except Exception:
                pass

    def start(self):
        """Starts the transport and runtime."""
        if self.is_running:
            return
            
        logger.info(f"Starting ResQNet NodeRuntime [{self.node_id}]")
        self.transport.start()
        self.is_running = True
        
        from resqnet.backend.app.runtime.health_monitor import NeighborHealthMonitor
        
        my_node = self.topology.get_node_by_id(self.node_id)
        active_neighbors = [n.node_id for n in self.topology.get_active_neighbors(my_node.ip_address)]
        
        self.health_monitor = NeighborHealthMonitor(
            node_id=self.node_id,
            neighbors=set(active_neighbors),
            send_hello_callback=self._send_hello,
            failure_callback=self._on_neighbor_failure,
            heartbeat_interval=1.0,
            neighbor_timeout=3.0
        )
        self.health_monitor.start()

        # Start control port listener if configured
        if self.control_port:
            self._start_control_listener()
        
        configured_ip = self.endpoint_config[self.node_id][0]
        mode = "LOCALHOST" if configured_ip == "127.0.0.1" else "LAN"
        port = self.endpoint_config[self.node_id][1]
        
        banner = f"""
========================================
RESQNET NODE
========================================
Node ID: {self.node_id}
Transport: UDP
Bind: {self.bind_host}:{port}
Configured endpoint: {configured_ip}:{port}
Mode: {mode}
Neighbors: {', '.join(active_neighbors) if active_neighbors else 'None'}
Status: READY
========================================"""
        print(banner)
        logger.info(f"[{self.node_id}] Node is READY.")

        self._emit_event("NODE_STARTED", {
            "node_id": self.node_id,
            "endpoint": f"{configured_ip}:{port}",
            "mode": mode
        })
        self._emit_event("NODE_READY", {
            "node_id": self.node_id,
            "status": "READY"
        })

    def stop(self):
        # Cancel all active ACK timers and clear pending state unconditionally
        with self._ack_lock:
            for timer in self._ack_timers.values():
                try:
                    timer.cancel()
                except Exception:
                    pass
            self._ack_timers.clear()
            self._pending_acks.clear()

        if not self.is_running:
            return
            
        logger.info(f"Stopping ResQNet NodeRuntime [{self.node_id}]")
        self.is_running = False

        if hasattr(self, 'health_monitor'):
            self.health_monitor.stop()

        if self._control_sock:
            try:
                self._control_sock.close()
            except Exception:
                pass
            self._control_sock = None

        self.transport.stop()
        self._emit_event("NODE_STOPPED", {"node_id": self.node_id})

    def _start_control_listener(self):
        try:
            self._control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._control_sock.bind(("127.0.0.1", self.control_port))
            self._control_thread = threading.Thread(target=self._control_loop, daemon=True)
            self._control_thread.start()
            logger.info(f"[{self.node_id}] Command control listener active on 127.0.0.1:{self.control_port}")
        except Exception as e:
            logger.error(f"[{self.node_id}] Failed to bind control listener on {self.control_port}: {e}")

    def _control_loop(self):
        while self.is_running:
            try:
                data, _ = self._control_sock.recvfrom(4096)
                if not data:
                    break
                cmd = json.loads(data.decode("utf-8"))
                cmd_type = cmd.get("command")
                if cmd_type == "SEND_DATA":
                    self.send_data(cmd.get("destination_id"), cmd.get("payload"))
                elif cmd_type == "SEND_SOS":
                    self.send_sos(cmd.get("payload", {}))
                elif cmd_type == "STOP":
                    self.stop()
                    break
            except Exception:
                break

    def send_data(self, destination_id: str, payload: Any):
        """
        Manually inject a DATA packet originating from this node.
        """
        packet = Packet(
            source_id=self.node_id,
            destination_id=destination_id,
            payload=payload,
            packet_type=PacketType.DATA
        )
        self._emit_event("DATA_CREATED", {
            "packet_id": packet.packet_id,
            "source_id": self.node_id,
            "destination_id": destination_id,
            "hop_count": 0,
            "status": packet.status.name,
            "payload": payload if isinstance(payload, str) else str(payload)
        })
        self._process_packet(packet)

    def send_sos(self, sos_request: dict):
        """
        Sends an SOS distress message wrapped in a standard DATA packet and tracks return ACK.
        """
        message_id = sos_request.get("message_id") or str(uuid.uuid4())
        dest_id = sos_request.get("destination_id", "H")
        timeout_seconds = float(sos_request.get("timeout_seconds", 5.0))

        with self._ack_lock:
            self._pending_acks[message_id] = {
                "message_id": message_id,
                "source_id": self.node_id,
                "destination_id": dest_id,
                "status": "PENDING",
                "created_at": time.time(),
                "timeout_seconds": timeout_seconds,
                "confirmed_at": None,
                "rtt_ms": None
            }
            timer = threading.Timer(timeout_seconds, self._on_ack_timeout, args=[message_id])
            self._ack_timers[message_id] = timer
            timer.start()

        payload = {
            "type": "sos",
            "message_id": message_id,
            "message": sos_request.get("message", "HELP REQUIRED"),
            "latitude": sos_request.get("latitude", 18.5204),
            "longitude": sos_request.get("longitude", 73.8567),
            "priority": sos_request.get("priority", "HIGH")
        }
        self._emit_event("SOS_SENT", {
            "message_id": message_id,
            "source_id": self.node_id,
            "destination_id": dest_id,
            "message": payload["message"],
            "latitude": payload["latitude"],
            "longitude": payload["longitude"],
            "priority": payload["priority"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        self.send_data(dest_id, payload)
        return {
            "success": True,
            "message_id": message_id,
            "ack_status": "PENDING"
        }

    def _on_ack_timeout(self, message_id: str):
        with self._ack_lock:
            if message_id in self._pending_acks:
                record = self._pending_acks[message_id]
                if record["status"] == "PENDING":
                    record["status"] = "TIMEOUT"
                    if message_id in self._ack_timers:
                        del self._ack_timers[message_id]
                    self._emit_event("ACK_TIMEOUT", {
                        "message_id": message_id,
                        "source_id": self.node_id,
                        "hospital_id": record["destination_id"],
                        "timeout_sec": record["timeout_seconds"],
                        "status": "TIMEOUT"
                    })

    def get_sos_status(self, message_id: str) -> Optional[dict]:
        with self._ack_lock:
            return self._pending_acks.get(message_id)

    def get_pending_acks(self) -> Dict[str, dict]:
        with self._ack_lock:
            return dict(self._pending_acks)

    def _send_hello(self, neighbor_id: str):
        packet = Packet(
            source_id=self.node_id,
            destination_id=neighbor_id,
            payload={"msg": "HELLO"},
            packet_type=PacketType.HELLO,
            ttl=1
        )
        packet.sender_id = self.node_id
        self._emit_event("NEIGHBOR_HELLO_SENT", {
            "node_id": self.node_id,
            "neighbor_id": neighbor_id
        })
        self.transport.send(packet, [neighbor_id])
        
    def _on_neighbor_failure(self, neighbor_id: str):
        logger.info(f"[{self.node_id}] INVALIDATING ROUTE TO * VIA {neighbor_id}")
        self._emit_event("NEIGHBOR_DOWN", {
            "node_id": self.node_id,
            "neighbor_id": neighbor_id
        })
        self.router.handle_link_failure(neighbor_id)
        self._dispatch_generated_packets()

    def _on_packet_received(self, packet: Packet):
        """
        Callback invoked by UDPTransport when a datagram is received.
        """
        if packet.current_node != self.node_id:
            packet.move_to(self.node_id)
            
        if packet.status == PacketStatus.DROPPED:
            if packet.destination_id != self.node_id and packet.destination_id != "*":
                logger.warning(f"[{self.node_id}] Received packet dropped due to TTL or invalid move: {packet.packet_id}")
                self._emit_event("DATA_DROPPED", {
                    "packet_id": packet.packet_id,
                    "node_id": self.node_id,
                    "reason": "TTL_OR_INVALID_MOVE"
                })
                return
            
        self._process_packet(packet)

    def _translate_router_events(self, packet: Packet):
        """Translates AODVRouter raw event strings into standardized events."""
        if not hasattr(self.router, 'events') or not self.router.events:
            return
            
        for ev in list(self.router.events):
            logger.info(f"[{self.node_id}] EVENT: {ev} for packet {packet.packet_id}")
            if ev.startswith("ROUTE_INVALIDATED:"):
                parts = ev.replace("ROUTE_INVALIDATED: ", "").split(" ")
                data_map = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=")
                        data_map[k] = v
                dest = data_map.get("dest") or data_map.get("destination", "")
                self._emit_event("ROUTE_INVALIDATED", {
                    "node_id": self.node_id,
                    "destination": dest,
                    **data_map
                })
            elif ev.startswith("FORWARD_ROUTE_INSTALLED:"):
                parts = ev.replace("FORWARD_ROUTE_INSTALLED: ", "").split(" ")
                data_map = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=")
                        data_map[k] = v
                self._emit_event("FORWARD_ROUTE_INSTALLED", {
                    "node_id": self.node_id,
                    **data_map
                })
            elif ev.startswith("ROUTE_DISCOVERY_COMPLETED:"):
                parts = ev.replace("ROUTE_DISCOVERY_COMPLETED: ", "").split(" ")
                data_map = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=")
                        data_map[k] = v
                self._emit_event("ROUTE_DISCOVERY_COMPLETED", {
                    "node_id": self.node_id,
                    **data_map
                })
            elif ev.startswith("RERR_GENERATED:"):
                self._emit_event("RERR_GENERATED", {
                    "node_id": self.node_id,
                    "packet_id": packet.packet_id
                })
            elif ev.startswith("RREP_GENERATED:"):
                self._emit_event("RREP_GENERATED", {
                    "node_id": self.node_id,
                    "packet_id": packet.packet_id,
                    "source_id": packet.source_id,
                    "destination_id": packet.destination_id
                })
            elif ev.startswith("RREP_RECEIVED:"):
                self._emit_event("RREP_RECEIVED", {
                    "node_id": self.node_id,
                    "packet_id": packet.packet_id,
                    "source_id": packet.source_id,
                    "destination_id": packet.destination_id
                })
        self.router.events.clear()

    def _process_packet(self, packet: Packet):
        """
        Processes a packet using the AODV router and dispatches generated/forwarded packets.
        """
        if packet.packet_type == PacketType.HELLO:
            if hasattr(self, 'health_monitor') and packet.sender_id:
                # Check if this neighbor was down before recording hello
                was_down = self.health_monitor.is_down.get(packet.sender_id, False)
                self.health_monitor.record_hello(packet.sender_id)
                self._emit_event("NEIGHBOR_HELLO_RECEIVED", {
                    "node_id": self.node_id,
                    "neighbor_id": packet.sender_id
                })
                if was_down:
                    self._emit_event("NEIGHBOR_RECOVERED", {
                        "node_id": self.node_id,
                        "neighbor_id": packet.sender_id
                    })
            return

        # 1. Check if it's a DATA packet destined for us
        if packet.destination_id == self.node_id:
            if packet.packet_type == PacketType.DATA:
                packet.mark_delivered()
                logger.info(f"[{self.node_id}] PACKET DELIVERED: {packet.payload}")
                deliv_data = {
                    "packet_id": packet.packet_id,
                    "source_id": packet.source_id,
                    "destination_id": packet.destination_id,
                    "sender_id": packet.sender_id,
                    "current_node": self.node_id,
                    "hop_count": packet.hop_count,
                    "payload": packet.payload if isinstance(packet.payload, str) else str(packet.payload)
                }
                self._emit_event("DATA_DELIVERED", deliv_data)
                
                # Check for SOS payload delivery at Hospital-H
                if isinstance(packet.payload, dict) and packet.payload.get("type") == "sos":
                    msg_id = packet.payload.get("message_id")
                    is_dup = msg_id in self.processed_sos
                    if not is_dup:
                        self.processed_sos[msg_id] = {
                            "created_at": time.time(),
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
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        self._emit_event("SOS_DELIVERED", sos_entry)
                    else:
                        self.processed_sos[msg_id]["ack_count"] += 1
                        logger.info(f"[{self.node_id}] Duplicate SOS received for {msg_id}; retransmitting ACK")

                    # Hospital generates ACK DATA packet addressed to sender (packet.source_id)
                    ack_payload = {
                        "type": "ack",
                        "ack_for_message_id": msg_id,
                        "is_retransmit": is_dup,
                        "retransmit_count": self.processed_sos[msg_id]["ack_count"],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    self._emit_event("ACK_SENT", {
                        "message_id": msg_id,
                        "source_id": self.node_id,
                        "destination_id": packet.source_id,
                        "is_retransmit": is_dup
                    })
                    self.send_data(packet.source_id, ack_payload)
                    return

                # Check for ACK payload delivery at Rescue-A
                elif isinstance(packet.payload, dict) and packet.payload.get("type") == "ack":
                    is_valid, reason, msg_id = self._validate_ack_packet(packet)
                    if not is_valid:
                        logger.warning(f"[{self.node_id}] Rejected invalid ACK packet: reason={reason}")
                        self._emit_event("ACK_INVALID", {
                            "node_id": self.node_id,
                            "reason": reason,
                            "packet_id": packet.packet_id,
                            "source_id": packet.source_id
                        })
                        return

                    with self._ack_lock:
                        record = self._pending_acks.get(msg_id)
                        if not record:
                            self._emit_event("ACK_INVALID", {
                                "node_id": self.node_id,
                                "reason": "UNKNOWN_MESSAGE_ID",
                                "message_id": msg_id
                            })
                            return

                        curr_status = record["status"]
                        now = time.time()
                        if curr_status == "PENDING":
                            record["status"] = "CONFIRMED"
                            record["confirmed_at"] = now
                            rtt_ms = (now - record["created_at"]) * 1000
                            record["rtt_ms"] = rtt_ms
                            if msg_id in self._ack_timers:
                                self._ack_timers[msg_id].cancel()
                                del self._ack_timers[msg_id]
                            self._emit_event("ACK_RECEIVED", {
                                "message_id": msg_id,
                                "source_id": self.node_id,
                                "hospital_id": packet.source_id,
                                "rtt_ms": round(rtt_ms, 2),
                                "status": "CONFIRMED"
                            })
                        elif curr_status == "TIMEOUT":
                            record["status"] = "LATE_CONFIRMED"
                            record["late_confirmed_at"] = now
                            rtt_ms = (now - record["created_at"]) * 1000
                            record["rtt_ms"] = rtt_ms
                            self._emit_event("ACK_RECEIVED_LATE", {
                                "message_id": msg_id,
                                "source_id": self.node_id,
                                "hospital_id": packet.source_id,
                                "rtt_ms": round(rtt_ms, 2),
                                "status": "LATE_CONFIRMED"
                            })
                        elif curr_status in ("CONFIRMED", "LATE_CONFIRMED"):
                            self._emit_event("ACK_DUPLICATE_IGNORED", {
                                "message_id": msg_id,
                                "source_id": self.node_id,
                                "hospital_id": packet.source_id,
                                "status": curr_status
                            })
                return
            elif packet.packet_type == PacketType.RREQ:
                packet.mark_delivered()
                self._emit_event("RREQ_RECEIVED", {
                    "node_id": self.node_id,
                    "packet_id": packet.packet_id,
                    "source_id": packet.source_id,
                    "destination_id": packet.destination_id
                })
                
        # 2. Let router handle the packet
        next_hops = self.router.handle_packet(packet)
        
        # 3. Handle router events
        self._translate_router_events(packet)

        # 4. Handle newly generated packets (e.g. RREP, RERR, or RREQ)
        self._dispatch_generated_packets()
            
        # 5. Forward original packet if requested
        if next_hops:
            packet.sender_id = self.node_id
            for nh in next_hops:
                if packet.packet_type == PacketType.RREQ:
                    self._emit_event("RREQ_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id,
                        "source_id": packet.source_id,
                        "destination_id": packet.destination_id
                    })
                elif packet.packet_type == PacketType.RREP:
                    self._emit_event("RREP_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id
                    })
                elif packet.packet_type == PacketType.RERR:
                    self._emit_event("RERR_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id
                    })
                elif packet.packet_type == PacketType.DATA:
                    self._emit_event("DATA_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id
                    })
            self.transport.send(packet, next_hops)
        else:
            if packet.packet_type == PacketType.DATA and packet.status != PacketStatus.DELIVERED:
                packet.mark_dropped()
                logger.warning(f"[{self.node_id}] DATA packet dropped: no next hop to {packet.destination_id}")
                self._emit_event("DATA_DROPPED", {
                    "packet_id": packet.packet_id,
                    "node_id": self.node_id,
                    "source_id": packet.source_id,
                    "destination_id": packet.destination_id,
                    "reason": "NO_ROUTE_AVAILABLE"
                })
            
    def _dispatch_generated_packets(self):
        if hasattr(self.router, 'generated_packets') and self.router.generated_packets:
            new_packets = list(self.router.generated_packets)
            self.router.generated_packets.clear()
            for new_packet in new_packets:
                self._dispatch_packet(new_packet)
            
    def _dispatch_packet(self, packet: Packet):
        """
        Sends a newly generated packet by processing it locally to determine next hops.
        """
        if packet.packet_type == PacketType.RREQ:
            self._emit_event("RREQ_GENERATED", {
                "node_id": self.node_id,
                "packet_id": packet.packet_id,
                "source_id": packet.source_id,
                "destination_id": packet.destination_id
            })
            
        next_hops = self.router.handle_packet(packet)
        self._translate_router_events(packet)
        
        # In case processing it generated more packets (rare, but possible)
        if hasattr(self.router, 'generated_packets') and self.router.generated_packets:
            new_packets = list(self.router.generated_packets)
            self.router.generated_packets.clear()
            for new_packet in new_packets:
                self._dispatch_packet(new_packet)
            
        if next_hops:
            packet.sender_id = self.node_id
            for nh in next_hops:
                if packet.packet_type == PacketType.RREQ:
                    self._emit_event("RREQ_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id,
                        "source_id": packet.source_id,
                        "destination_id": packet.destination_id
                    })
                elif packet.packet_type == PacketType.RREP:
                    self._emit_event("RREP_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id
                    })
                elif packet.packet_type == PacketType.DATA:
                    self._emit_event("DATA_FORWARDED", {
                        "node_id": self.node_id,
                        "from_node": self.node_id,
                        "to_node": nh,
                        "packet_id": packet.packet_id
                    })
            self.transport.send(packet, next_hops)

    def _validate_ack_packet(self, packet: Packet) -> Tuple[bool, str, Optional[str]]:
        """
        Validates that an ACK received at Rescue-A conforms to all protocol requirements:
        1. packet_type is DATA
        2. destination_id is self.node_id
        3. source_id is 'H'
        4. payload is dict with type == 'ack'
        5. ack_for_message_id is non-empty string
        6. ack_for_message_id matches an SOS previously initiated by this node
        """
        if packet.packet_type != PacketType.DATA:
            return False, "PACKET_TYPE_NOT_DATA", None
        if packet.destination_id != self.node_id:
            return False, "DESTINATION_NOT_ME", None
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

