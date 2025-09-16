"""Tests for the get_politicians endpoint focusing on behavior, not implementation."""

import pytest
from unittest.mock import AsyncMock, Mock as SyncMock, patch
from fastapi.testclient import TestClient

from poliloom.api import app
from poliloom.api.auth import User
from poliloom.models import (
    Politician,
    Property,
    PropertyType,
    Position,
    Location,
    HoldsPosition,
    BornAt,
    ArchivedPage,
    PropertyEvaluation,
)


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
def politician_with_unevaluated_data(db_session):
    """Create a politician with various types of unevaluated extracted data."""
    # Create supporting entities
    archived_page = ArchivedPage(
        url="https://example.com/test",
        content_hash="test123",
    )
    position = Position.create_with_entity(db_session, "Q30185", "Mayor")
    location = Location.create_with_entity(db_session, "Q28513", "Springfield")

    db_session.add(archived_page)
    db_session.flush()

    # Create politician
    politician = Politician(name="Test Politician", wikidata_id="Q123456")
    db_session.add(politician)
    db_session.flush()

    # Add extracted (unevaluated) data
    extracted_property = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1970-01-15",
        archived_page_id=archived_page.id,
        proof_line="Born on January 15, 1970",
    )

    extracted_position = HoldsPosition(
        politician_id=politician.id,
        position_id=position.wikidata_id,
        start_date="2020",
        end_date="2024",
        archived_page_id=archived_page.id,
        proof_line="Served as Mayor from 2020 to 2024",
    )

    extracted_birthplace = BornAt(
        politician_id=politician.id,
        location_id=location.wikidata_id,
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

    wikidata_position = HoldsPosition(
        politician_id=politician.id,
        position_id=position.wikidata_id,
        start_date="2018",
        end_date="2020",
        archived_page_id=None,  # This makes it Wikidata data
    )

    wikidata_birthplace = BornAt(
        politician_id=politician.id,
        location_id=location.wikidata_id,
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
    politician = Politician(name="Evaluated Politician", wikidata_id="Q789012")
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
    evaluation = PropertyEvaluation(
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

    politician = Politician(name="Wikidata Only Politician", wikidata_id="Q345678")
    db_session.add(politician)
    db_session.flush()

    # Add only Wikidata (non-extracted) data
    wikidata_property = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1965-12-10",
        archived_page_id=None,  # This makes it Wikidata data
    )

    wikidata_position = HoldsPosition(
        politician_id=politician.id,
        position_id=position.wikidata_id,
        start_date="2016",
        archived_page_id=None,  # This makes it Wikidata data
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

        # Should have unevaluated extracted data
        assert len(politician_data["extracted_properties"]) == 1
        assert len(politician_data["extracted_positions"]) == 1
        assert len(politician_data["extracted_birthplaces"]) == 1

        # Should also have Wikidata data
        assert len(politician_data["wikidata_properties"]) == 1
        assert len(politician_data["wikidata_positions"]) == 1
        assert len(politician_data["wikidata_birthplaces"]) == 1

    def test_excludes_politicians_with_only_evaluated_data(
        self, client, mock_auth, politician_with_evaluated_data
    ):
        """Test that politicians with only evaluated extracted data are excluded."""
        response = client.get("/politicians/", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0  # Should be empty since all extracted data is evaluated

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

        # Test array fields exist
        array_fields = [
            "wikidata_properties",
            "wikidata_positions",
            "wikidata_birthplaces",
            "extracted_properties",
            "extracted_positions",
            "extracted_birthplaces",
        ]
        for field in array_fields:
            assert field in politician_data
            assert isinstance(politician_data[field], list)

    def test_extracted_data_contains_proof_and_archive_info(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that extracted data includes proof_line and archived_page info."""
        response = client.get("/politicians/", headers=mock_auth)

        data = response.json()
        politician_data = data[0]

        # Check extracted property
        extracted_prop = politician_data["extracted_properties"][0]
        assert extracted_prop["proof_line"] == "Born on January 15, 1970"
        assert extracted_prop["archived_page"] is not None
        assert "url" in extracted_prop["archived_page"]

        # Check extracted position
        extracted_pos = politician_data["extracted_positions"][0]
        assert extracted_pos["proof_line"] == "Served as Mayor from 2020 to 2024"
        assert extracted_pos["archived_page"] is not None

        # Check extracted birthplace
        extracted_bp = politician_data["extracted_birthplaces"][0]
        assert extracted_bp["proof_line"] == "Born in Springfield"
        assert extracted_bp["archived_page"] is not None

    def test_wikidata_data_excludes_extraction_fields(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that Wikidata entries don't include extraction-specific fields."""
        response = client.get("/politicians/", headers=mock_auth)

        data = response.json()
        politician_data = data[0]

        # Wikidata properties should not have proof_line or archived_page
        wikidata_prop = politician_data["wikidata_properties"][0]
        assert "proof_line" not in wikidata_prop
        assert "archived_page" not in wikidata_prop

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
            politician = Politician(
                name=f"Politician {i}", wikidata_id=f"Q{100000 + i}"
            )
            db_session.add_all([archived_page, politician])
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

    def test_mixed_evaluation_states(self, client, mock_auth, db_session):
        """Test politician with mix of evaluated and unevaluated data appears in results."""
        # Create politician with both evaluated and unevaluated extracted data
        archived_page = ArchivedPage(
            url="https://example.com/mixed",
            content_hash="mixed123",
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")

        db_session.add(archived_page)
        db_session.flush()

        politician = Politician(name="Mixed Evaluation", wikidata_id="Q999999")
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

        evaluation = PropertyEvaluation(
            user_id="testuser",
            is_confirmed=True,
            property_id=evaluated_prop.id,
        )

        # Add unevaluated extracted position
        unevaluated_pos = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2020",
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
        assert (
            len(politician_data["extracted_properties"]) == 0
        )  # Evaluated, so not returned
        assert (
            len(politician_data["extracted_positions"]) == 1
        )  # Unevaluated, so returned

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
        politician = Politician(name="Birthplace Only", wikidata_id="Q777777")
        db_session.add(politician)
        db_session.flush()

        birthplace = BornAt(
            politician_id=politician.id,
            location_id=location.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(birthplace)
        db_session.commit()

        response = client.get("/politicians/", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        politician_data = data[0]
        assert len(politician_data["extracted_properties"]) == 0
        assert len(politician_data["extracted_positions"]) == 0
        assert len(politician_data["extracted_birthplaces"]) == 1
