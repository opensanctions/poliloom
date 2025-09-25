"""Tests for the Politician model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    Language,
    Country,
    WikipediaLink,
    WikidataRelation,
    RelationType,
)
from poliloom.wikidata_date import WikidataDate
from ..conftest import assert_model_fields


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_creation(self, db_session):
        """Test basic politician creation."""
        politician = Politician.create_with_entity(db_session, "Q789012", "Jane Smith")
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Jane Smith", "wikidata_id": "Q789012"},
        )

    def test_politician_unique_wikidata_id(self, db_session, sample_politician_data):
        """Test that wikidata_id must be unique."""
        # Create first politician
        Politician.create_with_entity(
            db_session,
            sample_politician_data["wikidata_id"],
            sample_politician_data["name"],
        )
        db_session.commit()

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            Politician.create_with_entity(
                db_session,
                sample_politician_data["wikidata_id"],  # Same wikidata_id
                "Different Name",
            )
            db_session.commit()

        # Roll back the failed transaction to clean up the session
        db_session.rollback()

    def test_politician_default_values(self, db_session):
        """Test default values for politician fields."""
        politician = Politician(name="Test Person")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Test Person", "is_deceased": False, "wikidata_id": None},
        )

    def test_politician_cascade_delete_properties(self, db_session, sample_politician):
        """Test that deleting a politician cascades to properties."""
        # Use fixture politician
        politician = sample_politician

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
        )
        db_session.add(prop)
        db_session.commit()

        # Delete politician should cascade to properties
        db_session.delete(politician)
        db_session.commit()

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
        db_session.commit()
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
        self, db_session, sample_politician, sample_wikipedia_link
    ):
        """Test get_priority_wikipedia_links when only English link available."""
        # Create English language entry
        english_lang = Language.create_with_entity(db_session, "Q1860", "English")
        english_lang.iso1_code = "en"
        english_lang.iso3_code = "eng"
        db_session.commit()

        # sample_wikipedia_link fixture creates an English link
        result = sample_politician.get_priority_wikipedia_links(db_session)

        assert len(result) == 1
        wiki_link, iso1_code, iso3_code = result[0]
        assert wiki_link.iso_code == "en"
        assert iso1_code == "en"
        assert iso3_code == "eng"

    def test_get_priority_wikipedia_links_citizenship_priority(
        self, db_session, sample_politician, sample_country, sample_language
    ):
        """Test get_priority_wikipedia_links with citizenship-based prioritization."""
        # Create a German country and language
        german_country = Country.create_with_entity(db_session, "Q183", "Germany")
        german_country.iso_code = "DE"
        german_language = Language.create_with_entity(db_session, "Q188", "German")
        german_language.iso1_code = "de"
        german_language.iso3_code = "deu"
        db_session.commit()

        # Create official language relation: German is official language of Germany
        relation = WikidataRelation(
            parent_entity_id=german_language.wikidata_id,
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
        db_session.commit()

        # Create multiple German links to simulate popularity
        for i in range(50):  # Make German popular
            dummy_politician = Politician.create_with_entity(
                db_session, f"Q{1000 + i}", f"Dummy {i}"
            )
            db_session.commit()
            de_link = WikipediaLink(
                politician_id=dummy_politician.id,
                url=f"https://de.wikipedia.org/wiki/Dummy_{i}",
                iso_code="de",
            )
            db_session.add(de_link)

        # Create the actual politician's links
        german_link = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://de.wikipedia.org/wiki/Test_Politician",
            iso_code="de",
        )
        english_link = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            iso_code="en",
        )
        db_session.add(german_link)
        db_session.add(english_link)
        db_session.commit()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should get both German (from citizenship) and English, but German should be prioritized
        assert len(result) >= 1
        # German should be first due to citizenship priority
        wiki_link, iso1_code, iso3_code = result[0]
        assert wiki_link.iso_code == "de"
        assert iso1_code == "de"
        assert iso3_code == "deu"

    def test_get_priority_wikipedia_links_no_citizenship(
        self, db_session, sample_politician
    ):
        """Test get_priority_wikipedia_links when politician has no citizenship."""
        # Create multiple Wikipedia links without citizenship
        links_data = [
            ("https://en.wikipedia.org/wiki/Test_Politician", "en"),
            ("https://fr.wikipedia.org/wiki/Test_Politician", "fr"),
            ("https://de.wikipedia.org/wiki/Test_Politician", "de"),
            (
                "https://es.wikipedia.org/wiki/Test_Politician",
                "es",
            ),  # Add Spanish as 4th language
        ]

        # Create corresponding languages
        languages = [
            ("Q1860", "English", "en", "eng"),
            ("Q150", "French", "fr", "fra"),
            ("Q188", "German", "de", "deu"),
            ("Q1321", "Spanish", "es", "spa"),
        ]

        for wid, name, iso1, iso3 in languages:
            lang = Language.create_with_entity(db_session, wid, name)
            lang.iso1_code = iso1
            lang.iso3_code = iso3

        # Create many links for each language to simulate different popularity
        # Make French most popular (100), German second (50), Spanish third (30), English least (25)
        popularity_data = [("fr", 100), ("de", 50), ("es", 30), ("en", 25)]

        base_qid = 50000  # Use a higher base to avoid conflicts
        for iso_code, count in popularity_data:
            for i in range(count):
                qid = f"Q{base_qid + i}"
                dummy_politician = Politician.create_with_entity(
                    db_session,
                    qid,
                    f"Dummy {iso_code} {i}",
                )
                db_session.commit()
                link = WikipediaLink(
                    politician_id=dummy_politician.id,
                    url=f"https://{iso_code}.wikipedia.org/wiki/Dummy_{i}",
                    iso_code=iso_code,
                )
                db_session.add(link)
            base_qid += count  # Increment base to avoid overlaps

        # Create politician's actual links
        for url, iso_code in links_data:
            link = WikipediaLink(
                politician_id=sample_politician.id,
                url=url,
                iso_code=iso_code,
            )
            db_session.add(link)

        db_session.commit()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should return exactly 3 languages (the most popular ones available)
        assert len(result) == 3, f"Expected exactly 3 results, got {len(result)}"

        # Get the ISO codes of returned languages
        returned_iso_codes = {link.iso_code for link, _, _ in result}

        # Should contain the 3 most popular languages: fr (100), de (50), es (30)
        # Should NOT contain en (25) as it's the 4th most popular
        expected_top_3 = {"fr", "de", "es"}
        assert returned_iso_codes == expected_top_3, (
            f"Expected top 3 languages {expected_top_3}, got {returned_iso_codes}"
        )

    def test_get_priority_wikipedia_links_multiple_citizenships(
        self, db_session, sample_politician
    ):
        """Test get_priority_wikipedia_links with multiple citizenships."""
        # Create two countries with different official languages
        usa = Country.create_with_entity(db_session, "Q30", "United States")
        usa.iso_code = "US"
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"

        # Create languages
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso1_code = "en"
        english.iso3_code = "eng"
        german = Language.create_with_entity(db_session, "Q188", "German")
        german.iso1_code = "de"
        german.iso3_code = "deu"
        db_session.commit()

        # Create official language relations
        relations = [
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=usa.wikidata_id,
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="test_statement_en_us",
            ),
            WikidataRelation(
                parent_entity_id=german.wikidata_id,
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

        # Create Wikipedia links
        links = [
            WikipediaLink(
                politician_id=sample_politician.id,
                url="https://en.wikipedia.org/wiki/Test_Politician",
                iso_code="en",
            ),
            WikipediaLink(
                politician_id=sample_politician.id,
                url="https://de.wikipedia.org/wiki/Test_Politician",
                iso_code="de",
            ),
        ]
        for link in links:
            db_session.add(link)

        db_session.commit()

        result = sample_politician.get_priority_wikipedia_links(db_session)

        # Should get languages from citizenships prioritized, up to 3 total
        assert len(result) <= 3
        assert len(result) >= 1

        # Both citizenship languages should be represented (they get priority boost)
        iso_codes = {link.iso_code for link, _, _ in result}
        assert (
            "en" in iso_codes or "de" in iso_codes
        )  # At least one citizenship language
