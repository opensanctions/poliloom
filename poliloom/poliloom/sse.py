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


def notify_all(event: dict) -> None:
    """Broadcast an event to every connected subscriber."""
    for queues in _subscribers.values():
        for queue in queues:
            queue.put_nowait(event)
