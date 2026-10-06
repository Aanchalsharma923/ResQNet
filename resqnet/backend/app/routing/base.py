from abc import ABC, abstractmethod
from typing import Optional, List

from resqnet.backend.app.simulation.topology import NetworkTopology

class BaseRouter(ABC):
    """
    Abstract base class for routing logic.
    Each node in the simulation will have a router instance.
    """
    def __init__(self, node_id: str, topology: NetworkTopology):
        self.node_id = node_id
        self.topology = topology
        self.generated_packets = []
        self.events = []

    @abstractmethod
    def get_next_hop(self, destination_id: str) -> Optional[str]:
        """
        Returns the node_id of the next hop to reach the destination_id.
        Returns None if no route is available or if the route is broken.
        """
        pass

    def handle_packet(self, packet) -> List[str]:
        """
        Process an incoming packet and determine where it should be forwarded.
        Returns a list of next hop node IDs.
        For normal unicast forwarding, returns a list with 1 element.
        For broadcasting, returns a list of active neighbor node IDs.
        For dropped or consumed packets, returns an empty list.
        """
        # Default behavior: Unicast via get_next_hop
        next_hop = self.get_next_hop(packet.destination_id)
        if next_hop:
            return [next_hop]
        return []
