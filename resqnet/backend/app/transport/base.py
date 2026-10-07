from abc import ABC, abstractmethod
from typing import List, Callable, Optional
from resqnet.backend.app.models.packet import Packet

class BaseTransport(ABC):
    """
    Abstract interface for packet delivery mechanisms.
    A transport is responsible for taking a packet and logically moving it
    to the next specified hops (whether via simulation, UDP, etc).
    It does NOT make routing decisions.
    """
    def __init__(self):
        self._running = False
        self._receive_callback: Optional[Callable[[Packet], None]] = None

    def start(self):
        """Start the transport layer."""
        self._running = True

    def stop(self):
        """Stop the transport layer."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def set_receive_callback(self, callback: Callable[[Packet], None]):
        """
        Register a callback to be invoked when a packet arrives at this node
        from the transport layer.
        """
        self._receive_callback = callback

    @abstractmethod
    def send(self, packet: Packet, next_hops: List[str]) -> bool:
        """
        Dispatches the given packet to the specified next hops.
        
        Args:
            packet: The Packet to send.
            next_hops: A list of node_ids representing the physical next hops to send to.
            
        Returns:
            bool: True if the packet was successfully dispatched to at least one valid next hop.
        """
        pass
