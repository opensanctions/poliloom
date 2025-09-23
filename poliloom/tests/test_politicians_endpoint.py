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
    ArchivedPage,
    Evaluation,
)


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
        "BIRTH_DATE": [],
        "DEATH_DATE": [],
        "POSITION": [],
        "BIRTHPLACE": [],
        "CITIZENSHIP": [],
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
            "P580": [
                {
                    "datatype": "time",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2020-01-01T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
            "P582": [
                {
                    "datatype": "time",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2024-01-01T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
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
            "P580": [
                {
                    "datatype": "time",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2018-01-01T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
            "P582": [
                {
                    "datatype": "time",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2020-01-01T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
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
            "P580": [
                {
                    "datatype": "time",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2016-01-01T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ]
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
        assert "BIRTH_DATE" in property_types
        assert "DEATH_DATE" in property_types
        assert "POSITION" in property_types
        assert "BIRTHPLACE" in property_types

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
        assert len(extracted_properties["BIRTH_DATE"]) == 1
        extracted_prop = extracted_properties["BIRTH_DATE"][0]
        assert extracted_prop["proof_line"] == "Born on January 15, 1970"
        assert extracted_prop["archived_page"] is not None
        assert "url" in extracted_prop["archived_page"]

        # Check extracted position
        assert len(extracted_properties["POSITION"]) == 1
        extracted_pos = extracted_properties["POSITION"][0]
        assert extracted_pos["proof_line"] == "Served as Mayor from 2020 to 2024"
        assert extracted_pos["archived_page"] is not None

        # Check extracted birthplace
        assert len(extracted_properties["BIRTHPLACE"]) == 1
        extracted_bp = extracted_properties["BIRTHPLACE"][0]
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
        assert len(wikidata_properties["DEATH_DATE"]) >= 1
        wikidata_prop = wikidata_properties["DEATH_DATE"][0]
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

        # Test offset parameter
        response = client.get("/politicians/?offset=2&limit=2", headers=mock_auth)
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
                "P580": [
                    {
                        "datatype": "time",
                        "snaktype": "value",
                        "datavalue": {
                            "type": "time",
                            "value": {
                                "time": "+2020-01-01T00:00:00Z",
                                "after": 0,
                                "before": 0,
                                "timezone": 0,
                                "precision": 9,
                                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                            },
                        },
                    }
                ]
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
            len(extracted_properties["BIRTH_DATE"]) == 1
        )  # Evaluated but no statement_id, so still returned for re-evaluation
        assert len(extracted_properties["POSITION"]) == 1  # Unevaluated, so returned

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

        assert len(extracted_properties["BIRTH_DATE"]) == 0
        assert len(extracted_properties["POSITION"]) == 0
        assert len(extracted_properties["BIRTHPLACE"]) == 1

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
        assert "BIRTH_DATE" in property_types
        assert "POSITION" in property_types
        assert "BIRTHPLACE" in property_types

    def test_property_response_structure(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test property response has correct fields."""
        response = client.get("/politicians/", headers=mock_auth)
        politician = response.json()[0]

        for prop in politician["properties"]:
            assert "id" in prop
            assert "type" in prop

            if prop["type"] in ["BIRTH_DATE", "DEATH_DATE"]:
                assert prop["value"] is not None
                assert prop["entity_id"] is None
            elif prop["type"] in ["BIRTHPLACE", "POSITION", "CITIZENSHIP"]:
                assert prop["entity_id"] is not None
                assert prop["value"] is None
                assert "entity_name" in prop

    def test_evaluate_single_list(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation accepts single list."""
        # First get some properties to evaluate
        response = client.get("/politicians/", headers=mock_auth)
        politician = response.json()[0]
        test_properties = politician["properties"][:2]  # Take first 2 properties

        # Old format should NOT work
        old_format = {
            "property_evaluations": [
                {"id": test_properties[0]["id"], "is_confirmed": True}
            ],
            "position_evaluations": [],
            "birthplace_evaluations": [],
        }
        response = client.post(
            "/politicians/evaluate", json=old_format, headers=mock_auth
        )
        assert response.status_code == 422  # Validation error

        # New format should work
        new_format = {
            "evaluations": [
                {"id": test_properties[0]["id"], "is_confirmed": True},
                {"id": test_properties[1]["id"], "is_confirmed": False},
            ]
        }
        response = client.post(
            "/politicians/evaluate", json=new_format, headers=mock_auth
        )
        assert response.status_code == 200
        assert response.json()["evaluation_count"] == 2

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
