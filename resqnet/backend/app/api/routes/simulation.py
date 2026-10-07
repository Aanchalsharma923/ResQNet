from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import asyncio
from resqnet.backend.app.models.api_models import (
    NetworkResponse, MessageSendRequest, MessageSendResponse, 
    LinkActionRequest, MetricsResponse, SOSMessageRequest
)
from resqnet.backend.app.services.simulation_service import simulation_service
from resqnet.backend.app.services.broadcaster import broadcaster
from typing import List

router = APIRouter()

@router.get("/network", response_model=NetworkResponse)
def get_network():
    return simulation_service.get_network_state()

@router.post("/simulation/reset")
def reset_simulation():
    simulation_service.reset()
    return {"status": "reset successful"}

@router.get("/events", response_model=List[str])
def get_events():
    return simulation_service.get_events()

@router.get("/metrics", response_model=MetricsResponse)
def get_metrics():
    return simulation_service.get_metrics()

@router.post("/nodes/{node_id}/fail")
def fail_node(node_id: str):
    success = simulation_service.set_node_status(node_id, False)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "success", "node_id": node_id, "is_active": False}

@router.post("/nodes/{node_id}/recover")
def recover_node(node_id: str):
    success = simulation_service.set_node_status(node_id, True)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "success", "node_id": node_id, "is_active": True}

@router.post("/links/fail")
def fail_link(request: LinkActionRequest):
    success = simulation_service.set_link_status(request.node_a, request.node_b, False)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "success", "link": f"{request.node_a}-{request.node_b}", "is_active": False}

@router.post("/links/recover")
def recover_link(request: LinkActionRequest):
    success = simulation_service.set_link_status(request.node_a, request.node_b, True)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"status": "success", "link": f"{request.node_a}-{request.node_b}", "is_active": True}

@router.post("/messages/send", response_model=MessageSendResponse)
def send_message(request: MessageSendRequest):
    result = simulation_service.send_message(
        request.source, 
        request.destination, 
        request.message
    )
    return result

@router.post("/sos", response_model=MessageSendResponse)
def send_sos(request: SOSMessageRequest):
    result = simulation_service.send_sos(request.model_dump())
    return result

@router.get("/hospital/inbox")
def get_hospital_inbox():
    return simulation_service.get_hospital_inbox()

@router.post("/hospital/respond", response_model=MessageSendResponse)
def respond_hospital(request: MessageSendRequest):
    # This just uses normal message send API but can be extended
    result = simulation_service.send_message(
        request.source,
        request.destination,
        {"type": "response", "message": request.message}
    )
    return result

@router.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # Ensure loop is set
        try:
            broadcaster.set_loop(asyncio.get_running_loop())
        except RuntimeError:
            pass # No running loop in this context
            
        queue = await broadcaster.subscribe()
        
        # Send initial state
        await websocket.send_json({
            "type": "INITIAL_STATE",
            "data": simulation_service.get_network_state()
        })
        
        while True:
            # Wait for events and push to client
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        broadcaster.unsubscribe(queue)
    except Exception as e:
        broadcaster.unsubscribe(queue)
        await websocket.close(code=1011, reason=str(e))
