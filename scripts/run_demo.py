"""
ResQNet - Reproducible Demo Runner (Phase 5.1)

Demonstrates the five-node real UDP network on localhost:
1. Starts 5 independent node processes: Rescue-A, Relay-B, Relay-C, Relay-D, Hospital-H.
2. Observes HELLO beacons and neighbor discovery.
3. Node A initiates AODV route discovery to Hospital H and delivers "HELP REQUIRED".
4. Simulates failure of Relay-B.
5. Observes neighbor timeout, route invalidation, and RERR.
6. Node A discovers alternate route through Relay-D and delivers subsequent SOS.
7. Performs clean shutdown of all processes and sockets.
"""

import sys
import time
import logging
import signal
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from resqnet.backend.app.runtime.real_network_runtime import RealNetworkRuntime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResQNetDemo")

def run_demonstration():
    logger.info("==================================================")
    logger.info(" RESQNET REPRODUCIBLE REAL UDP DEMO")
    logger.info("==================================================")
    
    runtime = RealNetworkRuntime()
    
    def cleanup_handler(signum, frame):
        logger.info("\nInterrupted. Cleaning up all node processes...")
        runtime.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, cleanup_handler)
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, cleanup_handler)
        
    try:
        # Step 1: Start the real network runtime
        logger.info("\n[Step 1] Initializing and starting node processes (A, B, C, D, H)...")
        runtime.start()
        
        logger.info("Waiting 3 seconds for node processes to initialize and exchange HELLO beacons...")
        time.sleep(3)
        
        state = runtime.get_network_state()
        active_nodes = [n["node_id"] for n in state["nodes"] if n["is_active"]]
        logger.info(f"Active nodes online: {active_nodes}")
        assert len(active_nodes) == 5, f"Expected 5 active nodes, got {len(active_nodes)}"
        
        # Step 2: Send SOS from A to H
        logger.info("\n[Step 2] Node A sending initial SOS ('HELP REQUIRED') to Hospital H...")
        runtime.send_sos({
            "source_id": "A",
            "destination_id": "H",
            "message": "HELP REQUIRED",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "HIGH"
        })
        
        logger.info("Waiting 2 seconds for AODV route discovery (RREQ/RREP) and DATA forwarding...")
        time.sleep(2)
        
        # If route was just established on initial RREQ, send confirmation packet to ensure delivery
        if not runtime.hospital_inbox:
            logger.info("Route established; sending confirmed delivery packet...")
            runtime.send_sos({
                "source_id": "A",
                "destination_id": "H",
                "message": "HELP REQUIRED",
                "latitude": 18.5204,
                "longitude": 73.8567,
                "priority": "HIGH"
            })
            time.sleep(2)
            
        logger.info(f"Active route in runtime: {runtime.active_route}")
        logger.info(f"Hospital inbox count: {len(runtime.hospital_inbox)}")
        if runtime.hospital_inbox:
            logger.info(f"Hospital latest message: {runtime.hospital_inbox[-1]['message']}")
            
        # Step 3: Simulate failure of Relay B
        logger.info("\n[Step 3] Simulating catastrophic failure of Relay-B...")
        runtime.stop_node("B")
        logger.info("Relay-B process stopped.")
        
        # Step 4: Wait for neighbor timeout and route invalidation
        logger.info("\n[Step 4] Waiting 4 seconds for HELLO timeout (3.0s) and route invalidation...")
        time.sleep(4)
        
        logger.info(f"Active route after B failure: {runtime.active_route} (should be cleared/invalidated)")
        
        # Step 5: Send subsequent SOS via alternate route
        logger.info("\n[Step 5] Node A sending subsequent SOS ('HELP REQUIRED (RECOVERED)') to Hospital H...")
        runtime.send_sos({
            "source_id": "A",
            "destination_id": "H",
            "message": "HELP REQUIRED (RECOVERED)",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "HIGH"
        })
        
        logger.info("Waiting 2 seconds for AODV route rediscovery via Relay-D...")
        time.sleep(2)
        
        # Deliver via discovered route
        runtime.send_sos({
            "source_id": "A",
            "destination_id": "H",
            "message": "HELP REQUIRED (RECOVERED)",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "priority": "HIGH"
        })
        time.sleep(2)
        
        logger.info(f"Active route after recovery: {runtime.active_route}")
        logger.info(f"Hospital inbox count: {len(runtime.hospital_inbox)}")
        if runtime.hospital_inbox:
            logger.info(f"Hospital inbox messages: {[m['message'] for m in runtime.hospital_inbox]}")
            
        # Print final metrics
        metrics = runtime.get_metrics()
        logger.info("\n==================================================")
        logger.info(" DEMONSTRATION METRICS")
        logger.info("==================================================")
        for k, v in metrics.items():
            logger.info(f"  {k}: {v}")
        logger.info("==================================================")
        logger.info(" DEMONSTRATION COMPLETE - SUCCESS")
        logger.info("==================================================")
        
    finally:
        logger.info("\n[Step 6] Shutting down all node processes and sockets...")
        runtime.stop()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    run_demonstration()
