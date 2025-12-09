"""Tests for the ArchivedPage model."""

from datetime import datetime, timezone
from unittest.mock import patch
from poliloom.models import (
    ArchivedPage,
    Campaign,
    CampaignSource,
    Language,
    Politician,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
    RelationType,
)
from poliloom import archive


class TestArchivedPage:
    """Test cases for the ArchivedPage model."""

    def test_create_references_json_with_wikipedia_source(self, db_session):
        """Test that create_references_json includes P4656, P143, and P813 for Wikipedia sources."""
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
            url="https://en.wikipedia.org/wiki/Example",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Example&oldid=123456",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()
        db_session.refresh(archived_page)

        references_json = archived_page.create_references_json()

        assert len(references_json) == 3

        assert references_json[0]["property"]["id"] == "P4656"
        assert references_json[0]["value"]["type"] == "value"
        assert (
            references_json[0]["value"]["content"]
            == "https://en.wikipedia.org/w/index.php?title=Example&oldid=123456"
        )

        assert references_json[1]["property"]["id"] == "P143"
        assert references_json[1]["value"]["type"] == "value"
        assert references_json[1]["value"]["content"] == "Q328"

        assert references_json[2]["property"]["id"] == "P813"
        assert references_json[2]["value"]["type"] == "value"

    def test_link_languages_from_source_with_languages(self, db_session):
        """Test linking languages from Wikipedia source's project LANGUAGE_OF_WORK relations."""
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

        archived_page.link_languages_from_source(db_session)
        db_session.flush()

        assert len(archived_page.archived_page_languages) == 1
        assert (
            archived_page.archived_page_languages[0].language_id == language.wikidata_id
        )

    def test_link_languages_from_source_campaign_source(self, db_session):
        """Test that link_languages_from_source does nothing for campaign sources."""
        campaign = Campaign(name="Test Campaign")
        db_session.add(campaign)
        db_session.flush()

        campaign_source = CampaignSource(
            campaign_id=campaign.id, url="https://example.com/test"
        )
        db_session.add(campaign_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            campaign_source_id=campaign_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        archived_page.link_languages_from_source(db_session)
        db_session.flush()

        assert len(archived_page.archived_page_languages) == 0

    def test_link_languages_from_source_with_multiple_languages(self, db_session):
        """Test linking multiple languages from Wikipedia project."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        english_language = Language.create_with_entity(db_session, "Q1860", "English")
        english_language.iso_639_1 = "en"
        english_language.iso_639_2 = "eng"
        german_language = Language.create_with_entity(db_session, "Q188", "German")
        german_language.iso_639_1 = "de"
        german_language.iso_639_2 = "deu"
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"

        # Add English language relation
        db_session.add(
            WikidataRelation(
                parent_entity_id=english_language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement-english",
            )
        )

        # Add German language relation to the Wikipedia project
        db_session.add(
            WikidataRelation(
                parent_entity_id=german_language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement-german",
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

        archived_page.link_languages_from_source(db_session)
        db_session.flush()

        assert len(archived_page.archived_page_languages) == 2
        language_ids = {
            link.language_id for link in archived_page.archived_page_languages
        }
        assert english_language.wikidata_id in language_ids
        assert german_language.wikidata_id in language_ids

    def test_save_archived_files_all_formats(self, db_session):
        """Test saving both file formats (MHTML, HTML)."""
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
            url="https://example.com/test",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        mhtml_content = "MHTML content"
        html_content = "<html>HTML content</html>"

        with patch.object(archive, "save_archived_content") as mock_save:
            archived_page.save_archived_files(mhtml_content, html_content)

            assert mock_save.call_count == 2
            mock_save.assert_any_call(archived_page.path_root, "mhtml", mhtml_content)
            mock_save.assert_any_call(archived_page.path_root, "html", html_content)

    def test_save_archived_files_partial_formats(self, db_session):
        """Test saving only some file formats when others are None."""
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
            url="https://example.com/test",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        html_content = "<html>HTML content</html>"

        with patch.object(archive, "save_archived_content") as mock_save:
            archived_page.save_archived_files(None, html_content)

            assert mock_save.call_count == 1
            mock_save.assert_called_once_with(
                archived_page.path_root, "html", html_content
            )

    def test_save_archived_files_none_formats(self, db_session):
        """Test that save_archived_files handles all None gracefully."""
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
            url="https://example.com/test",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        with patch.object(archive, "save_archived_content") as mock_save:
            archived_page.save_archived_files(None, None)

            assert mock_save.call_count == 0

    def test_create_references_json_with_campaign_source(self, db_session):
        """Test that create_references_json uses P854 and P813 for campaign sources."""
        campaign = Campaign(name="Test Campaign")
        db_session.add(campaign)
        db_session.flush()

        campaign_source = CampaignSource(
            campaign_id=campaign.id, url="https://example.com/test"
        )
        db_session.add(campaign_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://example.com/article",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            campaign_source_id=campaign_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        references_json = archived_page.create_references_json()

        assert len(references_json) == 2
        assert references_json[0]["property"]["id"] == "P854"
        assert references_json[0]["value"]["type"] == "value"
        assert references_json[0]["value"]["content"] == "https://example.com/article"

        assert references_json[1]["property"]["id"] == "P813"
        assert references_json[1]["value"]["type"] == "value"

    def test_create_references_json_p813_retrieved_date_format(self, db_session):
        """Test that P813 (retrieved date) is correctly formatted with proper Wikidata time value."""
        fetch_time = datetime(2025, 11, 24, 10, 30, 45, tzinfo=timezone.utc)

        campaign = Campaign(name="Test Campaign")
        db_session.add(campaign)
        db_session.flush()

        campaign_source = CampaignSource(
            campaign_id=campaign.id, url="https://example.com/test"
        )
        db_session.add(campaign_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
            fetch_timestamp=fetch_time,
            campaign_source_id=campaign_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        references_json = archived_page.create_references_json()

        p813_refs = [r for r in references_json if r["property"]["id"] == "P813"]
        assert len(p813_refs) == 1, "Should have exactly one P813 reference"

        p813_ref = p813_refs[0]

        assert p813_ref["value"]["type"] == "value"
        assert "content" in p813_ref["value"]

        time_value = p813_ref["value"]["content"]
        assert time_value["time"] == "+2025-11-24T00:00:00Z"
        assert time_value["precision"] == 11
        assert time_value["timezone"] == 0
        assert time_value["before"] == 0
        assert time_value["after"] == 0
        assert time_value["calendarmodel"] == "http://www.wikidata.org/entity/Q1985727"
