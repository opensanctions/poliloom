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


class EventBus:
    """Manages SSE subscriptions and the PostgreSQL LISTEN task."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._task: asyncio.Task | None = None

    @staticmethod
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

    def subscribe(self, user_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(user_id, []).append(queue)
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(user_id)
        if queues:
            try:
                queues.remove(queue)
            except ValueError:
                pass
            if not queues:
                del self._subscribers[user_id]

    def _fanout(self, payload: dict) -> None:
        """Fan out a deserialized event to all local subscribers."""
        for queues in self._subscribers.values():
            for queue in queues:
                queue.put_nowait(payload)

    async def _listen(self, ready: asyncio.Event | None = None) -> None:
        """Listen for PostgreSQL notifications and fan out to local subscribers."""
        conn_params = get_conn_params()
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    **conn_params, autocommit=True
                ) as conn:
                    await conn.execute(
                        sql.SQL("LISTEN {}").format(sql.Identifier(CHANNEL))
                    )
                    log.info("SSE listener connected")
                    if ready is not None:
                        ready.set()
                        ready = None  # only signal on first connect
                    async for notification in conn.notifies():
                        self._fanout(json.loads(notification.payload))
            except asyncio.CancelledError:
                return
            except Exception:
                log.warning(
                    "SSE listener connection lost, reconnecting...", exc_info=True
                )
                await asyncio.sleep(1)

    def start(self) -> asyncio.Event:
        """Start the background LISTEN task. Returns an event set once connected."""
        ready = asyncio.Event()
        self._task = asyncio.create_task(self._listen(ready))
        return ready

    async def stop(self) -> None:
        """Stop the background LISTEN task."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


event_bus = EventBus()
