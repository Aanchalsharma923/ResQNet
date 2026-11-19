from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class NodeResponse(BaseModel):
    node_id: str
    ip_address: str
    is_active: bool
    latitude: float
    longitude: float
    endpoint: Optional[str] = None
    status: Optional[str] = None

class LinkResponse(BaseModel):
    node_a_id: str
    node_b_id: str
    is_active: bool

class NetworkResponse(BaseModel):
    nodes: List[NodeResponse]
    links: List[LinkResponse]
    mode: Optional[str] = "simulation"
    active_route: Optional[List[str]] = []
    neighbor_health: Optional[Dict[str, Dict[str, str]]] = None

class RuntimeModeRequest(BaseModel):
    mode: str


class LinkActionRequest(BaseModel):
    node_a: str
    node_b: str

class MessageSendRequest(BaseModel):
    source: str
    destination: str
    message: str
    sos_message_id: Optional[str] = None

class HospitalResponseRequest(BaseModel):
    source_id: Optional[str] = None
    destination_id: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    message: str
    sos_message_id: Optional[str] = None

    def get_source(self) -> str:
        return self.source_id or self.source or "H"

    def get_destination(self) -> str:
        return self.destination_id or self.destination or "A"

class SOSMessageRequest(BaseModel):
    source_id: str
    destination_id: str
    message: str
    latitude: Optional[float] = 18.5204
    longitude: Optional[float] = 73.8567
    priority: Optional[str] = "HIGH"
    message_id: Optional[str] = None
    timeout_seconds: Optional[float] = 5.0
    auto_discover: Optional[bool] = False


class RouteHistoryItem(BaseModel):
    node_id: str

class PacketResponse(BaseModel):
    packet_id: str
    source_id: str
    destination_id: str
    packet_type: str
    status: str
    hop_count: int
    route_history: List[str]
    sender_id: Optional[str]
    payload: Any

class MessageSendResponse(BaseModel):
    success: bool
    events: List[str] = Field(default_factory=list)
    packet: Optional[PacketResponse] = None
    message_id: Optional[str] = None
    ack_status: Optional[str] = None
    status: Optional[str] = "success"
    rtt_ms: Optional[float] = None
    confirmed_at: Optional[float] = None
    active_route: Optional[List[str]] = None
    error: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None

class MetricsResponse(BaseModel):
    packets_sent: int
    packets_delivered: int
    packets_dropped: int
    pdr: str
    loss: str
    avg_hop_count: str
    rreq_count: int
    rrep_count: int
    rerr_count: int
    route_discovery_time: str
    recovery_time: str
    latency: str
    throughput: str
