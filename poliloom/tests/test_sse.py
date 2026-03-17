"""Tests for the SSE subscriber registry."""

import asyncio

from poliloom.sse import (
    ArchivedPageStatusEvent,
    EnrichmentCompleteEvent,
    subscribe,
    unsubscribe,
    notify,
    _subscribers,
)


class TestSSE:
    """Test subscribe/unsubscribe/notify."""

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

    def test_notify_broadcasts_to_all(self):
        q1 = subscribe("user1")
        q2 = subscribe("user2")
        notify(
            ArchivedPageStatusEvent(
                politician_ids=["pol-1"],
                archived_page_id="page-1",
                status="done",
            )
        )
        assert q1.qsize() == 1
        assert q2.qsize() == 1
        payload = q1.get_nowait()
        assert payload["type"] == "archived_page_status"
        assert payload["politician_ids"] == ["pol-1"]
        assert payload["archived_page_id"] == "page-1"

    def test_enrichment_complete_event(self):
        q1 = subscribe("user1")
        notify(EnrichmentCompleteEvent(languages=["Q1"], countries=[]))
        payload = q1.get_nowait()
        assert payload["type"] == "enrichment_complete"
        assert payload["languages"] == ["Q1"]

    def test_notify_no_subscribers(self):
        """Should not raise when no subscribers exist."""
        notify(ArchivedPageStatusEvent(archived_page_id="x", status="done"))
        notify(EnrichmentCompleteEvent(languages=[], countries=[]))
