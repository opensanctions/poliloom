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
        mock_message = Mock()
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
        mock_message.parsed = mock_parsed
        mock_response = Mock()
        mock_response.choices = [Mock(message=mock_message)]
        mock_openai_client.beta.chat.completions.parse.return_value = mock_response

        properties = extract_properties(
            mock_openai_client, "test content", "Test Politician"
        )

        assert properties is not None
        assert len(properties) == 2
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == "1970-01-15"
        assert properties[1].type == PropertyType.DEATH_DATE

    def test_extract_properties_none_parsed(self, mock_openai_client):
        """Test property extraction when LLM returns None."""
        mock_message = Mock()
        mock_message.parsed = None
        mock_response = Mock()
        mock_response.choices = [Mock(message=mock_message)]
        mock_openai_client.beta.chat.completions.parse.return_value = mock_response

        properties = extract_properties(
            mock_openai_client, "test content", "Test Politician"
        )

        assert properties is None

    def test_extract_properties_exception(self, mock_openai_client):
        """Test property extraction handles exceptions."""
        mock_openai_client.beta.chat.completions.parse.side_effect = Exception(
            "API Error"
        )

        properties = extract_properties(
            mock_openai_client, "test content", "Test Politician"
        )

        assert properties is None

    def test_extract_positions_success(
        self, mock_openai_client, db_session, sample_position_data
    ):
        """Test successful position extraction and mapping."""
        # Create position in database
        position = Position(**sample_position_data)
        db_session.add(position)
        db_session.commit()

        # Mock Stage 1: Free-form extraction
        class FreeFormPosition(BaseModel):
            name: str
            start_date: str = None
            end_date: str = None
            proof: str

        class FreeFormPositionResult(BaseModel):
            positions: list

        mock_message1 = Mock()
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
        mock_message1.parsed = mock_parsed1

        # Mock Stage 2: Mapping
        mock_message2 = Mock()
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_position_name = "Mayor"
        mock_message2.parsed = mock_parsed2

        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]
        mock_response2 = Mock()
        mock_response2.choices = [Mock(message=mock_message2)]

        mock_openai_client.beta.chat.completions.parse.side_effect = [
            mock_response1,
            mock_response2,
        ]

        # Mock embedding generation
        with patch(
            "poliloom.enrichment.generate_embedding",
            return_value=[0.1] * 384,
        ):
            positions = extract_positions(
                mock_openai_client, db_session, "test content", "Test Politician"
            )

        assert positions is not None
        assert len(positions) == 1
        assert positions[0].name == "Mayor"
        assert positions[0].start_date == "2020"
        assert positions[0].end_date == "2024"

    def test_extract_positions_no_results(self, mock_openai_client, db_session):
        """Test position extraction with no results."""
        mock_message = Mock()
        mock_parsed = Mock()
        mock_parsed.positions = []
        mock_message.parsed = mock_parsed
        mock_response = Mock()
        mock_response.choices = [Mock(message=mock_message)]
        mock_openai_client.beta.chat.completions.parse.return_value = mock_response

        positions = extract_positions(
            mock_openai_client, db_session, "test content", "Test Politician"
        )

        assert positions == []

    def test_extract_birthplaces_success(
        self, mock_openai_client, db_session, sample_location_data
    ):
        """Test successful birthplace extraction and mapping."""
        # Create location in database
        location = Location(**sample_location_data)
        db_session.add(location)
        db_session.commit()

        # Mock Stage 1: Free-form extraction
        class FreeFormBirthplace(BaseModel):
            location_name: str
            proof: str

        class FreeFormBirthplaceResult(BaseModel):
            birthplaces: list

        mock_message1 = Mock()
        mock_parsed1 = FreeFormBirthplaceResult(
            birthplaces=[
                FreeFormBirthplace(
                    location_name="Springfield, Illinois",
                    proof="born in Springfield, Illinois",
                )
            ]
        )
        mock_message1.parsed = mock_parsed1

        # Mock Stage 2: Mapping
        mock_message2 = Mock()
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_location_name = "Springfield, Illinois"
        mock_message2.parsed = mock_parsed2

        mock_response1 = Mock()
        mock_response1.choices = [Mock(message=mock_message1)]
        mock_response2 = Mock()
        mock_response2.choices = [Mock(message=mock_message2)]

        mock_openai_client.beta.chat.completions.parse.side_effect = [
            mock_response1,
            mock_response2,
        ]

        # Mock embedding generation
        with patch(
            "poliloom.enrichment.generate_embedding",
            return_value=[0.2] * 384,
        ):
            birthplaces = extract_birthplaces(
                mock_openai_client, db_session, "test content", "Test Politician"
            )

        assert birthplaces is not None
        assert len(birthplaces) == 1
        assert birthplaces[0].location_name == "Springfield, Illinois"

    def test_store_extracted_data_properties(
        self,
        db_session,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted properties."""
        # Create entities
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
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
        sample_mayor_of_springfield_position_data,
        sample_archived_page_data,
        sample_country_data,
    ):
        """Test storing extracted positions."""
        # Create entities
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)
        position = Position(**sample_mayor_of_springfield_position_data)

        db_session.add_all([country, politician, archived_page, position])
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
                name="Mayor of Springfield",
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
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
        archived_page = ArchivedPage(**sample_archived_page_data)
        location = Location(**sample_location_data)

        db_session.add_all([country, politician, archived_page, location])
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
            ExtractedBirthplace(
                location_name="Springfield, Illinois", proof="born in Springfield"
            )
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
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
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
                name="Nonexistent Position",
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
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
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
        politician = Politician(name="No Links Politician", wikidata_id="Q999999")
        db_session.add(politician)
        db_session.commit()

        with patch("poliloom.enrichment.OpenAI"):
            result = await enrich_politician_from_wikipedia(politician)

        assert result is False
        assert politician.enriched_at is not None

    @pytest.mark.asyncio
    async def test_enrich_politician_no_english_wikipedia(
        self, db_session, sample_country_data
    ):
        """Test enrichment when politician has no English Wikipedia link."""
        # Create politician with only non-English Wikipedia link
        country = Country(**sample_country_data)
        politician = Politician(name="Test Politician", wikidata_id="Q123456")
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
            result = await enrich_politician_from_wikipedia(politician)

        assert result is False
        assert politician.enriched_at is not None
