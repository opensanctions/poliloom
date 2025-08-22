"""Tests for PositionExtractionService."""

import pytest
from unittest.mock import Mock, patch

from poliloom.models import Politician, Position
from poliloom.services.position_extraction_service import (
    FreeFormExtractedPosition,
    FreeFormPositionExtractionResult,
    PositionExtractionService,
)


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

    def test_extract_and_map_success(
        self,
        position_extraction_service,
        mock_openai_client,
        db_session,
        sample_politician_data,
        sample_position_data,
        sample_wikipedia_content,
    ):
        """Test successful position extraction and mapping."""

        # Create model instances from fixture data
        politician = Politician(**sample_politician_data)
        position = Position(**sample_position_data)
        db_session.add_all([politician, position])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(position)

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
                db_session,
                sample_wikipedia_content,
                "Test Politician",
                politician,
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
        db_session,
        sample_politician_data,
        sample_wikipedia_content,
    ):
        """Test extraction when no positions are found."""

        # Create model instance from fixture data
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Mock Stage 1: Empty result
        mock_message1 = Mock()
        mock_message1.parsed = FreeFormPositionExtractionResult(positions=[])
        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]

        mock_openai_client.beta.chat.completions.parse.return_value = mock_response1

        result = position_extraction_service.extract_and_map(
            db_session,
            sample_wikipedia_content,
            "Test Politician",
            politician,
            "positions",
        )

        assert result == []

    def test_extract_and_map_llm_failure(
        self,
        position_extraction_service,
        mock_openai_client,
        db_session,
        sample_politician_data,
        sample_wikipedia_content,
    ):
        """Test extraction when LLM fails."""

        # Create model instance from fixture data
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Mock Stage 1: LLM failure
        mock_openai_client.beta.chat.completions.parse.side_effect = Exception(
            "LLM Error"
        )

        result = position_extraction_service.extract_and_map(
            db_session,
            sample_wikipedia_content,
            "Test Politician",
            politician,
            "positions",
        )

        assert result is None
