from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class NodeResponse(BaseModel):
    node_id: str
    ip_address: str
    is_active: bool

class LinkResponse(BaseModel):
    node_a_id: str
    node_b_id: str
    is_active: bool

class NetworkResponse(BaseModel):
    nodes: List[NodeResponse]
    links: List[LinkResponse]

class LinkActionRequest(BaseModel):
    node_a: str
    node_b: str

class MessageSendRequest(BaseModel):
    source: str
    destination: str
    message: str

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
    # Dummy structure for now
    total_events: int
    total_packets_pending: int
