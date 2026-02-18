"""Tests for the Politician model."""

from datetime import datetime, timezone
from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    WikidataRelation,
    RelationType,
)
from poliloom.wikidata_date import WikidataDate


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


class TestPoliticianFilterByUnevaluated:
    """Test cases for Politician.filter_by_unevaluated_properties method."""

    def test_filter_returns_politicians_with_unevaluated_properties(
        self, db_session, sample_politician, sample_archived_page, create_birth_date
    ):
        """Test that filter finds politicians with unevaluated properties."""
        # Add an unevaluated property
        create_birth_date(sample_politician, archived_page=sample_archived_page)
        db_session.flush()

        # Execute query with filter
        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_filter_excludes_politicians_with_only_evaluated_properties(
        self, db_session, sample_politician, sample_archived_page, create_birth_date
    ):
        """Test that filter excludes politicians with statement_id (pushed to Wikidata)."""
        # Add property with statement_id (evaluated and pushed)
        create_birth_date(
            sample_politician,
            archived_page=sample_archived_page,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.flush()

        # Execute query with filter
        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_filter_excludes_soft_deleted_properties(
        self, db_session, sample_politician
    ):
        """Test that filter excludes soft-deleted properties."""
        # Add soft-deleted unevaluated property (no statement_id, but deleted)
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(prop)
        db_session.flush()

        # Execute query with filter
        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_filter_with_language_parameter(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_german_language,
        create_archived_page,
        create_birth_date,
        create_death_date,
    ):
        """Test language filtering based on archived page languages."""
        # Create archived pages with language associations
        en_page = create_archived_page(
            url="https://en.example.com/test",
            content_hash="en123",
            languages=[sample_language],
        )
        de_page = create_archived_page(
            url="https://de.example.com/test",
            content_hash="de123",
            languages=[sample_german_language],
        )

        # Add properties from different language sources
        create_birth_date(sample_politician, archived_page=en_page)
        create_death_date(sample_politician, archived_page=de_page)
        db_session.flush()

        # Query with English language filter
        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query, languages=["Q1860"])
        result = db_session.execute(query).scalars().all()

        # Should find politician because they have English property
        assert len(result) == 1
        assert result[0].id == sample_politician.id


class TestPoliticianFilterByCountries:
    """Test cases for Politician.filter_by_countries method."""

    def test_filter_by_countries_finds_matching_politicians(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_archived_page,
        create_citizenship,
    ):
        """Test that country filter finds politicians with matching citizenship."""
        # Add citizenship property
        create_citizenship(sample_politician, sample_country, sample_archived_page)
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


class TestPropertyFindMatching:
    """Test cases for the Property.find_matching() class method.

    Note: Comparison logic is tested in TestPropertyCompareTo.
    These tests focus on the DB integration (no existing property case).
    """

    def test_find_matching_birth_date_no_existing(self, db_session, sample_politician):
        """Test find_matching returns None when no existing date exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert result is None

    def test_find_matching_position_no_existing(
        self, db_session, sample_politician, sample_position
    ):
        """Test find_matching returns None when no existing position exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.POSITION,
            entity_id=sample_position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-00-00T00:00:00Z", "precision": 9}
                        }
                    }
                ]
            },
        )

        assert result is None

    def test_find_matching_birthplace_no_existing(
        self, db_session, sample_politician, sample_location
    ):
        """Test find_matching returns None when no existing birthplace exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.BIRTHPLACE,
            entity_id=sample_location.wikidata_id,
        )

        assert result is None

    def test_find_matching_citizenship_no_existing(
        self, db_session, sample_politician, sample_country
    ):
        """Test find_matching returns None when no existing citizenship exists."""
        result = Property.find_matching(
            db_session,
            sample_politician.id,
            PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )

        assert result is None


class TestPropertyExtractTimeframe:
    """Tests for Property._extract_timeframe_from_qualifiers."""

    def test_extract_both_dates(self):
        """Test extracting both start and end dates."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-15T00:00:00Z", "precision": 11}
                    }
                }
            ],
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-06-30T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is not None
        assert end is not None
        assert start.precision == 11
        assert end.precision == 11

    def test_extract_start_only(self):
        """Test extracting only start date."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is not None
        assert end is None

    def test_extract_end_only(self):
        """Test extracting only end date."""
        qualifiers = {
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-12-31T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is None
        assert end is not None

    def test_extract_none_qualifiers(self):
        """Test with None qualifiers."""
        start, end = Property._extract_timeframe_from_qualifiers(None)

        assert start is None
        assert end is None

    def test_extract_empty_qualifiers(self):
        """Test with empty qualifiers dict."""
        start, end = Property._extract_timeframe_from_qualifiers({})

        assert start is None
        assert end is None

    def test_extract_other_qualifiers_only(self):
        """Test with qualifiers that don't include P580/P582."""
        qualifiers = {
            "P585": [  # Point in time
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is None
        assert end is None


class TestPropertyCompareTo:
    """Tests for Property._compare_to method."""

    def test_different_types_no_match(self, sample_politician):
        """Test that different property types don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.DEATH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_birth_date_equal_precision(self, sample_politician):
        """Test birth dates with equal precision."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_birth_date_self_more_precise(self, sample_politician):
        """Test birth date where self is more precise."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,  # Day
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-00T00:00:00Z",
            value_precision=10,  # Month
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.SELF_MORE_PRECISE

    def test_birth_date_other_more_precise(self, sample_politician):
        """Test birth date where other is more precise."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-00-00T00:00:00Z",
            value_precision=9,  # Year
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,  # Day
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.OTHER_MORE_PRECISE

    def test_birth_date_different_years_no_match(self, sample_politician):
        """Test birth dates with different years don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1951-05-15T00:00:00Z",
            value_precision=11,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_position_different_entity_no_match(self, sample_politician):
        """Test positions with different entities don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q456",
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_position_self_has_dates_other_none(self, sample_politician):
        """Test position where self has dates and other doesn't."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.SELF_MORE_PRECISE

    def test_position_other_has_dates_self_none(self, sample_politician):
        """Test position where other has dates and self doesn't."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.OTHER_MORE_PRECISE

    def test_position_both_no_dates_equal(self, sample_politician):
        """Test positions both without dates are equal."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json=None,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_position_different_timeframes_no_match(self, sample_politician):
        """Test positions with different timeframes don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.POSITION,
            entity_id="Q123",
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2015-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_birthplace_same_entity_equal(self, sample_politician):
        """Test birthplaces with same entity are equal."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q60",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q60",
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_birthplace_different_entity_no_match(self, sample_politician):
        """Test birthplaces with different entities don't match."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q60",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id="Q65",
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_citizenship_same_entity_equal(self, sample_politician):
        """Test citizenships with same entity are equal."""
        prop1 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
        )
        prop2 = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL
