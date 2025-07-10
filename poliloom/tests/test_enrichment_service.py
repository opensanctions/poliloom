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
    Position,
    HoldsPosition,
    WikipediaLink,
    HasCitizenship,
    Location,
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
    def politician_with_source(self, test_session, sample_country):
        """Create a politician with Wikipedia source and citizenship."""
        politician = Politician(
            name="Test Politician", wikidata_id="Q123456", is_deceased=False
        )

        # Add citizenship
        citizenship = HasCitizenship(country=sample_country)
        politician.citizenships.append(citizenship)

        # Add Wikipedia link
        test_session.add(politician)
        test_session.flush()  # Get politician ID

        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        test_session.add(wikipedia_link)
        test_session.commit()
        test_session.refresh(politician)
        return politician

    @pytest.fixture
    def sample_wikipedia_content(self):
        """Sample Wikipedia article content."""
        enrichment_data = load_json_fixture("enrichment_test_data.json")
        return enrichment_data["wikipedia_content_examples"]["test_politician_article"]

    @pytest.fixture
    def sample_position(self, test_session):
        """Create a sample position with embedding."""
        position = Position(
            name="Mayor of Springfield",
            wikidata_id="Q30185",
            embedding=[0.1] * 384,  # Mock embedding
        )
        test_session.add(position)
        test_session.commit()
        test_session.refresh(position)
        return position

    @pytest.fixture
    def sample_location(self, test_session):
        """Create a sample location with embedding."""
        location = Location(
            name="Springfield, Illinois",
            wikidata_id="Q28513",
            embedding=[0.2] * 384,  # Mock embedding
        )
        test_session.add(location)
        test_session.commit()
        test_session.refresh(location)
        return location

    def test_enrich_politician_not_found(self, enrichment_service, test_session):
        """Test enrichment fails when politician not found."""
        result = enrichment_service.enrich_politician_from_wikipedia("Q999999")

        assert result is False

    def test_enrich_politician_no_sources(self, enrichment_service, test_session):
        """Test enrichment fails when politician has no Wikipedia sources."""
        politician = Politician(
            name="No Sources Politician", wikidata_id="Q123456", is_deceased=False
        )
        test_session.add(politician)
        test_session.commit()

        result = enrichment_service.enrich_politician_from_wikipedia("Q123456")

        assert result is False

    def test_fetch_wikipedia_content_success(
        self, enrichment_service, mock_http_client
    ):
        """Test successful Wikipedia content fetching."""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <div id="mw-content-text">
                <p>First paragraph with content.</p>
                <p>Second paragraph with content.</p>
            </div>
        </html>
        """
        mock_http_client.get.return_value = mock_response

        content = enrichment_service._fetch_wikipedia_content(
            "https://en.wikipedia.org/wiki/Test"
        )

        assert content is not None
        assert "First paragraph with content." in content
        assert "Second paragraph with content." in content
        mock_http_client.get.assert_called_once_with(
            "https://en.wikipedia.org/wiki/Test"
        )

    def test_fetch_wikipedia_content_failure(
        self, enrichment_service, mock_http_client
    ):
        """Test Wikipedia content fetching failure."""
        import httpx

        mock_http_client.get.side_effect = httpx.RequestError("Network error")

        content = enrichment_service._fetch_wikipedia_content(
            "https://en.wikipedia.org/wiki/Test"
        )

        assert content is None

    def test_extract_properties_with_llm(
        self, enrichment_service, mock_openai_client, sample_wikipedia_content
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
                )
            ]
        )
        mock_response = Mock()
        mock_response.choices = [Mock(message=mock_message)]
        mock_openai_client.beta.chat.completions.parse.return_value = mock_response

        properties = enrichment_service._extract_properties_with_llm(
            sample_wikipedia_content, "Test Politician", "United States"
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
            "test content", "Test Politician", "United States"
        )

        assert properties is None

    def test_find_exact_position_match(
        self, enrichment_service, test_session, sample_position
    ):
        """Test exact position matching."""
        match = enrichment_service._find_exact_position_match(
            test_session, "Mayor of Springfield"
        )

        assert match is not None
        assert match.name == "Mayor of Springfield"

    def test_find_exact_location_match(
        self, enrichment_service, test_session, sample_location
    ):
        """Test exact location matching."""
        match = enrichment_service._find_exact_location_match(
            test_session, "Springfield, Illinois"
        )

        assert match is not None
        assert match.name == "Springfield, Illinois"

    def test_store_extracted_data_properties(
        self, enrichment_service, test_session, politician_with_source
    ):
        """Test storing extracted properties."""
        source = politician_with_source.wikipedia_links[0]
        data = {
            "properties": [
                ExtractedProperty(type=PropertyType.BIRTH_DATE, value="1970-01-15")
            ],
            "positions": [],
            "birthplaces": [],
        }

        success = enrichment_service._store_extracted_data(
            test_session, politician_with_source, [(source, data)]
        )

        assert success is True

        # Verify property was stored
        property_obj = (
            test_session.query(Property)
            .filter_by(
                politician_id=politician_with_source.id, type=PropertyType.BIRTH_DATE
            )
            .first()
        )
        assert property_obj is not None
        assert property_obj.value == "1970-01-15"
        assert property_obj.is_extracted is True

    def test_store_extracted_data_positions(
        self, enrichment_service, test_session, politician_with_source, sample_position
    ):
        """Test storing extracted positions."""
        source = politician_with_source.wikipedia_links[0]
        from poliloom.services.position_extraction_service import ExtractedPosition

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
            test_session, politician_with_source, [(source, data)]
        )

        assert success is True

        # Verify position was stored
        holds_position = (
            test_session.query(HoldsPosition)
            .filter_by(
                politician_id=politician_with_source.id, position_id=sample_position.id
            )
            .first()
        )
        assert holds_position is not None
        assert holds_position.start_date == "2020"
        assert holds_position.end_date == "2024"
        assert holds_position.is_extracted is True

    def test_store_extracted_data_birthplaces(
        self, enrichment_service, test_session, politician_with_source, sample_location
    ):
        """Test storing extracted birthplaces."""
        source = politician_with_source.wikipedia_links[0]
        from poliloom.services.birthplace_extraction_service import ExtractedBirthplace

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
            test_session, politician_with_source, [(source, data)]
        )

        assert success is True

        # Verify birthplace was stored
        born_at = (
            test_session.query(BornAt)
            .filter_by(
                politician_id=politician_with_source.id, location_id=sample_location.id
            )
            .first()
        )
        assert born_at is not None
        assert born_at.is_extracted is True

    def test_store_extracted_data_skips_nonexistent_position(
        self, enrichment_service, test_session, politician_with_source
    ):
        """Test that storing skips positions that don't exist in database."""
        source = politician_with_source.wikipedia_links[0]
        from poliloom.services.position_extraction_service import ExtractedPosition

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
            test_session, politician_with_source, [(source, data)]
        )

        assert success is True

        # Verify no position was stored
        holds_positions = (
            test_session.query(HoldsPosition)
            .filter_by(politician_id=politician_with_source.id)
            .all()
        )
        assert len(holds_positions) == 0

    def test_store_extracted_data_skips_nonexistent_location(
        self, enrichment_service, test_session, politician_with_source
    ):
        """Test that storing skips locations that don't exist in database."""
        source = politician_with_source.wikipedia_links[0]
        from poliloom.services.birthplace_extraction_service import ExtractedBirthplace

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
            test_session, politician_with_source, [(source, data)]
        )

        assert success is True

        # Verify no birthplace was stored
        born_ats = (
            test_session.query(BornAt)
            .filter_by(politician_id=politician_with_source.id)
            .all()
        )
        assert len(born_ats) == 0

    def test_store_extracted_data_error_handling(
        self, enrichment_service, test_session, politician_with_source
    ):
        """Test error handling in store_extracted_data."""
        source = politician_with_source.wikipedia_links[0]

        # Create invalid data to trigger an error
        data = {
            "properties": [
                ExtractedProperty(type=PropertyType.BIRTH_DATE, value="1970-01-15")
            ],
            "positions": [],
            "birthplaces": [],
        }

        # Mock the session to raise an exception during add
        with patch.object(test_session, "add", side_effect=Exception("Database error")):
            success = enrichment_service._store_extracted_data(
                test_session, politician_with_source, [(source, data)]
            )

        assert success is False
