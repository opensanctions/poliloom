"""Tests for the SSE subscriber registry."""

import asyncio
from dataclasses import asdict

from sqlalchemy.orm import Session

from poliloom.database import get_engine
from poliloom.sse import (
    SourceStatusEvent,
    EnrichmentCompleteEvent,
    subscribe,
    unsubscribe,
    notify,
    start_listener,
    stop_listener,
    _fanout,
    _subscribers,
)


class TestSSE:
    """Test subscribe/unsubscribe/fanout."""

    def setup_method(self):
        _subscribers.clear()

    def test_subscribe_creates_queue(self):
        queue = subscribe("user1")
        assert isinstance(queue, asyncio.Queue)
        assert "user1" in _subscribers
        assert queue in _subscribers["user1"]

    def test_subscribe_multiple_queues_same_user(self):
        q1 = subscribe("user1")
        q2 = subscribe("user1")
        assert len(_subscribers["user1"]) == 2
        assert q1 is not q2

    def test_unsubscribe_removes_queue(self):
        queue = subscribe("user1")
        unsubscribe("user1", queue)
        assert "user1" not in _subscribers

    def test_unsubscribe_leaves_other_queues(self):
        q1 = subscribe("user1")
        q2 = subscribe("user1")
        unsubscribe("user1", q1)
        assert _subscribers["user1"] == [q2]

    def test_unsubscribe_nonexistent_user(self):
        """Should not raise."""
        unsubscribe("ghost", asyncio.Queue())

    def test_unsubscribe_nonexistent_queue(self):
        """Should not raise when queue not in list."""
        subscribe("user1")
        unsubscribe("user1", asyncio.Queue())

    def test_fanout_broadcasts_to_all(self):
        q1 = subscribe("user1")
        q2 = subscribe("user2")
        event = SourceStatusEvent(
            politician_ids=["pol-1"],
            source_id="page-1",
            status="done",
        )
        _fanout(asdict(event))
        assert q1.qsize() == 1
        assert q2.qsize() == 1
        payload = q1.get_nowait()
        assert payload["type"] == "source_status"
        assert payload["politician_ids"] == ["pol-1"]
        assert payload["source_id"] == "page-1"

    def test_fanout_enrichment_complete_event(self):
        q1 = subscribe("user1")
        _fanout(asdict(EnrichmentCompleteEvent(languages=["Q1"], countries=[])))
        payload = q1.get_nowait()
        assert payload["type"] == "enrichment_complete"
        assert payload["languages"] == ["Q1"]

    def test_fanout_no_subscribers(self):
        """Should not raise when no subscribers exist."""
        _fanout(asdict(SourceStatusEvent(source_id="x", status="done")))


class TestSSEIntegration:
    """Test the full notify → Postgres → listener → fanout round-trip."""

    def setup_method(self):
        _subscribers.clear()

    async def test_notify_round_trip(self):
        ready = start_listener()
        try:
            await asyncio.wait_for(ready.wait(), timeout=2)

            queue = subscribe("user1")
            with Session(get_engine()) as db:
                notify(
                    SourceStatusEvent(
                        politician_ids=["pol-1"],
                        source_id="src-1",
                        status="done",
                    ),
                    db,
                )
                db.commit()
            payload = await asyncio.wait_for(queue.get(), timeout=2)
            assert payload["type"] == "source_status"
            assert payload["source_id"] == "src-1"
            assert payload["politician_ids"] == ["pol-1"]
        finally:
            await stop_listener()

    async def test_notify_multiple_events(self):
        ready = start_listener()
        try:
            await asyncio.wait_for(ready.wait(), timeout=2)

            queue = subscribe("user1")
            with Session(get_engine()) as db:
                notify(SourceStatusEvent(source_id="a", status="processing"), db)
                notify(EnrichmentCompleteEvent(languages=["Q1"], countries=["Q30"]), db)
                db.commit()

            p1 = await asyncio.wait_for(queue.get(), timeout=2)
            p2 = await asyncio.wait_for(queue.get(), timeout=2)
            types = {p1["type"], p2["type"]}
            assert types == {"source_status", "enrichment_complete"}
        finally:
            await stop_listener()
