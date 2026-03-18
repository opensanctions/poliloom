"""Tests for source HTML API endpoints."""

from unittest.mock import patch


class TestSourcesAPI:
    """Test source API endpoints with transaction-based tests."""

    def test_source_endpoints_require_auth(self, client):
        """Test that source endpoints require authentication."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Test .html endpoint without auth
        response = client.get(f"/sources/{fake_id}.html")
        assert response.status_code == 401

    def test_invalid_uuid_format_rejected(self, client, mock_auth):
        """Test that invalid UUID format is rejected."""
        # Test with invalid UUID (.html)
        response = client.get("/sources/invalid-uuid.html", headers=mock_auth)
        assert response.status_code == 400
        assert "Invalid source ID format" in response.json()["detail"]

    def test_nonexistent_source_returns_404(self, client, mock_auth):
        """Test that nonexistent source returns 404."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        response = client.get(f"/sources/{fake_id}.html", headers=mock_auth)
        assert response.status_code == 404
        assert "Source not found" in response.json()["detail"]

    def test_file_not_found_returns_404(self, client, mock_auth, sample_source):
        """Test that missing files return 404 even when database record exists."""
        # Mock the archival service's read method to raise FileNotFoundError
        with patch(
            "poliloom.api.sources.read_archived_content",
            side_effect=FileNotFoundError("File not found"),
        ):
            response = client.get(
                f"/sources/{sample_source.id}.html", headers=mock_auth
            )
            assert response.status_code == 404
            assert "File not found" in response.json()["detail"]

    def test_html_endpoint_returns_html_content(self, client, mock_auth, sample_source):
        """Test that .html endpoint returns HTML content with correct content type."""

        # Mock the archival service's read method to return HTML
        def mock_read_content(path_root, extension):
            if extension == "html":
                return "<h1>Test HTML</h1>"
            raise FileNotFoundError()

        with patch(
            "poliloom.api.sources.read_archived_content",
            side_effect=mock_read_content,
        ):
            response = client.get(
                f"/sources/{sample_source.id}.html", headers=mock_auth
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"
            assert response.text == "<h1>Test HTML</h1>"
