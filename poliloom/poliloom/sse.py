"""In-memory SSE subscriber registry keyed by user_id."""

import asyncio
from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class Event:
    """Base SSE event."""


@dataclass
class ArchivedPageStatusEvent(Event):
    """Sent when an archived page's status changes."""

    type: str = field(init=False, default="archived_page_status")
    politician_ids: list[str] = field(default_factory=list)
    archived_page_id: str = ""
    status: str = ""
    error: str | None = None
    http_status_code: int | None = None


@dataclass
class EnrichmentCompleteEvent(Event):
    """Broadcast when enrichment produces new properties."""

    type: str = field(init=False, default="enrichment_complete")
    languages: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)


@dataclass
class EvaluationCountEvent(Event):
    """Broadcast when evaluations are created, carrying the updated total."""

    type: str = field(init=False, default="evaluation_count")
    total: int = 0


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


def notify(event: Event) -> None:
    """Broadcast an event to all connected subscribers."""
    payload = asdict(event)
    for queues in _subscribers.values():
        for queue in queues:
            queue.put_nowait(payload)
