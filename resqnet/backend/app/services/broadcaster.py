import asyncio
import uuid
from typing import List
from datetime import datetime, timezone

class EventBroadcaster:
    def __init__(self):
        self.subscribers: List[asyncio.Queue] = []
        self.loop = None
        
    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    def broadcast_sync(self, event_type: str, data: dict = None):
        """Called from synchronous threadpool code (e.g., API requests) to queue events for websockets"""
        event = {
            "event_id": str(uuid.uuid4()),
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {}
        }
        
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self._dispatch_to_subscribers, event)
        else:
            # Fallback for synchronous test environments without an event loop
            pass

    def _dispatch_to_subscribers(self, event: dict):
        for queue in self.subscribers:
            queue.put_nowait(event)

# Global singleton
broadcaster = EventBroadcaster()
