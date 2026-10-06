import pytest
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus

def test_valid_packet_creation():
    """Test standard valid packet creation establishes correct initial baseline."""
    packet = Packet("A", "H", "HELP REQUIRED")
    assert packet.packet_id is not None
    assert packet.source_id == "A"
    assert packet.destination_id == "H"
    assert packet.payload == "HELP REQUIRED"
    assert packet.packet_type == PacketType.DATA
    assert packet.current_node == "A"
    assert packet.hop_count == 0
    assert packet.route_history == ["A"]
    assert packet.status == PacketStatus.CREATED
    assert packet.ttl == 64

def test_unique_packet_id():
    """Test that every packet gets a unique ID."""
    packet1 = Packet("A", "H", "P1")
    packet2 = Packet("A", "H", "P2")
    assert packet1.packet_id != packet2.packet_id

def test_invalid_packet_creation():
    """Test validation of required fields at creation."""
    with pytest.raises(ValueError, match="Source and destination identifiers must be provided"):
        Packet("", "H", "P1")
    
    with pytest.raises(ValueError, match="Source and destination identifiers must be provided"):
        Packet("A", "", "P1")
        
    with pytest.raises(ValueError, match="Payload cannot be empty for DATA packets"):
        Packet("A", "H", "")

def test_packet_movement():
    """Test that movement accurately appends to route history without pre-computing."""
    packet = Packet("A", "H", "DATA")
    
    packet.move_to("B")
    assert packet.current_node == "B"
    assert packet.hop_count == 1
    assert packet.route_history == ["A", "B"]
    assert packet.status == PacketStatus.IN_TRANSIT
    
    packet.move_to("C")
    assert packet.current_node == "C"
    assert packet.hop_count == 2
    assert packet.route_history == ["A", "B", "C"]
    
def test_packet_ttl_drop():
    """Test TTL decrementing and dropping on 0."""
    packet = Packet("A", "H", "DATA", ttl=2)
    packet.move_to("B")
    assert packet.status == PacketStatus.IN_TRANSIT
    
    packet.move_to("C")
    # TTL reaches 0 after moving to C
    assert packet.status == PacketStatus.DROPPED
    assert packet.hop_count == 2

def test_packet_invalid_move():
    """Test preventing movement of a packet that is already delivered or dropped."""
    packet = Packet("A", "H", "DATA")
    packet.mark_delivered()
    
    with pytest.raises(ValueError, match="Cannot move packet with status DELIVERED"):
        packet.move_to("B")

def test_packet_status_updates():
    """Test explicit lifecycle status updates."""
    packet = Packet("A", "H", "DATA")
    packet.mark_delivered()
    assert packet.status == PacketStatus.DELIVERED
    
    packet2 = Packet("A", "H", "DATA")
    packet2.mark_failed()
    assert packet2.status == PacketStatus.FAILED

def test_packet_repr():
    """Test string representation."""
    packet = Packet("A", "H", "DATA")
    assert repr(packet) == "Packet(DATA, A -> H, curr=A, hops=0, stat=CREATED)"
