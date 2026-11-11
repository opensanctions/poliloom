"""Tests for enrichment candidate selection and source creation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from poliloom.enrichment_queue import (
    create_enrichment_sources,
    enrichment_candidates_query,
    get_enrichment_cooldown_cutoff,
)
from poliloom.models import (
    Politician,
    RelationType,
    Source,
    SourceError,
    SourceStatus,
    Statement,
    WikidataRelation,
    WikipediaLink,
)

from .conftest import create_with_entity, make_terms


@pytest.fixture
def create_citizenship(db_session):
    """Factory to create live P27 citizenship statements for a politician."""

    def _create_citizenship(politician, country):
        statement = Statement(
            politician_id=politician.id,
            document={
                "id": f"{politician.wikidata_id}$p27-{uuid.uuid4()}",
                "rank": "normal",
                "property": {"id": "P27", "data_type": "wikibase-item"},
                "value": {"type": "value", "content": country.wikidata_id},
            },
        )
        db_session.add(statement)
        db_session.flush()
        return statement

    return _create_citizenship


class TestEnrichmentSourceSelection:
    def test_caps_sources_in_deterministic_project_order(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_project,
        sample_german_wikipedia_project,
        sample_french_wikipedia_project,
        sample_spanish_wikipedia_project,
        create_wikipedia_link,
    ):
        """The workload cap uses deterministic project QID order."""
        # Create four eligible Wikipedia links
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_spanish_wikipedia_project)
        db_session.flush()

        sources = create_enrichment_sources(
            sample_politician,
            db_session,
            languages=["Q1860", "Q188", "Q150", "Q1321"],
        )

        assert [source.wikipedia_project_id for source in sources] == [
            "Q328",
            "Q48183",
            "Q8447",
        ]

    def test_filters_languages_and_claimed_projects(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        claimed = Source(
            url=sample_wikipedia_link.url,
            wikipedia_project_id=sample_wikipedia_link.wikipedia_project_id,
        )
        claimed.politicians.append(sample_politician)
        db_session.add(claimed)
        db_session.flush()

        sources = create_enrichment_sources(
            sample_politician,
            db_session,
            languages=["Q1860", "Q188"],
        )
        assert [source.wikipedia_project_id for source in sources] == [
            sample_german_wikipedia_project.wikidata_id
        ]


class TestEnrichmentCandidatesQuery:
    """Tests for enrichment_candidates_query."""

    def test_query_returns_politicians_with_wikipedia_links(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test that query finds politicians with Wikipedia links."""
        # sample_wikipedia_link fixture creates a Wikipedia link for sample_politician
        query = enrichment_candidates_query(["Q1860"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_excludes_politicians_without_wikipedia_links(
        self, db_session, sample_politician
    ):
        """Test that query excludes politicians without Wikipedia links."""
        # sample_politician has no Wikipedia links by default
        query = enrichment_candidates_query(["Q1860"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    @pytest.mark.parametrize("error", [None, SourceError.NO_RESPONSE])
    def test_query_includes_link_with_aged_out_source(
        self, db_session, sample_politician, sample_wikipedia_link, error
    ):
        """Aged-out snapshots, including failed ones, become candidates again."""
        source = Source(
            url=sample_wikipedia_link.url,
            wikipedia_project_id=sample_wikipedia_link.wikipedia_project_id,
            fetch_timestamp=get_enrichment_cooldown_cutoff() - timedelta(seconds=1),
            error=error,
        )
        source.politicians.append(sample_politician)
        db_session.add(source)
        db_session.flush()

        result = (
            db_session.execute(enrichment_candidates_query(["Q1860"])).scalars().all()
        )

        assert [politician.id for politician in result] == [sample_politician.id]

    @pytest.mark.parametrize("status", [SourceStatus.DONE, SourceStatus.PROCESSING])
    def test_query_excludes_link_with_recent_source(
        self, db_session, sample_politician, sample_wikipedia_link, status
    ):
        """Recent snapshots block candidates regardless of their processing status."""
        source = Source(
            url=sample_wikipedia_link.url,
            wikipedia_project_id=sample_wikipedia_link.wikipedia_project_id,
            fetch_timestamp=datetime.now(UTC),
            status=status,
        )
        source.politicians.append(sample_politician)
        db_session.add(source)
        db_session.flush()

        assert (
            db_session.execute(enrichment_candidates_query(["Q1860"])).scalars().all()
            == []
        )

    def test_fresh_source_for_another_politician_does_not_block(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_wikipedia_project,
    ):
        """Snapshots are checked per politician, not across the whole project."""
        other = create_with_entity(
            Politician, db_session, "Q999001", make_terms("Other Politician")
        )
        db_session.flush()
        db_session.add(
            WikipediaLink(
                politician_id=other.id,
                url="https://en.wikipedia.org/wiki/Other_Politician",
                wikipedia_project_id=sample_wikipedia_project.wikidata_id,
            )
        )
        source = Source(
            url="https://en.wikipedia.org/wiki/Other_Politician",
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
            fetch_timestamp=datetime.now(UTC),
        )
        source.politicians.append(other)
        db_session.add(source)
        db_session.flush()

        result = (
            db_session.execute(enrichment_candidates_query(["Q1860"])).scalars().all()
        )

        assert [politician.id for politician in result] == [sample_politician.id]

    def test_query_excludes_link_without_language_of_work_relation(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_wikipedia_project,
        sample_language,
    ):
        """Projects that cannot create sources are never enrichment candidates."""
        relation = next(
            relation
            for relation in db_session.query(WikidataRelation)
            if (
                relation.parent_entity_id == sample_language.wikidata_id
                and relation.child_entity_id == sample_wikipedia_project.wikidata_id
                and relation.relation_type == RelationType.LANGUAGE_OF_WORK
            )
        )
        db_session.delete(relation)
        db_session.flush()

        assert (
            db_session.execute(enrichment_candidates_query(["Q1860"])).scalars().all()
            == []
        )

    def test_query_with_country_filter(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test country filtering based on citizenship."""
        # Give politician US citizenship
        create_citizenship(sample_politician, sample_country)

        # Create Wikipedia link
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        # Query with US country filter
        query = enrichment_candidates_query(["Q1860"], countries=["Q30"])
        result = db_session.execute(query).scalars().all()

        # Should find politician with US citizenship
        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_with_combined_filters(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_german_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test combined language and country filtering."""
        create_citizenship(sample_politician, sample_germany_country)

        # Create Wikipedia link
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with both filters
        query = enrichment_candidates_query(languages=["Q188"], countries=["Q183"])
        result = db_session.execute(query).scalars().all()

        # Should find politician matching both filters
        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_excludes_politician_not_matching_country_filter(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test that politicians without matching citizenship are excluded."""
        # Note: Germany exists but politician doesn't have German citizenship

        # Create Wikipedia link
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with German country filter (politician has no German citizenship)
        query = enrichment_candidates_query(["Q188"], countries=["Q183"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_query_with_language_filter_requires_wikipedia_link(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test that language filtering requires Wikipedia link in that language."""
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        # Query with German language filter
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_query_considers_every_requested_language(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_wikipedia_project,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_language,
        sample_french_wikipedia_project,
        sample_spanish_language,
        sample_spanish_wikipedia_project,
        create_wikipedia_link,
    ):
        """Candidate selection does not rank or cap a politician's links."""
        # Create Wikipedia links for all 4 languages for sample_politician
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_spanish_wikipedia_project)
        db_session.flush()

        # Every requested language is considered, regardless of link count.
        query = enrichment_candidates_query(languages=["Q1860"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids

        # Query with German
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids

        # Query with French
        query = enrichment_candidates_query(languages=["Q150"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids

        # Query with Spanish
        query = enrichment_candidates_query(languages=["Q1321"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids


class TestCreateEnrichmentSources:
    def test_filters_languages_and_does_not_duplicate(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        sources = create_enrichment_sources(
            sample_politician, db_session, languages=["Q1860"]
        )
        assert [source.wikipedia_project_id for source in sources] == [
            sample_wikipedia_link.wikipedia_project_id
        ]
        assert (
            create_enrichment_sources(
                sample_politician, db_session, languages=["Q1860"]
            )
            == []
        )

    def test_aged_out_source_creates_new_snapshot(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Re-enrichment preserves the old snapshot and creates a new source."""
        old_source = Source(
            url=sample_wikipedia_link.url,
            wikipedia_project_id=sample_wikipedia_link.wikipedia_project_id,
            fetch_timestamp=get_enrichment_cooldown_cutoff() - timedelta(seconds=1),
            error=SourceError.NO_RESPONSE,
        )
        old_source.politicians.append(sample_politician)
        db_session.add(old_source)
        db_session.flush()
        old_source_id = old_source.id
        old_fetch_timestamp = old_source.fetch_timestamp

        sources = create_enrichment_sources(
            sample_politician, db_session, languages=["Q1860"]
        )
        db_session.flush()

        assert len(sources) == 1
        assert sources[0].id != old_source_id
        old_source = db_session.get(Source, old_source_id)
        assert old_source.fetch_timestamp == old_fetch_timestamp
        assert old_source.error == SourceError.NO_RESPONSE
        assert len(sample_politician.sources) == 2

    def test_existing_source_blocks_its_project(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        source = Source(
            url=sample_wikipedia_link.url,
            wikipedia_project_id=sample_wikipedia_link.wikipedia_project_id,
        )
        source.politicians.append(sample_politician)
        db_session.add(source)
        db_session.flush()

        assert (
            create_enrichment_sources(
                sample_politician, db_session, languages=["Q1860"]
            )
            == []
        )
