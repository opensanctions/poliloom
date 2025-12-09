"""Tests for the get_politicians endpoint focusing on behavior, not implementation."""

from datetime import datetime, timezone
from typing import List, Dict, Any

from poliloom.models import (
    ArchivedPage,
    ArchivedPageLanguage,
    Campaign,
    Country,
    Evaluation,
    Language,
    Location,
    Politician,
    Position,
    Property,
    PropertyType,
    RelationType,
    Source,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
)
from poliloom.wikidata_date import WikidataDate


def extract_properties_by_type(
    politician_data: Dict[str, Any], extracted: bool = True
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract properties from politician data based on whether they are extracted or Wikidata.

    Args:
        politician_data: The politician response data
        extracted: If True, return extracted properties (with archived_page), else Wikidata properties (without archived_page)

    Returns:
        Dictionary with keys by property type containing lists of matching properties
    """
    result = {
        "P569": [],  # BIRTH_DATE
        "P570": [],  # DEATH_DATE
        "P39": [],  # POSITION
        "P19": [],  # BIRTHPLACE
        "P27": [],  # CITIZENSHIP
    }

    # Extract properties by type
    for prop in politician_data.get("properties", []):
        if bool(prop.get("archived_page")) == extracted:
            prop_type = prop.get("type")
            if prop_type in result:
                result[prop_type].append(prop)

    return result


def create_wikipedia_setup(
    db_session, politician, language=None, wikipedia_project=None
):
    """Helper to create language, wikipedia project, and source chain."""
    if language is None:
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
    if wikipedia_project is None:
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"
    db_session.add(
        WikidataRelation(
            parent_entity_id=language.wikidata_id,
            child_entity_id=wikipedia_project.wikidata_id,
            relation_type=RelationType.LANGUAGE_OF_WORK,
            statement_id=f"{wikipedia_project.wikidata_id}$test-statement-{language.wikidata_id}",
        )
    )
    db_session.flush()

    wikipedia_source = WikipediaSource(
        politician_id=politician.id,
        url=f"https://en.wikipedia.org/wiki/{politician.name.replace(' ', '_')}",
        wikipedia_project_id=wikipedia_project.wikidata_id,
    )
    db_session.add(wikipedia_source)
    db_session.flush()

    return language, wikipedia_project, wikipedia_source


class TestGetPoliticiansEndpoint:
    """Test the behavior of the get_politicians endpoint."""

    def test_returns_politicians_with_unevaluated_extracted_data(
        self, client, mock_auth, db_session
    ):
        """Test that politicians with unevaluated extracted data are returned."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add extracted properties (with archived_page, no statement_id)
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on January 15, 1970"],
        )
        db_session.add(birth_prop)

        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
                "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
            },
            supporting_quotes=["Served as Mayor from 2020 to 2024"],
        )
        db_session.add(position_prop)

        birthplace_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born in Springfield"],
        )
        db_session.add(birthplace_prop)

        # Add Wikidata properties (no archived_page, has statement_id)
        death_prop = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="+2024-01-01T00:00:00Z",
            value_precision=11,
            statement_id="Q123456$death-statement-id",
        )
        db_session.add(death_prop)

        wikidata_position = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2010").to_wikidata_qualifier()]
            },
            statement_id="Q123456$position-statement-id",
        )
        db_session.add(wikidata_position)

        wikidata_birthplace = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            statement_id="Q123456$birthplace-statement-id",
        )
        db_session.add(wikidata_birthplace)

        db_session.flush()

        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert "politicians" in data
        assert "meta" in data
        politicians = data["politicians"]
        assert len(politicians) == 1

        politician_data = politicians[0]
        assert politician_data["name"] == "Test Politician"
        assert politician_data["wikidata_id"] == "Q123456"

        # Should have single properties list
        assert "properties" in politician_data
        assert isinstance(politician_data["properties"], list)
        assert (
            len(politician_data["properties"]) == 6
        )  # birth_date, position, birthplace (extracted) + death_date, position, birthplace (wikidata)

        # Should NOT have old grouped fields
        assert "positions" not in politician_data
        assert "birthplaces" not in politician_data

        # Verify all property types in single list
        property_types = [prop["type"] for prop in politician_data["properties"]]
        assert "P569" in property_types  # BIRTH_DATE
        assert "P570" in property_types  # DEATH_DATE
        assert "P39" in property_types  # POSITION
        assert "P19" in property_types  # BIRTHPLACE

    def test_includes_politicians_with_evaluated_data_without_statement_id(
        self, client, mock_auth, db_session
    ):
        """Test that politicians with evaluated extracted data but no statement_id are included."""
        politician = Politician.create_with_entity(
            db_session, "Q789012", "Evaluated Politician"
        )
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://example.com/test2",
            content_hash="test456",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add extracted property with evaluation
        extracted_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1980-05-20T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on May 20, 1980"],
        )
        db_session.add(extracted_property)
        db_session.flush()

        # Add evaluation (this makes the data "evaluated")
        evaluation = Evaluation(
            user_id="testuser",
            is_accepted=True,
            property_id=extracted_property.id,
        )
        db_session.add(evaluation)
        db_session.flush()

        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        politicians = data["politicians"]
        assert (
            len(politicians) == 1
        )  # Should include since evaluation failed to push to Wikidata

    def test_excludes_politicians_with_only_wikidata(
        self, client, mock_auth, db_session
    ):
        """Test that politicians with only Wikidata data are excluded."""
        politician = Politician.create_with_entity(
            db_session, "Q345678", "Wikidata Only Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        db_session.flush()

        # Add only Wikidata (non-extracted) data
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1965-12-10T00:00:00Z",
            value_precision=11,
            statement_id="Q345678$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(birth_prop)

        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2016").to_wikidata_qualifier()]
            },
            statement_id="Q345678$87654321-4321-4321-4321-210987654321",
        )
        db_session.add(position_prop)
        db_session.flush()

        response = client.get("/politicians/?has_unevaluated=true", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        politicians = data["politicians"]
        assert len(politicians) == 0  # Should be empty since no extracted data exists

    def test_returns_empty_list_when_no_qualifying_politicians(self, client, mock_auth):
        """Test that endpoint returns empty list when no politicians have unevaluated data."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert data["politicians"] == []

    def test_extracted_data_contains_supporting_quotes_and_archive_info(
        self, client, mock_auth, db_session
    ):
        """Test that extracted data includes supporting_quotes and archived_page info."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on January 15, 1970"],
        )
        db_session.add(birth_prop)

        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Served as Mayor from 2020 to 2024"],
        )
        db_session.add(position_prop)

        birthplace_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born in Springfield"],
        )
        db_session.add(birthplace_prop)
        db_session.flush()

        response = client.get("/politicians/", headers=mock_auth)

        data = response.json()
        politician_data = data["politicians"][0]

        # Find extracted properties (those with supporting_quotes and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        # Check extracted property
        assert len(extracted_properties["P569"]) == 1  # BIRTH_DATE
        extracted_prop = extracted_properties["P569"][0]
        assert extracted_prop["supporting_quotes"] == ["Born on January 15, 1970"]
        assert extracted_prop["archived_page"] is not None
        assert "url" in extracted_prop["archived_page"]

        # Check extracted position
        assert len(extracted_properties["P39"]) == 1  # POSITION
        extracted_pos = extracted_properties["P39"][0]
        assert extracted_pos["supporting_quotes"] == [
            "Served as Mayor from 2020 to 2024"
        ]
        assert extracted_pos["archived_page"] is not None

        # Check extracted birthplace
        assert len(extracted_properties["P19"]) == 1  # BIRTHPLACE
        extracted_bp = extracted_properties["P19"][0]
        assert extracted_bp["supporting_quotes"] == ["Born in Springfield"]
        assert extracted_bp["archived_page"] is not None

    def test_wikidata_data_excludes_extraction_fields(
        self, client, mock_auth, db_session
    ):
        """Test that Wikidata entries don't include extraction-specific fields."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Position.create_with_entity(db_session, "Q30185", "Mayor")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add extracted property
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on January 15, 1970"],
        )
        db_session.add(birth_prop)

        # Add Wikidata property
        death_prop = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="+2024-01-01T00:00:00Z",
            value_precision=11,
            statement_id="Q123456$death-statement-id",
        )
        db_session.add(death_prop)
        db_session.flush()

        response = client.get("/politicians/", headers=mock_auth)

        data = response.json()
        politician_data = data["politicians"][0]

        # Find Wikidata properties (those without supporting_quotes)
        wikidata_properties = extract_properties_by_type(
            politician_data, extracted=False
        )

        # Wikidata properties should not have supporting_quotes or archived_page
        assert len(wikidata_properties["P570"]) >= 1  # DEATH_DATE
        wikidata_prop = wikidata_properties["P570"][0]
        assert wikidata_prop.get("supporting_quotes") is None
        assert wikidata_prop.get("archived_page") is None

        # But they should have precision fields
        assert "value_precision" in wikidata_prop

    def test_pagination_limits_results(self, client, mock_auth, db_session):
        """Test that pagination parameters limit results correctly."""
        # Create shared language and project
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        # Create multiple politicians with unevaluated data
        for i in range(5):
            politician = Politician.create_with_entity(
                db_session, f"Q{100000 + i}", f"Politician {i}"
            )
            db_session.flush()

            wikipedia_source = WikipediaSource(
                politician_id=politician.id,
                url=f"https://en.wikipedia.org/wiki/Politician_{i}",
                wikipedia_project_id=wikipedia_project.wikidata_id,
            )
            db_session.add(wikipedia_source)
            db_session.flush()

            archived_page = ArchivedPage(
                url=f"https://example.com/test{i}",
                content_hash=f"test{i}",
                fetch_timestamp=datetime.now(timezone.utc),
                wikipedia_source_id=wikipedia_source.id,
            )
            db_session.add(archived_page)
            db_session.flush()

            # Add extracted property
            birth_prop = Property(
                politician_id=politician.id,
                type=PropertyType.BIRTH_DATE,
                value=f"+19{70 + i}-01-01T00:00:00Z",
                value_precision=11,
                archived_page_id=archived_page.id,
            )
            db_session.add(birth_prop)

        db_session.flush()

        # Test limit parameter
        response = client.get("/politicians/?limit=3", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 3

        # Test different limit value
        response = client.get("/politicians/?limit=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2

    def test_mixed_evaluation_states(self, client, mock_auth, db_session):
        """Test politician with mix of evaluated and unevaluated data appears in results."""
        politician = Politician.create_with_entity(
            db_session, "Q999999", "Mixed Evaluation"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://example.com/mixed",
            content_hash="mixed123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add evaluated extracted property
        evaluated_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1975-03-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(evaluated_prop)
        db_session.flush()

        evaluation = Evaluation(
            user_id="testuser",
            is_accepted=True,
            property_id=evaluated_prop.id,
        )
        db_session.add(evaluation)

        # Add unevaluated extracted position
        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()]
            },
        )
        db_session.add(position_prop)
        db_session.flush()

        # Should appear in results because has unevaluated position
        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        politicians = data["politicians"]
        assert len(politicians) == 1

        politician_data = politicians[0]

        # Find extracted properties (those with supporting_quotes and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        assert (
            len(extracted_properties["P569"]) == 1  # BIRTH_DATE
        )  # Evaluated but no statement_id, so still returned for re-evaluation
        assert (
            len(extracted_properties["P39"]) == 1
        )  # POSITION - Unevaluated, so returned

    def test_politician_with_partial_unevaluated_data_types(
        self, client, mock_auth, db_session
    ):
        """Test politicians appear even if they only have one type of unevaluated data."""
        politician = Politician.create_with_entity(
            db_session, "Q777777", "Birthplace Only"
        )
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://example.com/partial",
            content_hash="partial123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        birthplace_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(birthplace_prop)
        db_session.flush()

        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician_data = data["politicians"][0]

        # Find extracted properties (those with supporting_quotes and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        assert len(extracted_properties["P569"]) == 0  # BIRTH_DATE
        assert len(extracted_properties["P39"]) == 0  # POSITION
        assert len(extracted_properties["P19"]) == 1  # BIRTHPLACE

    def test_property_response_structure(self, client, mock_auth, db_session):
        """Test property response has correct fields."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(birth_prop)

        death_prop = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="+2024-01-01T00:00:00Z",
            value_precision=11,
            statement_id="Q123456$death-statement",
        )
        db_session.add(death_prop)

        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(position_prop)

        birthplace_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(birthplace_prop)
        db_session.flush()

        response = client.get("/politicians/", headers=mock_auth)
        politician_data = response.json()["politicians"][0]

        for prop in politician_data["properties"]:
            assert "id" in prop
            assert "type" in prop

            if prop["type"] in ["P569", "P570"]:  # BIRTH_DATE, DEATH_DATE
                assert prop["value"] is not None
                assert prop["entity_id"] is None
            elif prop["type"] in [
                "P19",
                "P39",
                "P27",
            ]:  # BIRTHPLACE, POSITION, CITIZENSHIP
                assert prop["entity_id"] is not None
                assert prop["value"] is None
                assert "entity_name" in prop

    def test_language_filtering(self, client, mock_auth, db_session):
        """Test filtering politicians by language QIDs based on archived page languages."""
        # Create languages
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso_639_1 = "en"
        english.iso_639_2 = "eng"
        german = Language.create_with_entity(db_session, "Q188", "German")
        german.iso_639_1 = "de"
        german.iso_639_2 = "deu"

        # Create Wikipedia projects
        en_wiki = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wiki.official_website = "https://en.wikipedia.org"
        de_wiki = WikipediaProject.create_with_entity(
            db_session, "Q48183", "German Wikipedia"
        )
        de_wiki.official_website = "https://de.wikipedia.org"

        db_session.add(
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=en_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$lang-en",
            )
        )
        db_session.add(
            WikidataRelation(
                parent_entity_id=german.wikidata_id,
                child_entity_id=de_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q48183$lang-de",
            )
        )
        db_session.flush()

        # Create politicians
        english_politician = Politician.create_with_entity(
            db_session, "Q1001", "English Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q1002", "German Politician"
        )
        no_lang_politician = Politician.create_with_entity(
            db_session, "Q1003", "No Language Politician"
        )
        db_session.flush()

        # Create sources and pages
        en_source = WikipediaSource(
            politician_id=english_politician.id,
            url="https://en.wikipedia.org/wiki/English_Politician",
            wikipedia_project_id=en_wiki.wikidata_id,
        )
        db_session.add(en_source)
        db_session.flush()

        english_page = ArchivedPage(
            url="https://en.example.com/test",
            content_hash="en123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=en_source.id,
        )
        db_session.add(english_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=english_page.id,
                language_id=english.wikidata_id,
            )
        )

        de_source = WikipediaSource(
            politician_id=german_politician.id,
            url="https://de.wikipedia.org/wiki/German_Politician",
            wikipedia_project_id=de_wiki.wikidata_id,
        )
        db_session.add(de_source)
        db_session.flush()

        german_page = ArchivedPage(
            url="https://de.example.com/test",
            content_hash="de123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=de_source.id,
        )
        db_session.add(german_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=german_page.id,
                language_id=german.wikidata_id,
            )
        )

        db_session.flush()

        # Add properties linked to language-specific archived pages
        en_birth_prop = Property(
            politician_id=english_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=english_page.id,
        )
        db_session.add(en_birth_prop)

        de_birth_prop = Property(
            politician_id=german_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1971-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=german_page.id,
        )
        db_session.add(de_birth_prop)

        # Property without archived page (should not appear in language filtering)
        no_lang_birth_prop = Property(
            politician_id=no_lang_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1972-01-01T00:00:00Z",
            value_precision=11,
        )
        db_session.add(no_lang_birth_prop)
        db_session.flush()

        # Test filtering by English language QID
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q1860", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "English Politician"

        # Test filtering by German language QID
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q188", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "German Politician"

        # Test filtering by multiple languages
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q1860&languages=Q188",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {"English Politician", "German Politician"}

        # Test filtering by non-existent language
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q999999", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 0

    def test_country_filtering(self, client, mock_auth, db_session):
        """Test filtering politicians by country QIDs based on citizenship properties."""
        usa_country = Country.create_with_entity(db_session, "Q30", "United States")
        usa_country.iso_code = "US"
        germany_country = Country.create_with_entity(db_session, "Q183", "Germany")
        germany_country.iso_code = "DE"

        # Create source (shared page mentioning multiple politicians)
        campaign = Campaign(name="Test Campaign")
        db_session.add(campaign)
        db_session.flush()

        source = Source(
            campaign_id=campaign.id,
            politician_id=Politician.create_with_entity(
                db_session, "Q9999", "Dummy Politician"
            ).id,  # Need politician_id since campaign_id alone is not enough
            url="https://example.com/campaign",
        )
        db_session.add(source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            source_id=source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Create politicians
        american_politician = Politician.create_with_entity(
            db_session, "Q2001", "American Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q2002", "German Politician"
        )
        dual_citizen_politician = Politician.create_with_entity(
            db_session, "Q2003", "Dual Citizen Politician"
        )
        no_citizenship_politician = Politician.create_with_entity(
            db_session, "Q2004", "No Citizenship Politician"
        )
        db_session.flush()

        # Add citizenship properties
        american_citizenship = Property(
            politician_id=american_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(american_citizenship)

        german_citizenship = Property(
            politician_id=german_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany_country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(german_citizenship)

        # Dual citizen - add both citizenships
        dual_us_citizenship = Property(
            politician_id=dual_citizen_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(dual_us_citizenship)

        dual_de_citizenship = Property(
            politician_id=dual_citizen_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany_country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(dual_de_citizenship)

        # Non-citizenship property for politician without citizenship
        no_citizenship_birth = Property(
            politician_id=no_citizenship_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1980-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(no_citizenship_birth)
        db_session.flush()

        # Test filtering by USA citizenship
        response = client.get("/politicians/?countries=Q30&limit=10", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {"American Politician", "Dual Citizen Politician"}

        # Test filtering by German citizenship
        response = client.get(
            "/politicians/?countries=Q183&limit=10", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {"German Politician", "Dual Citizen Politician"}

        # Test filtering by multiple countries
        response = client.get(
            "/politicians/?countries=Q30&countries=Q183&limit=10", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 3
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {
            "American Politician",
            "German Politician",
            "Dual Citizen Politician",
        }

        # Test filtering by non-existent country
        response = client.get(
            "/politicians/?countries=Q999999&limit=10", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 0

    def test_combined_language_and_country_filtering(
        self, client, mock_auth, db_session
    ):
        """Test filtering by both language and country filters combined."""
        # Create entities
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso_639_1 = "en"
        english.iso_639_2 = "eng"
        usa_country = Country.create_with_entity(db_session, "Q30", "United States")
        usa_country.iso_code = "US"
        germany_country = Country.create_with_entity(db_session, "Q183", "Germany")
        germany_country.iso_code = "DE"
        en_wiki = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wiki.official_website = "https://en.wikipedia.org"

        db_session.add(
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=en_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$lang-en",
            )
        )
        db_session.flush()

        # Create politicians first
        american_english_politician = Politician.create_with_entity(
            db_session, "Q3001", "American English Speaking Politician"
        )
        german_english_politician = Politician.create_with_entity(
            db_session, "Q3002", "German English Speaking Politician"
        )
        american_non_english_politician = Politician.create_with_entity(
            db_session, "Q3003", "American Non-English Speaking Politician"
        )
        db_session.flush()

        # Create Wikipedia sources and archived pages for each politician
        # American English speaking politician
        american_source = WikipediaSource(
            politician_id=american_english_politician.id,
            url="https://en.wikipedia.org/wiki/American_English",
            wikipedia_project_id=en_wiki.wikidata_id,
        )
        db_session.add(american_source)
        db_session.flush()

        american_page = ArchivedPage(
            url="https://en.example.com/american",
            content_hash="en_american",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=american_source.id,
        )
        db_session.add(american_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=american_page.id,
                language_id=english.wikidata_id,
            )
        )

        # German English speaking politician (also has English Wikipedia page)
        german_source = WikipediaSource(
            politician_id=german_english_politician.id,
            url="https://en.wikipedia.org/wiki/German_English",
            wikipedia_project_id=en_wiki.wikidata_id,
        )
        db_session.add(german_source)
        db_session.flush()

        german_page = ArchivedPage(
            url="https://en.example.com/german",
            content_hash="en_german",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=german_source.id,
        )
        db_session.add(german_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=german_page.id,
                language_id=english.wikidata_id,
            )
        )

        db_session.flush()

        # Add properties for American English speaking politician
        american_citizenship = Property(
            politician_id=american_english_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=american_page.id,
        )
        db_session.add(american_citizenship)

        american_birth = Property(
            politician_id=american_english_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=american_page.id,
        )
        db_session.add(american_birth)

        # Add properties for German English speaking politician
        german_citizenship = Property(
            politician_id=german_english_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany_country.wikidata_id,
            archived_page_id=german_page.id,
        )
        db_session.add(german_citizenship)

        german_birth = Property(
            politician_id=german_english_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1971-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=german_page.id,
        )
        db_session.add(german_birth)

        # Add properties for American non-English speaking politician (no archived page = Wikidata only)
        american_non_english_citizenship = Property(
            politician_id=american_non_english_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
        )
        db_session.add(american_non_english_citizenship)

        db_session.flush()

        # Test combined filtering: English language AND American citizenship
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q1860&countries=Q30",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "American English Speaking Politician"

        # Test combined filtering: English language AND German citizenship
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q1860&countries=Q183",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "German English Speaking Politician"

        # Test that individual filters work correctly
        # English language only - should return both English speaking politicians
        response = client.get(
            "/politicians/?has_unevaluated=true&languages=Q1860", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {
            "American English Speaking Politician",
            "German English Speaking Politician",
        }

    def test_language_filter_excludes_properties_from_other_languages(
        self, client, mock_auth, db_session
    ):
        """Test that when filtering by language, only properties from that language's archived pages are returned."""
        # Create languages
        english = Language.create_with_entity(db_session, "Q1860", "English")
        english.iso_639_1 = "en"
        english.iso_639_2 = "eng"
        german = Language.create_with_entity(db_session, "Q188", "German")
        german.iso_639_1 = "de"
        german.iso_639_2 = "deu"

        # Create Wikipedia projects
        en_wiki = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wiki.official_website = "https://en.wikipedia.org"
        de_wiki = WikipediaProject.create_with_entity(
            db_session, "Q48183", "German Wikipedia"
        )
        de_wiki.official_website = "https://de.wikipedia.org"

        db_session.add(
            WikidataRelation(
                parent_entity_id=english.wikidata_id,
                child_entity_id=en_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$lang-en",
            )
        )
        db_session.add(
            WikidataRelation(
                parent_entity_id=german.wikidata_id,
                child_entity_id=de_wiki.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q48183$lang-de",
            )
        )
        db_session.flush()

        # Create politician first
        politician = Politician.create_with_entity(
            db_session, "Q4001", "Multilingual Politician"
        )
        db_session.flush()

        # Create English Wikipedia source and page
        english_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Multilingual",
            wikipedia_project_id=en_wiki.wikidata_id,
        )
        db_session.add(english_source)
        db_session.flush()

        english_page = ArchivedPage(
            url="https://en.wikipedia.org/test",
            content_hash="en123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=english_source.id,
        )
        db_session.add(english_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=english_page.id,
                language_id=english.wikidata_id,
            )
        )

        # Create German Wikipedia source and page
        german_source = WikipediaSource(
            politician_id=politician.id,
            url="https://de.wikipedia.org/wiki/Multilingual",
            wikipedia_project_id=de_wiki.wikidata_id,
        )
        db_session.add(german_source)
        db_session.flush()

        german_page = ArchivedPage(
            url="https://de.wikipedia.org/test",
            content_hash="de123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=german_source.id,
        )
        db_session.add(german_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=german_page.id,
                language_id=german.wikidata_id,
            )
        )

        # Create a source page (no language association)
        campaign = Campaign(name="Test Campaign")
        db_session.add(campaign)
        db_session.flush()

        source = Source(
            campaign_id=campaign.id,
            politician_id=politician.id,
            url="https://example.com/campaign",
        )
        db_session.add(source)
        db_session.flush()

        no_lang_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="none123",
            fetch_timestamp=datetime.now(timezone.utc),
            source_id=source.id,
        )
        db_session.add(no_lang_page)
        db_session.flush()

        # Add properties from different language sources
        english_birth = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=english_page.id,
            supporting_quotes=["Born on January 1, 1970"],
        )
        db_session.add(english_birth)

        german_birth = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-02T00:00:00Z",  # Different date from German source
            value_precision=11,
            archived_page_id=german_page.id,
            supporting_quotes=["Geboren am 2. Januar 1970"],
        )
        db_session.add(german_birth)

        no_lang_birth = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-03T00:00:00Z",
            value_precision=11,
            archived_page_id=no_lang_page.id,
            supporting_quotes=["Unknown language source"],
        )
        db_session.add(no_lang_birth)

        # Add a Wikidata property (no archived page)
        wikidata_death = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="+2024-01-01T00:00:00Z",
            value_precision=11,
            statement_id="Q4001$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(wikidata_death)

        db_session.flush()

        # Test filtering by English - should only return English property
        response = client.get("/politicians/?languages=Q1860", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician_data = data["politicians"][0]
        # Extract only properties with archived_page (extracted properties)
        extracted_props = [
            p for p in politician_data["properties"] if p.get("archived_page")
        ]

        # Should only have the English property, not German or no-language ones
        assert len(extracted_props) == 1
        english_prop = extracted_props[0]
        assert english_prop["value"] == "+1970-01-01T00:00:00Z"
        assert english_prop["supporting_quotes"] == ["Born on January 1, 1970"]
        assert english_prop["archived_page"]["url"] == "https://en.wikipedia.org/test"

        # Test filtering by German - should only return German property
        response = client.get("/politicians/?languages=Q188", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician_data = data["politicians"][0]
        extracted_props = [
            p for p in politician_data["properties"] if p.get("archived_page")
        ]

        # Should only have the German property
        assert len(extracted_props) == 1
        german_prop = extracted_props[0]
        assert german_prop["value"] == "+1970-01-02T00:00:00Z"
        assert german_prop["supporting_quotes"] == ["Geboren am 2. Januar 1970"]
        assert german_prop["archived_page"]["url"] == "https://de.wikipedia.org/test"

    def test_excludes_soft_deleted_properties(self, client, mock_auth, db_session):
        """Test that soft-deleted properties are excluded from results."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add a normal unevaluated property
        normal_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1980-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on January 1, 1980"],
        )
        db_session.add(normal_property)

        # Add a soft-deleted property
        deleted_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Served as Mayor"],
            deleted_at=datetime.now(timezone.utc),  # Soft-delete it
        )
        db_session.add(deleted_property)

        db_session.flush()

        # Request politicians
        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        # Should return the politician because they have normal_property
        assert len(data["politicians"]) == 1
        politician_data = data["politicians"][0]

        # Extract properties by type
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        # Should have birth date property but NOT the soft-deleted position
        assert len(extracted_properties["P569"]) == 1  # BIRTH_DATE (normal)
        assert (
            len(extracted_properties["P39"]) == 0
        )  # POSITION (soft-deleted, excluded)

        # Verify the returned property is the correct one
        birth_prop = extracted_properties["P569"][0]
        assert birth_prop["value"] == "+1980-01-01T00:00:00Z"
        assert birth_prop["supporting_quotes"] == ["Born on January 1, 1980"]

    def test_excludes_politicians_with_only_soft_deleted_properties(
        self, client, mock_auth, db_session
    ):
        """Test that politicians with only soft-deleted unevaluated properties are excluded."""
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")

        politician = Politician.create_with_entity(
            db_session, "Q998877", "Only Deleted Properties Politician"
        )
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add only soft-deleted properties
        deleted_birth = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1975-05-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on May 15, 1975"],
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(deleted_birth)

        deleted_position = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            supporting_quotes=["Served as Deputy"],
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(deleted_position)

        db_session.flush()

        # Request politicians
        response = client.get("/politicians/?has_unevaluated=true", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        # Should return empty because this politician has no non-deleted unevaluated properties
        assert len(data["politicians"]) == 0

    def test_excludes_politicians_with_soft_deleted_wikidata_entity(
        self, client, mock_auth, db_session
    ):
        """Test that politicians whose WikidataEntity has been soft-deleted are excluded."""
        politician = Politician.create_with_entity(
            db_session, "Q997766", "Soft Deleted Entity Politician"
        )
        language, wikipedia_project, wikipedia_source = create_wikipedia_setup(
            db_session, politician
        )

        archived_page = ArchivedPage(
            url="https://example.com/soft_delete_test",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add unevaluated property
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1985-07-20T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on July 20, 1985"],
        )
        db_session.add(birth_prop)
        db_session.flush()

        # Verify politician appears before soft-delete
        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["wikidata_id"] == "Q997766"

        # Soft-delete the WikidataEntity
        politician.wikidata_entity.soft_delete()
        db_session.flush()

        # Request politicians again
        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        # Should return empty because the WikidataEntity has been soft-deleted
        assert len(data["politicians"]) == 0


class TestCreatePoliticianEndpoint:
    """Test the POST /politicians endpoint for creating new politicians."""

    def test_create_politician_minimal(self, client, mock_auth, db_session):
        """Test creating a politician with minimal data (just name)."""
        payload = {
            "politicians": [
                {
                    "name": "New Politician",
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1
        assert data["errors"] == []

        politician = data["politicians"][0]
        assert politician["id"] is not None
        assert politician["name"] == "New Politician"
        assert politician["wikidata_id"] is not None  # Wikidata entity was created
        assert politician["wikidata_id"].startswith("Q")
        assert politician["properties"] == []

        # Verify politician was created in database with wikidata_id
        db_politician = (
            db_session.query(Politician)
            .filter(Politician.name == "New Politician")
            .first()
        )
        assert db_politician is not None
        assert db_politician.wikidata_id is not None
        assert db_politician.wikidata_id.startswith("Q")

    def test_create_politician_with_properties(self, client, mock_auth, db_session):
        """Test creating a politician with properties."""
        payload = {
            "politicians": [
                {
                    "name": "John Smith",
                    "labels": ["John Smith", "J. Smith"],
                    "description": "American politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1962-00-00T00:00:00Z",
                            "value_precision": 9,
                        },
                        {
                            "type": "P570",
                            "value": "+2024-01-15T00:00:00Z",
                            "value_precision": 11,
                        },
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert politician["id"] is not None
        assert politician["wikidata_id"] is not None  # Wikidata entity was created
        assert politician["wikidata_id"].startswith("Q")
        assert len(politician["properties"]) == 2

        # Verify property data is returned
        property_types = [p["type"] for p in politician["properties"]]
        assert "P569" in property_types
        assert "P570" in property_types

        # Verify politician was created
        db_politician = (
            db_session.query(Politician).filter(Politician.name == "John Smith").first()
        )
        assert db_politician is not None

        # Verify properties were created
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == db_politician.id)
            .all()
        )
        assert len(properties) == 2

        birth_prop = next(p for p in properties if p.type == PropertyType.BIRTH_DATE)
        assert birth_prop.value == "+1962-00-00T00:00:00Z"
        assert birth_prop.value_precision == 9

        death_prop = next(p for p in properties if p.type == PropertyType.DEATH_DATE)
        assert death_prop.value == "+2024-01-15T00:00:00Z"
        assert death_prop.value_precision == 11

    def test_create_politician_with_entity_properties(
        self, client, mock_auth, db_session
    ):
        """Test creating a politician with entity relationship properties."""
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        db_session.flush()

        payload = {
            "politicians": [
                {
                    "name": "Jane Doe",
                    "properties": [
                        {"type": "P19", "entity_id": location.wikidata_id},
                        {"type": "P39", "entity_id": position.wikidata_id},
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert len(politician["properties"]) == 2

        # Verify entity names are included
        for prop in politician["properties"]:
            if prop["type"] == "P19":
                assert prop["entity_id"] == location.wikidata_id
                assert prop["entity_name"] is not None
            elif prop["type"] == "P39":
                assert prop["entity_id"] == position.wikidata_id
                assert prop["entity_name"] is not None

        # Verify properties reference entities correctly
        db_politician = (
            db_session.query(Politician).filter(Politician.name == "Jane Doe").first()
        )
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == db_politician.id)
            .all()
        )

        birthplace_prop = next(
            p for p in properties if p.type == PropertyType.BIRTHPLACE
        )
        assert birthplace_prop.entity_id == location.wikidata_id

        position_prop = next(p for p in properties if p.type == PropertyType.POSITION)
        assert position_prop.entity_id == position.wikidata_id

    def test_create_politician_invalid_property_type(self, client, mock_auth):
        """Test that invalid property type is rejected."""
        payload = {
            "politicians": [
                {
                    "name": "Invalid Properties Politician",
                    "properties": [
                        {
                            "type": "P999",  # Invalid property type
                            "value": "test",
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Pydantic validation error

    def test_create_politician_date_property_missing_value(self, client, mock_auth):
        """Test that date properties require both value and precision."""
        payload = {
            "politicians": [
                {
                    "name": "Missing Value Politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value_precision": 9,  # Missing value
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_date_property_missing_precision(self, client, mock_auth):
        """Test that date properties require both value and precision."""
        payload = {
            "politicians": [
                {
                    "name": "Missing Precision Politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1962-00-00T00:00:00Z",  # Missing precision
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_entity_property_missing_entity_id(
        self, client, mock_auth
    ):
        """Test that entity properties require entity_id."""
        payload = {
            "politicians": [
                {
                    "name": "Missing Entity ID Politician",
                    "properties": [
                        {
                            "type": "P19",  # Birthplace requires entity_id
                            "value": "test",  # Should not have value
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_invalid_precision_value(self, client, mock_auth):
        """Test that invalid precision values are rejected."""
        payload = {
            "politicians": [
                {
                    "name": "Invalid Precision Politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1962-00-00T00:00:00Z",
                            "value_precision": 5,  # Invalid precision (must be 9, 10, or 11)
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_empty_name(self, client, mock_auth):
        """Test that empty name is rejected."""
        payload = {
            "politicians": [
                {
                    "name": "   ",  # Empty/whitespace name
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_with_qualifiers_and_references(
        self, client, mock_auth, db_session
    ):
        """Test creating a politician with properties that have qualifiers and references."""
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        db_session.flush()

        payload = {
            "politicians": [
                {
                    "name": "Qualified Politician",
                    "properties": [
                        {
                            "type": "P39",
                            "entity_id": position.wikidata_id,
                            "qualifiers_json": {
                                "P580": [
                                    {
                                        "datavalue": {
                                            "value": {
                                                "time": "+2020-00-00T00:00:00Z",
                                                "precision": 9,
                                            },
                                            "type": "time",
                                        }
                                    }
                                ]
                            },
                            "references_json": [
                                {
                                    "property": {"id": "P854"},
                                    "value": {
                                        "type": "value",
                                        "content": "https://example.com",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert len(politician["properties"]) == 1

        # Verify qualifiers and references are returned
        prop = politician["properties"][0]
        assert prop["qualifiers"] is not None
        assert "P580" in prop["qualifiers"]
        assert prop["references"] is not None
        assert len(prop["references"]) == 1

        # Verify qualifiers and references were stored
        db_politician = (
            db_session.query(Politician)
            .filter(Politician.name == "Qualified Politician")
            .first()
        )
        db_property = (
            db_session.query(Property)
            .filter(Property.politician_id == db_politician.id)
            .first()
        )

        assert db_property.qualifiers_json is not None
        assert "P580" in db_property.qualifiers_json
        assert db_property.references_json is not None
        assert len(db_property.references_json) == 1

    def test_create_politician_requires_authentication(self, client):
        """Test that creating a politician requires authentication."""
        payload = {
            "politicians": [
                {
                    "name": "Unauthenticated Politician",
                }
            ]
        }

        response = client.post("/politicians/", json=payload)
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    def test_create_multiple_politicians_batch(self, client, mock_auth, db_session):
        """Test creating multiple politicians in a single batch request."""
        payload = {
            "politicians": [
                {
                    "name": "Politician One",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1960-00-00T00:00:00Z",
                            "value_precision": 9,
                        }
                    ],
                },
                {
                    "name": "Politician Two",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1970-00-00T00:00:00Z",
                            "value_precision": 9,
                        }
                    ],
                },
                {
                    "name": "Politician Three",
                },
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 3
        assert data["errors"] == []

        # Verify all politicians were created
        politician_names = [p["name"] for p in data["politicians"]]
        assert "Politician One" in politician_names
        assert "Politician Two" in politician_names
        assert "Politician Three" in politician_names

        # Verify properties data
        prop_counts = {p["name"]: len(p["properties"]) for p in data["politicians"]}
        assert prop_counts["Politician One"] == 1
        assert prop_counts["Politician Two"] == 1
        assert prop_counts["Politician Three"] == 0
