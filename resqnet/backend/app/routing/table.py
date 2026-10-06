from typing import Dict, Optional

class RouteEntry:
    def __init__(
        self,
        destination_id: str,
        next_hop: str,
        hop_count: int,
        sequence_number: int,
        is_valid: bool = True
    ):
        self.destination_id = destination_id
        self.next_hop = next_hop
        self.hop_count = hop_count
        self.sequence_number = sequence_number
        self.is_valid = is_valid

    def invalidate(self):
        """Mark the route as invalid."""
        self.is_valid = False


class RoutingTable:
    def __init__(self):
        self._routes: Dict[str, RouteEntry] = {}

    def get_route(self, destination_id: str) -> Optional[RouteEntry]:
        """Retrieve a route entry by destination ID."""
        return self._routes.get(destination_id)

    def add_or_update_route(
        self,
        destination_id: str,
        next_hop: str,
        hop_count: int,
        sequence_number: int
    ) -> bool:
        """
        Updates the routing table according to AODV rules.
        Returns True if a new route was added or an existing route was updated.
        """
        existing_route = self._routes.get(destination_id)

        if existing_route is None:
            # Route doesn't exist, insert it
            self._routes[destination_id] = RouteEntry(
                destination_id, next_hop, hop_count, sequence_number
            )
            return True

        # AODV update rules
        # 1. New sequence number is greater -> update
        # 2. Sequence numbers are equal, but new route has strictly lower hop count -> update
        # 3. Existing route is invalid, and new sequence number is at least as large -> update
        update = False
        if sequence_number > existing_route.sequence_number:
            update = True
        elif sequence_number == existing_route.sequence_number:
            if not existing_route.is_valid:
                update = True
            elif hop_count < existing_route.hop_count:
                update = True

        if update:
            existing_route.next_hop = next_hop
            existing_route.hop_count = hop_count
            existing_route.sequence_number = sequence_number
            existing_route.is_valid = True
            return True

        return False

    def invalidate_route(self, destination_id: str):
        """Mark an existing route to the destination as invalid."""
        route = self._routes.get(destination_id)
        if route:
            route.invalidate()

    def remove_route(self, destination_id: str):
        """Remove a route entirely from the table."""
        if destination_id in self._routes:
            del self._routes[destination_id]
