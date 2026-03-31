"""Cross-process SSE event bus using PostgreSQL LISTEN/NOTIFY."""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Dict, List

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_conn_params

log = logging.getLogger(__name__)

CHANNEL = "sse_events"


@dataclass
class Event:
    """Base SSE event."""


@dataclass
class SourceStatusEvent(Event):
    """Sent when a source's status changes."""

    type: str = field(init=False, default="source_status")
    politician_ids: list[str] = field(default_factory=list)
    source_id: str = ""
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
_listener_task: asyncio.Task | None = None


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


def _fanout(payload: dict) -> None:
    """Fan out a deserialized event to all local subscribers."""
    for queues in _subscribers.values():
        for queue in queues:
            queue.put_nowait(payload)


def notify(event: Event, session: Session) -> None:
    """Broadcast an event to all workers via PostgreSQL NOTIFY.

    The pg_notify runs in the caller's transaction, so the notification
    is only delivered when that transaction commits.
    """
    payload = json.dumps(asdict(event))
    session.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": CHANNEL, "payload": payload},
    )


async def _listen(ready: asyncio.Event | None = None) -> None:
    """Listen for PostgreSQL notifications and fan out to local subscribers."""
    conn_params = get_conn_params()
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(
                **conn_params, autocommit=True
            ) as conn:
                await conn.execute(sql.SQL("LISTEN {}").format(sql.Identifier(CHANNEL)))
                log.info("SSE listener connected")
                if ready is not None:
                    ready.set()
                    ready = None  # only signal on first connect
                async for notification in conn.notifies():
                    _fanout(json.loads(notification.payload))
        except asyncio.CancelledError:
            return
        except Exception:
            log.warning("SSE listener connection lost, reconnecting...", exc_info=True)
            await asyncio.sleep(1)


def start_listener() -> asyncio.Event:
    """Start the background LISTEN task. Returns an event that is set once connected."""
    global _listener_task
    ready = asyncio.Event()
    _listener_task = asyncio.create_task(_listen(ready))
    return ready


async def stop_listener() -> None:
    """Stop the background LISTEN task."""
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
