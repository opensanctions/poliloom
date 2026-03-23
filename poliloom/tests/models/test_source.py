"""Tests for the Source model."""

from datetime import datetime, timezone
from unittest.mock import patch
from poliloom.models import (
    Source,
    SourceStatus,
    WikidataRelation,
    RelationType,
)


class TestSource:
    """Test cases for the Source model."""

    def test_create_references_json_with_wikipedia_project_no_permanent_url(
        self, db_session, sample_wikipedia_project
    ):
        """Test that create_references_json includes P143 and P813 for Wikipedia without permanent_url."""
        # Create a source with a Wikipedia project ID but no permanent_url
        source = Source(
            url="https://en.wikipedia.org/wiki/Example",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
            permanent_url=None,
        )
        db_session.add(source)
        db_session.flush()

        references_json = source.create_references_json()

        # Should include P143 (imported from) and P813 (retrieved) - no URL reference without permanent_url
        assert len(references_json) == 2

        # First reference should be P143 (imported from)
        assert references_json[0]["property"]["id"] == "P143"
        assert references_json[0]["value"]["type"] == "value"
        assert references_json[0]["value"]["content"] == "Q328"

        # Second reference should be P813 (retrieved date)
        assert references_json[1]["property"]["id"] == "P813"
        assert references_json[1]["value"]["type"] == "value"

    def test_link_languages_from_project_with_languages(
        self, db_session, sample_wikipedia_project, sample_language
    ):
        """Test linking languages from Wikipedia project's LANGUAGE_OF_WORK relations."""
        # Note: sample_wikipedia_project fixture already creates a LANGUAGE_OF_WORK relation
        # with sample_language, so we don't need to create another relation

        # Create source with Wikipedia project
        source = Source(
            url="https://en.wikipedia.org/wiki/Test",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(source)
        db_session.flush()

        # Link languages from project
        source.link_languages_from_project(db_session)
        db_session.flush()

        # Verify language was linked
        assert len(source.source_languages) == 1
        assert source.source_languages[0].language_id == sample_language.wikidata_id

    def test_link_languages_from_project_without_wikipedia_project(self, db_session):
        """Test that link_languages_from_project does nothing when no wikipedia_project_id."""
        # Create source without Wikipedia project
        source = Source(
            url="https://example.com/test",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=None,
        )
        db_session.add(source)
        db_session.flush()

        # Try to link languages (should do nothing)
        source.link_languages_from_project(db_session)
        db_session.flush()

        # Verify no languages were linked
        assert len(source.source_languages) == 0

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

        # Create source
        source = Source(
            url="https://en.wikipedia.org/wiki/Test",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(source)
        db_session.flush()

        # Link languages
        source.link_languages_from_project(db_session)
        db_session.flush()

        # Verify both languages were linked
        assert len(source.source_languages) == 2
        language_ids = {link.language_id for link in source.source_languages}
        assert sample_language.wikidata_id in language_ids
        assert sample_german_language.wikidata_id in language_ids

    def test_create_references_json_without_wikipedia_project(self, db_session):
        """Test that create_references_json uses P854 and P813 for non-Wikipedia sources."""
        # Create a source without a Wikipedia project ID
        source = Source(
            url="https://example.com/article",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=None,
        )
        db_session.add(source)
        db_session.flush()

        references_json = source.create_references_json()

        # Should include P854 (reference URL) and P813 (retrieved date) for non-Wikipedia sources
        assert len(references_json) == 2
        assert references_json[0]["property"]["id"] == "P854"
        assert references_json[0]["value"]["type"] == "value"
        assert references_json[0]["value"]["content"] == "https://example.com/article"

        # Second reference should be P813 (retrieved date)
        assert references_json[1]["property"]["id"] == "P813"
        assert references_json[1]["value"]["type"] == "value"

    def test_create_references_json_p813_retrieved_date_format(self, db_session):
        """Test that P813 (retrieved date) is correctly formatted with proper Wikidata time value."""
        # Create a source with a specific fetch timestamp
        fetch_time = datetime(2025, 11, 24, 10, 30, 45, tzinfo=timezone.utc)
        source = Source(
            url="https://example.com/test",
            fetch_timestamp=fetch_time,
            wikipedia_project_id=None,
        )
        db_session.add(source)
        db_session.flush()

        references_json = source.create_references_json()

        # Find P813 reference
        p813_refs = [r for r in references_json if r["property"]["id"] == "P813"]
        assert len(p813_refs) == 1, "Should have exactly one P813 reference"

        p813_ref = p813_refs[0]

        assert p813_ref["value"]["type"] == "value"
        assert "content" in p813_ref["value"]

        time_value = p813_ref["value"]["content"]
        assert time_value["time"] == "+2025-11-24T00:00:00Z"
        assert time_value["precision"] == 11  # Day precision
        assert time_value["timezone"] == 0
        assert time_value["before"] == 0
        assert time_value["after"] == 0
        assert time_value["calendarmodel"] == "http://www.wikidata.org/entity/Q1985727"

    def test_create_references_json_with_permanent_url_uses_p4656(
        self, db_session, sample_wikipedia_project
    ):
        """Test that Wikipedia pages with permanent_url use P4656."""
        # Create a source with permanent_url
        source = Source(
            url="https://en.wikipedia.org/wiki/Example",
            permanent_url="https://en.wikipedia.org/w/index.php?title=Example&oldid=123456",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_project_id=sample_wikipedia_project.wikidata_id,
        )
        db_session.add(source)
        db_session.flush()

        references_json = source.create_references_json()

        # Should have P4656, P143, and P813
        assert len(references_json) == 3

        # First reference should be P4656 (Wikimedia import URL) with permanent_url
        assert references_json[0]["property"]["id"] == "P4656"
        assert references_json[0]["value"]["type"] == "value"
        assert (
            references_json[0]["value"]["content"]
            == "https://en.wikipedia.org/w/index.php?title=Example&oldid=123456"
        )

        # Second reference should be P143 (imported from)
        assert references_json[1]["property"]["id"] == "P143"

        # Third reference should be P813 (retrieved date)
        assert references_json[2]["property"]["id"] == "P813"

    @patch("poliloom.models.source.notify")
    def test_status_change_broadcasts_sse_with_politician_ids(
        self, mock_notify, db_session, sample_politician
    ):
        """Status change broadcasts SourceStatusEvent with linked politician IDs."""
        source = Source(
            url="https://example.com/test",
            fetch_timestamp=datetime.now(timezone.utc),
            status=SourceStatus.PROCESSING,
        )
        db_session.add(source)
        sample_politician.sources.append(source)
        db_session.flush()
        mock_notify.reset_mock()

        source.status = SourceStatus.DONE
        db_session.flush()

        assert mock_notify.call_count == 1
        event = mock_notify.call_args[0][0]
        assert event.politician_ids == [str(sample_politician.id)]
        assert event.source_id == str(source.id)
        assert event.status == "done"

    @patch("poliloom.models.source.notify")
    def test_status_change_broadcasts_multiple_politician_ids(
        self, mock_notify, db_session, sample_politician
    ):
        """Status change includes all linked politician IDs."""
        from poliloom.models import Politician

        second_politician = Politician.create_with_entity(
            db_session, "Q999999", "Second Politician"
        )
        db_session.flush()

        source = Source(
            url="https://example.com/shared",
            fetch_timestamp=datetime.now(timezone.utc),
            status=SourceStatus.PROCESSING,
        )
        db_session.add(source)
        sample_politician.sources.append(source)
        second_politician.sources.append(source)
        db_session.flush()
        mock_notify.reset_mock()

        source.status = SourceStatus.DONE
        db_session.flush()

        assert mock_notify.call_count == 1
        event = mock_notify.call_args[0][0]
        assert set(event.politician_ids) == {
            str(sample_politician.id),
            str(second_politician.id),
        }
        assert event.status == "done"
