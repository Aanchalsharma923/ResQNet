from typing import List, Optional

from resqnet.backend.app.routing.base import BaseRouter
from resqnet.backend.app.simulation.topology import NetworkTopology

class StaticRouter(BaseRouter):
    """
    A simple baseline router that follows a predetermined static route.
    It does not perform any dynamic route discovery or recovery.
    """
    def __init__(self, node_id: str, topology: NetworkTopology, route: List[str] = None):
        """
        route: A list of node IDs representing the explicit path, e.g., ["A", "B", "C", "H"]
        """
        super().__init__(node_id, topology)
        self.route = route if route is not None else []

    def get_next_hop(self, destination_id: str) -> Optional[str]:
        """
        Returns the next hop based on the configured static route.
        Validates that the next hop is currently an active neighbor.
        """
        if not self.route:
            return None
            
        # Check if this route is for the requested destination
        if self.route[-1] != destination_id:
            return None
            
        try:
            my_index = self.route.index(self.node_id)
        except ValueError:
            # We are not part of this route
            return None
            
        if my_index == len(self.route) - 1:
            # We are the destination itself
            return None
            
        next_hop_id = self.route[my_index + 1]
        
        # Verify that the next hop is physically reachable (active neighbor)
        # Topology guarantees neighbors returned are active and links are active
        my_node = self.topology.get_node_by_id(self.node_id)
        active_neighbors = self.topology.get_active_neighbors(my_node.ip_address)
        
        for neighbor in active_neighbors:
            if neighbor.node_id == next_hop_id:
                return next_hop_id
                
        # Link or neighbor is failed/inactive
        return None
