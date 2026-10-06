from typing import Optional, Set, Tuple

from resqnet.backend.app.routing.base import BaseRouter
from resqnet.backend.app.routing.table import RoutingTable
from resqnet.backend.app.simulation.topology import NetworkTopology
from resqnet.backend.app.models.packet import Packet


class AODVRouter(BaseRouter):
    """
    Genuine AODV router implementation.
    Discovers routes on-demand using RREQ/RREP propagation.
    """
    def __init__(self, node_id: str, topology: NetworkTopology):
        super().__init__(node_id, topology)
        self.routing_table = RoutingTable()
        
        # AODV protocol state
        self.node_sequence_number: int = 1
        self.broadcast_id_counter: int = 0
        
        # Cache for duplicate RREQ detection (source_id, broadcast_id)
        self.seen_rreqs: Set[Tuple[str, int]] = set()

    def get_next_hop(self, destination_id: str) -> Optional[str]:
        """
        Consult the routing table for the next hop.
        Returns None if no valid route exists.
        """
        route = self.routing_table.get_route(destination_id)
        if route and route.is_valid:
            return route.next_hop
        return None

    def has_valid_route(self, destination_id: str) -> bool:
        """
        Check if a valid route to the destination exists.
        """
        return self.get_next_hop(destination_id) is not None

    def increment_sequence_number(self) -> int:
        """
        Increment and return the node's sequence number.
        """
        self.node_sequence_number += 1
        return self.node_sequence_number

    def get_next_broadcast_id(self) -> int:
        """
        Increment and return the next broadcast ID for a new RREQ.
        """
        self.broadcast_id_counter += 1
        return self.broadcast_id_counter

    def has_seen_rreq(self, source_id: str, broadcast_id: int) -> bool:
        """
        Check if an RREQ identity has already been processed.
        """
        return (source_id, broadcast_id) in self.seen_rreqs

    def record_rreq(self, source_id: str, broadcast_id: int):
        """
        Record an RREQ identity to prevent processing duplicates.
        """
        self.seen_rreqs.add((source_id, broadcast_id))

    def initiate_route_discovery(self, destination_id: str):
        """
        API foundation to trigger AODV Route Discovery.
        
        Currently a placeholder. Does NOT implement RREQ generation
        or broadcasting yet.
        """
        # Explicitly indicates route discovery is not yet implemented
        raise NotImplementedError("Route discovery is not yet implemented.")
