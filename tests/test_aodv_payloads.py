import pytest
from resqnet.backend.app.models.aodv_payloads import RREQPayload, RREPPayload
from resqnet.backend.app.models.packet import Packet, PacketType

def test_rreq_creation_valid():
    """RREQ - 1. Valid RREQ creation. 2. Required fields. 3. Seq Nums. 4. Broadcast ID. 5. Hop count."""
    rreq = RREQPayload(
        source_id="A",
        destination_id="H",
        source_sequence_number=1,
        destination_sequence_number=0,
        broadcast_id=42,
        hop_count=0
    )
    assert rreq.source_id == "A"
    assert rreq.destination_id == "H"
    assert rreq.source_sequence_number == 1
    assert rreq.destination_sequence_number == 0
    assert rreq.broadcast_id == 42
    assert rreq.hop_count == 0

def test_rreq_invalid_fields():
    """RREQ - 6. Invalid field handling."""
    with pytest.raises(ValueError):
        RREQPayload("", "H", 1, 0, 42, 0)
    with pytest.raises(ValueError):
        RREQPayload("A", "", 1, 0, 42, 0)
    with pytest.raises(ValueError):
        RREQPayload("A", "H", -1, 0, 42, 0)
    with pytest.raises(ValueError):
        RREQPayload("A", "H", 1, -1, 42, 0)
    with pytest.raises(ValueError):
        RREQPayload("A", "H", 1, 0, -1, 0)
    with pytest.raises(ValueError):
        RREQPayload("A", "H", 1, 0, 42, -1)

def test_rreq_identity():
    """RREQ - 7. RREQ identity using (source_id, broadcast_id)."""
    rreq = RREQPayload("A", "H", 1, 0, 42, 0)
    assert rreq.identity == ("A", 42)

def test_rrep_creation_valid():
    """RREP - 1. Valid RREP creation. 2. Required fields. 3. Dest seq num. 4. Originator. 5. Hop count."""
    rrep = RREPPayload(
        destination_id="H",
        destination_sequence_number=5,
        originator_id="A",
        hop_count=2
    )
    assert rrep.destination_id == "H"
    assert rrep.destination_sequence_number == 5
    assert rrep.originator_id == "A"
    assert rrep.hop_count == 2

def test_rrep_invalid_fields():
    """RREP - 6. Invalid field handling."""
    with pytest.raises(ValueError):
        RREPPayload("", 5, "A", 2)
    with pytest.raises(ValueError):
        RREPPayload("H", 5, "", 2)
    with pytest.raises(ValueError):
        RREPPayload("H", -1, "A", 2)
    with pytest.raises(ValueError):
        RREPPayload("H", 5, "A", -1)

def test_packet_integration_rreq():
    """Packet integration - Verify PacketType.RREQ can carry RREQPayload"""
    rreq = RREQPayload("A", "H", 1, 0, 42, 0)
    packet = Packet(
        source_id="A",
        destination_id="H",
        payload=rreq,
        packet_type=PacketType.RREQ
    )
    assert packet.packet_type == PacketType.RREQ
    assert isinstance(packet.payload, RREQPayload)
    assert packet.payload.identity == ("A", 42)

def test_packet_integration_rrep():
    """Packet integration - Verify PacketType.RREP can carry RREPPayload"""
    rrep = RREPPayload("H", 5, "A", 2)
    packet = Packet(
        source_id="H",
        destination_id="A",
        payload=rrep,
        packet_type=PacketType.RREP
    )
    assert packet.packet_type == PacketType.RREP
    assert isinstance(packet.payload, RREPPayload)
    assert packet.payload.destination_sequence_number == 5

def test_packet_integration_data():
    """Packet integration - Verify existing DATA packets still work"""
    packet = Packet(
        source_id="A",
        destination_id="H",
        payload="HELP REQUIRED",
        packet_type=PacketType.DATA
    )
    assert packet.packet_type == PacketType.DATA
    assert packet.payload == "HELP REQUIRED"

def test_packet_integration_data_invalid():
    """Packet integration - Verify existing DATA packets require non-empty payload"""
    with pytest.raises(ValueError):
        Packet(
            source_id="A",
            destination_id="H",
            payload="",
            packet_type=PacketType.DATA
        )
