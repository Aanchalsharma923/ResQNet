import os
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from resqnet.backend.app.api.routes.simulation import router as simulation_router, websocket_simulation
from resqnet.backend.app.api.routes.demo import router as demo_router
from resqnet.backend.app.services.runtime_manager import runtime_manager

logger = logging.getLogger("resqnet.main")

def validate_production_configuration():
    """
    Strict pre-flight validation for production deployment.
    Prevents deploying in simulation mode or without required security credentials.
    """
    is_production = os.environ.get("RESQNET_PRODUCTION", "false").lower() in ("true", "1") or \
                    os.environ.get("RESQNET_ENV", "").lower() == "production" or \
                    os.environ.get("RESQNET_REQUIRE_REAL_MODE", "false").lower() in ("true", "1")

    if not is_production:
        return

    mode = os.environ.get("RESQNET_MODE", "").lower()
    if mode != "real":
        raise RuntimeError(
            "FATAL CONFIGURATION ERROR: Production deployment requires RESQNET_MODE=real. "
            f"Currently configured as RESQNET_MODE='{mode}'. "
            "ResQNet refuses to deploy in simulation mode for public production."
        )

    admin_key = os.environ.get("RESQNET_ADMIN_KEY")
    if not admin_key or admin_key.strip() in ("", "change_me_to_a_secure_random_token_12345", "admin", "123456"):
        raise RuntimeError(
            "FATAL SECURITY ERROR: Production deployment requires a secure RESQNET_ADMIN_KEY. "
            "Cannot use empty or default template key in production."
        )

    hospital_key = os.environ.get("RESQNET_HOSPITAL_KEY")
    if not hospital_key or hospital_key.strip() in ("", "change_me_to_a_secure_hospital_key_12345", "hospital", "123456"):
        raise RuntimeError(
            "FATAL SECURITY ERROR: Production deployment requires a secure RESQNET_HOSPITAL_KEY. "
            "Cannot use empty or default clinician key in production."
        )

    if admin_key.strip() == hospital_key.strip():
        raise RuntimeError(
            "FATAL SECURITY ERROR: RESQNET_ADMIN_KEY and RESQNET_HOSPITAL_KEY must not be identical. "
            "Network administrator credentials must be distinct from clinician triage credentials."
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_configuration()
    logger.info("ResQNet Application starting up...")
    mode = os.environ.get("RESQNET_MODE", "simulation").lower()
    if mode == "real":
        logger.info("Initializing Real Network Mode (Multi-process UDP sockets)...")
        try:
            runtime_manager.set_mode("real")
        except Exception as e:
            logger.error(f"Failed to initialize real network runtime: {e}")
            raise RuntimeError(f"FATAL: Real network mode initialization failed: {e}") from e

    yield
    logger.info("ResQNet Application shutting down...")
    try:
        runtime_manager.stop_real_runtime()
    except Exception as e:
        logger.warning(f"Error stopping runtime on shutdown: {e}")

app = FastAPI(
    title="ResQNet API",
    description="Backend API for the ResQNet Disaster-Resilient Network Simulation",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for localhost, LAN clients, and production domains
allowed_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5175", "http://127.0.0.1:5175",
    "http://localhost:4173", "http://127.0.0.1:4173",
    "http://localhost:80", "http://127.0.0.1:80",
    "http://localhost", "http://127.0.0.1"
]
extra_origins = os.environ.get("RESQNET_CORS_ORIGINS", "")
if extra_origins:
    allowed_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

cors_regex = os.environ.get(
    "RESQNET_CORS_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_allowed_origin(origin: str) -> bool:
    """Helper to validate origins for WebSockets and secure endpoints."""
    if not origin:
        return True
    if origin in allowed_origins:
        return True
    if cors_regex and re.match(cors_regex, origin):
        return True
    return False

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ResQNet",
        "runtime_mode": runtime_manager.get_mode(),
        "real_runtime_running": runtime_manager.real_runtime.is_running
    }

@app.websocket("/ws")
async def root_websocket(websocket: WebSocket):
    await websocket_simulation(websocket)

# Include routers
app.include_router(simulation_router, prefix="/api")
app.include_router(demo_router, prefix="/api/demo")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("RESQNET_HOST", "0.0.0.0")
    port = int(os.environ.get("RESQNET_PORT", 8000))
    uvicorn.run("resqnet.backend.app.main:app", host=host, port=port, reload=True)
