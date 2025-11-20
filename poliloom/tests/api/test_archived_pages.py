"""Tests for archived pages API endpoints."""

from unittest.mock import patch


class TestArchivedPagesAPI:
    """Test archived pages API endpoints with transaction-based tests."""

    def test_archived_page_endpoints_require_auth(self, client):
        """Test that archived pages endpoints require authentication."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Test .html endpoint without auth
        response = client.get(f"/archived-pages/{fake_id}.html")
        assert response.status_code == 403

        # Test .md endpoint without auth
        response = client.get(f"/archived-pages/{fake_id}.md")
        assert response.status_code == 403

    def test_invalid_uuid_format_rejected(self, client, mock_auth):
        """Test that invalid UUID format is rejected."""
        # Test with invalid UUID (.html)
        response = client.get("/archived-pages/invalid-uuid.html", headers=mock_auth)
        assert response.status_code == 400
        assert "Invalid archived page ID format" in response.json()["detail"]

        # Test with invalid UUID (.md)
        response = client.get("/archived-pages/invalid-uuid.md", headers=mock_auth)
        assert response.status_code == 400
        assert "Invalid archived page ID format" in response.json()["detail"]

    def test_nonexistent_archived_page_returns_404(self, client, mock_auth):
        """Test that nonexistent archived page returns 404."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Test both .html and .md endpoints
        response = client.get(f"/archived-pages/{fake_id}.html", headers=mock_auth)
        assert response.status_code == 404
        assert "Archived page not found" in response.json()["detail"]

        response = client.get(f"/archived-pages/{fake_id}.md", headers=mock_auth)
        assert response.status_code == 404
        assert "Archived page not found" in response.json()["detail"]

    def test_file_not_found_returns_404(self, client, mock_auth, sample_archived_page):
        """Test that missing files return 404 even when database record exists."""
        # Mock the archival service's read method to raise FileNotFoundError
        with patch(
            "poliloom.archive.read_archived_content",
            side_effect=FileNotFoundError("File not found"),
        ):
            response = client.get(
                f"/archived-pages/{sample_archived_page.id}.md", headers=mock_auth
            )
            assert response.status_code == 404
            assert "File not found" in response.json()["detail"]

    def test_html_endpoint_returns_html_content(
        self, client, mock_auth, sample_archived_page
    ):
        """Test that .html endpoint returns HTML content with correct content type."""

        # Mock the archival service's read method to return HTML
        def mock_read_content(path_root, extension):
            if extension == "html":
                return "<h1>Test HTML</h1>"
            raise FileNotFoundError()

        with patch(
            "poliloom.archive.read_archived_content", side_effect=mock_read_content
        ):
            response = client.get(
                f"/archived-pages/{sample_archived_page.id}.html", headers=mock_auth
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"
            assert response.text == "<h1>Test HTML</h1>"

    def test_markdown_endpoint_returns_markdown_content(
        self, client, mock_auth, sample_archived_page
    ):
        """Test that .md endpoint returns markdown content with correct content type."""

        # Mock the archival service's read method to return markdown
        def mock_read_content(path_root, extension):
            if extension == "md":
                return "# Test Markdown"
            raise FileNotFoundError()

        with patch(
            "poliloom.archive.read_archived_content", side_effect=mock_read_content
        ):
            response = client.get(
                f"/archived-pages/{sample_archived_page.id}.md", headers=mock_auth
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/markdown; charset=utf-8"
            assert response.text == "# Test Markdown"

    def test_both_formats_for_same_archived_page(
        self, client, mock_auth, sample_archived_page
    ):
        """Test that both .html and .md work for the same archived page."""

        # Mock the archival service to return different content based on extension
        def mock_read_content(path_root, extension):
            if extension == "md":
                return "# Test Markdown"
            elif extension == "html":
                return "<h1>Test HTML</h1>"
            raise FileNotFoundError()

        with patch(
            "poliloom.archive.read_archived_content", side_effect=mock_read_content
        ):
            # Test .html endpoint
            html_response = client.get(
                f"/archived-pages/{sample_archived_page.id}.html", headers=mock_auth
            )
            assert html_response.status_code == 200
            assert html_response.text == "<h1>Test HTML</h1>"

            # Test .md endpoint
            md_response = client.get(
                f"/archived-pages/{sample_archived_page.id}.md", headers=mock_auth
            )
            assert md_response.status_code == 200
            assert md_response.text == "# Test Markdown"
