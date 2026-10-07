import socket
import threading
import logging
from typing import List, Callable, Optional, Dict, Tuple

from resqnet.backend.app.transport.base import BaseTransport
from resqnet.backend.app.models.packet import Packet
from resqnet.backend.app.serialization import serialize_packet, deserialize_packet

logger = logging.getLogger(__name__)

class UDPTransport(BaseTransport):
    """
    Real UDP transport implementation.
    Delivers packets over physical OS-level UDP datagram sockets.
    """
    def __init__(self, local_node_id: str, endpoint_config: Dict[str, Tuple[str, int]], bind_host: str = "0.0.0.0"):
        super().__init__()
        self.local_node_id = local_node_id
        self.endpoint_config = endpoint_config
        self.bind_host = bind_host
        self._socket: Optional[socket.socket] = None
        self._receive_thread: Optional[threading.Thread] = None

    def start(self):
        """
        Create the UDP socket, bind to the local endpoint, and start the receive loop.
        """
        if self._running:
            logger.warning(f"UDPTransport for {self.local_node_id} is already running.")
            return

        if self.local_node_id not in self.endpoint_config:
            raise ValueError(f"Local node {self.local_node_id} not found in endpoint config")

        local_endpoint = self.endpoint_config[self.local_node_id]
        bind_tuple = (self.bind_host, local_endpoint[1])

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.bind(bind_tuple)
            # Use a timeout to ensure the receive thread can exit gracefully
            self._socket.settimeout(0.5)
        except Exception as e:
            if self._socket:
                self._socket.close()
                self._socket = None
            raise RuntimeError(f"Failed to bind UDP socket on {local_endpoint}: {e}")

        self._running = True
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            name=f"UDPReceiveThread-{self.local_node_id}",
            daemon=False
        )
        self._receive_thread.start()
        logger.info(f"UDP transport started: {self.local_node_id} listening on {bind_tuple[0]}:{bind_tuple[1]}")

    def stop(self):
        """
        Stop the receive loop, close the socket, and release resources.
        """
        if not self._running:
            return

        self._running = False
        
        if self._receive_thread:
            self._receive_thread.join(timeout=2.0)
            self._receive_thread = None

        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                logger.error(f"Error closing UDP socket for {self.local_node_id}: {e}")
            finally:
                self._socket = None

        logger.info(f"UDP transport stopped: {self.local_node_id}")

    def send(self, packet: Packet, next_hops: List[str]) -> bool:
        """
        Serialize and send a packet via UDP to the configured endpoints of next_hops.
        """
        if not self._running or not self._socket:
            logger.error(f"Cannot send, transport for {self.local_node_id} is not running.")
            return False

        try:
            data = serialize_packet(packet)
        except Exception as e:
            logger.error(f"Failed to serialize packet {packet.packet_id}: {e}")
            return False

        success = False
        for hop in next_hops:
            if hop not in self.endpoint_config:
                logger.error(f"Cannot send to {hop}: endpoint not configured.")
                continue

            destination_endpoint = self.endpoint_config[hop]
            try:
                self._socket.sendto(data, destination_endpoint)
                success = True
                logger.debug(f"UDP packet sent: {self.local_node_id} → {hop} endpoint {destination_endpoint[0]}:{destination_endpoint[1]} packet_id={packet.packet_id}")
            except Exception as e:
                logger.error(f"UDP sendto failed for {hop} at {destination_endpoint}: {e}")

        return success

    def _receive_loop(self):
        """
        Continuously listen for incoming datagrams and invoke the receive callback.
        """
        while self._running and self._socket:
            try:
                data, remote_address = self._socket.recvfrom(65535)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Ignore ICMP port unreachable on Windows for UDP sockets
                continue
            except OSError as e:
                # Windows error 10054 is WSAECONNRESET
                if getattr(e, 'winerror', None) == 10054:
                    continue
                if self._running:
                    logger.error(f"UDP socket receive error on {self.local_node_id}: {e}")
                break
            except Exception as e:
                if self._running:
                    logger.error(f"UDP socket receive error on {self.local_node_id}: {e}")
                break

            try:
                packet = deserialize_packet(data)
                logger.debug(f"UDP packet received: {self.local_node_id} ← {packet.sender_id} packet_id={packet.packet_id}")
                
                if self._receive_callback:
                    # Provide the deserialized packet to the consumer (AODV/Engine)
                    self._receive_callback(packet)
            except ValueError as e:
                logger.warning(f"Malformed UDP packet rejected on {self.local_node_id} from {remote_address}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing packet on {self.local_node_id} from {remote_address}: {e}")
