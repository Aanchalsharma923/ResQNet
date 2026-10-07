import threading
import time
import logging
from typing import Callable, Set, Dict

logger = logging.getLogger(__name__)

class NeighborHealthMonitor:
    """
    Monitors neighbor health by periodically sending HELLO messages and checking
    for received HELLOs. Generates NEIGHBOR_DOWN and NEIGHBOR_RECOVERED events.
    """
    def __init__(self, node_id: str, neighbors: Set[str], send_hello_callback: Callable[[str], None], failure_callback: Callable[[str], None], heartbeat_interval: float = 1.0, neighbor_timeout: float = 3.0):
        self.node_id = node_id
        self.neighbors = neighbors
        self.send_hello_callback = send_hello_callback
        self.failure_callback = failure_callback
        
        self.heartbeat_interval = heartbeat_interval
        self.neighbor_timeout = neighbor_timeout
        
        self.last_seen: Dict[str, float] = {}
        self.is_down: Dict[str, bool] = {n: False for n in neighbors}
        
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        
    def start(self):
        if self._running:
            return
        self._running = True
        
        now = time.monotonic()
        for neighbor in self.neighbors:
            self.last_seen[neighbor] = now
            self.is_down[neighbor] = False
            
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        
    def stop(self):
        if not self._running:
            return
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.heartbeat_interval * 2)
            
    def record_hello(self, neighbor_id: str):
        with self._lock:
            if neighbor_id not in self.neighbors:
                return # Ignore unknown neighbors
            self.last_seen[neighbor_id] = time.monotonic()
            if self.is_down[neighbor_id]:
                self.is_down[neighbor_id] = False
                logger.info(f"[{self.node_id}] NEIGHBOR_RECOVERED: {neighbor_id}")
                
    def _monitor_loop(self):
        while self._running:
            now = time.monotonic()
            
            # Send HELLO
            # Do not hold the lock while sending, to prevent deadlocks with transport
            neighbors_to_ping = list(self.neighbors)
            for neighbor in neighbors_to_ping:
                if self._running:
                    try:
                        self.send_hello_callback(neighbor)
                    except Exception as e:
                        logger.error(f"[{self.node_id}] Failed to send HELLO to {neighbor}: {e}")
                    
            # Check timeouts
            with self._lock:
                for neighbor in self.neighbors:
                    time_since_last_seen = now - self.last_seen.get(neighbor, now)
                    if time_since_last_seen > self.neighbor_timeout:
                        if not self.is_down[neighbor]:
                            self.is_down[neighbor] = True
                            logger.info(f"[{self.node_id}] HELLO TIMEOUT: {neighbor}")
                            logger.info(f"[{self.node_id}] NEIGHBOR_DOWN: {neighbor}")
                            self.failure_callback(neighbor)
                            
            time.sleep(self.heartbeat_interval)
