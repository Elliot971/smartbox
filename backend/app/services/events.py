import asyncio
import json
from collections.abc import AsyncGenerator


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    async def publish(self, event_type: str, payload: dict) -> None:
        message = json.dumps({"type": event_type, "payload": payload}, ensure_ascii=False)
        stale: list[asyncio.Queue[str]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            while True:
                message = await queue.get()
                yield f"data: {message}\n\n"
        finally:
            self._subscribers.discard(queue)


event_broker = EventBroker()

