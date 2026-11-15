"""In-process pub/sub used to push live updates to WebSocket clients."""
from __future__ import annotations

import asyncio
from typing import Any


class Broadcaster:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.subscribers: set[asyncio.Queue] = set()

    def bind(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers.discard(q)

    def _put(self, event: dict[str, Any]):
        for q in list(self.subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)

    def publish(self, event: dict[str, Any]):
        """Thread-safe: may be called from worker threads."""
        if self.loop is None or not self.subscribers:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self._put(event)
        else:
            self.loop.call_soon_threadsafe(self._put, event)


broadcaster = Broadcaster()
