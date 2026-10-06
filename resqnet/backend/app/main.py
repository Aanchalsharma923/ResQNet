from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from resqnet.backend.app.api.routes.simulation import router as simulation_router

app = FastAPI(
    title="ResQNet API",
    description="Backend API for the ResQNet Disaster-Resilient Network Simulation",
    version="1.0.0"
)

# CORS configuration for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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

# Include routers
app.include_router(simulation_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("resqnet.backend.app.main:app", host="0.0.0.1", port=8000, reload=True)
