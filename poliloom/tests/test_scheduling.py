"""Tests for scheduling module: orchestration of the enrichment pipeline."""

from unittest.mock import AsyncMock, patch

import pytest

from poliloom.scheduling import (
    ScheduledEnrichment,
    enrich_until_exhausted,
    has_enrichment_candidate,
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

        # Source creation claims the linked Wikipedia project.
        assert len(sample_politician.sources) >= 1

        # Sources should be created as PROCESSING (server_default)
        pages = db_session.query(Source).filter(Source.id.in_(result.source_ids)).all()
        assert all(p.status == SourceStatus.PROCESSING for p in pages)

    def test_returns_none_when_no_wikipedia_links(self, db_session, sample_politician):
        assert schedule_enrichment(db_session) is None


class TestHasEnrichmentCandidate:
    """Test has_enrichment_candidate mirrors schedule_enrichment eligibility."""

    def test_false_when_no_politicians(self, db_session):
        assert has_enrichment_candidate(db_session) is False

    def test_false_when_no_wikipedia_links(self, db_session, sample_politician):
        assert has_enrichment_candidate(db_session) is False

    def test_true_for_politician_with_wikipedia_links(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        assert has_enrichment_candidate(db_session) is True

    def test_false_after_source_claims_the_project(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        create_citizenship(sample_politician, sample_country)
        db_session.flush()
        schedule_enrichment(db_session)

        assert has_enrichment_candidate(db_session) is False


class TestProcessNextPolitician:
    """Test process_next_politician end-to-end orchestration."""

    @pytest.mark.asyncio
    async def test_no_wikipedia_links(self, db_session, sample_politician):
        """Test that no enrichment occurs when no politicians have Wikipedia links."""
        extracted = await process_next_politician()

        assert extracted is None

    @pytest.mark.asyncio
    async def test_notifies_when_no_candidate_found(self, db_session):
        """Waiting clients must be woken even when nothing was available to enrich."""
        with patch("poliloom.scheduling.event_bus.notify") as mock_notify:
            extracted = await process_next_politician()

        assert extracted is None
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_silent_when_no_properties_extracted(self, db_session):
        """Dry passes stay silent while callers chain the next candidate."""
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


class TestEnrichUntilExhausted:
    """Test enrich_until_exhausted processes every available candidate."""

    @pytest.mark.asyncio
    async def test_loops_until_candidates_are_exhausted(self, db_session):
        with patch(
            "poliloom.scheduling.process_next_politician", new_callable=AsyncMock
        ) as mock_process:
            mock_process.side_effect = [0, 4, None]
            enriched = await enrich_until_exhausted(
                languages=["Q1860"], countries=["Q30"]
            )

        assert enriched == 2
        assert mock_process.call_count == 3
        mock_process.assert_called_with(["Q1860"], ["Q30"], False)

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_candidates_exist(self, db_session):
        with patch(
            "poliloom.scheduling.process_next_politician",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_process:
            enriched = await enrich_until_exhausted(stateless=True)

        assert enriched == 0
        mock_process.assert_awaited_once_with(None, None, True)
