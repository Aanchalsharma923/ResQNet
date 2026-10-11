from pydantic import BaseModel
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

class SOSMessageRequest(BaseModel):
    source_id: str
    destination_id: str
    message: str
    latitude: float
    longitude: float
    priority: str


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
    events: List[str]
    packet: Optional[PacketResponse]

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
