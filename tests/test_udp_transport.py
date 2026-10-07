import pytest
import time
import socket
from resqnet.backend.app.models.packet import Packet, PacketType, PacketStatus
from resqnet.backend.app.transport.udp_transport import UDPTransport

# Helper to get free port
def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@pytest.fixture
def endpoint_config():
    return {
        "A": ("127.0.0.1", get_free_port()),
        "B": ("127.0.0.1", get_free_port()),
        "C": ("127.0.0.1", get_free_port())
    }

def test_udp_transport_lifecycle(endpoint_config):
    transport = UDPTransport("A", endpoint_config)
    assert transport.is_running is False
    
    transport.start()
    assert transport.is_running is True
    
    # Starting again should not crash
    transport.start()
    
    transport.stop()
    assert transport.is_running is False
    
    # Stopping again should not crash
    transport.stop()

def test_udp_transport_unconfigured_node():
    with pytest.raises(ValueError, match="not found in endpoint config"):
        transport = UDPTransport("X", {"A": ("127.0.0.1", 50000)})
        transport.start()

def test_udp_transport_port_collision(endpoint_config):
    transport1 = UDPTransport("A", endpoint_config)
    transport1.start()
    
    transport2 = UDPTransport("A", endpoint_config)
    with pytest.raises(RuntimeError, match="Failed to bind UDP socket"):
        transport2.start()
        
    transport1.stop()

def test_udp_transport_send_receive_data(endpoint_config):
    transport_a = UDPTransport("A", endpoint_config)
    transport_b = UDPTransport("B", endpoint_config)
    
    transport_a.start()
    transport_b.start()
    
    received_packets = []
    def on_receive(packet: Packet):
        received_packets.append(packet)
        
    transport_b.set_receive_callback(on_receive)
    
    packet = Packet(source_id="A", destination_id="B", payload={"msg": "hello"})
    packet.sender_id = "A"
    
    success = transport_a.send(packet, ["B"])
    assert success is True
    
    # Wait for UDP transmission
    time.sleep(0.1)
    
    transport_a.stop()
    transport_b.stop()
    
    assert len(received_packets) == 1
    received = received_packets[0]
    
    assert received.packet_id == packet.packet_id
    assert received.source_id == "A"
    assert received.destination_id == "B"
    assert received.sender_id == "A"
    assert received.payload == {"msg": "hello"}
    assert received.packet_type == PacketType.DATA

def test_udp_transport_bidirectional(endpoint_config):
    transport_a = UDPTransport("A", endpoint_config)
    transport_b = UDPTransport("B", endpoint_config)
    
    transport_a.start()
    transport_b.start()
    
    received_a = []
    received_b = []
    
    transport_a.set_receive_callback(lambda p: received_a.append(p))
    transport_b.set_receive_callback(lambda p: received_b.append(p))
    
    p1 = Packet(source_id="A", destination_id="B", payload="to B")
    p1.sender_id = "A"
    
    p2 = Packet(source_id="B", destination_id="A", payload="to A")
    p2.sender_id = "B"
    
    transport_a.send(p1, ["B"])
    transport_b.send(p2, ["A"])
    
    time.sleep(0.1)
    
    transport_a.stop()
    transport_b.stop()
    
    assert len(received_a) == 1
    assert len(received_b) == 1
    
    assert received_a[0].payload == "to A"
    assert received_b[0].payload == "to B"

def test_udp_transport_multinode(endpoint_config):
    ta = UDPTransport("A", endpoint_config)
    tb = UDPTransport("B", endpoint_config)
    tc = UDPTransport("C", endpoint_config)
    
    ta.start()
    tb.start()
    tc.start()
    
    rec_a, rec_b, rec_c = [], [], []
    ta.set_receive_callback(lambda p: rec_a.append(p))
    tb.set_receive_callback(lambda p: rec_b.append(p))
    tc.set_receive_callback(lambda p: rec_c.append(p))
    
    p_a_b = Packet("A", "B", "msg1")
    p_b_c = Packet("B", "C", "msg2")
    p_c_a = Packet("C", "A", "msg3")
    p_a_b.sender_id = "A"
    p_b_c.sender_id = "B"
    p_c_a.sender_id = "C"
    
    ta.send(p_a_b, ["B"])
    tb.send(p_b_c, ["C"])
    tc.send(p_c_a, ["A"])
    
    time.sleep(0.1)
    
    ta.stop()
    tb.stop()
    tc.stop()
    
    assert len(rec_a) == 1 and rec_a[0].payload == "msg3"
    assert len(rec_b) == 1 and rec_b[0].payload == "msg1"
    assert len(rec_c) == 1 and rec_c[0].payload == "msg2"

def test_udp_transport_malformed_datagram(endpoint_config):
    ta = UDPTransport("A", endpoint_config)
    tb = UDPTransport("B", endpoint_config)
    
    ta.start()
    tb.start()
    
    received_packets = []
    tb.set_receive_callback(lambda p: received_packets.append(p))
    
    # Manually send malformed data using socket
    dest = endpoint_config["B"]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(b"malformed json here", dest)
        
    time.sleep(0.1)
    
    # Transport B should still be running and receive a valid packet next
    assert tb.is_running is True
    
    p = Packet("A", "B", "valid")
    p.sender_id = "A"
    ta.send(p, ["B"])
    
    time.sleep(0.1)
    
    ta.stop()
    tb.stop()
    
    assert len(received_packets) == 1
    assert received_packets[0].payload == "valid"

def test_udp_transport_unknown_destination(endpoint_config):
    ta = UDPTransport("A", endpoint_config)
    ta.start()
    
    p = Packet("A", "UNKNOWN", "msg")
    p.sender_id = "A"
    
    # "UNKNOWN" is not in config, should fail to send
    success = ta.send(p, ["UNKNOWN"])
    assert success is False
    
    ta.stop()

def test_udp_transport_stopped_destination(endpoint_config):
    ta = UDPTransport("A", endpoint_config)
    ta.start()
    
    p = Packet("A", "B", "msg")
    p.sender_id = "A"
    
    # Sending to a port where nobody is listening. sendto() will succeed
    # but the packet will be lost. This verifies send returns True even if receiver is offline.
    success = ta.send(p, ["B"])
    assert success is True
    
    ta.stop()
