"""Tests for the ArchivedPage model."""

from datetime import datetime, timezone
from poliloom.models import ArchivedPage


class TestArchivedPage:
    """Test cases for the ArchivedPage model."""

    def test_create_references_json_with_wikipedia_project(
        self, db_session, sample_wikipedia_project
    ):
        """Test that create_references_json uses P143 for Wikipedia projects."""
        # Create an archived page with a Wikipedia project ID
        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Example",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(archived_page)
        db_session.flush()

        references_json = archived_page.create_references_json()

        # Should use P143 (imported from) for Wikipedia projects
        assert len(references_json) == 1
        assert references_json[0]["property"]["id"] == "P143"
        assert references_json[0]["value"]["type"] == "value"
        assert references_json[0]["value"]["content"] == "Q328"

    def test_create_references_json_without_wikipedia_project(self, db_session):
        """Test that create_references_json uses P854 for non-Wikipedia sources."""
        # Create an archived page without a Wikipedia project ID
        archived_page = ArchivedPage(
            url="https://example.com/article",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=None,
        )
        db_session.add(archived_page)
        db_session.flush()

        references_json = archived_page.create_references_json()

        # Should use P854 (reference URL) for non-Wikipedia sources
        assert len(references_json) == 1
        assert references_json[0]["property"]["id"] == "P854"
        assert references_json[0]["value"]["type"] == "value"
        assert references_json[0]["value"]["content"] == "https://example.com/article"
