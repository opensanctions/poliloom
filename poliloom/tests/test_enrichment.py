"""Tests for enrichment module functionality."""

import pytest
from unittest.mock import Mock, patch
from pydantic import BaseModel

from poliloom.enrichment import (
    enrich_politician_from_wikipedia,
    extract_properties_generic,
    extract_two_stage_generic,
    store_extracted_data,
    ExtractedProperty,
    ExtractedPosition,
    ExtractedBirthplace,
    PropertyType,
    DATES_CONFIG,
    POSITIONS_CONFIG,
    BIRTHPLACES_CONFIG,
)
from poliloom.models import (
    Location,
    Position,
    Politician,
    Property,
    WikipediaLink,
)


class TestEnrichment:
    """Test enrichment module functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    def test_extract_dates_success(self, mock_openai_client, sample_politician):
        """Test successful date extraction."""
        # Mock OpenAI response
        mock_parsed = Mock()
        mock_parsed.properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                proof="born January 15, 1970",
            ),
            ExtractedProperty(
                type=PropertyType.DEATH_DATE,
                value="2020-05-20",
                proof="died May 20, 2020",
            ),
        ]
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed
        mock_openai_client.responses.parse.return_value = mock_response

        properties = extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is not None
        assert len(properties) == 2
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == "1970-01-15"
        assert properties[1].type == PropertyType.DEATH_DATE

    def test_extract_dates_none_parsed(self, mock_openai_client, sample_politician):
        """Test date extraction when LLM returns None."""
        mock_response = Mock()
        mock_response.output_parsed = None
        mock_openai_client.responses.parse.return_value = mock_response

        properties = extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    def test_extract_dates_exception(self, mock_openai_client, sample_politician):
        """Test date extraction handles exceptions."""
        mock_openai_client.responses.parse.side_effect = Exception("API Error")

        properties = extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    def test_extract_positions_success(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test successful position extraction and mapping."""
        # Create position in database
        Position.create_with_entity(
            db_session, "Q30185", "Test Position", embedding=[0.1] * 384
        )
        db_session.commit()

        # Mock Stage 1: Free-form extraction
        class FreeFormPosition(BaseModel):
            name: str
            start_date: str = None
            end_date: str = None
            proof: str

        class FreeFormPositionResult(BaseModel):
            positions: list

        mock_parsed1 = FreeFormPositionResult(
            positions=[
                FreeFormPosition(
                    name="Mayor of Springfield",
                    start_date="2020",
                    end_date="2024",
                    proof="served as Mayor from 2020 to 2024",
                )
            ]
        )
        # Mock Stage 2: Mapping
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_position_qid = "Q30185"

        mock_response1 = Mock()
        mock_response1.output_parsed = mock_parsed1
        mock_response2 = Mock()
        mock_response2.output_parsed = mock_parsed2

        mock_openai_client.responses.parse.side_effect = [
            mock_response1,
            mock_response2,
        ]

        # Mock embedding generation
        with patch(
            "poliloom.enrichment.generate_embedding",
            return_value=[0.1] * 384,
        ):
            positions = extract_two_stage_generic(
                mock_openai_client,
                db_session,
                "test content",
                sample_politician,
                POSITIONS_CONFIG,
            )

        assert positions is not None
        assert len(positions) == 1
        assert positions[0].wikidata_id == "Q30185"
        assert positions[0].start_date == "2020"
        assert positions[0].end_date == "2024"

    def test_extract_positions_no_results(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test position extraction with no results."""
        mock_parsed = Mock()
        mock_parsed.positions = []
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed
        mock_openai_client.responses.parse.return_value = mock_response

        positions = extract_two_stage_generic(
            mock_openai_client,
            db_session,
            "test content",
            sample_politician,
            POSITIONS_CONFIG,
        )

        assert positions == []

    def test_extract_birthplaces_success(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test successful birthplace extraction and mapping."""
        # Create location in database
        Location.create_with_entity(
            db_session, "Q28513", "Test Location", embedding=[0.2] * 384
        )
        db_session.commit()

        # Mock Stage 1: Free-form extraction
        class FreeFormBirthplace(BaseModel):
            name: str  # Updated to match actual model
            proof: str

        class FreeFormBirthplaceResult(BaseModel):
            birthplaces: list

        mock_parsed1 = FreeFormBirthplaceResult(
            birthplaces=[
                FreeFormBirthplace(
                    name="Springfield, Illinois",  # Updated field name
                    proof="born in Springfield, Illinois",
                )
            ]
        )
        # Mock Stage 2: Mapping
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_location_qid = "Q28513"

        mock_response1 = Mock()
        mock_response1.output_parsed = mock_parsed1
        mock_response2 = Mock()
        mock_response2.output_parsed = mock_parsed2

        mock_openai_client.responses.parse.side_effect = [
            mock_response1,
            mock_response2,
        ]

        # Mock embedding generation
        with patch(
            "poliloom.enrichment.generate_embedding",
            return_value=[0.2] * 384,
        ):
            birthplaces = extract_two_stage_generic(
                mock_openai_client,
                db_session,
                "test content",
                sample_politician,
                BIRTHPLACES_CONFIG,
            )

        assert birthplaces is not None
        assert len(birthplaces) == 1
        assert birthplaces[0].wikidata_id == "Q28513"

    def test_store_extracted_data_properties(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
        sample_wikipedia_link,
    ):
        """Test storing extracted properties."""
        # Use fixture entities
        db_session.commit()

        # Add citizenship as Property (Wikipedia link already created by fixture)
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        db_session.add(citizenship)
        db_session.commit()

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                proof="born January 15, 1970",
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            properties,
            None,  # positions
            None,  # birthplaces
        )

        assert success is True

        # Verify property was stored
        property_obj = (
            db_session.query(Property)
            .filter_by(politician_id=sample_politician.id, type=PropertyType.BIRTH_DATE)
            .first()
        )
        assert property_obj is not None
        assert property_obj.value == "+1970-01-15T00:00:00Z"
        assert property_obj.value_precision == 11  # Day precision
        assert property_obj.archived_page_id == sample_archived_page.id

    def test_store_extracted_data_positions(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
        sample_position,
        sample_wikipedia_link,
    ):
        """Test storing extracted positions."""
        # Use fixture entities (position needs embedding for this test)
        # Embedding set by sample_position fixture
        db_session.commit()

        db_session.add(sample_archived_page)
        db_session.commit()

        # Add citizenship as Property and Wikipedia link
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        # Wikipedia link created by sample_wikipedia_link fixture
        db_session.add(citizenship)
        db_session.commit()

        positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2020",
                end_date="2024",
                proof="served as Mayor",
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            None,  # properties
            positions,
            None,  # birthplaces
        )

        assert success is True

        # Verify position was stored as Property
        position_property = (
            db_session.query(Property)
            .filter_by(
                politician_id=sample_politician.id,
                type=PropertyType.POSITION,
                entity_id=sample_position.wikidata_id,
            )
            .first()
        )
        assert position_property is not None
        assert position_property.qualifiers_json is not None
        assert "P580" in position_property.qualifiers_json  # start time
        assert "P582" in position_property.qualifiers_json  # end time

    def test_store_extracted_data_birthplaces(
        self,
        db_session,
        sample_location,
        sample_archived_page,
        sample_country,
        sample_politician,
    ):
        """Test storing extracted birthplaces."""
        # Use fixture entities

        db_session.add(sample_archived_page)
        db_session.commit()

        # Add citizenship as Property and Wikipedia link
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        # Wikipedia link created by sample_wikipedia_link fixture
        db_session.add(citizenship)
        db_session.commit()

        birthplaces = [
            ExtractedBirthplace(wikidata_id="Q28513", proof="born in Springfield")
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            None,  # properties
            None,  # positions
            birthplaces,
        )

        assert success is True

        # Verify birthplace was stored as Property
        birthplace_property = (
            db_session.query(Property)
            .filter_by(
                politician_id=sample_politician.id,
                type=PropertyType.BIRTHPLACE,
                entity_id=sample_location.wikidata_id,
            )
            .first()
        )
        assert birthplace_property is not None
        assert birthplace_property.archived_page_id == sample_archived_page.id

    def test_store_extracted_data_skips_nonexistent_position(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
    ):
        """Test that storing skips positions that don't exist in database."""
        # Use fixture entities
        db_session.commit()

        # Add citizenship as Property and Wikipedia link
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        # Wikipedia link created by sample_wikipedia_link fixture
        db_session.add(citizenship)
        db_session.commit()

        positions = [
            ExtractedPosition(
                wikidata_id="Q99999",
                start_date="2020",
                end_date="2024",
                proof="proof text",
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            None,  # properties
            positions,
            None,  # birthplaces
        )

        assert success is True

        # Verify no position was stored
        position_properties = (
            db_session.query(Property)
            .filter_by(politician_id=sample_politician.id, type=PropertyType.POSITION)
            .all()
        )
        assert len(position_properties) == 0

    def test_store_extracted_data_error_handling(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
    ):
        """Test error handling in store_extracted_data."""
        # Use fixture entities
        db_session.commit()

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                proof="born January 15, 1970",
            )
        ]

        # Mock the session to raise an exception during add
        with patch.object(db_session, "add", side_effect=Exception("Database error")):
            success = store_extracted_data(
                db_session,
                sample_politician,
                sample_archived_page,
                properties,
                None,
                None,
            )

        assert success is False

    @pytest.mark.asyncio
    async def test_enrich_politician_no_wikipedia_links(self, db_session):
        """Test enrichment when politician has no Wikipedia links."""
        politician = Politician.create_with_entity(
            db_session, "Q999999", "No Links Politician"
        )
        db_session.commit()

        with patch("poliloom.enrichment.OpenAI"):
            with pytest.raises(ValueError, match="No Wikipedia links found"):
                await enrich_politician_from_wikipedia(politician)

        # The enriched_at timestamp should still be updated even when raising an error
        assert politician.enriched_at is not None

    @pytest.mark.asyncio
    async def test_enrich_politician_no_english_wikipedia(
        self, db_session, sample_country, sample_politician
    ):
        """Test enrichment when politician has no English Wikipedia link."""
        # Use fixture entities

        # Add non-English Wikipedia link
        wikipedia_link = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://fr.wikipedia.org/wiki/Test_Politician",
            iso_code="fr",
        )
        db_session.add(wikipedia_link)
        db_session.commit()

        with patch("poliloom.enrichment.OpenAI"):
            with pytest.raises(ValueError, match="No English Wikipedia source found"):
                await enrich_politician_from_wikipedia(sample_politician)

        # The enriched_at timestamp should still be updated even when raising an error
        assert sample_politician.enriched_at is not None
