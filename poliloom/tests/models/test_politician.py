"""Tests for the Politician model."""

from datetime import datetime, timezone
from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    Language,
    Country,
    WikipediaLink,
    WikidataRelation,
    RelationType,
    ArchivedPage,
)
from poliloom.wikidata_date import WikidataDate


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_cascade_delete_properties(self, db_session, sample_politician):
        """Test that deleting a politician cascades to properties."""
        # Use fixture politician
        politician = sample_politician

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
        )
        db_session.add(prop)
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
    ):
        """Test politician with all property types stored correctly."""
        # Use fixture entities
        politician = sample_politician
        position = sample_position
        location = sample_location
        country = sample_country

        # Create properties of all types
        birth_date = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1970-01-15",
            value_precision=11,
        )
        death_date = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="2020-12-31",
            value_precision=11,
        )
        birthplace = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )
        pos_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
                "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
            },
        )
        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        db_session.add_all(
            [birth_date, death_date, birthplace, pos_property, citizenship]
        )
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
        url, iso_639_1, iso_639_2, iso_639_3 = result[0]
        assert "en.wikipedia.org" in url
        assert iso_639_1 == "en"
        assert iso_639_2 == "eng"

    def test_get_priority_wikipedia_links_citizenship_priority(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_wikipedia_project,
    ):
        """Test get_priority_wikipedia_links with citizenship-based prioritization."""
        # Create a German country
        german_country = Country.create_with_entity(db_session, "Q183", "Germany")
        german_country.iso_code = "DE"
        db_session.flush()

        # Create official language relation: German is official language of Germany
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=german_country.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_1",
        )
        db_session.add(relation)

        # Create citizenship property for politician
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=german_country.wikidata_id,
        )
        db_session.add(citizenship)

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
            de_link = WikipediaLink(
                politician_id=dummy_politician.id,
                url=f"https://de.wikipedia.org/wiki/Dummy_{i}",
                wikipedia_project_id=sample_german_wikipedia_project.wikidata_id,
            )
            db_session.add(de_link)

        # Create the actual politician's links
        german_link = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://de.wikipedia.org/wiki/Test_Politician",
            wikipedia_project_id=sample_german_wikipedia_project.wikidata_id,
        )
        english_link = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(german_link)
        db_session.add(english_link)
        db_session.flush()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should get both German (from citizenship) and English, but German should be prioritized
        assert len(result) >= 1
        # German should be first due to citizenship priority
        url, iso_639_1, iso_639_2, iso_639_3 = result[0]
        assert "de.wikipedia.org" in url
        assert iso_639_1 == "de"
        assert iso_639_2 == "deu"

    def test_get_priority_wikipedia_links_no_citizenship(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_project,
        sample_french_wikipedia_project,
        sample_german_wikipedia_project,
        sample_spanish_wikipedia_project,
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
                link = WikipediaLink(
                    politician_id=dummy_politician.id,
                    url=f"https://{iso_code}.wikipedia.org/wiki/Dummy_{i}",
                    wikipedia_project_id=wikipedia_projects[iso_code].wikidata_id,
                )
                db_session.add(link)
            base_qid += count  # Increment base to avoid overlaps

        # Create politician's actual links
        links_data = [
            ("https://en.wikipedia.org/wiki/Test_Politician", "en"),
            ("https://fr.wikipedia.org/wiki/Test_Politician", "fr"),
            ("https://de.wikipedia.org/wiki/Test_Politician", "de"),
            ("https://es.wikipedia.org/wiki/Test_Politician", "es"),
        ]
        for url, iso_code in links_data:
            link = WikipediaLink(
                politician_id=sample_politician.id,
                url=url,
                wikipedia_project_id=wikipedia_projects[iso_code].wikidata_id,
            )
            db_session.add(link)

        db_session.flush()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should return exactly 3 languages (the most popular ones available)
        assert len(result) == 3, f"Expected exactly 3 results, got {len(result)}"

        # Get the ISO codes of returned languages
        returned_iso_codes = {iso_639_1 for _, iso_639_1, _, _ in result}

        # Should contain the 3 most popular languages: fr (10), de (7), es (5)
        # Should NOT contain en (3) as it's the 4th most popular
        expected_top_3 = {"fr", "de", "es"}
        assert returned_iso_codes == expected_top_3, (
            f"Expected top 3 languages {expected_top_3}, got {returned_iso_codes}"
        )

    def test_get_priority_wikipedia_links_multiple_citizenships(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_wikipedia_project,
        sample_german_language,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test get_priority_wikipedia_links with multiple citizenships."""
        # Create two countries with different official languages
        usa = Country.create_with_entity(db_session, "Q30", "United States")
        usa.iso_code = "US"
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        db_session.flush()

        # Create official language relations
        relations = [
            WikidataRelation(
                parent_entity_id=sample_language.wikidata_id,
                child_entity_id=usa.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="test_statement_en_us",
            ),
            WikidataRelation(
                parent_entity_id=sample_german_language.wikidata_id,
                child_entity_id=germany.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="test_statement_de_de",
            ),
        ]
        for relation in relations:
            db_session.add(relation)

        # Create dual citizenship
        citizenships = [
            Property(
                politician_id=sample_politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=usa.wikidata_id,
            ),
            Property(
                politician_id=sample_politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            ),
        ]
        for citizenship in citizenships:
            db_session.add(citizenship)

        # Create Wikipedia links using the factory
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)

        db_session.flush()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should get languages from citizenships prioritized, up to 3 total
        assert len(result) <= 3
        assert len(result) >= 1

        # Both citizenship languages should be represented (they get priority boost)
        iso_codes = {iso_639_1 for _, iso_639_1, _, _ in result}
        assert (
            "en" in iso_codes or "de" in iso_codes
        )  # At least one citizenship language

    def test_get_priority_wikipedia_links_citizenship_no_matching_language(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test get_priority_wikipedia_links when politician has citizenship but Wikipedia link language doesn't match official languages."""
        # Create a country and language that don't match
        argentina = Country.create_with_entity(db_session, "Q414", "Argentina")
        argentina.iso_code = "AR"

        # Spanish as official language of Argentina
        spanish = Language.create_with_entity(db_session, "Q1321", "Spanish")
        spanish.iso_639_1 = "es"
        spanish.iso_639_2 = "spa"
        db_session.flush()

        # Create official language relation: Spanish is official language of Argentina
        relation = WikidataRelation(
            parent_entity_id=spanish.wikidata_id,
            child_entity_id=argentina.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_es_ar",
        )
        db_session.add(relation)

        # Give politician Argentine citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=argentina.wikidata_id,
        )
        db_session.add(citizenship)

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
        url, iso_639_1, iso_639_2, iso_639_3 = result[0]
        assert "en.wikipedia.org" in url
        assert iso_639_1 == "en"
        assert iso_639_2 == "eng"

    def test_get_priority_wikipedia_links_returns_all_three_with_citizenship_match(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_wikipedia_project,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test get_priority_wikipedia_links returns all 3 links when one matches citizenship language."""
        # Create Germany country with German as official language
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        db_session.flush()

        # Create official language relation: German is official language of Germany
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=germany.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany.wikidata_id,
        )
        db_session.add(citizenship)

        # Create 3 Wikipedia links
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        db_session.flush()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should return all 3 links
        assert len(result) == 3, f"Expected 3 results but got {len(result)}: {result}"

        iso_codes = {iso_639_1 for _, iso_639_1, _, _ in result}
        assert "de" in iso_codes, "German link should be included (citizenship match)"
        assert "en" in iso_codes, "English link should also be included"
        assert "fr" in iso_codes, "French link should also be included"


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
        self, db_session, sample_politician, sample_archived_page
    ):
        """Test that filter finds politicians with unevaluated properties."""
        # Add an unevaluated property
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
            statement_id=None,  # Unevaluated
        )
        db_session.add(prop)
        db_session.flush()

        # Execute query with filter
        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_filter_excludes_politicians_with_only_evaluated_properties(
        self, db_session, sample_politician, sample_archived_page
    ):
        """Test that filter excludes politicians with statement_id (pushed to Wikidata)."""
        # Add property with statement_id (evaluated and pushed)
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(prop)
        db_session.flush()

        # Execute query with filter
        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_filter_excludes_soft_deleted_properties(
        self, db_session, sample_politician, sample_archived_page
    ):
        """Test that filter excludes soft-deleted properties."""
        # Add soft-deleted unevaluated property
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
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
        self, db_session, sample_politician, sample_language
    ):
        """Test language filtering based on archived page iso codes."""
        # Create archived pages with different languages
        en_page = ArchivedPage(
            url="https://en.example.com/test", content_hash="en123", iso_639_1="en"
        )
        de_page = ArchivedPage(
            url="https://de.example.com/test", content_hash="de123", iso_639_1="de"
        )
        db_session.add_all([en_page, de_page])
        db_session.flush()

        # Add properties from different language sources
        en_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=en_page.id,
        )
        de_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.DEATH_DATE,
            value="2024-01-01",
            value_precision=11,
            archived_page_id=de_page.id,
        )
        db_session.add_all([en_prop, de_prop])
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
        self, db_session, sample_politician, sample_country, sample_archived_page
    ):
        """Test that country filter finds politicians with matching citizenship."""
        # Add citizenship property
        citizenship_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            archived_page_id=sample_archived_page.id,
        )
        db_session.add(citizenship_prop)
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
        assert result[0] == sample_politician.id

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
        sample_german_language,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test language filtering based on citizenship official languages."""
        # Create Germany
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        db_session.flush()

        # Create official language relation: German is official in Germany
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=germany.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany.wikidata_id,
        )
        db_session.add(citizenship)

        # Create German Wikipedia link
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with German language filter
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        # Should find politician because they have German citizenship
        # and German is official language of Germany
        assert len(result) == 1
        assert result[0] == sample_politician.id

    def test_query_with_language_filter_no_citizenship_match_but_has_citizenship_link(
        self,
        db_session,
        sample_politician,
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_language,
        sample_french_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test that politicians are excluded when they have citizenship-matched links but filter doesn't match."""
        # Create France
        france = Country.create_with_entity(db_session, "Q142", "France")
        france.iso_code = "FR"
        db_session.flush()

        # Create official language relation: French is official in France
        relation = WikidataRelation(
            parent_entity_id=sample_french_language.wikidata_id,
            child_entity_id=france.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_fr_fr",
        )
        db_session.add(relation)

        # Give politician French citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=france.wikidata_id,
        )
        db_session.add(citizenship)

        # Create BOTH French (citizenship match) and German Wikipedia links
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with German language filter
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        # Should NOT find politician - they have French link (citizenship match)
        # so French gets priority and German wouldn't be in top 3
        assert len(result) == 0

    def test_query_with_country_filter(
        self,
        db_session,
        sample_politician,
        sample_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test country filtering based on citizenship."""
        # Create USA
        usa = Country.create_with_entity(db_session, "Q30", "United States")
        usa.iso_code = "US"
        db_session.flush()

        # Give politician US citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa.wikidata_id,
        )
        db_session.add(citizenship)

        # Create Wikipedia link
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        # Query with US country filter
        query = Politician.query_for_enrichment(countries=["Q30"])
        result = db_session.execute(query).scalars().all()

        # Should find politician with US citizenship
        assert len(result) == 1
        assert result[0] == sample_politician.id

    def test_query_with_combined_filters(
        self,
        db_session,
        sample_politician,
        sample_german_language,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test combined language and country filtering."""
        # Create Germany
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        db_session.flush()

        # Create official language relation
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=germany.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany.wikidata_id,
        )
        db_session.add(citizenship)

        # Create Wikipedia link
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        db_session.flush()

        # Query with both filters
        query = Politician.query_for_enrichment(languages=["Q188"], countries=["Q183"])
        result = db_session.execute(query).scalars().all()

        # Should find politician matching both filters
        assert len(result) == 1
        assert result[0] == sample_politician.id

    def test_query_excludes_politician_not_matching_country_filter(
        self,
        db_session,
        sample_politician,
        sample_german_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test that politicians without matching citizenship are excluded."""
        # Create Germany but don't give politician German citizenship
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        db_session.flush()

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
        sample_german_language,
        sample_german_wikipedia_project,
        sample_french_language,
        sample_french_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test that politicians with multiple citizenships match if any citizenship language has a link."""
        # Create Germany and France
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        france = Country.create_with_entity(db_session, "Q142", "France")
        france.iso_code = "FR"
        db_session.flush()

        # Create official language relations
        de_relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=germany.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        fr_relation = WikidataRelation(
            parent_entity_id=sample_french_language.wikidata_id,
            child_entity_id=france.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_fr_fr",
        )
        db_session.add_all([de_relation, fr_relation])

        # Give politician dual citizenship
        citizenships = [
            Property(
                politician_id=sample_politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            ),
            Property(
                politician_id=sample_politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=france.wikidata_id,
            ),
        ]
        db_session.add_all(citizenships)

        # Create BOTH German and French Wikipedia links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        db_session.flush()

        # Query with German language filter - should match via German citizenship + German link
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0] == sample_politician.id

        # Query with French language filter - should also match via French citizenship + French link
        query = Politician.query_for_enrichment(languages=["Q150"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0] == sample_politician.id

    def test_query_with_language_filter_requires_wikipedia_link(
        self,
        db_session,
        sample_politician,
        sample_german_language,
        sample_wikipedia_project,
        create_wikipedia_link,
    ):
        """Test that language filtering requires Wikipedia link in that language."""
        # Create Germany
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"
        db_session.flush()

        # Create official language relation
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=germany.wikidata_id,
            relation_type=RelationType.OFFICIAL_LANGUAGE,
            statement_id="test_statement_de_de",
        )
        db_session.add(relation)

        # Give politician German citizenship
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany.wikidata_id,
        )
        db_session.add(citizenship)

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
        """Test that only top 3 most popular citizenship languages are considered."""
        # Create a country with 4 official languages
        multilingual_country = Country.create_with_entity(
            db_session, "Q668", "Multilingual Country"
        )
        multilingual_country.iso_code = "MC"
        db_session.flush()

        # Set up 4 languages with different popularity levels
        # English: 5, German: 4, French: 3, Spanish: 2 (should NOT match)
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
            ),  # Spanish - 4th (NOT in top 3)
        ]

        base_qid = 60000
        for lang, wp, popularity in languages_data:
            # Create official language relation
            relation = WikidataRelation(
                parent_entity_id=lang.wikidata_id,
                child_entity_id=multilingual_country.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id=f"test_statement_{lang.iso_639_1}_mc",
            )
            db_session.add(relation)

            # Create dummy politicians to establish popularity
            for i in range(popularity):
                dummy = Politician.create_with_entity(
                    db_session, f"Q{base_qid + i}", f"Dummy {lang.iso_639_1} {i}"
                )
                db_session.flush()
                create_wikipedia_link(dummy, wp)

            base_qid += popularity

        # Give sample_politician citizenship of multilingual country
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=multilingual_country.wikidata_id,
        )
        db_session.add(citizenship)

        # Create Wikipedia links for all 4 languages for sample_politician
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_french_wikipedia_project)
        create_wikipedia_link(sample_politician, sample_spanish_wikipedia_project)
        db_session.flush()

        # Query with English (most popular) - should match
        query = Politician.query_for_enrichment(languages=["Q1860"])
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1, "English (top 1) should match"
        assert result[0] == sample_politician.id

        # Query with German (2nd most popular) - should match
        query = Politician.query_for_enrichment(languages=["Q188"])
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1, "German (top 2) should match"
        assert result[0] == sample_politician.id

        # Query with French (3rd most popular) - should match
        query = Politician.query_for_enrichment(languages=["Q150"])
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1, "French (top 3) should match"
        assert result[0] == sample_politician.id

        # Query with Spanish (4th most popular) - should NOT match
        query = Politician.query_for_enrichment(languages=["Q1321"])
        result = db_session.execute(query).scalars().all()
        assert len(result) == 0, "Spanish (4th) should NOT match - outside top 3"

    def test_query_excludes_soft_deleted_wikidata_entity(
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test that query excludes politicians with soft-deleted WikidataEntity."""

        # Verify politician appears before soft-delete
        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1
        assert result[0] == sample_politician.id

        # Soft-delete the WikidataEntity
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        # Query again
        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()

        # Should return empty because WikidataEntity has been soft-deleted
        assert len(result) == 0


class TestPropertyShouldStore:
    """Test cases for the Property.should_store() method."""

    def test_should_store_birth_date_no_existing(self, db_session, sample_politician):
        """Test storing birth date when no existing date exists."""
        politician = sample_politician

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birth_date_more_precise(self, db_session, sample_politician):
        """Test storing birth date when new date is more precise."""
        politician = sample_politician

        # Create existing property with year precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,  # Year precision
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store more precise date (day precision)
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,  # Day precision
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birth_date_less_precise(self, db_session, sample_politician):
        """Test not storing birth date when new date is less precise."""
        politician = sample_politician

        # Create existing property with day precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,  # Day precision
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store less precise date (year precision)
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-00-00T00:00:00Z",
            value_precision=9,  # Year precision
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_birth_date_different_year(
        self, db_session, sample_politician
    ):
        """Test storing birth date when years are different."""
        politician = sample_politician

        # Create existing property for 1990
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store date for different year
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1991-01-01T00:00:00Z",
            value_precision=11,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_position_no_existing(
        self, db_session, sample_politician, sample_position
    ):
        """Test storing position when no existing position exists."""
        politician = sample_politician
        position = sample_position

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
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

        assert new_property.should_store(db_session) is True

    def test_should_store_position_more_precise_dates(
        self, db_session, sample_politician, sample_position
    ):
        """Test storing position when new dates are more precise."""
        politician = sample_politician
        position = sample_position

        # Create existing position with year precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-00-00T00:00:00Z",
                                "precision": 9,  # Year precision
                            }
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store position with more precise start date
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-01-15T00:00:00Z",
                                "precision": 11,  # Day precision
                            }
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_position_less_precise_dates(
        self, db_session, sample_politician, sample_position
    ):
        """Test not storing position when new dates are less precise."""
        politician = sample_politician
        position = sample_position

        # Create existing position with day precision
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-01-15T00:00:00Z",
                                "precision": 11,  # Day precision
                            }
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store position with less precise start date
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {
                                "time": "+2020-00-00T00:00:00Z",
                                "precision": 9,  # Year precision
                            }
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_position_different_timeframe(
        self, db_session, sample_politician, sample_position
    ):
        """Test storing position when timeframes are different."""
        politician = sample_politician
        position = sample_position

        # Create existing position for 2020
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
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
        db_session.add(existing_property)
        db_session.flush()

        # Try to store position for different year
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2021-01-01T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birthplace_no_existing(
        self, db_session, sample_politician, sample_location
    ):
        """Test storing birthplace when no existing birthplace exists."""
        politician = sample_politician
        location = sample_location

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birthplace_duplicate(
        self, db_session, sample_politician, sample_location
    ):
        """Test not storing birthplace when duplicate exists."""
        politician = sample_politician
        location = sample_location

        # Create existing birthplace
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store duplicate birthplace
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_citizenship_no_existing(
        self, db_session, sample_politician, sample_country
    ):
        """Test storing citizenship when no existing citizenship exists."""
        politician = sample_politician
        country = sample_country

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_citizenship_duplicate(
        self, db_session, sample_politician, sample_country
    ):
        """Test not storing citizenship when duplicate exists."""
        politician = sample_politician
        country = sample_country

        # Create existing citizenship
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store duplicate citizenship
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        assert new_property.should_store(db_session) is False

    def test_should_store_position_no_dates_when_dates_exist(
        self, db_session, sample_politician, sample_position
    ):
        """Test not storing position without dates when position with dates exists."""
        politician = sample_politician
        position = sample_position

        # Create existing position with dates (May 24, 2016 - present)
        existing_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2016-05-24T00:00:00Z", "precision": 11}
                        }
                    }
                ]
            },
        )
        db_session.add(existing_property)
        db_session.flush()

        # Try to store same position without any dates
        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json=None,  # No dates specified
        )

        assert new_property.should_store(db_session) is False
