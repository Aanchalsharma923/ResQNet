from abc import ABC, abstractmethod
from typing import Optional

from resqnet.backend.app.simulation.topology import NetworkTopology

class BaseRouter(ABC):
    """
    Abstract base class for routing logic.
    Each node in the simulation will have a router instance.
    """
    def __init__(self, node_id: str, topology: NetworkTopology):
        self.node_id = node_id
        self.topology = topology

    @abstractmethod
    def get_next_hop(self, destination_id: str) -> Optional[str]:
        """
        Returns the node_id of the next hop to reach the destination_id.
        Returns None if no route is available or if the route is broken.
        """
        pass
