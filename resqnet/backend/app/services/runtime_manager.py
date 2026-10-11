import logging
from typing import Dict, List, Optional, Any

from resqnet.backend.app.services.simulation_service import simulation_service
from resqnet.backend.app.runtime.real_network_runtime import RealNetworkRuntime
from resqnet.backend.app.services.broadcaster import broadcaster

logger = logging.getLogger(__name__)

class RuntimeManager:
    """
    Manages the active ResQNet runtime: Simulation Mode vs Real Network Mode.
    Provides a unified interface for FastAPI and WebSocket clients.
    Does NOT contain routing logic.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RuntimeManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.mode = "simulation"  # Default mode: "simulation" | "real"
        self.simulation_service = simulation_service
        self.real_runtime = RealNetworkRuntime()

    def get_mode(self) -> str:
        return self.mode

    def set_mode(self, new_mode: str) -> dict:
        if new_mode not in ["simulation", "real"]:
            raise ValueError(f"Invalid mode '{new_mode}'. Expected 'simulation' or 'real'.")
            
        old_mode = self.mode
        self.mode = new_mode
        logger.info(f"Runtime mode transitioned from '{old_mode}' to '{new_mode}'")
        
        # When switching to real, ensure real runtime is started
        if new_mode == "real" and not self.real_runtime.is_running:
            self.real_runtime.start()
        # When switching back to simulation, we can optionally stop real node processes
        elif new_mode == "simulation" and self.real_runtime.is_running:
            self.real_runtime.stop()
            
        state = self.get_network_state()
        broadcaster.broadcast_sync("RUNTIME_MODE_CHANGED", {"mode": new_mode})
        broadcaster.broadcast_sync("INITIAL_STATE", state)
        return {"status": "success", "mode": self.mode}

    def get_network_state(self) -> dict:
        if self.mode == "real":
            return self.real_runtime.get_network_state()
        else:
            state = self.simulation_service.get_network_state()
            state["mode"] = "simulation"
            state["active_route"] = []
            return state

    def reset(self) -> dict:
        if self.mode == "real":
            self.real_runtime.reset()
            return {"status": "reset successful", "mode": "real"}
        else:
            self.simulation_service.reset()
            return {"status": "reset successful", "mode": "simulation"}

    def get_events(self) -> List[str]:
        if self.mode == "real":
            return self.real_runtime.get_events()
        else:
            return self.simulation_service.get_events()

    def get_metrics(self) -> dict:
        if self.mode == "real":
            return self.real_runtime.get_metrics()
        else:
            return self.simulation_service.get_metrics()

    def set_node_status(self, node_id: str, is_active: bool) -> bool:
        if self.mode == "real":
            if is_active:
                return self.real_runtime.start_node(node_id)
            else:
                return self.real_runtime.stop_node(node_id)
        else:
            return self.simulation_service.set_node_status(node_id, is_active)

    def set_link_status(self, node_a_id: str, node_b_id: str, is_active: bool) -> bool:
        if self.mode == "real":
            logger.warning("Link control in Real Network mode is determined by physical connectivity and neighbor health.")
            return False
        else:
            return self.simulation_service.set_link_status(node_a_id, node_b_id, is_active)

    def send_message(self, source_id: str, destination_id: str, message: Any) -> dict:
        if self.mode == "real":
            return self.real_runtime.send_message(source_id, destination_id, message)
        else:
            return self.simulation_service.send_message(source_id, destination_id, message)

    def send_sos(self, sos_request: dict) -> dict:
        if self.mode == "real":
            return self.real_runtime.send_sos(sos_request)
        else:
            return self.simulation_service.send_sos(sos_request)

    def get_hospital_inbox(self) -> List[dict]:
        if self.mode == "real":
            return self.real_runtime.get_hospital_inbox()
        else:
            return self.simulation_service.get_hospital_inbox()

    def start_real_runtime(self) -> dict:
        self.real_runtime.start()
        return {"status": "started", "running": self.real_runtime.is_running}

    def stop_real_runtime(self) -> dict:
        self.real_runtime.stop()
        return {"status": "stopped", "running": self.real_runtime.is_running}

    def get_runtime_status(self) -> dict:
        return {
            "mode": self.mode,
            "real_runtime_running": self.real_runtime.is_running,
            "real_nodes": {
                k: (k in self.real_runtime.processes and self.real_runtime.processes[k].poll() is None)
                for k in self.real_runtime.endpoint_config
            }
        }

# Global singleton instance
runtime_manager = RuntimeManager()
