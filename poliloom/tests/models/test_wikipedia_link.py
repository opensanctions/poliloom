"""Tests for the WikipediaLink model."""

from poliloom.models import Politician, WikipediaLink
from ..conftest import assert_model_fields


class TestWikipediaLink:
    """Test cases for the WikipediaLink model."""

    def test_wikipedia_link_creation(self, db_session, sample_politician_data):
        """Test basic Wikipedia link creation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create wikipedia link
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/John_Doe",
            language_code="en",
        )
        db_session.add(wikipedia_link)
        db_session.commit()
        db_session.refresh(wikipedia_link)

        assert_model_fields(
            wikipedia_link,
            {
                "politician_id": politician.id,
                "url": "https://en.wikipedia.org/wiki/John_Doe",
                "language_code": "en",
            },
        )


class TestWikipediaLinkRelationships:
    """Test cases for Wikipedia link relationships."""

    def test_multiple_wikipedia_links_per_politician(
        self, db_session, sample_politician_data
    ):
        """Test that politicians can have multiple Wikipedia links."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create wikipedia links
        wiki_link1 = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/John_Doe",
            language_code="en",
        )
        wiki_link2 = WikipediaLink(
            politician_id=politician.id,
            url="https://de.wikipedia.org/wiki/John_Doe",
            language_code="de",
        )
        db_session.add_all([wiki_link1, wiki_link2])
        db_session.commit()

        # Verify relationship
        politician_refreshed = (
            db_session.query(Politician).filter_by(id=politician.id).first()
        )
        assert len(politician_refreshed.wikipedia_links) == 2
