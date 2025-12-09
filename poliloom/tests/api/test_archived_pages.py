"""Tests for archived pages API endpoints."""

from datetime import datetime, timezone
from unittest.mock import patch

from poliloom.models import (
    ArchivedPage,
    Language,
    Politician,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
    RelationType,
)


class TestArchivedPagesAPI:
    """Test archived pages API endpoints with transaction-based tests."""

    def test_archived_page_endpoints_require_auth(self, client):
        """Test that archived pages endpoints require authentication."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        # Test .html endpoint without auth
        response = client.get(f"/archived-pages/{fake_id}.html")
        assert response.status_code == 401

    def test_invalid_uuid_format_rejected(self, client, mock_auth):
        """Test that invalid UUID format is rejected."""
        # Test with invalid UUID (.html)
        response = client.get("/archived-pages/invalid-uuid.html", headers=mock_auth)
        assert response.status_code == 400
        assert "Invalid archived page ID format" in response.json()["detail"]

    def test_nonexistent_archived_page_returns_404(self, client, mock_auth):
        """Test that nonexistent archived page returns 404."""
        fake_id = "12345678-1234-1234-1234-123456789012"

        response = client.get(f"/archived-pages/{fake_id}.html", headers=mock_auth)
        assert response.status_code == 404
        assert "Archived page not found" in response.json()["detail"]

    def test_file_not_found_returns_404(self, client, mock_auth, db_session):
        """Test that missing files return 404 even when database record exists."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
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

        wikipedia_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Mock the archival service's read method to raise FileNotFoundError
        with patch(
            "poliloom.archive.read_archived_content",
            side_effect=FileNotFoundError("File not found"),
        ):
            response = client.get(
                f"/archived-pages/{archived_page.id}.html", headers=mock_auth
            )
            assert response.status_code == 404
            assert "File not found" in response.json()["detail"]

    def test_html_endpoint_returns_html_content(self, client, mock_auth, db_session):
        """Test that .html endpoint returns HTML content with correct content type."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
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

        wikipedia_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Mock the archival service's read method to return HTML
        def mock_read_content(path_root, extension):
            if extension == "html":
                return "<h1>Test HTML</h1>"
            raise FileNotFoundError()

        with patch(
            "poliloom.archive.read_archived_content", side_effect=mock_read_content
        ):
            response = client.get(
                f"/archived-pages/{archived_page.id}.html", headers=mock_auth
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"
            assert response.text == "<h1>Test HTML</h1>"
