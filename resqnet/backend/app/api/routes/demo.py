from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from resqnet.backend.app.services.demo_service import demo_service
from resqnet.backend.app.api.routes.simulation import verify_admin_key

router = APIRouter()

@router.get("/status")
def get_demo_status() -> Dict[str, Any]:
    """Retrieve the current state of the guided demonstration."""
    return demo_service.get_state()

@router.post("/start", dependencies=[Depends(verify_admin_key)])
def start_demo() -> Dict[str, Any]:
    """Start or restart the guided demonstration from Stage 1."""
    return demo_service.start_demo()

@router.post("/next", dependencies=[Depends(verify_admin_key)])
def next_demo_stage() -> Dict[str, Any]:
    """Advance to the next stage in the guided demonstration."""
    return demo_service.next_stage()

@router.post("/prev", dependencies=[Depends(verify_admin_key)])
def prev_demo_stage() -> Dict[str, Any]:
    """Move to the previous stage in the guided demonstration."""
    return demo_service.prev_stage()

@router.post("/step/{stage}", dependencies=[Depends(verify_admin_key)])
def step_demo_stage(stage: int) -> Dict[str, Any]:
    """Jump to or execute a specific stage (1 through 6)."""
    if stage < 1 or stage > 6:
        raise HTTPException(status_code=400, detail="Stage must be an integer between 1 and 6.")
    return demo_service.step_demo(stage)

@router.post("/reset", dependencies=[Depends(verify_admin_key)])
def reset_demo() -> Dict[str, Any]:
    """Reset the demonstration and underlying network to the clean initial state."""
    return demo_service.reset_demo()
