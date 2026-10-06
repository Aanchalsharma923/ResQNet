from resqnet.backend.app.models.node import Node

class Link:
    """
    Represents a logical bidirectional connection between two network nodes.
    """
    def __init__(self, node1: Node, node2: Node, is_active: bool = True):
        # Validate that endpoints are strictly Node objects
        if not isinstance(node1, Node) or not isinstance(node2, Node):
            raise TypeError("Endpoints must be instances of Node")
        
        # Prevent self-loop links
        if node1.node_id == node2.node_id:
            raise ValueError("A link cannot connect a node to itself")

        self.node1 = node1
        self.node2 = node2
        self.is_active = is_active

    def fail(self):
        """Simulate physical link failure."""
        self.is_active = False

    def recover(self):
        """Simulate physical link recovery."""
        self.is_active = True

    def connects(self, ip_address: str) -> bool:
        """Helper to quickly check if a specific IP is an endpoint of this link."""
        return self.node1.ip_address == ip_address or self.node2.ip_address == ip_address

    def get_peer(self, ip_address: str) -> Node:
        """Returns the peer node given one of the endpoint IPs."""
        if self.node1.ip_address == ip_address:
            return self.node2
        elif self.node2.ip_address == ip_address:
            return self.node1
        raise ValueError(f"IP {ip_address} is not connected to this link.")

    def __eq__(self, other: object) -> bool:
        """
        Bidirectional equality: Link(A, B) == Link(B, A).
        """
        if not isinstance(other, Link):
            return False
        
        same_direct = (self.node1.node_id == other.node1.node_id) and (self.node2.node_id == other.node2.node_id)
        same_reversed = (self.node1.node_id == other.node2.node_id) and (self.node2.node_id == other.node1.node_id)
        return same_direct or same_reversed

    def __hash__(self) -> int:
        """
        Consistent hashing for bidirectional equivalence using a frozenset.
        """
        return hash(frozenset([self.node1.node_id, self.node2.node_id]))

    def __repr__(self) -> str:
        status = "ACTIVE" if self.is_active else "FAILED"
        return f"Link({self.node1.node_id} <-> {self.node2.node_id}, {status})"
