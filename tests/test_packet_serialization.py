import pytest
import json
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.models.aodv_payloads import RREQPayload, RREPPayload, RERRPayload
from resqnet.backend.app.serialization import serialize_packet, deserialize_packet, CURRENT_VERSION

def test_serialize_deserialize_data_packet():
    packet = Packet(source_id="A", destination_id="H", payload={"msg": "SOS", "lat": 10.0})
    packet.sender_id = "B"
    packet.current_node = "C"
    packet.hop_count = 2
    packet.ttl = 62
    packet.route_history = ["A", "B", "C"]
    packet.status = PacketStatus.IN_TRANSIT
    
    data = serialize_packet(packet)
    assert isinstance(data, bytes)
    
    decoded = deserialize_packet(data)
    assert decoded.packet_id == packet.packet_id
    assert decoded.source_id == "A"
    assert decoded.destination_id == "H"
    assert decoded.sender_id == "B"
    assert decoded.current_node == "C"
    assert decoded.hop_count == 2
    assert decoded.ttl == 62
    assert decoded.route_history == ["A", "B", "C"]
    assert decoded.status == PacketStatus.IN_TRANSIT
    assert decoded.payload == {"msg": "SOS", "lat": 10.0}
    assert decoded.packet_type == PacketType.DATA

def test_serialize_deserialize_rreq():
    payload = RREQPayload(
        source_id="A",
        destination_id="H",
        source_sequence_number=10,
        destination_sequence_number=5,
        broadcast_id=1,
        hop_count=2
    )
    packet = Packet(source_id="A", destination_id="H", payload=payload, packet_type=PacketType.RREQ)
    packet.sender_id = "B"
    
    data = serialize_packet(packet)
    decoded = deserialize_packet(data)
    
    assert decoded.packet_type == PacketType.RREQ
    assert isinstance(decoded.payload, RREQPayload)
    assert decoded.payload.source_id == "A"
    assert decoded.payload.destination_id == "H"
    assert decoded.payload.source_sequence_number == 10
    assert decoded.payload.destination_sequence_number == 5
    assert decoded.payload.broadcast_id == 1
    assert decoded.payload.hop_count == 2
    assert decoded.sender_id == "B"

def test_serialize_deserialize_rrep():
    payload = RREPPayload(
        destination_id="H",
        destination_sequence_number=6,
        originator_id="A",
        hop_count=3
    )
    packet = Packet(source_id="H", destination_id="A", payload=payload, packet_type=PacketType.RREP)
    packet.sender_id = "H"
    
    data = serialize_packet(packet)
    decoded = deserialize_packet(data)
    
    assert decoded.packet_type == PacketType.RREP
    assert isinstance(decoded.payload, RREPPayload)
    assert decoded.payload.destination_id == "H"
    assert decoded.payload.destination_sequence_number == 6
    assert decoded.payload.originator_id == "A"
    assert decoded.payload.hop_count == 3
    assert decoded.sender_id == "H"

def test_serialize_deserialize_rerr():
    payload = RERRPayload(unreachable_destinations=[("H", 6), ("X", 2)])
    packet = Packet(source_id="C", destination_id="A", payload=payload, packet_type=PacketType.RERR)
    packet.sender_id = "C"
    
    data = serialize_packet(packet)
    decoded = deserialize_packet(data)
    
    assert decoded.packet_type == PacketType.RERR
    assert isinstance(decoded.payload, RERRPayload)
    assert decoded.payload.unreachable_destinations == [("H", 6), ("X", 2)]
    assert decoded.sender_id == "C"

def test_malformed_json_rejection():
    with pytest.raises(ValueError, match="Invalid JSON data"):
        deserialize_packet(b"{invalid_json")

def test_missing_field_rejection():
    bad_data = json.dumps({"version": CURRENT_VERSION, "packet_type": "DATA"}).encode("utf-8")
    with pytest.raises(ValueError, match="Missing required field"):
        deserialize_packet(bad_data)

def test_unknown_packet_type_rejection():
    bad_data = json.dumps({
        "version": CURRENT_VERSION,
        "packet_id": "123",
        "packet_type": "UNKNOWN_TYPE",
        "source_id": "A",
        "destination_id": "B",
        "payload": "data"
    }).encode("utf-8")
    with pytest.raises(ValueError, match="Unknown packet_type: UNKNOWN_TYPE"):
        deserialize_packet(bad_data)

def test_unsupported_version_rejection():
    bad_data = json.dumps({
        "version": 999,
        "packet_id": "123",
        "packet_type": "DATA",
        "source_id": "A",
        "destination_id": "B",
        "payload": "data"
    }).encode("utf-8")
    with pytest.raises(ValueError, match="Unsupported packet version: 999"):
        deserialize_packet(bad_data)

def test_malformed_payload_rejection():
    # RREQ missing required fields
    bad_data = json.dumps({
        "version": CURRENT_VERSION,
        "packet_id": "123",
        "packet_type": "RREQ",
        "source_id": "A",
        "destination_id": "B",
        "payload": {"source_id": "A"} # Missing other RREQ fields
    }).encode("utf-8")
    with pytest.raises(ValueError, match="Malformed RREQ payload"):
        deserialize_packet(bad_data)

def test_deterministic_serialization():
    packet = Packet(source_id="A", destination_id="H", payload={"a": 1, "b": 2})
    data1 = serialize_packet(packet)
    data2 = serialize_packet(packet)
    assert data1 == data2 # output must be perfectly deterministic for the same object
