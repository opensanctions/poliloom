"""Tests for BirthplaceExtractionService."""

import pytest
from unittest.mock import Mock, patch

from poliloom.services.birthplace_extraction_service import (
    BirthplaceExtractionService,
    FreeFormBirthplaceExtractionResult,
    FreeFormExtractedBirthplace,
)


class TestBirthplaceExtractionService:
    """Test BirthplaceExtractionService functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.fixture
    def birthplace_extraction_service(self, mock_openai_client):
        """Create BirthplaceExtractionService with mocked OpenAI client."""
        return BirthplaceExtractionService(mock_openai_client)

    def test_extract_and_map_success(
        self,
        birthplace_extraction_service,
        mock_openai_client,
        test_session,
        sample_politician,
        sample_location,
        sample_wikipedia_content,
    ):
        """Test successful birthplace extraction and mapping."""
        # Mock Stage 1: Free-form extraction
        mock_message1 = Mock()
        mock_message1.parsed = FreeFormBirthplaceExtractionResult(
            birthplaces=[
                FreeFormExtractedBirthplace(
                    location_name="Springfield, Illinois",
                    proof="born January 15, 1970 in Springfield, Illinois",
                )
            ]
        )
        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]

        # Mock Stage 2: Mapping
        mock_message2 = Mock()
        mock_message2.parsed = Mock()
        mock_message2.parsed.wikidata_location_name = "Springfield, Illinois"
        mock_response2 = Mock()
        mock_response2.choices = [Mock(message=mock_message2)]

        mock_openai_client.beta.chat.completions.parse.side_effect = [
            mock_response1,
            mock_response2,
        ]

        # Mock embedding generation
        with patch("poliloom.embeddings.generate_embedding", return_value=[0.2] * 384):
            result = birthplace_extraction_service.extract_and_map(
                test_session,
                sample_wikipedia_content,
                "Test Politician",
                "United States",
                sample_politician,
                "birthplaces",
            )

        assert result is not None
        assert len(result) == 1
        assert result[0].location_name == "Springfield, Illinois"
        assert result[0].proof == "born January 15, 1970 in Springfield, Illinois"

    def test_extract_and_map_no_birthplaces(
        self,
        birthplace_extraction_service,
        mock_openai_client,
        test_session,
        sample_politician,
        sample_wikipedia_content,
    ):
        """Test extraction when no birthplaces are found."""
        # Mock Stage 1: Empty result
        mock_message1 = Mock()
        mock_message1.parsed = FreeFormBirthplaceExtractionResult(birthplaces=[])
        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]

        mock_openai_client.beta.chat.completions.parse.return_value = mock_response1

        result = birthplace_extraction_service.extract_and_map(
            test_session,
            sample_wikipedia_content,
            "Test Politician",
            "United States",
            sample_politician,
            "birthplaces",
        )

        assert result == []

    def test_extract_and_map_llm_failure(
        self,
        birthplace_extraction_service,
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

        result = birthplace_extraction_service.extract_and_map(
            test_session,
            sample_wikipedia_content,
            "Test Politician",
            "United States",
            sample_politician,
            "birthplaces",
        )

        assert result is None
