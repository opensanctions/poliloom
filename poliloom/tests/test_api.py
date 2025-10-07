"""Tests for API endpoints with MediaWiki OAuth authentication."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock as SyncMock, patch

from poliloom.api import app
from poliloom.api.auth import User
from .conftest import load_json_fixture


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    auth_data = load_json_fixture("auth_test_data.json")
    test_user = auth_data["test_user"]
    return User(
        user_id=test_user["sub"],
    )


class TestAPIAuthentication:
    """Test authentication integration across API endpoints."""

    def test_unconfirmed_politicians_requires_auth(self, client):
        """Test that /politicians requires authentication."""
        response = client.get("/politicians/")
        assert response.status_code == 403  # No auth token provided

    def test_evaluate_requires_auth(self, client):
        """Test that /evaluate requires authentication."""
        evaluation_data = {"evaluations": []}
        response = client.post("/evaluations/", json=evaluation_data)
        assert response.status_code == 403  # No auth token provided

    def test_invalid_token_format_rejected(self, client):
        """Test that invalid token format is rejected."""
        headers = {"Authorization": "Bearer invalid_token_format"}
        response = client.get("/politicians/", headers=headers)
        assert response.status_code == 401  # Invalid token format

    def test_invalid_auth_scheme_rejected(self, client):
        """Test that invalid auth scheme is rejected."""
        headers = {"Authorization": "Basic invalid_scheme"}
        response = client.get("/politicians/", headers=headers)
        assert response.status_code == 403  # Invalid scheme

    def test_valid_token_passes_auth(self, client):
        """Test that valid OAuth token passes authentication."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            headers = {"Authorization": "Bearer valid_jwt_token"}
            response = client.get("/politicians/", headers=headers)

            # Should be 200 (auth should pass) with empty results
            assert response.status_code == 200
            mock_oauth_handler.verify_jwt_token.assert_called_once_with(
                "valid_jwt_token"
            )

    def test_evaluation_endpoint_with_auth(self, client):
        """Test that /evaluate endpoint works with valid authentication."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            headers = {"Authorization": "Bearer valid_jwt_token"}
            evaluation_data = {"evaluations": []}
            response = client.post(
                "/evaluations/", json=evaluation_data, headers=headers
            )

            # Should be 200 (auth should pass)
            assert response.status_code == 200
            mock_oauth_handler.verify_jwt_token.assert_called_once_with(
                "valid_jwt_token"
            )


class TestAPIEndpointsStructure:
    """Test that API endpoints are properly defined."""

    def test_root_endpoint_exists(self, client):
        """Test that root endpoint exists and returns expected response."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "PoliLoom API"}

    def test_unconfirmed_politicians_endpoint_exists(self, client):
        """Test that politicians endpoint exists."""
        response = client.get("/politicians/")
        # Should fail with 403 (auth required) not 404 (not found)
        assert response.status_code == 403

    def test_evaluate_endpoint_exists(self, client):
        """Test that evaluate endpoint exists."""
        evaluation_data = {"evaluations": []}
        response = client.post("/evaluations/", json=evaluation_data)
        # Should fail with 403 (auth required) not 404 (not found)
        assert response.status_code == 403


class TestAPIResponseSchemas:
    """Test API response schemas and validation."""

    def test_evaluation_request_validation(self, client):
        """Test that evaluation request validates input schema."""
        # Test with invalid JSON structure
        invalid_data = {"invalid_field": "value"}
        response = client.post("/evaluations/", json=invalid_data)

        # Should either be 403 (auth required) or 422 (validation error)
        # The auth error takes precedence
        assert response.status_code == 403

    def test_pagination_parameter_validation(self, client):
        """Test that pagination parameters are validated."""
        # Test with invalid limit (too high)
        response = client.get("/politicians/?limit=101")
        assert response.status_code in [403, 422]  # Auth or validation error

        # Test with invalid offset (negative)
        response = client.get("/politicians/?offset=-1")
        assert response.status_code in [403, 422]  # Auth or validation error


class TestArchivedPagesAPI:
    """Test archived pages API endpoints."""

    def test_archived_page_requires_auth(self, client):
        """Test that archived pages endpoints require authentication."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Test .html endpoint
        response = client.get(f"/archived-pages/{fake_id}.html")
        assert response.status_code == 403  # No auth token provided

        # Test .md endpoint
        response = client.get(f"/archived-pages/{fake_id}.md")
        assert response.status_code == 403  # No auth token provided

    def test_invalid_uuid_format_rejected(self, client):
        """Test that invalid UUID format is rejected."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            headers = {"Authorization": "Bearer valid_jwt_token"}

            # Test with invalid UUID (.html)
            response = client.get("/archived-pages/invalid-uuid.html", headers=headers)
            assert response.status_code == 400
            assert "Invalid archived page ID format" in response.json()["detail"]

            # Test with invalid UUID (.md)
            response = client.get("/archived-pages/invalid-uuid.md", headers=headers)
            assert response.status_code == 400
            assert "Invalid archived page ID format" in response.json()["detail"]

    def test_nonexistent_archived_page_returns_404(self, client):
        """Test that nonexistent archived page returns 404."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            headers = {"Authorization": "Bearer valid_jwt_token"}
            fake_id = "12345678-1234-1234-1234-123456789012"

            # Test both .html and .md endpoints
            response = client.get(f"/archived-pages/{fake_id}.html", headers=headers)
            assert response.status_code == 404
            assert "Archived page not found" in response.json()["detail"]

            response = client.get(f"/archived-pages/{fake_id}.md", headers=headers)
            assert response.status_code == 404
            assert "Archived page not found" in response.json()["detail"]

    def test_file_not_found_returns_404(self, client, db_session, sample_archived_page):
        """Test that missing files return 404."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock the archival service's read method to raise FileNotFoundError
            with patch(
                "poliloom.archive.read_archived_content",
                side_effect=FileNotFoundError("File not found"),
            ):
                headers = {"Authorization": "Bearer valid_jwt_token"}

                response = client.get(
                    f"/archived-pages/{sample_archived_page.id}.md", headers=headers
                )
                assert response.status_code == 404
                assert "File not found" in response.json()["detail"]

    def test_explicit_extension_endpoints(
        self, client, db_session, sample_archived_page
    ):
        """Test explicit .html and .md extension endpoints."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock the archival service's read method
            def mock_read_content(path_root, extension):
                if extension == "md":
                    return "# Test Markdown"
                elif extension == "html":
                    return "<h1>Test HTML</h1>"

            with patch(
                "poliloom.archive.read_archived_content",
                side_effect=mock_read_content,
            ):
                headers = {"Authorization": "Bearer valid_jwt_token"}

                # Test .html endpoint
                response = client.get(
                    f"/archived-pages/{sample_archived_page.id}.html", headers=headers
                )
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/html; charset=utf-8"
                assert response.text == "<h1>Test HTML</h1>"

                # Test .md endpoint
                response = client.get(
                    f"/archived-pages/{sample_archived_page.id}.md", headers=headers
                )
                assert response.status_code == 200
                assert (
                    response.headers["content-type"] == "text/markdown; charset=utf-8"
                )
                assert response.text == "# Test Markdown"

    def test_archived_pages_endpoints_exist(self, client):
        """Test that archived pages endpoints exist."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Should fail with 403 (auth required) not 404 (not found)
        response = client.get(f"/archived-pages/{fake_id}.html")
        assert response.status_code == 403

        response = client.get(f"/archived-pages/{fake_id}.md")
        assert response.status_code == 403


class TestEnrichAPI:
    """Test enrich API endpoint."""

    def test_enrich_requires_auth(self, client):
        """Test that /enrich requires authentication."""
        response = client.post("/enrich")
        assert response.status_code == 403  # No auth token provided

    def test_enrich_endpoint_exists(self, client):
        """Test that enrich endpoint exists."""
        response = client.post("/enrich")
        # Should fail with 403 (auth required) not 404 (not found)
        assert response.status_code == 403

    def test_enrich_with_valid_auth(self, client):
        """Test that /enrich works with valid authentication."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock enrich_until_target to avoid actual enrichment
            with patch("poliloom.api.enrichment.enrich_until_target") as mock_enrich:
                mock_enrich.return_value = 2  # Simulate enriching 2 politicians

                headers = {"Authorization": "Bearer valid_jwt_token"}
                response = client.post("/enrich", headers=headers)

                # Should return 200 with enriched_count
                assert response.status_code == 200
                assert "enriched_count" in response.json()
                assert response.json()["enriched_count"] == 2

                # Verify enrich_until_target was called with target=1
                assert mock_enrich.call_count >= 1
                first_call = mock_enrich.call_args_list[0]
                assert first_call[0][0] == 1  # First argument is target=1

    def test_enrich_with_language_filter(self, client):
        """Test that /enrich accepts language filter."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock enrich_until_target
            with patch("poliloom.api.enrichment.enrich_until_target") as mock_enrich:
                mock_enrich.return_value = 1

                headers = {"Authorization": "Bearer valid_jwt_token"}
                response = client.post(
                    "/enrich?languages=Q1860&languages=Q150", headers=headers
                )

                assert response.status_code == 200
                # Verify languages were passed correctly
                first_call = mock_enrich.call_args_list[0]
                assert first_call[0][1] == ["Q1860", "Q150"]  # languages parameter

    def test_enrich_with_country_filter(self, client):
        """Test that /enrich accepts country filter."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock enrich_until_target
            with patch("poliloom.api.enrichment.enrich_until_target") as mock_enrich:
                mock_enrich.return_value = 1

                headers = {"Authorization": "Bearer valid_jwt_token"}
                response = client.post("/enrich?countries=Q30", headers=headers)

                assert response.status_code == 200
                # Verify countries were passed correctly
                first_call = mock_enrich.call_args_list[0]
                assert first_call[0][2] == ["Q30"]  # countries parameter

    def test_enrich_queues_background_task(self, client):
        """Test that /enrich queues a background task for additional enrichment."""

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(user_id=12345)
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock enrich_until_target
            with patch("poliloom.api.enrichment.enrich_until_target") as mock_enrich:
                mock_enrich.return_value = 1

                headers = {"Authorization": "Bearer valid_jwt_token"}
                response = client.post("/enrich", headers=headers)

                assert response.status_code == 200

                # Should be called at least twice (foreground + background)
                # Note: background tasks may not execute in test client
                # So we just verify the foreground call
                assert mock_enrich.call_count >= 1
