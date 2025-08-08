"""Tests for EnrichmentService core functionality."""

import pytest
from unittest.mock import Mock, patch

from poliloom.services.enrichment_service import (
    EnrichmentService,
    PropertyExtractionResult,
    ExtractedProperty,
    PropertyType,
)
from poliloom.models import (
    Politician,
    Property,
    HoldsPosition,
    WikipediaLink,
    HasCitizenship,
    BornAt,
)
from .conftest import load_json_fixture


class TestEnrichmentService:
    """Test EnrichmentService core functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        return Mock()

    @pytest.fixture
    def enrichment_service(self, mock_openai_client, mock_http_client):
        """Create EnrichmentService with mocked dependencies."""
        with (
            patch("poliloom.services.enrichment_service.OpenAI") as mock_openai,
            patch("poliloom.services.enrichment_service.httpx.Client") as mock_httpx,
        ):
            mock_openai.return_value = mock_openai_client
            mock_httpx.return_value = mock_http_client

            service = EnrichmentService()
            return service

    @pytest.fixture
    def politician_with_source(self, sample_country_data, db_session):
        """Create a politician with Wikipedia source and citizenship."""
        from poliloom.models import Country

        # Create country
        country = Country(**sample_country_data)
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)

        # Create politician
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Add citizenship
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        db_session.add(citizenship)

        # Add Wikipedia link
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(wikipedia_link)
        db_session.commit()
        db_session.refresh(politician)
        return politician

    async def test_enrich_politician_not_found(self, enrichment_service):
        """Test enrichment fails when politician not found."""
        result = await enrichment_service.enrich_politician_from_wikipedia("Q999999")

        assert result is False

    async def test_enrich_politician_no_sources(self, enrichment_service, db_session):
        """Test enrichment fails when politician has no Wikipedia sources."""
        politician = Politician(name="No Sources Politician", wikidata_id="Q123456")
        db_session.add(politician)
        db_session.commit()

        result = await enrichment_service.enrich_politician_from_wikipedia("Q123456")

        assert result is False

    def test_extract_properties_with_llm(
        self, enrichment_service, mock_openai_client, enrichment_wikipedia_content
    ):
        """Test property extraction with LLM."""
        # Load test data from fixture
        enrichment_data = load_json_fixture("enrichment_test_data.json")
        openai_response = enrichment_data["openai_responses"][
            "successful_property_extraction"
        ]

        # Mock OpenAI response
        mock_message = Mock()
        mock_message.parsed = PropertyExtractionResult(
            properties=[
                ExtractedProperty(
                    type=PropertyType.BIRTH_DATE,
                    value=openai_response["properties"][0]["value"],
                    proof="born January 15, 1970",
                )
            ]
        )
        mock_response = Mock()
        mock_response.choices = [Mock(message=mock_message)]
        mock_openai_client.beta.chat.completions.parse.return_value = mock_response

        properties = enrichment_service._extract_properties_with_llm(
            enrichment_wikipedia_content, "Test Politician"
        )

        assert properties is not None
        assert len(properties) == 1
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == openai_response["properties"][0]["value"]

    def test_extract_properties_with_llm_failure(
        self, enrichment_service, mock_openai_client
    ):
        """Test property extraction failure."""
        mock_openai_client.beta.chat.completions.parse.side_effect = Exception(
            "API Error"
        )

        properties = enrichment_service._extract_properties_with_llm(
            "test content", "Test Politician"
        )

        assert properties is None

    def test_find_exact_position_match(
        self, enrichment_service, db_session, sample_mayor_of_springfield_position_data
    ):
        """Test exact position matching."""
        from poliloom.models import Position

        # Create the position using the test session
        position = Position(**sample_mayor_of_springfield_position_data)
        db_session.add(position)
        db_session.commit()

        match = enrichment_service._find_exact_position_match(
            db_session, "Mayor of Springfield"
        )

        assert match is not None
        assert match.name == "Mayor of Springfield"

    def test_find_exact_location_match(
        self, enrichment_service, db_session, sample_location_data
    ):
        """Test exact location matching."""
        from poliloom.models import Location

        # Create the location using the test session
        location = Location(**sample_location_data)
        db_session.add(location)
        db_session.commit()

        match = enrichment_service._find_exact_location_match(
            db_session, "Springfield, Illinois"
        )

        assert match is not None
        assert match.name == "Springfield, Illinois"

    def test_store_extracted_data_properties(
        self,
        enrichment_service,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted properties."""
        from poliloom.models import (
            ArchivedPage,
            Politician,
            Country,
            WikipediaLink,
            HasCitizenship,
        )

        # Create country, politician and archived page directly using data fixtures
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add(country)
        db_session.add(politician)
        db_session.add(archived_page)
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(citizenship)
        db_session.add(wikipedia_link)
        db_session.commit()

        data = {
            "properties": [
                ExtractedProperty(
                    type=PropertyType.BIRTH_DATE,
                    value="1970-01-15",
                    proof="born January 15, 1970",
                )
            ],
            "positions": [],
            "birthplaces": [],
        }

        success = enrichment_service._store_extracted_data(
            db_session, politician, [(archived_page, data)]
        )

        assert success is True

        # Verify property was stored
        property_obj = (
            db_session.query(Property)
            .filter_by(politician_id=politician.id, type=PropertyType.BIRTH_DATE)
            .first()
        )
        assert property_obj is not None
        assert property_obj.value == "1970-01-15"
        assert property_obj.archived_page_id == archived_page.id

    def test_store_extracted_data_positions(
        self,
        enrichment_service,
        db_session,
        sample_mayor_of_springfield_position_data,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted positions."""
        from poliloom.services.position_extraction_service import ExtractedPosition
        from poliloom.models import (
            ArchivedPage,
            Position,
            Politician,
            Country,
            WikipediaLink,
            HasCitizenship,
        )

        # Create all required entities directly using data fixtures
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position(**sample_mayor_of_springfield_position_data)

        db_session.add(country)
        db_session.add(politician)
        db_session.add(archived_page)
        db_session.add(position)
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(citizenship)
        db_session.add(wikipedia_link)
        db_session.commit()

        data = {
            "properties": [],
            "positions": [
                ExtractedPosition(
                    name="Mayor of Springfield",
                    start_date="2020",
                    end_date="2024",
                    proof="served as Mayor",
                )
            ],
            "birthplaces": [],
        }

        success = enrichment_service._store_extracted_data(
            db_session, politician, [(archived_page, data)]
        )

        assert success is True

        # Verify position was stored
        holds_position = (
            db_session.query(HoldsPosition)
            .filter_by(
                politician_id=politician.id,
                position_id=position.id,
            )
            .first()
        )
        assert holds_position is not None
        assert holds_position.start_date == "2020"
        assert holds_position.end_date == "2024"
        assert holds_position.archived_page_id == archived_page.id

    def test_store_extracted_data_birthplaces(
        self,
        enrichment_service,
        db_session,
        sample_location_data,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted birthplaces."""
        from poliloom.services.birthplace_extraction_service import ExtractedBirthplace
        from poliloom.models import (
            ArchivedPage,
            Location,
            Politician,
            Country,
            WikipediaLink,
            HasCitizenship,
        )

        # Create all required entities directly using data fixtures
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)
        location = Location(**sample_location_data)

        db_session.add(country)
        db_session.add(politician)
        db_session.add(archived_page)
        db_session.add(location)
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(citizenship)
        db_session.add(wikipedia_link)
        db_session.commit()

        data = {
            "properties": [],
            "positions": [],
            "birthplaces": [
                ExtractedBirthplace(
                    location_name="Springfield, Illinois", proof="born in Springfield"
                )
            ],
        }

        success = enrichment_service._store_extracted_data(
            db_session, politician, [(archived_page, data)]
        )

        assert success is True

        # Verify birthplace was stored
        born_at = (
            db_session.query(BornAt)
            .filter_by(politician_id=politician.id, location_id=location.id)
            .first()
        )
        assert born_at is not None
        assert born_at.archived_page_id == archived_page.id

    def test_store_extracted_data_skips_nonexistent_position(
        self,
        enrichment_service,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test that storing skips positions that don't exist in database."""
        from poliloom.services.position_extraction_service import ExtractedPosition
        from poliloom.models import (
            ArchivedPage,
            Politician,
            Country,
            WikipediaLink,
            HasCitizenship,
        )

        # Create all required entities directly using data fixtures
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add(country)
        db_session.add(politician)
        db_session.add(archived_page)
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(citizenship)
        db_session.add(wikipedia_link)
        db_session.commit()

        data = {
            "properties": [],
            "positions": [
                ExtractedPosition(
                    name="Nonexistent Position",
                    start_date="2020",
                    end_date="2024",
                    proof="proof text",
                )
            ],
            "birthplaces": [],
        }

        success = enrichment_service._store_extracted_data(
            db_session, politician, [(archived_page, data)]
        )

        assert success is True

        # Verify no position was stored
        holds_positions = (
            db_session.query(HoldsPosition).filter_by(politician_id=politician.id).all()
        )
        assert len(holds_positions) == 0

    def test_store_extracted_data_skips_nonexistent_location(
        self,
        enrichment_service,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test that storing skips locations that don't exist in database."""
        from poliloom.services.birthplace_extraction_service import ExtractedBirthplace
        from poliloom.models import (
            ArchivedPage,
            Politician,
            Country,
            WikipediaLink,
            HasCitizenship,
        )

        # Create all required entities directly using data fixtures
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add(country)
        db_session.add(politician)
        db_session.add(archived_page)
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(citizenship)
        db_session.add(wikipedia_link)
        db_session.commit()

        data = {
            "properties": [],
            "positions": [],
            "birthplaces": [
                ExtractedBirthplace(
                    location_name="Nonexistent Location", proof="proof text"
                )
            ],
        }

        success = enrichment_service._store_extracted_data(
            db_session, politician, [(archived_page, data)]
        )

        assert success is True

        # Verify no birthplace was stored
        born_ats = db_session.query(BornAt).filter_by(politician_id=politician.id).all()
        assert len(born_ats) == 0

    def test_store_extracted_data_error_handling(
        self,
        enrichment_service,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test error handling in store_extracted_data."""
        from poliloom.models import (
            ArchivedPage,
            Politician,
            Country,
            WikipediaLink,
            HasCitizenship,
        )

        # Create all required entities directly using data fixtures
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add(country)
        db_session.add(politician)
        db_session.add(archived_page)
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(politician_id=politician.id, country_id=country.id)
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add(citizenship)
        db_session.add(wikipedia_link)
        db_session.commit()

        # Create invalid data to trigger an error
        data = {
            "properties": [
                ExtractedProperty(
                    type=PropertyType.BIRTH_DATE,
                    value="1970-01-15",
                    proof="born January 15, 1970",
                )
            ],
            "positions": [],
            "birthplaces": [],
        }

        # Mock the session to raise an exception during add
        with patch.object(db_session, "add", side_effect=Exception("Database error")):
            success = enrichment_service._store_extracted_data(
                db_session, politician, [(archived_page, data)]
            )

        assert success is False
