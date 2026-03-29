"""Tests for scheduling module: orchestration of the enrichment pipeline."""

import pytest

from poliloom.scheduling import process_next_politician, schedule_enrichment
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
        politician_found = await process_next_politician()

        assert politician_found is False

        db_session.refresh(sample_politician)
        assert sample_politician.enriched_at is None
