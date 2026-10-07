import logging
import threading
import time
from typing import Dict, Tuple, Optional

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
    def __init__(self, node_id: str, endpoint_config: Dict[str, Tuple[str, int]], topology_links: Optional[list[Tuple[str, str]]] = None, bind_host: str = "0.0.0.0"):
        self.node_id = node_id
        self.endpoint_config = endpoint_config
        self.topology_links = topology_links
        self.bind_host = bind_host
        self.is_running = False

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

    def stop(self):
        """Stops the transport and runtime."""
        if not self.is_running:
            return
            
        logger.info(f"Stopping ResQNet NodeRuntime [{self.node_id}]")
        if hasattr(self, 'health_monitor'):
            self.health_monitor.stop()
        self.transport.stop()
        self.is_running = False

    def send_data(self, destination_id: str, payload: dict):
        """
        Manually inject a DATA packet originating from this node.
        """
        packet = Packet(
            source_id=self.node_id,
            destination_id=destination_id,
            payload=payload,
            packet_type=PacketType.DATA
        )
        # Process it locally first to invoke routing
        self._process_packet(packet)

    def _send_hello(self, neighbor_id: str):
        packet = Packet(
            source_id=self.node_id,
            destination_id=neighbor_id,
            payload={"msg": "HELLO"},
            packet_type=PacketType.HELLO,
            ttl=1
        )
        packet.sender_id = self.node_id
        self.transport.send(packet, [neighbor_id])
        
    def _on_neighbor_failure(self, neighbor_id: str):
        logger.info(f"[{self.node_id}] INVALIDATING ROUTE TO * VIA {neighbor_id}")
        self.router.handle_link_failure(neighbor_id)
        self._dispatch_generated_packets()

    def _on_packet_received(self, packet: Packet):
        """
        Callback invoked by UDPTransport when a datagram is received.
        """
        # Packet has physically arrived at this node. Update its location.
        if packet.current_node != self.node_id:
            packet.move_to(self.node_id)
            
        if packet.status == PacketStatus.DROPPED:
            if packet.destination_id != self.node_id and packet.destination_id != "*":
                logger.warning(f"[{self.node_id}] Received packet dropped due to TTL or invalid move: {packet.packet_id}")
                return
            
        self._process_packet(packet)

    def _process_packet(self, packet: Packet):
        """
        Processes a packet using the AODV router and dispatches generated/forwarded packets.
        """
        if packet.packet_type == PacketType.HELLO:
            if hasattr(self, 'health_monitor') and packet.sender_id:
                self.health_monitor.record_hello(packet.sender_id)
            return

        # 1. Check if it's a DATA packet destined for us
        if packet.destination_id == self.node_id:
            if packet.packet_type == PacketType.DATA:
                packet.mark_delivered()
                logger.info(f"[{self.node_id}] PACKET DELIVERED: {packet.payload}")
                return
            elif packet.packet_type == PacketType.RREQ:
                packet.mark_delivered()
                # AODV still needs to process RREQ to generate RREP
                
        # 2. Let router handle the packet
        next_hops = self.router.handle_packet(packet)
        
        # 3. Handle newly generated packets (e.g. RREP, RERR, or RREQ)
        self._dispatch_generated_packets()
            
        # 4. Handle events logging
        if hasattr(self.router, 'events') and self.router.events:
            for event in self.router.events:
                logger.info(f"[{self.node_id}] EVENT: {event} for packet {packet.packet_id}")
            self.router.events.clear()
            
        # 5. Forward original packet if requested
        if next_hops:
            packet.sender_id = self.node_id
            self.transport.send(packet, next_hops)
            
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
        next_hops = self.router.handle_packet(packet)
        
        # In case processing it generated more packets (rare, but possible)
        if hasattr(self.router, 'generated_packets') and self.router.generated_packets:
            new_packets = list(self.router.generated_packets)
            self.router.generated_packets.clear()
            for new_packet in new_packets:
                self._dispatch_packet(new_packet)
            
        if hasattr(self.router, 'events') and self.router.events:
            for event in self.router.events:
                logger.info(f"[{self.node_id}] EVENT: {event} for packet {packet.packet_id}")
            self.router.events.clear()
            
        if next_hops:
            packet.sender_id = self.node_id
            self.transport.send(packet, next_hops)
