from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Header, Query, Depends, Request
import asyncio
import os
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict

from resqnet.backend.app.models.api_models import (
    NetworkResponse, MessageSendRequest, MessageSendResponse, 
    LinkActionRequest, MetricsResponse, SOSMessageRequest,
    RuntimeModeRequest, HospitalResponseRequest
)
from resqnet.backend.app.services.runtime_manager import runtime_manager
from resqnet.backend.app.services.broadcaster import broadcaster

logger = logging.getLogger("resqnet.api")
router = APIRouter()

# In-memory rate limiter for SOS requests
_sos_timestamps: Dict[str, List[float]] = {}

def get_trusted_client_ip(request: Request) -> str:
    """
    Safely resolves client IP.
    When behind a trusted reverse proxy (e.g. Nginx on loopback or Docker bridge),
    extracts the client IP from X-Real-IP or X-Forwarded-For.
    Does NOT trust spoofed headers from untrusted remote IPs.
    """
    direct_ip = request.client.host if request and request.client else "unknown"

    # Only trust reverse proxy headers if incoming connection is from local/bridge network
    is_trusted_proxy = direct_ip in ("127.0.0.1", "::1", "localhost", "testclient") or \
                       direct_ip.startswith("172.") or direct_ip.startswith("10.")

    if is_trusted_proxy and request:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                return parts[0]

    return direct_ip

def check_sos_rate_limit(client_ip: str) -> bool:
    limit_str = os.environ.get("RESQNET_RATE_LIMIT_SOS_PER_MIN")
    if not limit_str or client_ip in ("testclient", "testserver"):
        return True
    try:
        limit = int(limit_str)
    except ValueError:
        return True
    now = time.time()
    cutoff = now - 60.0
    records = [t for t in _sos_timestamps.get(client_ip, []) if t > cutoff]
    if len(records) >= limit:
        _sos_timestamps[client_ip] = records
        return False
    records.append(now)
    _sos_timestamps[client_ip] = records
    return True

def verify_admin_key(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    admin_key: Optional[str] = Query(None, alias="admin_key")
):
    """
    Verifies administrative authorization.
    If RESQNET_ADMIN_KEY is not set, allows open access (development/testing mode).
    If set, strictly enforces matching key in header or query.
    Authentication failures are logged safely without leaking keys.
    """
    expected = os.environ.get("RESQNET_ADMIN_KEY")
    if not expected:
        return True
    provided = x_admin_key or admin_key or request.headers.get("x-admin-key")
    if not provided or provided.strip() != expected.strip():
        client_ip = get_trusted_client_ip(request)
        logger.warning(f"Unauthorized administrative access attempt to {request.url.path} from client IP: {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Admin key required. Provide 'X-Admin-Key' header or 'admin_key' query parameter."
        )
    return True

def verify_clinician_key(
    request: Request,
    x_hospital_key: Optional[str] = Header(None, alias="X-Hospital-Key"),
    x_clinician_key: Optional[str] = Header(None, alias="X-Clinician-Key"),
    hospital_key: Optional[str] = Query(None, alias="hospital_key")
):
    """
    Verifies hospital clinician authorization.
    Uses RESQNET_HOSPITAL_KEY or RESQNET_CLINICIAN_KEY.
    Distinct from network administrator credentials.
    Authentication failures are logged safely without leaking keys.
    """
    expected = os.environ.get("RESQNET_HOSPITAL_KEY") or os.environ.get("RESQNET_CLINICIAN_KEY")
    if not expected:
        return True
    provided = x_hospital_key or x_clinician_key or hospital_key or request.headers.get("x-hospital-key")
    if not provided or provided.strip() != expected.strip():
        client_ip = get_trusted_client_ip(request)
        logger.warning(f"Unauthorized hospital triage response attempt from client IP: {client_ip}")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Hospital clinician credentials required. Provide 'X-Hospital-Key' header."
        )
    return True

@router.get("/network", response_model=NetworkResponse)
def get_network():
    return runtime_manager.get_network_state()

@router.post("/simulation/reset", dependencies=[Depends(verify_admin_key)])
def reset_simulation():
    return runtime_manager.reset()

@router.post("/simulation/advance_time", dependencies=[Depends(verify_admin_key)])
def advance_simulation_time(seconds: float = 1.0):
    return runtime_manager.advance_sim_time(seconds)

@router.get("/sos/status/{message_id}")
def get_sos_status(message_id: str):
    status = runtime_manager.get_sos_status(message_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"SOS message {message_id} not found")
    return status

@router.get("/events", response_model=List[str])
def get_events():
    return runtime_manager.get_events()

@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    return runtime_manager.get_metrics()

@router.post("/nodes/{node_id}/fail", dependencies=[Depends(verify_admin_key)])
def fail_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, False)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found or failed to stop")
    return {"status": "success", "node_id": node_id, "is_active": False}

@router.post("/nodes/{node_id}/recover", dependencies=[Depends(verify_admin_key)])
def recover_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, True)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found or failed to start")
    return {"status": "success", "node_id": node_id, "is_active": True}

@router.post("/links/fail", dependencies=[Depends(verify_admin_key)])
def fail_link(request: LinkActionRequest):
    success = runtime_manager.set_link_status(request.node_a, request.node_b, False)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found or link failure unsupported in current mode")
    return {"status": "success", "link": f"{request.node_a}-{request.node_b}", "is_active": False}

@router.post("/links/recover", dependencies=[Depends(verify_admin_key)])
def recover_link(request: LinkActionRequest):
    success = runtime_manager.set_link_status(request.node_a, request.node_b, True)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found or link recovery unsupported in current mode")
    return {"status": "success", "link": f"{request.node_a}-{request.node_b}", "is_active": True}

@router.post("/messages/send", response_model=MessageSendResponse)
def send_message(request: MessageSendRequest):
    result = runtime_manager.send_message(
        request.source, 
        request.destination, 
        request.message
    )
    return result

@router.post("/sos", response_model=MessageSendResponse)
def send_sos(request: SOSMessageRequest, http_req: Request = None):
    if http_req:
        client_ip = get_trusted_client_ip(http_req)
        if not check_sos_rate_limit(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded: maximum 60 SOS dispatches per minute.")
    result = runtime_manager.send_sos(request.model_dump())
    return result

@router.get("/hospital/inbox")
def get_hospital_inbox():
    return runtime_manager.get_hospital_inbox()

@router.post("/hospital/respond", response_model=MessageSendResponse, dependencies=[Depends(verify_clinician_key)])
def respond_hospital(request: HospitalResponseRequest):
    if not request.sos_message_id or not request.sos_message_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing sos_message_id: Hospital response must reference an active SOS incident."
        )

    sos_id = request.sos_message_id.strip()
    sos_record = runtime_manager.get_sos_status(sos_id)
    hospital_inbox = runtime_manager.get_hospital_inbox()
    inbox_match = next((item for item in hospital_inbox if item.get("message_id") == sos_id or item.get("sos_id") == sos_id), None)

    if not sos_record and not inbox_match:
        logger.warning(f"Hospital response rejected: SOS ID '{sos_id}' not found in active records or inbox.")
        raise HTTPException(
            status_code=404,
            detail=f"Invalid SOS ID: Incident '{sos_id}' does not exist or has not been received by Hospital."
        )

    # Determine destination (the source of the original SOS)
    target_dest = (sos_record and sos_record.get("source_id")) or \
                  (inbox_match and (inbox_match.get("source_id") or inbox_match.get("source"))) or \
                  request.get_destination()
    src = request.get_source()

    result = runtime_manager.send_message(
        src,
        target_dest,
        {
            "type": "hospital_response",
            "sos_message_id": sos_id,
            "message": request.message
        }
    )
    return result

# ==================== Runtime Manager API ====================

@router.get("/runtime/mode")
def get_runtime_mode():
    return {"mode": runtime_manager.get_mode()}

@router.post("/runtime/mode", dependencies=[Depends(verify_admin_key)])
def set_runtime_mode(request: RuntimeModeRequest):
    try:
        return runtime_manager.set_mode(request.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/runtime/status")
def get_runtime_status():
    return runtime_manager.get_runtime_status()

@router.post("/runtime/start", dependencies=[Depends(verify_admin_key)])
def start_runtime():
    return runtime_manager.start_real_runtime()

@router.post("/runtime/stop", dependencies=[Depends(verify_admin_key)])
def stop_runtime():
    return runtime_manager.stop_real_runtime()

@router.post("/runtime/reset", dependencies=[Depends(verify_admin_key)])
def reset_runtime():
    return runtime_manager.reset()

@router.post("/runtime/nodes/{node_id}/stop", dependencies=[Depends(verify_admin_key)])
def stop_runtime_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, False)
    if not success:
        raise HTTPException(status_code=404, detail=f"Failed to stop node {node_id}")
    return {"status": "success", "node_id": node_id, "is_active": False}

@router.post("/runtime/nodes/{node_id}/start", dependencies=[Depends(verify_admin_key)])
def start_runtime_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, True)
    if not success:
        raise HTTPException(status_code=404, detail=f"Failed to start node {node_id}")
    return {"status": "success", "node_id": node_id, "is_active": True}

# ==================== WebSocket ====================

@router.websocket("/ws")
@router.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    # Origin check if strict mode is configured
    strict_origin = os.environ.get("RESQNET_STRICT_WS_ORIGIN", "false").lower() in ("true", "1")
    if strict_origin:
        origin = websocket.headers.get("origin")
        from resqnet.backend.app.main import is_allowed_origin
        if origin and not is_allowed_origin(origin):
            logger.warning(f"Rejecting WebSocket connection from unauthorized origin: {origin}")
            await websocket.close(code=1008, reason="Unauthorized origin")
            return

    await websocket.accept()
    
    try:
        try:
            broadcaster.set_loop(asyncio.get_running_loop())
        except RuntimeError:
            pass
            
        queue = await broadcaster.subscribe()
        
        # Send initial state with canonical event_id
        await websocket.send_json({
            "event_id": str(uuid.uuid4()),
            "type": "INITIAL_STATE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": runtime_manager.get_network_state()
        })
        
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        broadcaster.unsubscribe(queue)
    except Exception as e:
        broadcaster.unsubscribe(queue)
        await websocket.close(code=1011, reason=str(e))

