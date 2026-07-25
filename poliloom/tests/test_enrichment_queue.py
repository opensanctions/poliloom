"""Tests for enrichment candidate selection and source creation."""

from datetime import datetime, timedelta, timezone

import pytest

from poliloom.enrichment_queue import (
    create_enrichment_sources,
    enrichment_candidates_query,
    get_enrichment_cooldown_cutoff,
    get_priority_wikipedia_links,
)
from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    RelationType,
    Source,
    SourceError,
    SourceStatus,
    WikidataRelation,
)


class TestPriorityWikipediaLinks:
    def test_get_priority_wikipedia_links_no_links(self, db_session, sample_politician):
        """Test get_priority_wikipedia_links when politician has no Wikipedia links."""
        result = get_priority_wikipedia_links(sample_politician, db_session)
        assert result == []

    def test_get_priority_wikipedia_links_english_only(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_language,
    ):
        """Test get_priority_wikipedia_links when only English link available."""
        # sample_wikipedia_link fixture creates an English link
        # sample_language fixture creates the English language with LANGUAGE_OF_WORK relation
        result = get_priority_wikipedia_links(sample_politician, db_session)

        assert len(result) == 1
        url, wikipedia_project_id = result[0]
        assert "en.wikipedia.org" in url
        assert wikipedia_project_id == "Q328"  # English Wikipedia project

    def test_get_priority_wikipedia_links_citizenship_priority(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_german_language,
        sample_germany_country,
        sample_german_wikipedia_project,
        sample_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test get_priority_wikipedia_links with citizenship-based prioritization."""
        # Create official language relation: German is official language of Germany
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_germany_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_1",
        )
        db_session.add(relation)

        # Create citizenship property for politician
        create_citizenship(sample_politician, sample_germany_country)

        # Create Wikipedia links for both German and English
        # Add more German wikipedia links globally to make it "popular"
        Politician.create_with_entity(db_session, "Q999", "Other Politician")
        db_session.flush()

        # Create multiple German links to simulate popularity
        for i in range(5):  # Make German popular
            dummy_politician = Politician.create_with_entity(
                db_session, f"Q{1000 + i}", f"Dummy {i}"
            )
            db_session.flush()
            create_wikipedia_link(
                dummy_politician, sample_german_wikipedia_project, f"Dummy_{i}"
            )

        # Create the actual politician's links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        result = get_priority_wikipedia_links(sample_politician, db_session)

        # Should get both German (from citizenship) and English, but German should be prioritized
        assert len(result) >= 1
        # German should be first due to citizenship priority
        url, wikipedia_project_id = result[0]
        assert "de.wikipedia.org" in url

    def test_get_priority_wikipedia_links_no_citizenship(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_project,
        sample_french_wikipedia_project,
        sample_german_wikipedia_project,
        sample_spanish_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test get_priority_wikipedia_links when politician has no citizenship."""
        # Map ISO codes to Wikipedia projects for convenience
        wikipedia_projects = {
            "en": sample_wikipedia_project,
            "fr": sample_french_wikipedia_project,
            "de": sample_german_wikipedia_project,
            "es": sample_spanish_wikipedia_project,
        }

        # Create many links for each language to simulate different popularity
        # Make French most popular (10), German second (7), Spanish third (5), English least (3)
        popularity_data = [("fr", 10), ("de", 7), ("es", 5), ("en", 3)]

        base_qid = 50000  # Use a higher base to avoid conflicts
        for iso_code, count in popularity_data:
            for i in range(count):
                qid = f"Q{base_qid + i}"
                dummy_politician = Politician.create_with_entity(
                    db_session,
                    qid,
                    f"Dummy {iso_code} {i}",
                )
                db_session.flush()
                create_wikipedia_link(
                    dummy_politician, wikipedia_projects[iso_code], f"Dummy_{i}"
                )
            base_qid += count  # Increment base to avoid overlaps

        # Create politician's actual links
        for iso_code in ["en", "fr", "de", "es"]:
            create_wikipedia_link(sample_politician, wikipedia_projects[iso_code])

        db_session.flush()

        result = get_priority_wikipedia_links(sample_politician, db_session)

        # Should return exactly 3 languages (the most popular ones available)
        assert len(result) == 3, f"Expected exactly 3 results, got {len(result)}"

        # Get the Wikipedia project IDs of returned results
        returned_project_ids = {project_id for _, project_id in result}

        # Should contain the 3 most popular: French (10), German (7), Spanish (5)
        # Should NOT contain English (3) as it's the 4th most popular
        expected_priority_projects = {
            "Q8447",
            "Q48183",
            "Q8449",
        }  # French, German, Spanish Wikipedia
        assert returned_project_ids == expected_priority_projects, (
            "Expected priority projects "
            f"{expected_priority_projects}, got {returned_project_ids}"
        )

    def test_get_priority_wikipedia_links_multiple_citizenships(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_germany_country,
        sample_language,
        sample_wikipedia_project,
        sample_german_language,
        sample_german_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test get_priority_wikipedia_links with multiple citizenships."""
        # Create official language relations
        relations = [
            WikidataRelation(
                parent_entity_id=sample_language.wikidata_id,
                child_entity_id=sample_country.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="test_statement_en_us",
            ),
            WikidataRelation(
                parent_entity_id=sample_german_language.wikidata_id,
                child_entity_id=sample_germany_country.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="test_statement_de_de",
            ),
        ]
        for relation in relations:
            db_session.add(relation)

        # Create dual citizenship
        create_citizenship(sample_politician, sample_country)
        create_citizenship(sample_politician, sample_germany_country)

        # Create Wikipedia links using the factory
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)

        db_session.flush()

        result = get_priority_wikipedia_links(sample_politician, db_session)

        # Should get languages from citizenships prioritized, up to 3 total
        assert len(result) <= 3
        assert len(result) >= 1

        # Both citizenship languages should be represented (they get priority boost)
        project_ids = {project_id for _, project_id in result}
        assert (
            "Q328" in project_ids or "Q48183" in project_ids
        )  # At least one citizenship language (English or German Wikipedia)

    def test_get_priority_wikipedia_links_citizenship_no_matching_language(
        self,
        db_session,
        sample_politician,
        sample_argentina_country,
        sample_spanish_language,
        sample_language,
        sample_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test get_priority_wikipedia_links when politician has citizenship but Wikipedia link language doesn't match official languages."""
        # Create official language relation: Spanish is official language of Argentina
        relation = WikidataRelation(
            parent_entity_id=sample_spanish_language.wikidata_id,
            child_entity_id=sample_argentina_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_es_ar",
        )
        db_session.add(relation)

        # Give politician Argentine citizenship
        create_citizenship(sample_politician, sample_argentina_country)

        # Create only an English Wikipedia link (not matching the official language)
        # sample_language and sample_wikipedia_project provide English language/project
        create_wikipedia_link(
            sample_politician, sample_wikipedia_project, "Carlos_Cánepa"
        )
        db_session.flush()

        result = get_priority_wikipedia_links(sample_politician, db_session)

        # Should return the English link even though it's not an official language
        # When no links match official languages, should fall back to all available links
        assert len(result) == 1, f"Expected 1 result but got {len(result)}: {result}"
        url, wikipedia_project_id = result[0]
        assert "en.wikipedia.org" in url
        assert wikipedia_project_id == "Q328"  # English Wikipedia project

    def test_get_priority_wikipedia_links_returns_all_three_with_citizenship_match(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_language,
        sample_wikipedia_project,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test get_priority_wikipedia_links returns all 3 links when one matches citizenship language."""
        # Create official language relation: German is official language of Germany
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_germany_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        create_citizenship(sample_politician, sample_germany_country)

        # Create 3 Wikipedia links
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        db_session.flush()

        result = get_priority_wikipedia_links(sample_politician, db_session)

        # Should return all 3 links
        assert len(result) == 3, f"Expected 3 results but got {len(result)}: {result}"

        project_ids = {project_id for _, project_id in result}
        assert "Q48183" in project_ids, (
            "German Wikipedia should be included (citizenship match)"
        )
        assert "Q328" in project_ids, "English Wikipedia should also be included"
        assert "Q8447" in project_ids, "French Wikipedia should also be included"

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

        links = get_priority_wikipedia_links(
            sample_politician,
            db_session,
            languages=["Q1860", "Q188"],
            eligible_only=True,
        )
        assert [project_id for _, project_id in links] == [
            sample_german_wikipedia_project.wikidata_id
        ]


class TestEnrichmentCandidatesQuery:
    """Tests for enrichment_candidates_query."""

    def test_query_returns_politicians_with_wikipedia_links(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test that query finds politicians with Wikipedia links."""
        # sample_wikipedia_link fixture creates a Wikipedia link for sample_politician
        query = enrichment_candidates_query()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_excludes_politicians_without_wikipedia_links(
        self, db_session, sample_politician
    ):
        """Test that query excludes politicians without Wikipedia links."""
        # sample_politician has no Wikipedia links by default
        query = enrichment_candidates_query()
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

        result = db_session.execute(enrichment_candidates_query()).scalars().all()

        assert [politician.id for politician in result] == [sample_politician.id]

    @pytest.mark.parametrize("status", [SourceStatus.DONE, SourceStatus.PROCESSING])
    def test_query_excludes_link_with_recent_source(
        self, db_session, sample_politician, sample_wikipedia_link, status
    ):
        """Recent snapshots block candidates regardless of their processing status."""
        source = Source(
            url=sample_wikipedia_link.url,
            wikipedia_project_id=sample_wikipedia_link.wikipedia_project_id,
            fetch_timestamp=datetime.now(timezone.utc),
            status=status,
        )
        source.politicians.append(sample_politician)
        db_session.add(source)
        db_session.flush()

        assert db_session.execute(enrichment_candidates_query()).scalars().all() == []

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
        relation.soft_delete()
        db_session.flush()

        assert db_session.execute(enrichment_candidates_query()).scalars().all() == []

    def test_query_with_language_filter_citizenship_match(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_german_language,
        sample_german_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test language filtering based on citizenship official languages."""
        # Create official language relation: German is official in Germany
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_germany_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        create_citizenship(sample_politician, sample_germany_country)

        # Create German Wikipedia link
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with German language filter
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        # Should find politician because they have German citizenship
        # and German is official language of Germany
        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_with_language_filter_non_citizenship_match_in_top_3(
        self,
        db_session,
        sample_politician,
        sample_france_country,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_language,
        sample_french_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test that politicians are found when filter language is in top 3, even if not citizenship-matched."""
        # Create official language relation: French is official in France
        relation = WikidataRelation(
            parent_entity_id=sample_french_language.wikidata_id,
            child_entity_id=sample_france_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_fr_fr",
        )
        db_session.add(relation)

        # Give politician French citizenship
        create_citizenship(sample_politician, sample_france_country)

        # Create BOTH French (citizenship match) and German Wikipedia links
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with German language filter
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        # Should find politician - German is in their top 3 (they only have 2 links)
        # Citizenship match affects ranking but doesn't exclude other languages
        assert len(result) == 1
        assert result[0].id == sample_politician.id

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
        query = enrichment_candidates_query(countries=["Q30"])
        result = db_session.execute(query).scalars().all()

        # Should find politician with US citizenship
        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_with_combined_filters(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_german_language,
        sample_german_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test combined language and country filtering."""
        # Create official language relation
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_germany_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
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
        query = enrichment_candidates_query(countries=["Q183"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_query_with_multiple_citizenships_matches_any(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_france_country,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_language,
        sample_french_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test that politicians with multiple citizenships match if any citizenship language has a link."""
        # Create official language relations
        de_relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_germany_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        fr_relation = WikidataRelation(
            parent_entity_id=sample_french_language.wikidata_id,
            child_entity_id=sample_france_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_fr_fr",
        )
        db_session.add_all([de_relation, fr_relation])

        # Give politician dual citizenship
        create_citizenship(sample_politician, sample_germany_country)
        create_citizenship(sample_politician, sample_france_country)

        # Create BOTH German and French Wikipedia links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        db_session.flush()

        # Query with German language filter - should match via German citizenship + German link
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

        # Query with French language filter - should also match via French citizenship + French link
        query = enrichment_candidates_query(languages=["Q150"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_with_language_filter_requires_wikipedia_link(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_german_language,
        sample_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test that language filtering requires Wikipedia link in that language."""
        # Create official language relation
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_germany_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        create_citizenship(sample_politician, sample_germany_country)

        # Create only English Wikipedia link (not German)
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        # Query with German language filter
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        # Should NOT find politician - they have German citizenship but no German Wikipedia link
        assert len(result) == 0

    def test_query_respects_priority_wikipedia_project_limit(
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
        """Test that only three highest-priority Wikipedia projects are considered."""
        # Set up four projects with different global link-count popularity levels
        # English: 5, German: 4, French: 3, Spanish: 2
        languages_data = [
            (sample_language, sample_wikipedia_project, 5),  # English - most popular
            (
                sample_german_language,
                sample_german_wikipedia_project,
                4,
            ),  # German - 2nd
            (
                sample_french_language,
                sample_french_wikipedia_project,
                3,
            ),  # French - 3rd
            (
                sample_spanish_language,
                sample_spanish_wikipedia_project,
                2,
            ),  # Spanish - 4th
        ]

        base_qid = 60000
        for lang, wp, popularity in languages_data:
            # Create dummy politicians to establish global project popularity.
            # Each has one project link, so it does not affect priority ranking.
            for i in range(popularity):
                dummy = Politician.create_with_entity(
                    db_session, f"Q{base_qid + i}", f"Dummy {lang.iso_639_1} {i}"
                )
                db_session.flush()
                create_wikipedia_link(dummy, wp)

            base_qid += popularity

        # Create Wikipedia links for all 4 languages for sample_politician
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_spanish_wikipedia_project)
        db_session.flush()

        # Query with English (most popular) - sample_politician should be in results
        query = enrichment_candidates_query(languages=["Q1860"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids, "English (top 1) should match"

        # Query with German (2nd most popular) - sample_politician should be in results
        query = enrichment_candidates_query(languages=["Q188"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids, "German (top 2) should match"

        # Query with French (3rd most popular) - sample_politician should be in results
        query = enrichment_candidates_query(languages=["Q150"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids, "French (top 3) should match"

        # Query with Spanish (4th most popular) - sample_politician should NOT be in results
        # Spanish is outside sample_politician's top 3
        query = enrichment_candidates_query(languages=["Q1321"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids

    def test_query_excludes_soft_deleted_wikidata_entity(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test that query excludes politicians with soft-deleted WikidataEntity."""

        # Verify politician appears before soft-delete
        query = enrichment_candidates_query()
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1
        assert result[0].id == sample_politician.id

        # Soft-delete the WikidataEntity
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        # Query again
        query = enrichment_candidates_query()
        result = db_session.execute(query).scalars().all()

        # Should return empty because WikidataEntity has been soft-deleted
        assert len(result) == 0

    def test_query_with_non_official_language_wikipedia_link(
        self,
        db_session,
        sample_politician,
        sample_spain_country,
        sample_spanish_language,
        sample_language,
        sample_wikipedia_project,
        create_wikipedia_link,
        create_citizenship,
    ):
        """Test that politicians with Wikipedia links in non-official languages are found."""
        # Create official language relation: Spanish is official in Spain
        relation = WikidataRelation(
            parent_entity_id=sample_spanish_language.wikidata_id,
            child_entity_id=sample_spain_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_es_es",
        )
        db_session.add(relation)

        # Give politician Spanish citizenship
        create_citizenship(sample_politician, sample_spain_country)

        # Create ONLY an English Wikipedia link (not Spanish)
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        # Query with English language filter
        query = enrichment_candidates_query(languages=["Q1860"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_stateless_finds_politicians_without_citizenship(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
    ):
        """Test that stateless=True finds politicians without any citizenship property."""
        # sample_politician has no citizenship by default
        # sample_wikipedia_link ensures they have Wikipedia links

        query = enrichment_candidates_query(stateless=True)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_stateless_excludes_politicians_with_citizenship(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_wikipedia_link,
        create_citizenship,
    ):
        """Test that stateless=True excludes politicians who have citizenship."""
        # Add citizenship property
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        query = enrichment_candidates_query(stateless=True)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_query_stateless_excludes_soft_deleted_citizenship(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_wikipedia_link,
    ):
        """Test that stateless=True includes politicians whose citizenship was soft-deleted."""
        # Add soft-deleted citizenship property
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(prop)
        db_session.flush()

        # Should find politician because the only citizenship is soft-deleted
        query = enrichment_candidates_query(stateless=True)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_stateless_requires_wikipedia_links(
        self,
        db_session,
        sample_politician,
    ):
        """Test that stateless=True still requires Wikipedia links."""
        # sample_politician has no Wikipedia links and no citizenship
        query = enrichment_candidates_query(stateless=True)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


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

        sources = create_enrichment_sources(sample_politician, db_session)
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

        assert create_enrichment_sources(sample_politician, db_session) == []
