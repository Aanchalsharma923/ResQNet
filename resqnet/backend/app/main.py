import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from resqnet.backend.app.api.routes.simulation import router as simulation_router, websocket_simulation
from resqnet.backend.app.api.routes.demo import router as demo_router

app = FastAPI(
    title="ResQNet API",
    description="Backend API for the ResQNet Disaster-Resilient Network Simulation",
    version="1.0.0"
)

# CORS configuration for localhost and LAN clients
allowed_origins = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173"
]
extra_origins = os.environ.get("RESQNET_CORS_ORIGINS", "")
if extra_origins:
    allowed_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ResQNet"
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
