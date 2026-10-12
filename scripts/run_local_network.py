import argparse
import sys
import logging
import json
import time
import subprocess
import signal
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from resqnet.backend.app.runtime.node import NodeRuntime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Standard demo endpoint configuration
DEFAULT_ENDPOINTS = {
    "A": ("127.0.0.1", 50010),
    "B": ("127.0.0.1", 50011),
    "C": ("127.0.0.1", 50012),
    "D": ("127.0.0.1", 50013),
    "H": ("127.0.0.1", 50014)
}

def run_single_node(node_id: str, config: dict):
    """
    Runs a single ResQNet node in the current process.
    """
    logger.info(f"[{node_id}] Initializing node...")
    runtime = NodeRuntime(node_id, config)
    
    def handle_shutdown(signum, frame):
        logger.info(f"[{node_id}] Shutdown signal received.")
        runtime.stop()
        sys.exit(0)

    # Register signals for graceful shutdown
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    try:
        runtime.start()
        logger.info(f"[{node_id}] RUNNING on {config[node_id][0]}:{config[node_id][1]}")
        # Keep process alive
        while True:
            time.sleep(1)
    except Exception as e:
        logger.error(f"[{node_id}] Error: {e}")
        runtime.stop()
        sys.exit(1)

def launch_all_nodes(config: dict):
    """
    Spawns child processes for all nodes defined in the config.
    """
    logger.info("Starting ResQNet Launcher...")
    processes = []
    
    # Write temp config file to pass to children if needed, or pass via command line.
    # Since DEFAULT_ENDPOINTS is known, we can just pass the node_id.
    
    # Path to this script
    script_path = os.path.abspath(__file__)
    
    try:
        for node_id, (ip, port) in config.items():
            logger.info(f"Launching process for Node {node_id}")
            cmd = [sys.executable, script_path, "--node-id", node_id]
            p = subprocess.Popen(cmd)
            processes.append((node_id, p))
            
        logger.info("All nodes launched. Press Ctrl+C to terminate.")
        
        # Monitor processes
        while True:
            time.sleep(1)
            for node_id, p in list(processes):
                if p.poll() is not None:
                    logger.warning(f"Process for Node {node_id} exited with code {p.returncode}")
                    # Remove from list so we don't spam
                    processes.remove((node_id, p))
                    
            if not processes:
                logger.info("All child processes have exited.")
                break
                
    except KeyboardInterrupt:
        logger.info("Launcher received KeyboardInterrupt. Stopping all nodes...")
    finally:
        for node_id, p in processes:
            if p.poll() is None:
                logger.info(f"Terminating Node {node_id}...")
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Node {node_id} did not terminate. Killing...")
                    p.kill()
        logger.info("Launcher shutdown complete.")

def main():
    parser = argparse.ArgumentParser(description="ResQNet Multi-Process Launcher")
    parser.add_argument("--node-id", type=str, help="Run a specific node ID (e.g. A). If not specified, launches all nodes.")
    
    args = parser.parse_args()
    
    if args.node_id:
        if args.node_id not in DEFAULT_ENDPOINTS:
            logger.error(f"Unknown node ID: {args.node_id}")
            sys.exit(1)
        # Re-configure logger format to include node ID
        logging.getLogger().handlers[0].setFormatter(logging.Formatter(f"%(asctime)s [{args.node_id}] %(message)s"))
        run_single_node(args.node_id, DEFAULT_ENDPOINTS)
    else:
        launch_all_nodes(DEFAULT_ENDPOINTS)

if __name__ == "__main__":
    main()
