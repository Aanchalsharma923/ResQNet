import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from resqnet.backend.app.services.broadcaster import broadcaster

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../configs/localhost_nodes.json")
)

NODE_COORDINATES = {
    "A": (18.5204, 73.8567),
    "B": (18.5210, 73.8580),
    "C": (18.5220, 73.8600),
    "D": (18.5190, 73.8585),
    "H": (18.5230, 73.8620),
}

DEFAULT_LINKS = [
    ("A", "B"),
    ("A", "D"),
    ("B", "C"),
    ("C", "D"),
    ("C", "H")
]

class RealNetworkRuntime:
    """
    Manages real independent node processes over UDP/LAN.
    Acts as an event bridge between real node processes and the FastAPI broadcaster.
    Does NOT perform routing; routing is exclusively performed by AODV within each node.
    """
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH, event_port: int = 50099):
        self.config_path = config_path
        self.event_port = event_port
        self.processes: Dict[str, subprocess.Popen] = {}
        self.is_running = False
        
        self.event_listener_sock: Optional[socket.socket] = None
        self.event_listener_thread: Optional[threading.Thread] = None
        
        self.endpoint_config: Dict[str, Tuple[str, int]] = {}
        self.control_ports: Dict[str, int] = {}
        self.node_status: Dict[str, bool] = {}
        self.active_route: List[str] = []
        self.neighbor_health: Dict[str, Dict[str, str]] = {}
        self.hospital_inbox: List[dict] = []
        self.recent_events: List[str] = []
        
        # Metrics tracking
        self.metrics = {
            "packets_sent": 0,
            "packets_delivered": 0,
            "packets_dropped": 0,
            "total_hop_count": 0,
            "rreq_count": 0,
            "rrep_count": 0,
            "rerr_count": 0,
            "route_discovery_time": "N/A",
            "recovery_time": "N/A",
            "latency": "N/A",
            "throughput": "N/A"
        }
        
        self._route_discovery_start: Optional[float] = None
        self._route_recovery_start: Optional[float] = None
        self._packet_send_times: Dict[str, float] = {}
        self._delivered_latencies: List[float] = []
        self._delivered_bytes: int = 0
        self._total_transit_time: float = 0.0

        self._routing_entries: Dict[str, Dict[str, str]] = {}
        self.topology_links = DEFAULT_LINKS
        self._load_config()

    def _recalculate_active_route(self, source_id: str = "A", destination_id: str = "H"):
        """
        Dynamically reconstructs the end-to-end path solely from actual
        distributed AODV routing table entries reported by nodes.
        Does NOT invent hops, infer paths from topological connectivity, or guess.
        """
        curr = source_id
        route = [curr]
        visited = {curr}
        while curr in self._routing_entries and destination_id in self._routing_entries[curr]:
            nxt = self._routing_entries[curr][destination_id]
            if not nxt or nxt in visited:
                break

            # Verify that curr and nxt are valid configured neighbors
            is_valid_neighbor = any(
                (link[0] == curr and link[1] == nxt) or (link[1] == curr and link[0] == nxt)
                for link in self.topology_links
            )
            if not is_valid_neighbor:
                logger.warning(f"Rejecting invalid hop {curr} -> {nxt}: not configured neighbors")
                break

            route.append(nxt)
            visited.add(nxt)
            curr = nxt
            if curr == destination_id:
                self.active_route = route
                return

        # If destination could not be reached through valid AODV routing entries
        self.active_route = []

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                raw = json.load(f)
            nodes = raw["nodes"] if "nodes" in raw else raw
            self.endpoint_config = {k: (v["host"], v["port"]) for k, v in nodes.items()}
            # Derive control port as port + 1000
            self.control_ports = {k: v[1] + 1000 for k, v in self.endpoint_config.items()}
            for k in self.endpoint_config:
                self.node_status[k] = False
                self.neighbor_health[k] = {}
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")

    def start(self):
        """Starts the event bridge and launches all configured node processes."""
        if self.is_running:
            return
        logger.info("Starting RealNetworkRuntime...")
        self.is_running = True
        
        # 1. Start event listener
        self._start_event_listener()
        
        # 2. Launch child processes for all nodes
        for node_id in self.endpoint_config:
            self.start_node(node_id)
            
        logger.info("RealNetworkRuntime started.")

    def stop(self):
        """Stops all running node processes and shuts down the event listener."""
        if not self.is_running:
            return
        logger.info("Stopping RealNetworkRuntime...")
        self.is_running = False
        
        # Stop all node processes
        for node_id in list(self.processes.keys()):
            self.stop_node(node_id)
            
        # Stop event listener socket
        if self.event_listener_sock:
            try:
                self.event_listener_sock.close()
            except Exception:
                pass
            self.event_listener_sock = None
            
        logger.info("RealNetworkRuntime stopped.")

    def reset(self):
        """Resets application state, metrics, and restarts all nodes."""
        logger.info("Resetting RealNetworkRuntime...")
        self.stop()
        self.hospital_inbox.clear()
        self.recent_events.clear()
        self.active_route.clear()
        self._routing_entries.clear()
        self._delivered_latencies.clear()
        self._delivered_bytes = 0
        self._total_transit_time = 0.0
        self._route_discovery_start = None
        self._route_recovery_start = None
        self._packet_send_times.clear()
        self.metrics = {
            "packets_sent": 0,
            "packets_delivered": 0,
            "packets_dropped": 0,
            "total_hop_count": 0,
            "rreq_count": 0,
            "rrep_count": 0,
            "rerr_count": 0,
            "route_discovery_time": "N/A",
            "recovery_time": "N/A",
            "latency": "N/A",
            "throughput": "N/A"
        }
        self.start()
        broadcaster.broadcast_sync("SIMULATION_RESET", self.get_network_state())

    def start_node(self, node_id: str) -> bool:
        """Launches a node as an independent process."""
        if node_id not in self.endpoint_config:
            logger.error(f"Cannot start unknown node {node_id}")
            return False
            
        if node_id in self.processes and self.processes[node_id].poll() is None:
            logger.info(f"Node {node_id} is already running.")
            return True
            
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../../scripts/run_node.py")
        )
        ctrl_port = self.control_ports.get(node_id, 51010)
        cmd = [
            sys.executable,
            script_path,
            "--node-id", node_id,
            "--config", self.config_path,
            "--event-host", "127.0.0.1",
            "--event-port", str(self.event_port),
            "--control-port", str(ctrl_port)
        ]
        
        try:
            logger.info(f"Launching process for node {node_id}: {' '.join(cmd)}")
            p = subprocess.Popen(cmd)
            self.processes[node_id] = p
            self.node_status[node_id] = True
            
            broadcaster.broadcast_sync("NODE_RECOVERED", {"node_id": node_id})
            return True
        except Exception as e:
            logger.error(f"Failed to launch node {node_id}: {e}")
            return False

    def stop_node(self, node_id: str) -> bool:
        """Stops the real process for the specified node."""
        if node_id not in self.processes:
            self.node_status[node_id] = False
            return False
            
        p = self.processes[node_id]
        if p.poll() is None:
            logger.info(f"Terminating process for node {node_id} (PID: {p.pid})...")
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                
        del self.processes[node_id]
        self.node_status[node_id] = False
        
        was_in_active_route = (node_id in self.active_route)

        # Purge routing entries originating from or pointing to this stopped node
        if node_id in self._routing_entries:
            self._routing_entries[node_id].clear()
        for n, d_map in self._routing_entries.items():
            to_del = [d for d, nh in d_map.items() if nh == node_id]
            for d in to_del:
                del d_map[d]
        self._recalculate_active_route("A", "H")

        # If this node was in active route, invalidate the route
        if was_in_active_route:
            self.active_route.clear()
            if self._route_recovery_start is None:
                self._route_recovery_start = time.time()
            broadcaster.broadcast_sync("ROUTE_INVALIDATED", {"invalidated_node": node_id})
            
        broadcaster.broadcast_sync("NODE_FAILED", {"node_id": node_id})
        return True

    def _start_event_listener(self):
        """Starts the UDP event socket listener on 127.0.0.1:<event_port>."""
        try:
            self.event_listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.event_listener_sock.bind(("127.0.0.1", self.event_port))
            self.event_listener_thread = threading.Thread(target=self._event_listener_loop, daemon=True)
            self.event_listener_thread.start()
            logger.info(f"Event listener bound to 127.0.0.1:{self.event_port}")
        except Exception as e:
            logger.error(f"Failed to start event listener on port {self.event_port}: {e}")

    def _event_listener_loop(self):
        while self.is_running:
            try:
                if not self.event_listener_sock:
                    break
                data, _ = self.event_listener_sock.recvfrom(65535)
                if not data:
                    break
                raw_str = data.decode("utf-8")
                event = json.loads(raw_str)
                self._handle_incoming_event(event)
            except Exception:
                if not self.is_running:
                    break

    def _handle_incoming_event(self, event: dict):
        """Processes structured events received from node processes and broadcasts them."""
        event_type = event.get("type", "UNKNOWN")
        data = event.get("data", {})
        
        # Log recent event
        self.recent_events.append(f"[{data.get('node_id', '?')}] {event_type}")
        if len(self.recent_events) > 200:
            self.recent_events.pop(0)

        # 1. Update Metrics & Route Tracking
        if event_type == "DATA_CREATED":
            self.metrics["packets_sent"] += 1
            pkt_id = data.get("packet_id")
            if pkt_id:
                self._packet_send_times[pkt_id] = time.time()
                
        elif event_type == "DATA_DELIVERED":
            self.metrics["packets_delivered"] += 1
            self.metrics["total_hop_count"] += data.get("hop_count", 0)
            pkt_id = data.get("packet_id")
            if pkt_id and pkt_id in self._packet_send_times:
                lat = (time.time() - self._packet_send_times[pkt_id]) * 1000
                self._delivered_latencies.append(lat)
                avg_lat = sum(self._delivered_latencies) / len(self._delivered_latencies)
                self.metrics["latency"] = f"{avg_lat:.1f}ms"
                
                payload = data.get("payload", "")
                payload_bytes = len(payload.encode("utf-8")) if isinstance(payload, str) else len(str(payload).encode("utf-8"))
                self._delivered_bytes += payload_bytes
                self._total_transit_time += (lat / 1000.0)
                if self._total_transit_time > 0:
                    throughput_kbps = (self._delivered_bytes * 8) / (self._total_transit_time * 1000)
                    self.metrics["throughput"] = f"{throughput_kbps:.1f} kbps"
                
        elif event_type == "DATA_DROPPED":
            self.metrics["packets_dropped"] += 1
            
        elif event_type == "RREQ_GENERATED":
            self.metrics["rreq_count"] += 1
            if self._route_discovery_start is None:
                self._route_discovery_start = time.time()
                
        elif event_type == "RREP_GENERATED":
            self.metrics["rrep_count"] += 1
            
        elif event_type == "RERR_GENERATED":
            self.metrics["rerr_count"] += 1
            
        elif event_type in ("FORWARD_ROUTE_INSTALLED", "ROUTE_DISCOVERY_COMPLETED"):
            nid = data.get("node_id")
            dest = data.get("dest") or data.get("destination")
            nxt = data.get("next") or data.get("next_hop")
            if nid and dest and nxt:
                if nid not in self._routing_entries:
                    self._routing_entries[nid] = {}
                self._routing_entries[nid][dest] = nxt
                self._recalculate_active_route("A", dest)

            if event_type == "ROUTE_DISCOVERY_COMPLETED":
                if self._route_discovery_start is not None:
                    duration = (time.time() - self._route_discovery_start) * 1000
                    self.metrics["route_discovery_time"] = f"{duration:.1f}ms"
                    self._route_discovery_start = None
                if self._route_recovery_start is not None:
                    rec_duration = (time.time() - self._route_recovery_start) * 1000
                    self.metrics["recovery_time"] = f"{rec_duration:.1f}ms"
                    self._route_recovery_start = None

        elif event_type == "ROUTE_INVALIDATED":
            nid = data.get("node_id")
            dest = data.get("dest") or data.get("destination")
            if nid and nid in self._routing_entries and dest in self._routing_entries[nid]:
                del self._routing_entries[nid][dest]
            if dest == "H":
                self.active_route.clear()
                if self._route_recovery_start is None:
                    self._route_recovery_start = time.time()

        elif event_type == "NEIGHBOR_DOWN":
            nid = data.get("node_id")
            neighbor = data.get("neighbor_id")
            if nid and neighbor:
                if nid not in self.neighbor_health:
                    self.neighbor_health[nid] = {}
                self.neighbor_health[nid][neighbor] = "DOWN"
                
            # Purge routing entries involving this down neighbor
            had_route_via_neighbor = (neighbor in self.active_route)
            if neighbor in self._routing_entries:
                self._routing_entries[neighbor].clear()
            for n, d_map in self._routing_entries.items():
                to_del = [d for d, nh in d_map.items() if nh == neighbor]
                if to_del:
                    had_route_via_neighbor = True
                for d in to_del:
                    del d_map[d]

            if had_route_via_neighbor:
                self.active_route.clear()
                if self._route_recovery_start is None:
                    self._route_recovery_start = time.time()
                
        elif event_type == "NEIGHBOR_RECOVERED":
            nid = data.get("node_id")
            neighbor = data.get("neighbor_id")
            if nid and neighbor:
                if nid not in self.neighbor_health:
                    self.neighbor_health[nid] = {}
                self.neighbor_health[nid][neighbor] = "UP"
                
        elif event_type == "SOS_DELIVERED":
            msg_id = data.get("message_id")
            if not msg_id or not any(x.get("message_id") == msg_id for x in self.hospital_inbox):
                self.hospital_inbox.append(data)
            
        elif event_type == "DATA_FORWARDED":
            pass  # Animation event, does not alter routing state

        # Attach authoritative active route to route-related events
        if event_type in ("ROUTE_DISCOVERY_COMPLETED", "FORWARD_ROUTE_INSTALLED", "ROUTE_INVALIDATED", "NEIGHBOR_DOWN"):
            data["active_route"] = list(self.active_route)

        # 2. Forward to WebSocket broadcaster
        broadcaster.broadcast_sync(event_type, data)

    def send_message(self, source_id: str, destination_id: str, message: Any) -> dict:
        """Sends command to the source node's control port to dispatch a DATA packet."""
        if source_id not in self.control_ports:
            return {"success": False, "detail": f"Unknown source node {source_id}"}
            
        ctrl_port = self.control_ports[source_id]
        cmd = {
            "command": "SEND_DATA",
            "destination_id": destination_id,
            "payload": message
        }
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(json.dumps(cmd).encode("utf-8"), ("127.0.0.1", ctrl_port))
            s.close()
            return {"success": True, "source": source_id, "destination": destination_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_sos(self, sos_request: dict) -> dict:
        """Sends command to the source node's control port to dispatch an SOS packet."""
        src_id = sos_request.get("source_id", "A")
        if src_id not in self.control_ports:
            return {"success": False, "detail": f"Unknown source node {src_id}"}
            
        ctrl_port = self.control_ports[src_id]
        cmd = {
            "command": "SEND_SOS",
            "payload": sos_request
        }
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(json.dumps(cmd).encode("utf-8"), ("127.0.0.1", ctrl_port))
            s.close()
            return {"success": True, "source": src_id, "destination": sos_request.get("destination_id", "H")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_network_state(self) -> dict:
        """Exposes the real-network state for REST and WebSocket INITIAL_STATE."""
        nodes = []
        for nid, (host, port) in self.endpoint_config.items():
            is_proc_alive = (nid in self.processes and self.processes[nid].poll() is None)
            coords = NODE_COORDINATES.get(nid, (18.5200, 73.8580))
            nodes.append({
                "node_id": nid,
                "ip_address": host,
                "endpoint": f"{host}:{port}",
                "is_active": is_proc_alive,
                "status": "UP" if is_proc_alive else "DOWN",
                "latitude": coords[0],
                "longitude": coords[1]
            })
            
        links = []
        for n1, n2 in DEFAULT_LINKS:
            if n1 in self.endpoint_config and n2 in self.endpoint_config:
                n1_alive = (n1 in self.processes and self.processes[n1].poll() is None)
                n2_alive = (n2 in self.processes and self.processes[n2].poll() is None)
                links.append({
                    "node_a_id": n1,
                    "node_b_id": n2,
                    "is_active": n1_alive and n2_alive
                })
                
        return {
            "nodes": nodes,
            "links": links,
            "mode": "real",
            "active_route": list(self.active_route),
            "neighbor_health": dict(self.neighbor_health)
        }

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
            "route_discovery_time": self.metrics["route_discovery_time"],
            "recovery_time": self.metrics["recovery_time"],
            "latency": self.metrics["latency"],
            "throughput": self.metrics["throughput"]
        }

    def get_hospital_inbox(self) -> List[dict]:
        return list(self.hospital_inbox)

    def get_events(self) -> List[str]:
        return list(self.recent_events)
