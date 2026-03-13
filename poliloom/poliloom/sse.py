"""In-memory SSE subscriber registry keyed by user_id."""

import asyncio
from typing import Dict, List

_subscribers: Dict[str, List[asyncio.Queue]] = {}


def subscribe(user_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(user_id, []).append(queue)
    return queue


def unsubscribe(user_id: str, queue: asyncio.Queue) -> None:
    queues = _subscribers.get(user_id)
    if queues:
        try:
            queues.remove(queue)
        except ValueError:
            pass
        if not queues:
            del _subscribers[user_id]


def notify(event: dict, user_id: str | None = None) -> None:
    """Send an event to subscribers. Targets a single user if user_id is given, otherwise broadcasts to all."""
    if user_id:
        queues = _subscribers.get(user_id, [])
        for queue in queues:
            queue.put_nowait(event)
    else:
        for queues in _subscribers.values():
            for queue in queues:
                queue.put_nowait(event)
