"""Tests for the get_politicians endpoint focusing on behavior, not implementation."""

import pytest
from unittest.mock import AsyncMock, Mock as SyncMock, patch
from fastapi.testclient import TestClient
from typing import List, Dict, Any

from poliloom.api import app
from poliloom.api.auth import User
from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    Position,
    Location,
    Country,
    Language,
    ArchivedPage,
    Evaluation,
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


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth():
    """Mock authentication for tests."""
    with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
        mock_user = User(user_id=12345)
        mock_oauth_handler = SyncMock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
        mock_get_oauth_handler.return_value = mock_oauth_handler
        yield {"Authorization": "Bearer valid_jwt_token"}


@pytest.fixture
def politician_with_unevaluated_data(
    db_session, sample_politician, sample_position, sample_location
):
    """Create a politician with various types of unevaluated extracted data."""
    # Create supporting entities
    archived_page = ArchivedPage(
        url="https://example.com/test",
        content_hash="test123",
    )
    # Use fixture entities
    politician = sample_politician
    position = sample_position
    location = sample_location

    db_session.add(archived_page)
    db_session.flush()

    # Add extracted (unevaluated) data
    extracted_property = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1970-01-15",
        archived_page_id=archived_page.id,
        proof_line="Born on January 15, 1970",
    )

    extracted_position = Property(
        politician_id=politician.id,
        type=PropertyType.POSITION,
        entity_id=position.wikidata_id,
        qualifiers_json={
            "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
        },
        archived_page_id=archived_page.id,
        proof_line="Served as Mayor from 2020 to 2024",
    )

    extracted_birthplace = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTHPLACE,
        entity_id=location.wikidata_id,
        archived_page_id=archived_page.id,
        proof_line="Born in Springfield",
    )

    # Add Wikidata (non-extracted) data
    wikidata_property = Property(
        politician_id=politician.id,
        type=PropertyType.DEATH_DATE,
        value="2024-01-01",
        archived_page_id=None,  # This makes it Wikidata data
    )

    wikidata_position = Property(
        politician_id=politician.id,
        type=PropertyType.POSITION,
        entity_id=position.wikidata_id,
        qualifiers_json={
            "P580": [WikidataDate.from_date_string("2018").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
        },
        archived_page_id=None,  # This makes it Wikidata data
    )

    wikidata_birthplace = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTHPLACE,
        entity_id=location.wikidata_id,
        archived_page_id=None,  # This makes it Wikidata data
    )

    db_session.add_all(
        [
            extracted_property,
            extracted_position,
            extracted_birthplace,
            wikidata_property,
            wikidata_position,
            wikidata_birthplace,
        ]
    )
    db_session.commit()

    return politician


@pytest.fixture
def politician_with_evaluated_data(db_session):
    """Create a politician with only evaluated extracted data (should be excluded)."""
    # Create supporting entities
    archived_page = ArchivedPage(
        url="https://example.com/test2",
        content_hash="test456",
    )
    Position.create_with_entity(db_session, "Q30186", "Governor")

    db_session.add(archived_page)
    db_session.flush()

    # Create politician
    politician = Politician.create_with_entity(
        db_session, "Q789012", "Evaluated Politician"
    )
    db_session.add(politician)
    db_session.flush()

    # Add extracted property with evaluation
    extracted_property = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1980-05-20",
        archived_page_id=archived_page.id,
        proof_line="Born on May 20, 1980",
    )
    db_session.add(extracted_property)
    db_session.flush()

    # Add evaluation (this makes the data "evaluated")
    evaluation = Evaluation(
        user_id="testuser",
        is_confirmed=True,
        property_id=extracted_property.id,
    )
    db_session.add(evaluation)
    db_session.commit()

    return politician


@pytest.fixture
def politician_with_only_wikidata(db_session):
    """Create a politician with only Wikidata (non-extracted) data."""
    position = Position.create_with_entity(db_session, "Q30187", "Senator")
    Location.create_with_entity(db_session, "Q1297", "Chicago")

    db_session.flush()

    politician = Politician.create_with_entity(
        db_session, "Q345678", "Wikidata Only Politician"
    )
    db_session.add(politician)
    db_session.flush()

    # Add only Wikidata (non-extracted) data
    wikidata_property = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1965-12-10",
        archived_page_id=None,  # This makes it Wikidata data
        statement_id="Q345678$12345678-1234-1234-1234-123456789012",  # Wikidata statement ID
    )

    wikidata_position = Property(
        politician_id=politician.id,
        type=PropertyType.POSITION,
        entity_id=position.wikidata_id,
        qualifiers_json={
            "P580": [WikidataDate.from_date_string("2016").to_wikidata_qualifier()]
        },
        archived_page_id=None,  # This makes it Wikidata data
        statement_id="Q345678$87654321-4321-4321-4321-210987654321",  # Wikidata statement ID
    )

    db_session.add_all([wikidata_property, wikidata_position])
    db_session.commit()

    return politician


class TestGetPoliticiansEndpoint:
    """Test the behavior of the get_politicians endpoint."""

    def test_returns_politicians_with_unevaluated_extracted_data(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that politicians with unevaluated extracted data are returned."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        politician_data = data[0]
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
        self, client, mock_auth, politician_with_evaluated_data
    ):
        """Test that politicians with evaluated extracted data but no statement_id are included."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert (
            len(data) == 1
        )  # Should include since evaluation failed to push to Wikidata

    def test_excludes_politicians_with_only_wikidata(
        self, client, mock_auth, politician_with_only_wikidata
    ):
        """Test that politicians with only Wikidata data are excluded."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0  # Should be empty since no extracted data exists

    def test_returns_empty_list_when_no_qualifying_politicians(self, client, mock_auth):
        """Test that endpoint returns empty list when no politicians have unevaluated data."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_response_schema_structure(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that response follows the expected schema structure."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        politician_data = data[0]

        # Test top-level politician fields
        required_fields = ["id", "name", "wikidata_id"]
        for field in required_fields:
            assert field in politician_data

        # Test properties array field exists
        assert "properties" in politician_data
        assert isinstance(politician_data["properties"], list)

        # Test that old grouped fields don't exist
        assert "positions" not in politician_data
        assert "birthplaces" not in politician_data

    def test_extracted_data_contains_proof_and_archive_info(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that extracted data includes proof_line and archived_page info."""
        response = client.get("/politicians/", headers=mock_auth)

        data = response.json()
        politician_data = data[0]

        # Find extracted properties (those with proof_line and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        # Check extracted property
        assert len(extracted_properties["P569"]) == 1  # BIRTH_DATE
        extracted_prop = extracted_properties["P569"][0]
        assert extracted_prop["proof_line"] == "Born on January 15, 1970"
        assert extracted_prop["archived_page"] is not None
        assert "url" in extracted_prop["archived_page"]

        # Check extracted position
        assert len(extracted_properties["P39"]) == 1  # POSITION
        extracted_pos = extracted_properties["P39"][0]
        assert extracted_pos["proof_line"] == "Served as Mayor from 2020 to 2024"
        assert extracted_pos["archived_page"] is not None

        # Check extracted birthplace
        assert len(extracted_properties["P19"]) == 1  # BIRTHPLACE
        extracted_bp = extracted_properties["P19"][0]
        assert extracted_bp["proof_line"] == "Born in Springfield"
        assert extracted_bp["archived_page"] is not None

    def test_wikidata_data_excludes_extraction_fields(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that Wikidata entries don't include extraction-specific fields."""
        response = client.get("/politicians/", headers=mock_auth)

        data = response.json()
        politician_data = data[0]

        # Find Wikidata properties (those without proof_line)
        wikidata_properties = extract_properties_by_type(
            politician_data, extracted=False
        )

        # Wikidata properties should not have proof_line or archived_page
        assert len(wikidata_properties["P570"]) >= 1  # DEATH_DATE
        wikidata_prop = wikidata_properties["P570"][0]
        assert wikidata_prop.get("proof_line") is None
        assert wikidata_prop.get("archived_page") is None

        # But they should have precision fields
        assert "value_precision" in wikidata_prop

    def test_pagination_limits_results(self, client, mock_auth, db_session):
        """Test that pagination parameters limit results correctly."""
        # Create multiple politicians with unevaluated data
        politicians = []
        for i in range(5):
            archived_page = ArchivedPage(
                url=f"https://example.com/test{i}",
                content_hash=f"test{i}",
            )
            politician = Politician.create_with_entity(
                db_session, f"Q{100000 + i}", f"Politician {i}"
            )
            db_session.add(archived_page)
            db_session.flush()

            # Add extracted property
            prop = Property(
                politician_id=politician.id,
                type=PropertyType.BIRTH_DATE,
                value=f"19{70 + i}-01-01",
                archived_page_id=archived_page.id,
            )
            db_session.add(prop)
            politicians.append(politician)

        db_session.commit()

        # Test limit parameter
        response = client.get("/politicians/?limit=3", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Test different limit value
        response = client.get("/politicians/?limit=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_mixed_evaluation_states(
        self, client, mock_auth, db_session, sample_position
    ):
        """Test politician with mix of evaluated and unevaluated data appears in results."""
        # Create politician with both evaluated and unevaluated extracted data
        archived_page = ArchivedPage(
            url="https://example.com/mixed",
            content_hash="mixed123",
        )
        position = sample_position

        db_session.add(archived_page)
        db_session.flush()

        politician = Politician.create_with_entity(
            db_session, "Q999999", "Mixed Evaluation"
        )
        db_session.add(politician)
        db_session.flush()

        # Add evaluated extracted property
        evaluated_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1975-03-15",
            archived_page_id=archived_page.id,
        )
        db_session.add(evaluated_prop)
        db_session.flush()

        evaluation = Evaluation(
            user_id="testuser",
            is_confirmed=True,
            property_id=evaluated_prop.id,
        )

        # Add unevaluated extracted position
        unevaluated_pos = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()]
            },
            archived_page_id=archived_page.id,
        )

        db_session.add_all([evaluation, unevaluated_pos])
        db_session.commit()

        # Should appear in results because has unevaluated position
        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        politician_data = data[0]

        # Find extracted properties (those with proof_line and archived_page)
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
        archived_page = ArchivedPage(
            url="https://example.com/partial",
            content_hash="partial123",
        )
        location = Location.create_with_entity(db_session, "Q100", "Boston")

        db_session.add(archived_page)
        db_session.flush()

        # Politician with only unevaluated birthplace
        politician = Politician.create_with_entity(
            db_session, "Q777777", "Birthplace Only"
        )
        db_session.flush()

        birthplace = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(birthplace)
        db_session.commit()

        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        politician_data = data[0]

        # Find extracted properties (those with proof_line and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        assert len(extracted_properties["P569"]) == 0  # BIRTH_DATE
        assert len(extracted_properties["P39"]) == 0  # POSITION
        assert len(extracted_properties["P19"]) == 1  # BIRTHPLACE

    def test_get_politicians_returns_flat_property_list(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that API returns single flat list of properties."""
        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        politician = data[0]

        # Should have single properties list
        assert "properties" in politician
        assert isinstance(politician["properties"], list)

        # Should NOT have old grouped fields
        assert "positions" not in politician
        assert "birthplaces" not in politician

        # Verify all property types in single list
        property_types = [prop["type"] for prop in politician["properties"]]
        assert "P569" in property_types  # BIRTH_DATE
        assert "P39" in property_types  # POSITION
        assert "P19" in property_types  # BIRTHPLACE

    def test_property_response_structure(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test property response has correct fields."""
        response = client.get("/politicians/", headers=mock_auth)
        politician = response.json()[0]

        for prop in politician["properties"]:
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

    def test_backwards_compatibility_broken(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Ensure old API format no longer works (intentional breaking change)."""
        # This documents that we're intentionally breaking compatibility
        response = client.get("/politicians/", headers=mock_auth)
        politician = response.json()[0]

        # Old structure should not exist
        assert not any(
            key in politician
            for key in ["positions", "birthplaces", "properties_by_type"]
        )

    def test_language_filtering(self, client, mock_auth, db_session, sample_language):
        """Test filtering politicians by language QIDs based on archived page iso codes."""
        # Use the sample_language fixture (English) and create additional languages
        german_lang = Language.create_with_entity(db_session, "Q188", "German")
        german_lang.iso1_code = "de"
        german_lang.iso3_code = "deu"
        french_lang = Language.create_with_entity(db_session, "Q150", "French")
        french_lang.iso1_code = "fr"
        french_lang.iso3_code = "fra"

        # Create archived pages with different language codes
        english_page = ArchivedPage(
            url="https://en.example.com/test", content_hash="en123", iso1_code="en"
        )
        german_page = ArchivedPage(
            url="https://de.example.com/test", content_hash="de123", iso3_code="deu"
        )

        db_session.add_all([english_page, german_page])
        db_session.flush()

        # Create politicians with properties from different language pages
        english_politician = Politician.create_with_entity(
            db_session, "Q1001", "English Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q1002", "German Politician"
        )
        no_lang_politician = Politician.create_with_entity(
            db_session, "Q1003", "No Language Politician"
        )

        db_session.add_all([english_politician, german_politician, no_lang_politician])
        db_session.flush()

        # Add properties linked to language-specific archived pages
        english_prop = Property(
            politician_id=english_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1970-01-01",
            archived_page_id=english_page.id,
        )

        german_prop = Property(
            politician_id=german_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1971-01-01",
            archived_page_id=german_page.id,
        )

        # Property without archived page (should not appear in language filtering)
        no_lang_prop = Property(
            politician_id=no_lang_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1972-01-01",
            archived_page_id=None,  # No archived page = no language filtering
        )

        db_session.add_all([english_prop, german_prop, no_lang_prop])
        db_session.commit()

        # Test filtering by English language QID
        response = client.get("/politicians/?languages=Q1860", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "English Politician"

        # Test filtering by German language QID
        response = client.get("/politicians/?languages=Q188", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "German Politician"

        # Test filtering by multiple languages
        response = client.get(
            "/politicians/?languages=Q1860&languages=Q188", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        politician_names = {p["name"] for p in data}
        assert politician_names == {"English Politician", "German Politician"}

        # Test filtering by non-existent language
        response = client.get("/politicians/?languages=Q999999", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_country_filtering(self, client, mock_auth, db_session, sample_country):
        """Test filtering politicians by country QIDs based on citizenship properties."""
        # Use the sample_country fixture (USA) and create additional countries
        usa_country = sample_country
        germany_country = Country.create_with_entity(db_session, "Q183", "Germany")
        germany_country.iso_code = "DE"
        france_country = Country.create_with_entity(db_session, "Q142", "France")
        france_country.iso_code = "FR"

        # Create archived page
        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
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

        db_session.add_all(
            [
                american_politician,
                german_politician,
                dual_citizen_politician,
                no_citizenship_politician,
            ]
        )
        db_session.flush()

        # Add citizenship properties
        american_citizenship = Property(
            politician_id=american_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=archived_page.id,
        )

        german_citizenship = Property(
            politician_id=german_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany_country.wikidata_id,
            archived_page_id=archived_page.id,
        )

        # Dual citizen - add both citizenships
        dual_usa_citizenship = Property(
            politician_id=dual_citizen_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=archived_page.id,
        )

        dual_germany_citizenship = Property(
            politician_id=dual_citizen_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany_country.wikidata_id,
            archived_page_id=archived_page.id,
        )

        # Non-citizenship property for politician without citizenship
        birth_date_prop = Property(
            politician_id=no_citizenship_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            archived_page_id=archived_page.id,
        )

        db_session.add_all(
            [
                american_citizenship,
                german_citizenship,
                dual_usa_citizenship,
                dual_germany_citizenship,
                birth_date_prop,
            ]
        )
        db_session.commit()

        # Test filtering by USA citizenship
        response = client.get("/politicians/?countries=Q30", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        politician_names = {p["name"] for p in data}
        assert politician_names == {"American Politician", "Dual Citizen Politician"}

        # Test filtering by German citizenship
        response = client.get("/politicians/?countries=Q183", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        politician_names = {p["name"] for p in data}
        assert politician_names == {"German Politician", "Dual Citizen Politician"}

        # Test filtering by multiple countries
        response = client.get(
            "/politicians/?countries=Q30&countries=Q183", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        politician_names = {p["name"] for p in data}
        assert politician_names == {
            "American Politician",
            "German Politician",
            "Dual Citizen Politician",
        }

        # Test filtering by non-existent country
        response = client.get("/politicians/?countries=Q999999", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_combined_language_and_country_filtering(
        self, client, mock_auth, db_session, sample_language, sample_country
    ):
        """Test filtering by both language and country filters combined."""
        # Use fixtures for English language and USA country
        usa_country = sample_country
        germany_country = Country.create_with_entity(db_session, "Q183", "Germany")
        germany_country.iso_code = "DE"

        # Create archived pages
        english_page = ArchivedPage(
            url="https://en.example.com/test", content_hash="en123", iso1_code="en"
        )
        db_session.add(english_page)
        db_session.flush()

        # Create politicians
        american_english_politician = Politician.create_with_entity(
            db_session, "Q3001", "American English Speaking Politician"
        )
        german_english_politician = Politician.create_with_entity(
            db_session, "Q3002", "German English Speaking Politician"
        )
        american_non_english_politician = Politician.create_with_entity(
            db_session, "Q3003", "American Non-English Speaking Politician"
        )

        db_session.add_all(
            [
                american_english_politician,
                german_english_politician,
                american_non_english_politician,
            ]
        )
        db_session.flush()

        # Add properties for American English speaking politician
        american_eng_citizenship = Property(
            politician_id=american_english_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=english_page.id,
        )
        american_eng_birth = Property(
            politician_id=american_english_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1970-01-01",
            archived_page_id=english_page.id,
        )

        # Add properties for German English speaking politician
        german_eng_citizenship = Property(
            politician_id=german_english_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=germany_country.wikidata_id,
            archived_page_id=english_page.id,
        )
        german_eng_birth = Property(
            politician_id=german_english_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1971-01-01",
            archived_page_id=english_page.id,
        )

        # Add properties for American non-English speaking politician
        american_non_eng_citizenship = Property(
            politician_id=american_non_english_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=usa_country.wikidata_id,
            archived_page_id=None,  # No archived page = won't match language filter
        )

        db_session.add_all(
            [
                american_eng_citizenship,
                american_eng_birth,
                german_eng_citizenship,
                german_eng_birth,
                american_non_eng_citizenship,
            ]
        )
        db_session.commit()

        # Test combined filtering: English language AND American citizenship
        response = client.get(
            "/politicians/?languages=Q1860&countries=Q30", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "American English Speaking Politician"

        # Test combined filtering: English language AND German citizenship
        response = client.get(
            "/politicians/?languages=Q1860&countries=Q183", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "German English Speaking Politician"

        # Test that individual filters work correctly
        # English language only - should return both English speaking politicians
        response = client.get("/politicians/?languages=Q1860", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        politician_names = {p["name"] for p in data}
        assert politician_names == {
            "American English Speaking Politician",
            "German English Speaking Politician",
        }
