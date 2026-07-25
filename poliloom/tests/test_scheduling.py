"""Tests for scheduling module: orchestration of the enrichment pipeline."""

from unittest.mock import AsyncMock, patch

import pytest

from poliloom.scheduling import (
    ScheduledEnrichment,
    enrich_review_buffer,
    process_next_politician,
    schedule_enrichment,
)
from poliloom.models import Source, SourceStatus


class TestScheduleEnrichment:
    """Test schedule_enrichment selects a politician and creates sources."""

    def test_returns_none_when_no_politicians(self, db_session):
        assert schedule_enrichment(db_session) is None

    def test_schedules_politician_with_wikipedia_links(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        result = schedule_enrichment(db_session)

        assert result is not None
        assert result.politician_id == sample_politician.id
        assert len(result.source_ids) >= 1

        # Politician should be marked as enriched
        db_session.refresh(sample_politician)
        assert sample_politician.enriched_at is not None

        # Sources should be created as PROCESSING (server_default)
        pages = db_session.query(Source).filter(Source.id.in_(result.source_ids)).all()
        assert all(p.status == SourceStatus.PROCESSING for p in pages)

    def test_returns_none_when_no_wikipedia_links(self, db_session, sample_politician):
        assert schedule_enrichment(db_session) is None


class TestProcessNextPolitician:
    """Test process_next_politician end-to-end orchestration."""

    @pytest.mark.asyncio
    async def test_no_wikipedia_links(self, db_session, sample_politician):
        """Test that no enrichment occurs when no politicians have Wikipedia links."""
        extracted = await process_next_politician()

        assert extracted is None

        db_session.refresh(sample_politician)
        assert sample_politician.enriched_at is None

    @pytest.mark.asyncio
    async def test_notifies_when_no_candidate_found(self, db_session):
        """Waiting clients must be woken even when nothing was available to enrich."""
        with patch("poliloom.scheduling.event_bus.notify") as mock_notify:
            extracted = await process_next_politician()

        assert extracted is None
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_silent_when_no_properties_extracted(self, db_session):
        """Dry passes stay silent: enrich_review_buffer chains the next candidate."""
        scheduled = ScheduledEnrichment(politician_id="p1", source_ids=["s1", "s2"])

        with (
            patch("poliloom.scheduling.schedule_enrichment", return_value=scheduled),
            patch(
                "poliloom.scheduling.process_source_task", new_callable=AsyncMock
            ) as mock_process,
            patch("poliloom.scheduling.event_bus.notify") as mock_notify,
        ):
            mock_process.return_value = 0
            extracted = await process_next_politician()

        assert extracted == 0
        mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_extracted_property_count(self, db_session):
        """Returns the total number of properties extracted across sources."""
        scheduled = ScheduledEnrichment(politician_id="p1", source_ids=["s1", "s2"])

        with (
            patch("poliloom.scheduling.schedule_enrichment", return_value=scheduled),
            patch(
                "poliloom.scheduling.process_source_task", new_callable=AsyncMock
            ) as mock_process,
            patch("poliloom.scheduling.event_bus.notify") as mock_notify,
        ):
            mock_process.side_effect = [3, 4]
            extracted = await process_next_politician()

        assert extracted == 7
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_notifies_when_processing_fails(self, db_session):
        """Waiting clients must be woken even when source processing errors out."""
        scheduled = ScheduledEnrichment(politician_id="p1", source_ids=["s1"])

        with (
            patch("poliloom.scheduling.schedule_enrichment", return_value=scheduled),
            patch(
                "poliloom.scheduling.process_source_task", new_callable=AsyncMock
            ) as mock_process,
            patch("poliloom.scheduling.event_bus.notify") as mock_notify,
        ):
            mock_process.side_effect = RuntimeError("archiving failed")
            with pytest.raises(RuntimeError):
                await process_next_politician()

        mock_notify.assert_called_once()


class TestEnrichReviewBuffer:
    """Test enrich_review_buffer tops up the unevaluated pool to the threshold."""

    @pytest.mark.asyncio
    async def test_does_nothing_when_buffer_full(self, db_session, monkeypatch):
        """No enrichment when unevaluated count already meets the threshold."""
        monkeypatch.setenv("MIN_UNEVALUATED_POLITICIANS", "10")

        with (
            patch("poliloom.scheduling.count_unevaluated", return_value=10),
            patch(
                "poliloom.scheduling.process_next_politician", new_callable=AsyncMock
            ) as mock_process,
        ):
            enriched = await enrich_review_buffer()

        assert enriched == 0
        mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_enriches_until_threshold_reached(self, db_session, monkeypatch):
        """Loops until the buffer reaches the threshold."""
        monkeypatch.setenv("MIN_UNEVALUATED_POLITICIANS", "2")

        with (
            patch("poliloom.scheduling.count_unevaluated", side_effect=[0, 1, 2]),
            patch(
                "poliloom.scheduling.process_next_politician", new_callable=AsyncMock
            ) as mock_process,
        ):
            mock_process.side_effect = [5, 3]
            enriched = await enrich_review_buffer(
                languages=["Q1860"], countries=["Q30"]
            )

        assert enriched == 2
        assert mock_process.call_count == 2
        mock_process.assert_called_with(["Q1860"], ["Q30"], False)

    @pytest.mark.asyncio
    async def test_continues_past_dry_extractions(self, db_session, monkeypatch):
        """Zero-property passes do not count as filling the buffer."""
        monkeypatch.setenv("MIN_UNEVALUATED_POLITICIANS", "1")

        with (
            patch("poliloom.scheduling.count_unevaluated", side_effect=[0, 0, 1]),
            patch(
                "poliloom.scheduling.process_next_politician", new_callable=AsyncMock
            ) as mock_process,
        ):
            mock_process.side_effect = [0, 4]
            enriched = await enrich_review_buffer()

        assert enriched == 2

    @pytest.mark.asyncio
    async def test_stops_when_candidates_exhausted(self, db_session, monkeypatch):
        """Stops when no more politicians are available, even below threshold."""
        monkeypatch.setenv("MIN_UNEVALUATED_POLITICIANS", "10")

        with (
            patch("poliloom.scheduling.count_unevaluated", return_value=0),
            patch(
                "poliloom.scheduling.process_next_politician", new_callable=AsyncMock
            ) as mock_process,
        ):
            mock_process.side_effect = [2, None]
            enriched = await enrich_review_buffer()

        assert enriched == 1

    @pytest.mark.asyncio
    async def test_stateless_uses_stateless_buffer_count(self, db_session, monkeypatch):
        """Stateless mode measures the stateless unevaluated-citizenship buffer."""
        monkeypatch.setenv("MIN_UNEVALUATED_POLITICIANS", "5")

        with (
            patch(
                "poliloom.scheduling.count_stateless_with_unevaluated_citizenship",
                return_value=5,
            ),
            patch("poliloom.scheduling.count_unevaluated") as mock_count,
            patch(
                "poliloom.scheduling.process_next_politician", new_callable=AsyncMock
            ) as mock_process,
        ):
            enriched = await enrich_review_buffer(stateless=True)

        assert enriched == 0
        mock_count.assert_not_called()
        mock_process.assert_not_called()
