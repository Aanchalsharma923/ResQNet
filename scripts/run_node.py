import argparse
import sys
import logging
import json
import time
import signal
import os

from resqnet.backend.app.runtime.node import NodeRuntime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def run_single_node(node_id: str, config_path: str, bind_host: str):
    """
    Runs a single ResQNet node in the current process.
    """
    try:
        with open(config_path, "r") as f:
            raw_config = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load configuration from {config_path}: {e}")
        sys.exit(1)
        
    endpoint_config = {k: (v["host"], v["port"]) for k, v in raw_config.items()}
    
    if node_id not in endpoint_config:
        logger.error(f"Unknown node ID: {node_id}")
        sys.exit(1)
        
    logger.info(f"[{node_id}] Initializing node...")
    
    # Optional topology_links can be provided if needed, but defaults are configured in NodeRuntime
    runtime = NodeRuntime(node_id, endpoint_config, bind_host=bind_host)
    
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
        # Keep process alive
        while True:
            time.sleep(1)
    except Exception as e:
        logger.error(f"[{node_id}] Error: {e}")
        runtime.stop()
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="ResQNet Node Launcher")
    parser.add_argument("--node-id", type=str, required=True, help="Run a specific node ID (e.g. A).")
    parser.add_argument("--config", type=str, required=True, help="Path to JSON configuration file.")
    parser.add_argument("--bind-host", type=str, default="0.0.0.0", help="Host address to bind the UDP socket to (default: 0.0.0.0).")
    
    args = parser.parse_args()
    
    # Re-configure logger format to include node ID
    logging.getLogger().handlers[0].setFormatter(logging.Formatter(f"%(asctime)s [{args.node_id}] %(message)s"))
    run_single_node(args.node_id, args.config, args.bind_host)

if __name__ == "__main__":
    main()
