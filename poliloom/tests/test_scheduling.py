"""Tests for scheduling module: orchestration of the enrichment pipeline."""

from unittest.mock import AsyncMock, patch

import pytest

from poliloom.models import Politician, Source, SourceStatus
from poliloom.scheduling import (
    ScheduledEnrichment,
    enrich_until_serveable,
    process_enrichment,
    schedule_enrichment,
)

from .conftest import create_with_entity, make_terms


class TestScheduleEnrichment:
    """Test schedule_enrichment selects a politician and creates sources."""

    def test_returns_none_when_no_politicians(self, db_session):
        assert schedule_enrichment(db_session, ["Q1860"]) is None

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

        result = schedule_enrichment(db_session, ["Q1860"])

        assert result is not None
        assert result.politician_id == sample_politician.id
        assert result.wikidata_id == sample_politician.wikidata_id
        assert len(result.source_ids) >= 1

        # Source creation claims the linked Wikipedia project.
        assert len(sample_politician.sources) >= 1

        # Sources should be created as PROCESSING (server_default)
        pages = db_session.query(Source).filter(Source.id.in_(result.source_ids)).all()
        assert all(p.status == SourceStatus.PROCESSING for p in pages)

    def test_prefers_politician_with_full_language_coverage(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_project,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        english_only = create_with_entity(
            Politician, db_session, "Q999999999", make_terms("English Only")
        )
        db_session.flush()
        create_wikipedia_link(english_only, sample_wikipedia_project)
        db_session.flush()

        result = schedule_enrichment(db_session, ["Q1860", "Q188"])

        assert result is not None
        assert result.wikidata_id == sample_politician.wikidata_id
        sources = (
            db_session.query(Source).filter(Source.id.in_(result.source_ids)).all()
        )
        assert {source.wikipedia_project_id for source in sources} == {
            sample_wikipedia_project.wikidata_id,
            sample_german_wikipedia_project.wikidata_id,
        }

    def test_returns_none_when_no_wikipedia_links(self, db_session, sample_politician):
        assert schedule_enrichment(db_session, ["Q1860"]) is None


class TestProcessEnrichment:
    @pytest.mark.asyncio
    async def test_processes_every_scheduled_source(self):
        scheduled = ScheduledEnrichment(
            politician_id="p1", wikidata_id="Q1", source_ids=["s1", "s2"]
        )
        with patch(
            "poliloom.scheduling.process_source_task", new_callable=AsyncMock
        ) as process:
            await process_enrichment(scheduled)

        assert process.await_count == 2
        process.assert_any_await("s1", "p1")
        process.assert_any_await("s2", "p1")


class TestEnrichUntilServeable:
    @pytest.mark.asyncio
    async def test_stops_without_enriching_when_floor_exists(self):
        with (
            patch("poliloom.scheduling.count_serveable", return_value=1),
            patch("poliloom.scheduling.schedule_enrichment") as schedule,
        ):
            await enrich_until_serveable(["Q1860"], ["Q30"])
        schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_enriches_until_floor_is_reached(self):
        scheduled = ScheduledEnrichment(
            politician_id="p1", wikidata_id="Q1", source_ids=["s1"]
        )
        with (
            patch("poliloom.scheduling.count_serveable", side_effect=[0, 0, 1]),
            patch(
                "poliloom.scheduling.schedule_enrichment", return_value=scheduled
            ) as schedule,
            patch(
                "poliloom.scheduling.process_enrichment", new_callable=AsyncMock
            ) as process,
        ):
            await enrich_until_serveable(["Q1860"], ["Q30"])

        assert schedule.call_count == 2
        assert process.await_count == 2

    @pytest.mark.asyncio
    async def test_stops_when_no_candidates_remain(self):
        with (
            patch("poliloom.scheduling.count_serveable", return_value=0),
            patch("poliloom.scheduling.schedule_enrichment", return_value=None),
            patch(
                "poliloom.scheduling.process_enrichment", new_callable=AsyncMock
            ) as process,
        ):
            await enrich_until_serveable(["Q1860"])
        process.assert_not_awaited()
