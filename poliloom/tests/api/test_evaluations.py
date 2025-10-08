"""Tests for the evaluations API endpoint."""

import pytest
from unittest.mock import AsyncMock, Mock as SyncMock, patch
from fastapi.testclient import TestClient

from poliloom.api import app
from poliloom.api.auth import User
from poliloom.models import (
    Property,
    PropertyType,
    ArchivedPage,
)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_auth():
    """Mock authentication for tests."""
    with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
        mock_user = User(user_id=12345, jwt_token="valid_jwt_token")
        mock_oauth_handler = SyncMock()
        mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
        mock_get_oauth_handler.return_value = mock_oauth_handler
        yield {"Authorization": "Bearer valid_jwt_token"}


@pytest.fixture
def politician_with_unevaluated_data(db_session, sample_politician, sample_position):
    """Create a politician with unevaluated extracted data for testing evaluations."""
    # Create supporting entities
    archived_page = ArchivedPage(
        url="https://example.com/test",
        content_hash="test123",
    )
    politician = sample_politician
    position = sample_position

    db_session.add(archived_page)
    db_session.flush()

    # Add extracted (unevaluated) data
    extracted_property = Property(
        politician_id=politician.id,
        type=PropertyType.BIRTH_DATE,
        value="1970-01-15",
        value_precision=11,
        archived_page_id=archived_page.id,
        proof_line="Born on January 15, 1970",
    )

    extracted_position = Property(
        politician_id=politician.id,
        type=PropertyType.POSITION,
        entity_id=position.wikidata_id,
        archived_page_id=archived_page.id,
        proof_line="Served as Mayor from 2020 to 2024",
    )

    db_session.add_all([extracted_property, extracted_position])
    db_session.commit()

    return politician, [extracted_property, extracted_position]


class TestEvaluationsEndpoint:
    """Test the evaluations API endpoint."""

    def test_evaluate_single_list(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation accepts single list format."""
        politician, test_properties = politician_with_unevaluated_data

        # Old format should NOT work
        old_format = {
            "property_evaluations": [
                {"id": str(test_properties[0].id), "is_confirmed": True}
            ],
            "position_evaluations": [],
            "birthplace_evaluations": [],
        }
        response = client.post("/evaluations/", json=old_format, headers=mock_auth)
        assert response.status_code == 422  # Validation error

        # New format should work
        new_format = {
            "evaluations": [
                {"id": str(test_properties[0].id), "is_confirmed": True},
                {"id": str(test_properties[1].id), "is_confirmed": False},
            ]
        }
        response = client.post("/evaluations/", json=new_format, headers=mock_auth)
        assert response.status_code == 200
        assert response.json()["evaluation_count"] == 2

    def test_evaluate_nonexistent_property(self, client, mock_auth):
        """Test evaluation with nonexistent property ID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        evaluation_data = {
            "evaluations": [
                {"id": fake_uuid, "is_confirmed": True}  # Nonexistent ID
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200  # Should succeed but with errors
        result = response.json()
        assert result["evaluation_count"] == 0
        assert len(result["errors"]) > 0
        assert f"Property {fake_uuid} not found" in result["errors"]

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_mixed_valid_invalid_properties(
        self, mock_push_evaluation, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test evaluation with mix of valid and invalid property IDs."""
        mock_push_evaluation.return_value = True
        politician, test_properties = politician_with_unevaluated_data

        fake_uuid = "99999999-9999-9999-9999-999999999999"
        evaluation_data = {
            "evaluations": [
                {"id": str(test_properties[0].id), "is_confirmed": True},  # Valid
                {"id": fake_uuid, "is_confirmed": False},  # Invalid
                {"id": str(test_properties[1].id), "is_confirmed": True},  # Valid
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["evaluation_count"] == 2  # Only valid properties evaluated
        assert len(result["errors"]) == 1
        assert f"Property {fake_uuid} not found" in result["errors"][0]

    def test_evaluate_requires_authentication(self, client):
        """Test that evaluation endpoint requires authentication."""
        evaluation_data = {
            "evaluations": [
                {"id": "11111111-1111-1111-1111-111111111111", "is_confirmed": True}
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data)
        assert response.status_code in [401, 403]  # Unauthorized

    def test_evaluate_empty_list(self, client, mock_auth):
        """Test evaluation with empty evaluations list."""
        evaluation_data = {"evaluations": []}
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["evaluation_count"] == 0
        assert result["success"] is True

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push(
        self, mock_push_evaluation, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that evaluations are pushed to Wikidata when confirmed."""
        mock_push_evaluation.return_value = True
        politician, test_properties = politician_with_unevaluated_data

        evaluation_data = {
            "evaluations": [{"id": str(test_properties[0].id), "is_confirmed": True}]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["evaluation_count"] == 1

        # Verify push_evaluation was called
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push_failure(
        self, mock_push_evaluation, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test handling of Wikidata push failures."""
        mock_push_evaluation.side_effect = Exception("Wikidata API error")
        politician, test_properties = politician_with_unevaluated_data

        evaluation_data = {
            "evaluations": [{"id": str(test_properties[0].id), "is_confirmed": True}]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200  # Should still succeed locally
        result = response.json()
        assert result["evaluation_count"] == 1
        assert len(result["errors"]) > 0
        assert any("Wikidata API error" in error for error in result["errors"])
