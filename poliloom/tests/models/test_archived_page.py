"""Tests for the ArchivedPage model."""

from datetime import datetime, timezone
from unittest.mock import patch
from poliloom.models import (
    ArchivedPage,
    WikidataRelation,
    RelationType,
)
from poliloom import archive


class TestArchivedPage:
    """Test cases for the ArchivedPage model."""

    def test_create_references_json_with_wikipedia_project(
        self, db_session, sample_wikipedia_project
    ):
        """Test that create_references_json includes P854 and P143 for Wikipedia projects."""
        # Create an archived page with a Wikipedia project ID
        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Example",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(archived_page)
        db_session.flush()

        references_json = archived_page.create_references_json()

        # Should include both P854 (reference URL) and P143 (imported from)
        assert len(references_json) == 2

        # First reference should be P854 (reference URL)
        assert references_json[0]["property"]["id"] == "P854"
        assert references_json[0]["value"]["type"] == "value"
        assert (
            references_json[0]["value"]["content"]
            == "https://en.wikipedia.org/wiki/Example"
        )

        # Second reference should be P143 (imported from)
        assert references_json[1]["property"]["id"] == "P143"
        assert references_json[1]["value"]["type"] == "value"
        assert references_json[1]["value"]["content"] == "Q328"

    def test_link_languages_from_project_with_languages(
        self, db_session, sample_wikipedia_project, sample_language
    ):
        """Test linking languages from Wikipedia project's LANGUAGE_OF_WORK relations."""
        # Note: sample_wikipedia_project fixture already creates a LANGUAGE_OF_WORK relation
        # with sample_language, so we don't need to create another relation

        # Create archived page with Wikipedia project
        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Link languages from project
        archived_page.link_languages_from_project(db_session)
        db_session.flush()

        # Verify language was linked
        assert len(archived_page.archived_page_languages) == 1
        assert (
            archived_page.archived_page_languages[0].language_id
            == sample_language.wikidata_id
        )

    def test_link_languages_from_project_without_wikipedia_project(self, db_session):
        """Test that link_languages_from_project does nothing when no wikipedia_project_id."""
        # Create archived page without Wikipedia project
        archived_page = ArchivedPage(
            url="https://example.com/test",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=None,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Try to link languages (should do nothing)
        archived_page.link_languages_from_project(db_session)
        db_session.flush()

        # Verify no languages were linked
        assert len(archived_page.archived_page_languages) == 0

    def test_link_languages_from_project_with_multiple_languages(
        self,
        db_session,
        sample_wikipedia_project,
        sample_language,
        sample_german_language,
    ):
        """Test linking multiple languages from Wikipedia project."""
        # Note: sample_wikipedia_project already has a LANGUAGE_OF_WORK relation with sample_language (Q1860)
        # So we just need to add German language to test multiple languages

        # Add German language relation to the Wikipedia project
        relation = WikidataRelation(
            parent_entity_id=sample_german_language.wikidata_id,
            child_entity_id=sample_wikipedia_project.wikidata_id,
            relation_type=RelationType.LANGUAGE_OF_WORK,
            statement_id="Q328$test-statement-german",
        )
        db_session.add(relation)
        db_session.flush()

        # Create archived page
        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Link languages
        archived_page.link_languages_from_project(db_session)
        db_session.flush()

        # Verify both languages were linked
        assert len(archived_page.archived_page_languages) == 2
        language_ids = {
            link.language_id for link in archived_page.archived_page_languages
        }
        assert sample_language.wikidata_id in language_ids
        assert sample_german_language.wikidata_id in language_ids

    def test_save_archived_files_all_formats(self, db_session):
        """Test saving all three file formats (MHTML, HTML, markdown)."""
        archived_page = ArchivedPage(
            url="https://example.com/test",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        mhtml_content = "MHTML content"
        html_content = "<html>HTML content</html>"
        markdown_content = "# Markdown content"

        with patch.object(archive, "save_archived_content") as mock_save:
            archived_page.save_archived_files(
                mhtml_content, html_content, markdown_content
            )

            # Verify all three formats were saved
            assert mock_save.call_count == 3

            # Check MHTML call
            mock_save.assert_any_call(archived_page.path_root, "mhtml", mhtml_content)

            # Check HTML call
            mock_save.assert_any_call(archived_page.path_root, "html", html_content)

            # Check markdown call
            mock_save.assert_any_call(archived_page.path_root, "md", markdown_content)

    def test_save_archived_files_partial_formats(self, db_session):
        """Test saving only some file formats when others are None."""
        archived_page = ArchivedPage(
            url="https://example.com/test",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        html_content = "<html>HTML content</html>"

        with patch.object(archive, "save_archived_content") as mock_save:
            # Only HTML content provided
            archived_page.save_archived_files(None, html_content, None)

            # Verify only HTML was saved
            assert mock_save.call_count == 1
            mock_save.assert_called_once_with(
                archived_page.path_root, "html", html_content
            )

    def test_save_archived_files_none_formats(self, db_session):
        """Test that save_archived_files handles all None gracefully."""
        archived_page = ArchivedPage(
            url="https://example.com/test",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        with patch.object(archive, "save_archived_content") as mock_save:
            # All None
            archived_page.save_archived_files(None, None, None)

            # Verify nothing was saved
            assert mock_save.call_count == 0

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
