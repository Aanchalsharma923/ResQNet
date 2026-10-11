from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import asyncio
import uuid
from datetime import datetime, timezone
from typing import List

from resqnet.backend.app.models.api_models import (
    NetworkResponse, MessageSendRequest, MessageSendResponse, 
    LinkActionRequest, MetricsResponse, SOSMessageRequest,
    RuntimeModeRequest
)
from resqnet.backend.app.services.runtime_manager import runtime_manager
from resqnet.backend.app.services.broadcaster import broadcaster

router = APIRouter()

@router.get("/network", response_model=NetworkResponse)
def get_network():
    return runtime_manager.get_network_state()

@router.post("/simulation/reset")
def reset_simulation():
    return runtime_manager.reset()

@router.get("/events", response_model=List[str])
def get_events():
    return runtime_manager.get_events()

@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    return runtime_manager.get_metrics()

@router.post("/nodes/{node_id}/fail")
def fail_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, False)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found or failed to stop")
    return {"status": "success", "node_id": node_id, "is_active": False}

@router.post("/nodes/{node_id}/recover")
def recover_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, True)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found or failed to start")
    return {"status": "success", "node_id": node_id, "is_active": True}

@router.post("/links/fail")
def fail_link(request: LinkActionRequest):
    success = runtime_manager.set_link_status(request.node_a, request.node_b, False)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found or link failure unsupported in current mode")
    return {"status": "success", "link": f"{request.node_a}-{request.node_b}", "is_active": False}

@router.post("/links/recover")
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
def send_sos(request: SOSMessageRequest):
    result = runtime_manager.send_sos(request.model_dump())
    return result

@router.get("/hospital/inbox")
def get_hospital_inbox():
    return runtime_manager.get_hospital_inbox()

@router.post("/hospital/respond", response_model=MessageSendResponse)
def respond_hospital(request: MessageSendRequest):
    result = runtime_manager.send_message(
        request.source,
        request.destination,
        {"type": "response", "message": request.message}
    )
    return result

# ==================== Runtime Manager API ====================

@router.get("/runtime/mode")
def get_runtime_mode():
    return {"mode": runtime_manager.get_mode()}

@router.post("/runtime/mode")
def set_runtime_mode(request: RuntimeModeRequest):
    try:
        return runtime_manager.set_mode(request.mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/runtime/status")
def get_runtime_status():
    return runtime_manager.get_runtime_status()

@router.post("/runtime/start")
def start_runtime():
    return runtime_manager.start_real_runtime()

@router.post("/runtime/stop")
def stop_runtime():
    return runtime_manager.stop_real_runtime()

@router.post("/runtime/reset")
def reset_runtime():
    return runtime_manager.reset()

@router.post("/runtime/nodes/{node_id}/stop")
def stop_runtime_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, False)
    if not success:
        raise HTTPException(status_code=404, detail=f"Failed to stop node {node_id}")
    return {"status": "success", "node_id": node_id, "is_active": False}

@router.post("/runtime/nodes/{node_id}/start")
def start_runtime_node(node_id: str):
    success = runtime_manager.set_node_status(node_id, True)
    if not success:
        raise HTTPException(status_code=404, detail=f"Failed to start node {node_id}")
    return {"status": "success", "node_id": node_id, "is_active": True}

# ==================== WebSocket ====================

@router.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
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

