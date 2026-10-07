import ipaddress

class Node:
    """
    Represents a single node in the network simulation.
    """
    def __init__(self, node_id: str, ip_address: str, is_active: bool = True, latitude: float = 0.0, longitude: float = 0.0):
        self.node_id = node_id
        self._ip_address = None
        # Setting ip_address triggers the property setter for validation
        self.ip_address = ip_address
        self.is_active = is_active
        self.latitude = latitude
        self.longitude = longitude

    @property
    def ip_address(self) -> str:
        return self._ip_address

    @ip_address.setter
    def ip_address(self, value: str):
        try:
            # Validate that the string is a strictly valid IPv4 address
            ip = ipaddress.IPv4Address(value)
            self._ip_address = str(ip)
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid IPv4 address: {value}")

    def fail(self):
        """Simulate node failure."""
        self.is_active = False

    def recover(self):
        """Simulate node recovery."""
        self.is_active = True

    def __repr__(self) -> str:
        return f"Node({self.node_id}, {self.ip_address}, active={self.is_active})"
