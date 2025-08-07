"""Tests for API endpoints with MediaWiki OAuth authentication."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from poliloom.api.app import app
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
        username=test_user["username"],
        user_id=test_user["sub"],
        email=test_user["email"],
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
        response = client.post("/politicians/evaluate", json=evaluation_data)
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

    def test_valid_token_passes_auth(self, client, test_engine):
        """Test that valid OAuth token passes authentication."""
        from unittest.mock import AsyncMock, Mock as SyncMock

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(
                username="testuser", user_id=12345, email="test@example.com"
            )
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
        from unittest.mock import AsyncMock, Mock as SyncMock

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(
                username="testuser", user_id=12345, email="test@example.com"
            )
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock the database session
            with patch("poliloom.api.politicians.get_db") as mock_get_db:
                mock_db = SyncMock()
                mock_db.commit.return_value = None
                mock_get_db.return_value = mock_db

                headers = {"Authorization": "Bearer valid_jwt_token"}
                evaluation_data = {"evaluations": []}
                response = client.post(
                    "/politicians/evaluate", json=evaluation_data, headers=headers
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
        response = client.post("/politicians/evaluate", json=evaluation_data)
        # Should fail with 403 (auth required) not 404 (not found)
        assert response.status_code == 403


class TestAPIResponseSchemas:
    """Test API response schemas and validation."""

    def test_evaluation_request_validation(self, client):
        """Test that evaluation request validates input schema."""
        # Test with invalid JSON structure
        invalid_data = {"invalid_field": "value"}
        response = client.post("/politicians/evaluate", json=invalid_data)

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

    @pytest.fixture
    def test_client_with_db_override(self, test_session):
        """Create a test client with database dependency override."""
        from poliloom.api.app import app
        from poliloom.database import get_db

        def get_test_db():
            yield test_session

        app.dependency_overrides[get_db] = get_test_db
        client = TestClient(app)
        yield client
        app.dependency_overrides.clear()

    def test_archived_page_requires_auth(self, test_client_with_db_override):
        """Test that archived pages endpoints require authentication."""
        client = test_client_with_db_override
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Test .html endpoint
        response = client.get(f"/archived-pages/{fake_id}.html")
        assert response.status_code == 403  # No auth token provided

        # Test .md endpoint
        response = client.get(f"/archived-pages/{fake_id}.md")
        assert response.status_code == 403  # No auth token provided

    def test_invalid_uuid_format_rejected(self, test_client_with_db_override):
        """Test that invalid UUID format is rejected."""
        from unittest.mock import AsyncMock, Mock as SyncMock

        client = test_client_with_db_override

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(
                username="testuser", user_id=12345, email="test@example.com"
            )
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

    def test_nonexistent_archived_page_returns_404(self, test_client_with_db_override):
        """Test that nonexistent archived page returns 404."""
        from unittest.mock import AsyncMock, Mock as SyncMock

        client = test_client_with_db_override

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(
                username="testuser", user_id=12345, email="test@example.com"
            )
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

    def test_file_not_found_returns_404(
        self, test_client_with_db_override, sample_archived_page
    ):
        """Test that missing files return 404."""
        from unittest.mock import AsyncMock, Mock as SyncMock, patch

        client = test_client_with_db_override

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(
                username="testuser", user_id=12345, email="test@example.com"
            )
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock the archived page's read methods to raise FileNotFoundError
            with patch(
                "poliloom.models.ArchivedPage.read_markdown_content",
                side_effect=FileNotFoundError("File not found"),
            ):
                headers = {"Authorization": "Bearer valid_jwt_token"}

                response = client.get(
                    f"/archived-pages/{sample_archived_page.id}.md", headers=headers
                )
                assert response.status_code == 404
                assert "File not found" in response.json()["detail"]

    def test_explicit_extension_endpoints(
        self, test_client_with_db_override, sample_archived_page
    ):
        """Test explicit .html and .md extension endpoints."""
        from unittest.mock import AsyncMock, Mock as SyncMock, patch

        client = test_client_with_db_override

        with patch("poliloom.api.auth.get_oauth_handler") as mock_get_oauth_handler:
            # Mock successful OAuth verification
            mock_user = User(
                username="testuser", user_id=12345, email="test@example.com"
            )
            mock_oauth_handler = SyncMock()
            mock_oauth_handler.verify_jwt_token = AsyncMock(return_value=mock_user)
            mock_get_oauth_handler.return_value = mock_oauth_handler

            # Mock the archived page's read methods
            with (
                patch(
                    "poliloom.models.ArchivedPage.read_markdown_content",
                    return_value="# Test Markdown",
                ),
                patch(
                    "poliloom.models.ArchivedPage.read_html_content",
                    return_value="<h1>Test HTML</h1>",
                ),
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

    def test_archived_pages_endpoints_exist(self, test_client_with_db_override):
        """Test that archived pages endpoints exist."""
        client = test_client_with_db_override
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Should fail with 403 (auth required) not 404 (not found)
        response = client.get(f"/archived-pages/{fake_id}.html")
        assert response.status_code == 403

        response = client.get(f"/archived-pages/{fake_id}.md")
        assert response.status_code == 403
