from resqnet.backend.app.models.node import Node
from resqnet.backend.app.models.link import Link

class NetworkTopology:
    """
    Central manager for physical/logical connectivity and node/link state.
    Serves as the source of truth for the simulation and routing algorithms.
    """
    def __init__(self):
        self.nodes_by_id = {}
        self.nodes_by_ip = {}
        self.links = set()

    def add_node(self, node: Node):
        """Register a node in the topology."""
        if not isinstance(node, Node):
            raise TypeError("Must add a Node instance")
        if node.node_id in self.nodes_by_id:
            raise ValueError(f"Node ID {node.node_id} already exists in topology")
        if node.ip_address in self.nodes_by_ip:
            raise ValueError(f"Node IP {node.ip_address} already exists in topology")
        
        self.nodes_by_id[node.node_id] = node
        self.nodes_by_ip[node.ip_address] = node

    def get_node_by_id(self, node_id: str) -> Node:
        """Lookup node by its string ID."""
        if node_id not in self.nodes_by_id:
            raise KeyError(f"Node ID {node_id} not found in topology")
        return self.nodes_by_id[node_id]

    def get_node_by_ip(self, ip_address: str) -> Node:
        """Lookup node by its IP address."""
        if ip_address not in self.nodes_by_ip:
            raise KeyError(f"Node IP {ip_address} not found in topology")
        return self.nodes_by_ip[ip_address]

    def add_link(self, link: Link):
        """Register a bidirectional link in the topology."""
        if not isinstance(link, Link):
            raise TypeError("Must add a Link instance")
        
        # Ensure both endpoints are fully registered in this topology
        if link.node1.node_id not in self.nodes_by_id or link.node2.node_id not in self.nodes_by_id:
            raise ValueError("Both endpoints of the link must be added to the topology first")
        
        if link in self.links:
            raise ValueError("This logical link already exists in the topology")
            
        self.links.add(link)

    def get_link(self, ip1: str, ip2: str) -> Link:
        """Helper to fetch a specific logical link between two IPs."""
        node1 = self.get_node_by_ip(ip1)
        node2 = self.get_node_by_ip(ip2)
        # Create a dummy link just for equality checking against the registered links
        dummy_link = Link(node1, node2)
        
        for link in self.links:
            if link == dummy_link:
                return link
        raise KeyError(f"No logical link found between {ip1} and {ip2}")

    def get_active_neighbors(self, ip_address: str) -> list[Node]:
        """
        Returns a list of reachable active neighbor nodes for a given IP address.
        A neighbor is considered reachable ONLY if:
        1. The source node is active.
        2. The link to the neighbor is active.
        3. The neighboring node is active.
        """
        source_node = self.get_node_by_ip(ip_address)
        
        # If the requesting node itself is failed, it can't communicate with anyone
        if not source_node.is_active:
            return []

        neighbors = []
        for link in self.links:
            if link.connects(ip_address) and link.is_active:
                peer = link.get_peer(ip_address)
                if peer.is_active:
                    neighbors.append(peer)
        
        return neighbors
