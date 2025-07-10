"""Tests for PositionExtractionService."""

import pytest
from unittest.mock import Mock, patch

from poliloom.services.position_extraction_service import (
    PositionExtractionService,
    FreeFormPositionExtractionResult,
    FreeFormExtractedPosition,
)
from poliloom.models import Position, Politician


class TestPositionExtractionService:
    """Test PositionExtractionService functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.fixture
    def position_extraction_service(self, mock_openai_client):
        """Create PositionExtractionService with mocked OpenAI client."""
        return PositionExtractionService(mock_openai_client)

    @pytest.fixture
    def sample_politician(self):
        """Create a sample politician for testing."""
        return Politician(
            name="Test Politician", wikidata_id="Q123456", is_deceased=False
        )

    @pytest.fixture
    def sample_position(self, test_session):
        """Create a sample position with embedding."""
        position = Position(
            name="Mayor",
            wikidata_id="Q30185",
            embedding=[0.1] * 384,  # Mock embedding
        )
        test_session.add(position)
        test_session.commit()
        test_session.refresh(position)
        return position

    @pytest.fixture
    def sample_wikipedia_content(self):
        """Sample Wikipedia content for testing."""
        return """
        Test Politician (born January 15, 1970) is an American politician who served as Mayor of Springfield from 2020 to 2024.
        He previously worked as a city councilman from 2018 to 2020.
        """

    def test_extract_and_map_success(
        self,
        position_extraction_service,
        mock_openai_client,
        test_session,
        sample_politician,
        sample_position,
        sample_wikipedia_content,
    ):
        """Test successful position extraction and mapping."""
        # Mock Stage 1: Free-form extraction
        mock_message1 = Mock()
        mock_message1.parsed = FreeFormPositionExtractionResult(
            positions=[
                FreeFormExtractedPosition(
                    name="Mayor of Springfield",
                    start_date="2020",
                    end_date="2024",
                    proof="served as Mayor of Springfield from 2020 to 2024",
                )
            ]
        )
        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]

        # Mock Stage 2: Mapping
        mock_message2 = Mock()
        mock_message2.parsed = Mock()
        mock_message2.parsed.wikidata_position_name = "Mayor"
        mock_response2 = Mock()
        mock_response2.choices = [Mock(message=mock_message2)]

        mock_openai_client.beta.chat.completions.parse.side_effect = [
            mock_response1,
            mock_response2,
        ]

        # Mock embedding generation
        with patch("poliloom.embeddings.generate_embedding", return_value=[0.1] * 384):
            result = position_extraction_service.extract_and_map(
                test_session,
                sample_wikipedia_content,
                "Test Politician",
                "United States",
                sample_politician,
                "positions",
            )

        assert result is not None
        assert len(result) == 1
        assert result[0].name == "Mayor"
        assert result[0].start_date == "2020"
        assert result[0].end_date == "2024"
        assert result[0].proof == "served as Mayor of Springfield from 2020 to 2024"

    def test_extract_and_map_no_positions(
        self,
        position_extraction_service,
        mock_openai_client,
        test_session,
        sample_politician,
        sample_wikipedia_content,
    ):
        """Test extraction when no positions are found."""
        # Mock Stage 1: Empty result
        mock_message1 = Mock()
        mock_message1.parsed = FreeFormPositionExtractionResult(positions=[])
        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]

        mock_openai_client.beta.chat.completions.parse.return_value = mock_response1

        result = position_extraction_service.extract_and_map(
            test_session,
            sample_wikipedia_content,
            "Test Politician",
            "United States",
            sample_politician,
            "positions",
        )

        assert result == []

    def test_extract_and_map_llm_failure(
        self,
        position_extraction_service,
        mock_openai_client,
        test_session,
        sample_politician,
        sample_wikipedia_content,
    ):
        """Test extraction when LLM fails."""
        # Mock Stage 1: LLM failure
        mock_openai_client.beta.chat.completions.parse.side_effect = Exception(
            "LLM Error"
        )

        result = position_extraction_service.extract_and_map(
            test_session,
            sample_wikipedia_content,
            "Test Politician",
            "United States",
            sample_politician,
            "positions",
        )

        assert result is None
