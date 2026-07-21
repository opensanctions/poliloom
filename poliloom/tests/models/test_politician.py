"""Tests for the Politician model."""

from datetime import datetime, timedelta, timezone
from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    WikidataRelation,
    RelationType,
)
from poliloom.wikidata.date import WikidataDate


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_cascade_delete_properties(
        self, db_session, sample_politician, create_birth_date
    ):
        """Test that deleting a politician cascades to properties."""
        # Use fixture politician
        politician = sample_politician

        # Create property
        create_birth_date(politician)
        db_session.flush()

        # Delete politician should cascade to properties
        db_session.delete(politician)
        db_session.flush()

        # Property should be deleted
        assert (
            db_session.query(Property).filter_by(politician_id=politician.id).first()
            is None
        )

    def test_politician_with_all_property_types(
        self,
        db_session,
        sample_politician,
        sample_position,
        sample_location,
        sample_country,
        create_birth_date,
        create_death_date,
        create_birthplace,
        create_position,
        create_citizenship,
    ):
        """Test politician with all property types stored correctly."""
        # Use fixture entities
        politician = sample_politician
        position = sample_position
        location = sample_location
        country = sample_country

        # Create properties of all types using fixtures
        qualifiers = {
            "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
        }
        create_birth_date(politician, value="1970-01-15")
        create_death_date(politician, value="2020-12-31")
        create_birthplace(politician, location)
        create_position(politician, position, qualifiers_json=qualifiers)
        create_citizenship(politician, country)
        db_session.flush()
        db_session.refresh(politician)

        # Verify all properties are in politician.properties
        properties = politician.properties
        assert len(properties) == 5

        # Group by type for easy verification
        properties_by_type = {prop.type: prop for prop in properties}

        # Verify each property type exists with correct type enum value
        assert PropertyType.BIRTH_DATE in properties_by_type
        assert (
            properties_by_type[PropertyType.BIRTH_DATE].type == PropertyType.BIRTH_DATE
        )
        assert properties_by_type[PropertyType.BIRTH_DATE].value == "1970-01-15"
        assert properties_by_type[PropertyType.BIRTH_DATE].entity_id is None

        assert PropertyType.DEATH_DATE in properties_by_type
        assert (
            properties_by_type[PropertyType.DEATH_DATE].type == PropertyType.DEATH_DATE
        )
        assert properties_by_type[PropertyType.DEATH_DATE].value == "2020-12-31"
        assert properties_by_type[PropertyType.DEATH_DATE].entity_id is None

        assert PropertyType.BIRTHPLACE in properties_by_type
        assert (
            properties_by_type[PropertyType.BIRTHPLACE].type == PropertyType.BIRTHPLACE
        )
        assert (
            properties_by_type[PropertyType.BIRTHPLACE].entity_id
            == location.wikidata_id
        )
        assert properties_by_type[PropertyType.BIRTHPLACE].value is None

        assert PropertyType.POSITION in properties_by_type
        assert properties_by_type[PropertyType.POSITION].type == PropertyType.POSITION
        assert (
            properties_by_type[PropertyType.POSITION].entity_id == position.wikidata_id
        )
        assert properties_by_type[PropertyType.POSITION].value is None
        assert properties_by_type[PropertyType.POSITION].qualifiers_json is not None

        assert PropertyType.CITIZENSHIP in properties_by_type
        assert (
            properties_by_type[PropertyType.CITIZENSHIP].type
            == PropertyType.CITIZENSHIP
        )
        assert (
            properties_by_type[PropertyType.CITIZENSHIP].entity_id
            == country.wikidata_id
        )
        assert properties_by_type[PropertyType.CITIZENSHIP].value is None

    def test_get_priority_wikipedia_links_no_links(self, db_session, sample_politician):
        """Test get_priority_wikipedia_links when politician has no Wikipedia links."""
        result = sample_politician.get_priority_wikipedia_links(db_session)
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
        result = sample_politician.get_priority_wikipedia_links(db_session)

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

        result = sample_politician.get_priority_wikipedia_links(db_session)

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

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should return exactly 3 languages (the most popular ones available)
        assert len(result) == 3, f"Expected exactly 3 results, got {len(result)}"

        # Get the Wikipedia project IDs of returned results
        returned_project_ids = {project_id for _, project_id in result}

        # Should contain the 3 most popular: French (10), German (7), Spanish (5)
        # Should NOT contain English (3) as it's the 4th most popular
        expected_top_3 = {
            "Q8447",
            "Q48183",
            "Q8449",
        }  # French, German, Spanish Wikipedia
        assert returned_project_ids == expected_top_3, (
            f"Expected top 3 projects {expected_top_3}, got {returned_project_ids}"
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

        result = sample_politician.get_priority_wikipedia_links(db_session)

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

        result = sample_politician.get_priority_wikipedia_links(db_session)

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

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should return all 3 links
        assert len(result) == 3, f"Expected 3 results but got {len(result)}: {result}"

        project_ids = {project_id for _, project_id in result}
        assert "Q48183" in project_ids, (
            "German Wikipedia should be included (citizenship match)"
        )
        assert "Q328" in project_ids, "English Wikipedia should also be included"
        assert "Q8447" in project_ids, "French Wikipedia should also be included"


class TestPoliticianQueryBase:
    """Test cases for Politician.query_base method."""

    def test_query_base_returns_non_deleted_politicians(
        self, db_session, sample_politician
    ):
        """Test that query_base returns non-soft-deleted politicians."""
        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_base_excludes_soft_deleted_politicians(
        self, db_session, sample_politician
    ):
        """Test that query_base excludes soft-deleted politicians."""
        # Soft-delete the WikidataEntity
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


class TestPoliticianFilterByCountries:
    """Test cases for Politician.filter_by_countries method."""

    def test_filter_by_countries_finds_matching_politicians(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_source,
        create_citizenship,
    ):
        """Test that country filter finds politicians with matching citizenship."""
        # Add citizenship property
        create_citizenship(sample_politician, sample_country, sample_source)
        db_session.flush()

        # Query with country filter
        query = Politician.query_base()
        query = Politician.filter_by_countries(query, ["Q30"])
        result = db_session.execute(query).scalars().all()

        # Should find politician with US citizenship
        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_filter_by_countries_excludes_non_matching(
        self, db_session, sample_politician
    ):
        """Test that country filter excludes politicians without matching citizenship."""
        # Query with country filter (no citizenship property exists)
        query = Politician.query_base()
        query = Politician.filter_by_countries(query, ["Q30"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


class TestPoliticianQueryForEnrichment:
    """Test cases for Politician.query_for_enrichment method."""

    def test_query_returns_politicians_with_wikipedia_links(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test that query finds politicians with Wikipedia links."""
        # sample_wikipedia_link fixture creates a Wikipedia link for sample_politician
        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_excludes_politicians_without_wikipedia_links(
        self, db_session, sample_politician
    ):
        """Test that query excludes politicians without Wikipedia links."""
        # sample_politician has no Wikipedia links by default
        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

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
        query = Politician.query_for_enrichment(languages=["Q188"])
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
        query = Politician.query_for_enrichment(languages=["Q188"])
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
        query = Politician.query_for_enrichment(countries=["Q30"])
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
        query = Politician.query_for_enrichment(languages=["Q188"], countries=["Q183"])
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
        query = Politician.query_for_enrichment(countries=["Q183"])
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
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

        # Query with French language filter - should also match via French citizenship + French link
        query = Politician.query_for_enrichment(languages=["Q150"])
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
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        # Should NOT find politician - they have German citizenship but no German Wikipedia link
        assert len(result) == 0

    def test_query_respects_top_3_language_popularity_limit(
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
        """Test that only top 3 most popular languages are considered for a politician."""
        # Set up 4 languages with different global popularity levels
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
            # Create dummy politicians to establish global popularity
            # These dummies only have ONE language each, so they won't interfere with top-3 logic
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
        query = Politician.query_for_enrichment(languages=["Q1860"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids, "English (top 1) should match"

        # Query with German (2nd most popular) - sample_politician should be in results
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids, "German (top 2) should match"

        # Query with French (3rd most popular) - sample_politician should be in results
        query = Politician.query_for_enrichment(languages=["Q150"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id in result_ids, "French (top 3) should match"

        # Query with Spanish (4th most popular) - sample_politician should NOT be in results
        # Spanish is outside sample_politician's top 3
        query = Politician.query_for_enrichment(languages=["Q1321"])
        result = db_session.execute(query).scalars().all()
        result_ids = {p.id for p in result}
        assert sample_politician.id not in result_ids, (
            "Spanish (4th) should NOT match for sample_politician - outside top 3"
        )

    def test_query_excludes_soft_deleted_wikidata_entity(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test that query excludes politicians with soft-deleted WikidataEntity."""

        # Verify politician appears before soft-delete
        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1
        assert result[0].id == sample_politician.id

        # Soft-delete the WikidataEntity
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        # Query again
        query = Politician.query_for_enrichment()
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
        query = Politician.query_for_enrichment(languages=["Q1860"])
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

        query = Politician.query_for_enrichment(stateless=True)
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

        query = Politician.query_for_enrichment(stateless=True)
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
        query = Politician.query_for_enrichment(stateless=True)
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
        query = Politician.query_for_enrichment(stateless=True)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


class TestCountStatelessWithUnevaluatedCitizenship:
    """Test Politician.count_stateless_with_unevaluated_citizenship method."""

    def test_count_politician_with_extracted_citizenship_no_wikidata(
        self,
        db_session,
        sample_politician,
        sample_country,
    ):
        """Test counting politician with extracted citizenship but no Wikidata citizenship."""
        # Add extracted citizenship (no statement_id)
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            statement_id=None,
        )
        db_session.add(prop)
        db_session.flush()

        count = Politician.count_stateless_with_unevaluated_citizenship(db_session)
        assert count == 1

    def test_count_excludes_politician_with_wikidata_citizenship(
        self,
        db_session,
        sample_politician,
        sample_country,
    ):
        """Test that politicians with Wikidata citizenship are excluded."""
        # Add Wikidata citizenship (has statement_id)
        wikidata_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            statement_id="Q123$test-statement",
        )
        db_session.add(wikidata_prop)

        # Also add extracted citizenship (no statement_id)
        extracted_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            statement_id=None,
        )
        db_session.add(extracted_prop)
        db_session.flush()

        # Should be 0 because politician has Wikidata citizenship
        count = Politician.count_stateless_with_unevaluated_citizenship(db_session)
        assert count == 0

    def test_count_excludes_evaluated_extracted_citizenship(
        self,
        db_session,
        sample_politician,
        sample_country,
    ):
        """Test that evaluated (pushed) extracted citizenship is excluded."""
        # Add extracted citizenship that was already pushed (has statement_id)
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            statement_id="Q123$pushed-statement",
        )
        db_session.add(prop)
        db_session.flush()

        count = Politician.count_stateless_with_unevaluated_citizenship(db_session)
        assert count == 0

    def test_count_excludes_soft_deleted_citizenship(
        self,
        db_session,
        sample_politician,
        sample_country,
    ):
        """Test that soft-deleted citizenship is excluded."""
        # Add soft-deleted extracted citizenship (no statement_id, but deleted)
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            statement_id=None,
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(prop)
        db_session.flush()

        count = Politician.count_stateless_with_unevaluated_citizenship(db_session)
        assert count == 0

    def test_count_zero_when_no_extracted_citizenship(
        self,
        db_session,
        sample_politician,
    ):
        """Test count is 0 when politician has no extracted citizenship."""
        # sample_politician has no properties
        count = Politician.count_stateless_with_unevaluated_citizenship(db_session)
        assert count == 0


class TestHasEnrichable:
    """Test Politician.has_enrichable classmethod."""

    def test_returns_true_when_enrichable_exists(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        """Test returns True when a politician with Wikipedia links exists."""
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        assert Politician.has_enrichable(db_session) is True

    def test_returns_false_when_no_politicians(self, db_session):
        """Test returns False when no politicians exist."""
        assert Politician.has_enrichable(db_session) is False

    def test_returns_false_when_no_wikipedia_links(self, db_session, sample_politician):
        """Test returns False when politician has no Wikipedia links."""
        assert Politician.has_enrichable(db_session) is False

    def test_respects_language_filter(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        """Test that only a top-three linked language is accepted."""
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        assert Politician.has_enrichable(db_session, languages=["Q1860"]) is True
        assert Politician.has_enrichable(db_session, languages=["Q188"]) is False
        assert (
            Politician.has_enrichable(
                db_session, languages=["Q1860"], countries=["Q30"]
            )
            is True
        )
        assert (
            Politician.has_enrichable(
                db_session, languages=["Q1860"], countries=["Q183"]
            )
            is False
        )

    def test_respects_stateless_filter(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        """Test stateless mode only accepts politicians without citizenship."""
        assert Politician.has_enrichable(db_session, stateless=True) is True

        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        assert Politician.has_enrichable(db_session, stateless=True) is False

    def test_respects_country_filter(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_country,
        create_citizenship,
    ):
        """Test that country filter is applied."""
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        assert Politician.has_enrichable(db_session, countries=["Q30"]) is True
        assert Politician.has_enrichable(db_session, countries=["Q183"]) is False


class TestHasEnrichableQueryParity:
    """Ensure the existence check remains equivalent to enrichment selection."""

    @staticmethod
    def assert_matches_enrichment_query(db_session, expected, **filters):
        """Assert both query shapes agree on whether an eligible row exists."""
        selected = (
            db_session.execute(Politician.query_for_enrichment(**filters).limit(1))
            .scalars()
            .first()
            is not None
        )
        assert selected is expected
        assert Politician.has_enrichable(db_session, **filters) is selected

    def test_matches_ranked_language_boundary_and_combined_filters(
        self,
        db_session,
        sample_politician,
        sample_germany_country,
        sample_language,
        sample_wikipedia_project,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_language,
        sample_french_wikipedia_project,
        sample_spanish_language,
        sample_spanish_wikipedia_project,
        create_citizenship,
        create_wikipedia_link,
    ):
        """Citizenship ranking and the fourth linked language agree at the cutoff."""
        db_session.add(
            WikidataRelation(
                parent_entity_id=sample_german_language.wikidata_id,
                child_entity_id=sample_germany_country.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="parity_de_official_language",
            )
        )
        create_citizenship(sample_politician, sample_germany_country)

        # Give each language a distinct global popularity; no rank-boundary ties.
        languages = [
            (sample_language, sample_wikipedia_project, 5),
            # German would be fourth by popularity, but is first via citizenship.
            (sample_german_language, sample_german_wikipedia_project, 2),
            (sample_french_language, sample_french_wikipedia_project, 4),
            (sample_spanish_language, sample_spanish_wikipedia_project, 3),
        ]
        qid = 70000
        for language, project, popularity in languages:
            for number in range(popularity):
                dummy = Politician.create_with_entity(
                    db_session,
                    f"Q{qid}",
                    f"{language.name} popularity {number}",
                )
                db_session.flush()
                create_wikipedia_link(dummy, project)
                qid += 1
            create_wikipedia_link(sample_politician, project)
        db_session.flush()

        germany = [sample_germany_country.wikidata_id]
        self.assert_matches_enrichment_query(
            db_session,
            True,
            languages=[sample_german_language.wikidata_id],
            countries=germany,
        )
        self.assert_matches_enrichment_query(
            db_session,
            True,
            languages=[sample_french_language.wikidata_id],
            countries=germany,
        )
        self.assert_matches_enrichment_query(
            db_session,
            False,
            languages=[sample_spanish_language.wikidata_id],
            countries=germany,
        )

    def test_matches_soft_deleted_citizenship_and_stateless_filters(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_wikipedia_link,
        create_citizenship,
    ):
        """Deleted citizenship does not match countries and does not disqualify stateless."""
        citizenship = create_citizenship(sample_politician, sample_country)
        citizenship.soft_delete()
        db_session.flush()

        self.assert_matches_enrichment_query(
            db_session, False, countries=[sample_country.wikidata_id]
        )
        self.assert_matches_enrichment_query(db_session, True, stateless=True)

    def test_matches_missing_rankable_path_and_soft_deleted_entity(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_link,
        sample_wikipedia_project,
        sample_language,
    ):
        """A link without an active language path cannot satisfy a language filter."""
        language_of_work = next(
            relation
            for relation in db_session.query(WikidataRelation)
            if (
                relation.parent_entity_id == sample_language.wikidata_id
                and relation.child_entity_id == sample_wikipedia_project.wikidata_id
                and relation.relation_type == RelationType.LANGUAGE_OF_WORK
            )
        )
        language_of_work.soft_delete()
        db_session.flush()

        self.assert_matches_enrichment_query(
            db_session, False, languages=[sample_language.wikidata_id]
        )
        self.assert_matches_enrichment_query(db_session, True)

        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()
        self.assert_matches_enrichment_query(db_session, False)

    def test_matches_cooldown_ineligible_candidate(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Recently enriched politicians are excluded until their cooldown elapses."""
        sample_politician.enriched_at = datetime.now(timezone.utc)
        db_session.flush()
        self.assert_matches_enrichment_query(db_session, False)

        sample_politician.enriched_at = datetime.now(timezone.utc) - timedelta(
            days=Politician.get_enrichment_cooldown_days() + 1
        )
        db_session.flush()
        self.assert_matches_enrichment_query(db_session, True)
