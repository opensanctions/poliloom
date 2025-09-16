"""Tests for enrichment module functionality."""

import pytest
from unittest.mock import Mock, patch
from pydantic import BaseModel

from poliloom.enrichment import (
    enrich_politician_from_wikipedia,
    extract_properties,
    extract_positions,
    extract_birthplaces,
    store_extracted_data,
    ExtractedProperty,
    ExtractedPosition,
    ExtractedBirthplace,
    PropertyType,
)
from poliloom.models import (
    ArchivedPage,
    BornAt,
    Country,
    HasCitizenship,
    HoldsPosition,
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

    @pytest.fixture
    def politician_with_source(self, sample_country_data, db_session):
        """Create a politician with Wikipedia source and citizenship."""
        # Create country
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)

        # Create politician
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Add citizenship
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
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

    def test_extract_properties_success(self, mock_openai_client):
        """Test successful property extraction."""
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

        # Create mock politician
        mock_politician = Mock()
        mock_politician.name = "Test Politician"
        mock_politician.wikidata_id = "Q123456"
        mock_politician.properties = []
        mock_politician.citizenships = []

        properties = extract_properties(
            mock_openai_client, "test content", mock_politician
        )

        assert properties is not None
        assert len(properties) == 2
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == "1970-01-15"
        assert properties[1].type == PropertyType.DEATH_DATE

    def test_extract_properties_none_parsed(self, mock_openai_client):
        """Test property extraction when LLM returns None."""
        mock_response = Mock()
        mock_response.output_parsed = None
        mock_openai_client.responses.parse.return_value = mock_response

        properties = extract_properties(
            mock_openai_client, "test content", "Test Politician"
        )

        assert properties is None

    def test_extract_properties_exception(self, mock_openai_client):
        """Test property extraction handles exceptions."""
        mock_openai_client.responses.parse.side_effect = Exception("API Error")

        properties = extract_properties(
            mock_openai_client, "test content", "Test Politician"
        )

        assert properties is None

    def test_extract_positions_success(self, mock_openai_client, db_session):
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

        # Create mock politician
        mock_politician = Mock()
        mock_politician.name = "Test Politician"
        mock_politician.wikidata_id = "Q123456"
        mock_politician.wikidata_positions = []
        mock_politician.citizenships = []

        # Mock embedding generation
        with patch(
            "poliloom.enrichment.generate_embedding",
            return_value=[0.1] * 384,
        ):
            positions = extract_positions(
                mock_openai_client, db_session, "test content", mock_politician
            )

        assert positions is not None
        assert len(positions) == 1
        assert positions[0].wikidata_id == "Q30185"
        assert positions[0].start_date == "2020"
        assert positions[0].end_date == "2024"

    def test_extract_positions_no_results(self, mock_openai_client, db_session):
        """Test position extraction with no results."""
        mock_parsed = Mock()
        mock_parsed.positions = []
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed
        mock_openai_client.responses.parse.return_value = mock_response

        # Create mock politician
        mock_politician = Mock()
        mock_politician.name = "Test Politician"
        mock_politician.wikidata_id = "Q123456"
        mock_politician.wikidata_positions = []
        mock_politician.citizenships = []

        positions = extract_positions(
            mock_openai_client, db_session, "test content", mock_politician
        )

        assert positions == []

    def test_extract_birthplaces_success(self, mock_openai_client, db_session):
        """Test successful birthplace extraction and mapping."""
        # Create location in database
        Location.create_with_entity(
            db_session, "Q28513", "Test Location", embedding=[0.2] * 384
        )
        db_session.commit()

        # Mock Stage 1: Free-form extraction
        class FreeFormBirthplace(BaseModel):
            location_name: str
            proof: str

        class FreeFormBirthplaceResult(BaseModel):
            birthplaces: list

        mock_parsed1 = FreeFormBirthplaceResult(
            birthplaces=[
                FreeFormBirthplace(
                    location_name="Springfield, Illinois",
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

        # Create mock politician
        mock_politician = Mock()
        mock_politician.name = "Test Politician"
        mock_politician.wikidata_id = "Q123456"
        mock_politician.wikidata_birthplaces = []
        mock_politician.citizenships = []

        # Mock embedding generation
        with patch(
            "poliloom.enrichment.generate_embedding",
            return_value=[0.2] * 384,
        ):
            birthplaces = extract_birthplaces(
                mock_openai_client, db_session, "test content", mock_politician
            )

        assert birthplaces is not None
        assert len(birthplaces) == 1
        assert birthplaces[0].wikidata_id == "Q28513"

    def test_store_extracted_data_properties(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted properties."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
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
            politician,
            archived_page,
            properties,
            None,  # positions
            None,  # birthplaces
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
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted positions."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
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
            politician,
            archived_page,
            None,  # properties
            positions,
            None,  # birthplaces
        )

        assert success is True

        # Verify position was stored
        holds_position = (
            db_session.query(HoldsPosition)
            .filter_by(
                politician_id=politician.id,
                position_id=position.wikidata_id,
            )
            .first()
        )
        assert holds_position is not None
        assert holds_position.start_date == "2020"
        assert holds_position.end_date == "2024"

    def test_store_extracted_data_birthplaces(
        self,
        db_session,
        sample_location_data,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted birthplaces."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        location = Location.create_with_entity(
            db_session, "Q28513", "Test Location", embedding=[0.2] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        birthplaces = [
            ExtractedBirthplace(wikidata_id="Q28513", proof="born in Springfield")
        ]

        success = store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            None,  # positions
            birthplaces,
        )

        assert success is True

        # Verify birthplace was stored
        born_at = (
            db_session.query(BornAt)
            .filter_by(politician_id=politician.id, location_id=location.wikidata_id)
            .first()
        )
        assert born_at is not None
        assert born_at.archived_page_id == archived_page.id

    def test_store_extracted_data_skips_nonexistent_position(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test that storing skips positions that don't exist in database."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
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
            politician,
            archived_page,
            None,  # properties
            positions,
            None,  # birthplaces
        )

        assert success is True

        # Verify no position was stored
        holds_positions = (
            db_session.query(HoldsPosition).filter_by(politician_id=politician.id).all()
        )
        assert len(holds_positions) == 0

    def test_store_extracted_data_error_handling(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test error handling in store_extracted_data."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)

        db_session.add_all([country, politician, archived_page])
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
                politician,
                archived_page,
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
        self, db_session, sample_country_data
    ):
        """Test enrichment when politician has no English Wikipedia link."""
        # Create politician with only non-English Wikipedia link
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.add_all([country, politician])
        db_session.commit()

        # Add non-English Wikipedia link
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://fr.wikipedia.org/wiki/Test_Politician",
            language_code="fr",
        )
        db_session.add(wikipedia_link)
        db_session.commit()

        with patch("poliloom.enrichment.OpenAI"):
            with pytest.raises(ValueError, match="No English Wikipedia source found"):
                await enrich_politician_from_wikipedia(politician)

        # The enriched_at timestamp should still be updated even when raising an error
        assert politician.enriched_at is not None

    def test_store_extracted_data_overlapping_position_timeframes(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test handling of overlapping position timeframes."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Add existing position with timeframe 2010-2015
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2010",
            end_date="2015",
            archived_page_id=None,  # This is from Wikidata
            proof_line=None,
        )
        db_session.add(existing_position)
        db_session.commit()

        # Try to add overlapping position with timeframe 2010-2018 (extends the end date)
        overlapping_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2010",
                end_date="2018",  # Extends beyond existing end date
                proof="served as Mayor from 2010 to 2018",
            )
        ]

        success = store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            overlapping_positions,
            None,  # birthplaces
        )

        assert success is True

        # Should have two separate position records (different end dates = different periods)
        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .all()
        )
        assert len(holds_positions) == 2

        # Verify both periods exist
        end_dates = {p.end_date for p in holds_positions}
        assert "2015" in end_dates  # Original period
        assert "2018" in end_dates  # New period

    def test_store_extracted_data_completely_overlapping_position_timeframes(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test handling of completely overlapping position timeframes (subset)."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Add existing position with timeframe 2010-2018 (longer period)
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2010",
            end_date="2018",
            archived_page_id=None,  # This is from Wikidata
            proof_line=None,
        )
        db_session.add(existing_position)
        db_session.commit()

        # Try to add subset position with timeframe 2012-2015 (within existing period)
        subset_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2012",
                end_date="2015",  # Subset of existing timeframe
                proof="served as Mayor from 2012 to 2015",
            )
        ]

        success = store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            subset_positions,
            None,  # birthplaces
        )

        assert success is True

        # Should have two separate position records (different start dates = different periods)
        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .all()
        )
        assert len(holds_positions) == 2

        # Verify both periods exist
        start_dates = {p.start_date for p in holds_positions}
        assert "2010" in start_dates  # Original period
        assert "2012" in start_dates  # New period

    def test_store_extracted_data_non_overlapping_position_timeframes(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test handling of non-overlapping position timeframes (different periods)."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Add existing position with timeframe 2010-2015
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2010",
            end_date="2015",
            archived_page_id=None,  # This is from Wikidata
            proof_line=None,
        )
        db_session.add(existing_position)
        db_session.commit()

        # Try to add non-overlapping position with timeframe 2020-2024
        non_overlapping_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2020",
                end_date="2024",  # Non-overlapping period
                proof="served as Mayor again from 2020 to 2024",
            )
        ]

        success = store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            non_overlapping_positions,
            None,  # birthplaces
        )

        assert success is True

        # Should have two position records (both periods are valid)
        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .order_by(HoldsPosition.start_date)
            .all()
        )
        assert len(holds_positions) == 2

        # First period should remain unchanged
        first_position = holds_positions[0]
        assert first_position.start_date == "2010"
        assert first_position.end_date == "2015"
        assert first_position.archived_page_id is None  # Wikidata source

        # Second period should be added
        second_position = holds_positions[1]
        assert second_position.start_date == "2020"
        assert second_position.end_date == "2024"
        assert second_position.archived_page_id == archived_page.id  # Extracted source

    def test_store_extracted_data_partial_overlap_scenarios(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test various partial overlap scenarios to understand current behavior."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Test Scenario 1: Small end overlap
        # Existing: 2010-2015, New: 2014-2018 (1-year overlap at end)
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2010",
            end_date="2015",
            archived_page_id=None,
            proof_line=None,
        )
        db_session.add(existing_position)
        db_session.commit()

        overlapping_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2014",
                end_date="2018",
                proof="served as Mayor from 2014 to 2018",
            )
        ]

        store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            overlapping_positions,
            None,  # birthplaces
        )

        # Check result
        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .order_by(HoldsPosition.start_date)
            .all()
        )

        # New behavior: partial overlaps create separate entities
        assert len(holds_positions) == 2, (
            f"Expected 2 separate position records for partial overlap, got {len(holds_positions)}"
        )

        # First period (existing from Wikidata)
        first_position = holds_positions[0]
        assert first_position.start_date == "2010"
        assert first_position.end_date == "2015"
        assert first_position.archived_page_id is None  # Wikidata source

        # Second period (new from extraction)
        second_position = holds_positions[1]
        assert second_position.start_date == "2014"
        assert second_position.end_date == "2018"
        assert second_position.archived_page_id == archived_page.id  # Extracted source

    def test_store_extracted_data_gap_between_periods(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test what should happen when periods have gaps that get filled."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Scenario: Bridging a gap
        # Existing: 2010-2012, New: 2011-2015 (overlaps and extends)
        # This creates a continuous period 2010-2015, but did they really serve continuously?
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2010",
            end_date="2012",
            archived_page_id=None,
            proof_line=None,
        )
        db_session.add(existing_position)
        db_session.commit()

        bridging_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2011",
                end_date="2015",
                proof="served as Mayor from 2011 to 2015",
            )
        ]

        store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            bridging_positions,
            None,  # birthplaces
        )

        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .order_by(HoldsPosition.start_date)
            .all()
        )

        # New behavior: partial overlaps create separate entities
        assert len(holds_positions) == 2, (
            f"Expected 2 separate position records for partial overlap, got {len(holds_positions)}"
        )

        # First period (existing from Wikidata)
        first_position = holds_positions[0]
        assert first_position.start_date == "2010"
        assert first_position.end_date == "2012"
        assert first_position.archived_page_id is None  # Wikidata source

        # Second period (new from extraction)
        second_position = holds_positions[1]
        assert second_position.start_date == "2011"
        assert second_position.end_date == "2015"
        assert second_position.archived_page_id == archived_page.id  # Extracted source

    def test_store_extracted_data_precision_preference(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test that higher precision dates replace lower precision ones."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Start with low precision existing data
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="1962",  # Year only (precision 9)
            end_date="1962",  # Year only (precision 9)
            archived_page_id=None,
            proof_line=None,
        )
        db_session.add(existing_position)
        db_session.commit()

        # Extract higher precision data for same period
        high_precision_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="1962-06-15",  # Full date (precision 11)
                end_date="1962-06-15",  # Full date (precision 11)
                proof="served as Mayor on June 15, 1962",
            )
        ]

        store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            high_precision_positions,
            None,  # birthplaces
        )

        # Should have only one position with the higher precision dates
        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .all()
        )

        assert len(holds_positions) == 1
        position_record = holds_positions[0]
        assert position_record.start_date == "1962-06-15"  # Updated to higher precision
        assert position_record.end_date == "1962-06-15"  # Updated to higher precision
        assert position_record.archived_page_id == archived_page.id  # Source updated

    def test_store_extracted_data_precision_preference_skip_lower(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test that lower precision dates are rejected when higher precision exists."""
        # Create entities
        country = Country.create_with_entity(db_session, "Q30", "United States", "US")
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position.create_with_entity(
            db_session, "Q30185", "Mayor of Springfield", embedding=[0.1] * 384
        )

        db_session.add_all([country, politician, archived_page])
        db_session.commit()

        # Add citizenship and Wikipedia link
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            language_code="en",
        )
        db_session.add_all([citizenship, wikipedia_link])
        db_session.commit()

        # Start with high precision existing data
        existing_position = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="1962-06-15",  # Full date (precision 11)
            end_date="1962-06-15",  # Full date (precision 11)
            archived_page_id=None,
            proof_line="precise date from Wikidata",
        )
        db_session.add(existing_position)
        db_session.commit()

        # Try to extract lower precision data for same period
        low_precision_positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="1962",  # Year only (precision 9)
                end_date="1962",  # Year only (precision 9)
                proof="served as Mayor in 1962",
            )
        ]

        store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,  # properties
            low_precision_positions,
            None,  # birthplaces
        )

        # Should still have only one position with the higher precision dates unchanged
        holds_positions = (
            db_session.query(HoldsPosition)
            .filter_by(politician_id=politician.id, position_id=position.wikidata_id)
            .all()
        )

        assert len(holds_positions) == 1
        position_record = holds_positions[0]
        assert (
            position_record.start_date == "1962-06-15"
        )  # Unchanged (higher precision)
        assert position_record.end_date == "1962-06-15"  # Unchanged (higher precision)
        assert position_record.archived_page_id is None  # Source unchanged
        assert (
            position_record.proof_line == "precise date from Wikidata"
        )  # Proof unchanged
