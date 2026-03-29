"""Tests for enrichment module functionality."""

import pytest
from unittest.mock import Mock, patch

from poliloom.enrichment import (
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
    FreeFormPosition,
    FreeFormPositionResult,
    FreeFormBirthplace,
    FreeFormBirthplaceResult,
)
from poliloom.models import (
    Location,
    Position,
    Property,
    PropertyReference,
)


class TestEnrichment:
    """Test enrichment module functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.mark.asyncio
    async def test_extract_dates_success(self, mock_openai_client, sample_politician):
        """Test successful date extraction."""
        # Mock OpenAI response
        mock_parsed = Mock()
        mock_parsed.properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            ),
            ExtractedProperty(
                type=PropertyType.DEATH_DATE,
                value="2020-05-20",
                supporting_quotes=["died May 20, 2020"],
            ),
        ]
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed

        # Make the mock async
        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is not None
        assert len(properties) == 2
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == "1970-01-15"
        assert properties[1].type == PropertyType.DEATH_DATE

    @pytest.mark.asyncio
    async def test_extract_dates_none_parsed(
        self, mock_openai_client, sample_politician
    ):
        """Test date extraction when LLM returns None."""
        mock_response = Mock()
        mock_response.output_parsed = None

        # Make the mock async
        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_dates_exception(self, mock_openai_client, sample_politician):
        """Test date extraction handles exceptions."""

        # Make the mock async and raise exception
        async def mock_parse(*args, **kwargs):
            raise Exception("API Error")

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_positions_success(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test successful position extraction and mapping."""
        # Create position in database with labels matching the search query
        Position.create_with_entity(
            db_session,
            "Q30185",
            "Mayor of Springfield",
            labels=["Mayor", "Mayor of Springfield"],
        )
        db_session.flush()

        # Mock Stage 1: Free-form extraction (using actual model from enrichment)
        mock_parsed1 = FreeFormPositionResult(
            positions=[
                FreeFormPosition(
                    name="Mayor of Springfield",
                    start_date="2020",
                    end_date="2024",
                    supporting_quotes=["served as Mayor from 2020 to 2024"],
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

        # Make the mock async with side_effect
        call_count = [0]

        async def mock_parse(*args, **kwargs):
            result = [mock_response1, mock_response2][call_count[0]]
            call_count[0] += 1
            return result

        mock_openai_client.responses.parse = mock_parse

        positions = await extract_two_stage_generic(
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

    @pytest.mark.asyncio
    async def test_extract_positions_no_results(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test position extraction with no results."""
        mock_parsed = Mock()
        mock_parsed.positions = []
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed

        # Make the mock async
        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        positions = await extract_two_stage_generic(
            mock_openai_client,
            db_session,
            "test content",
            sample_politician,
            POSITIONS_CONFIG,
        )

        assert positions == []

    @pytest.mark.asyncio
    async def test_extract_birthplaces_success(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test successful birthplace extraction and mapping."""
        # Create location in database with labels for fuzzy search
        Location.create_with_entity(
            db_session,
            "Q28513",
            "Springfield, Illinois",
            labels=["Springfield, Illinois", "Springfield"],
        )
        db_session.flush()

        # Mock Stage 1: Free-form extraction (using actual model from enrichment)
        mock_parsed1 = FreeFormBirthplaceResult(
            birthplaces=[
                FreeFormBirthplace(
                    name="Springfield, Illinois",
                    supporting_quotes=["born in Springfield, Illinois"],
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

        # Make the mock async with side_effect
        call_count = [0]

        async def mock_parse(*args, **kwargs):
            result = [mock_response1, mock_response2][call_count[0]]
            call_count[0] += 1
            return result

        mock_openai_client.responses.parse = mock_parse

        birthplaces = await extract_two_stage_generic(
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
        sample_source,
        sample_country,
        sample_politician,
        sample_wikipedia_link,
        create_citizenship,
    ):
        """Test storing extracted properties."""
        # Add citizenship as Property (Wikipedia link already created by fixture)
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_source,
            properties,
            None,  # positions
            None,  # birthplaces
            None,  # citizenships
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
        # Verify PropertyReference was created linking to source
        ref = (
            db_session.query(PropertyReference)
            .filter_by(property_id=property_obj.id)
            .first()
        )
        assert ref is not None
        assert ref.source_id == sample_source.id

    def test_store_extracted_data_positions(
        self,
        db_session,
        sample_source,
        sample_country,
        sample_politician,
        sample_position,
        sample_wikipedia_link,
        create_citizenship,
    ):
        """Test storing extracted positions."""
        # Add citizenship as Property (Wikipedia link created by sample_wikipedia_link fixture)
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2020",
                end_date="2024",
                supporting_quotes=["served as Mayor"],
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_source,
            None,  # properties
            positions,
            None,  # birthplaces
            None,  # citizenships
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
        sample_source,
        sample_country,
        sample_politician,
        create_citizenship,
    ):
        """Test storing extracted birthplaces."""
        # Add citizenship as Property
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        birthplaces = [
            ExtractedBirthplace(
                wikidata_id="Q28513", supporting_quotes=["born in Springfield"]
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_source,
            None,  # properties
            None,  # positions
            birthplaces,
            None,  # citizenships
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
        # Verify PropertyReference was created linking to source
        ref = (
            db_session.query(PropertyReference)
            .filter_by(property_id=birthplace_property.id)
            .first()
        )
        assert ref is not None
        assert ref.source_id == sample_source.id

    def test_store_extracted_data_existing_match_adds_reference(
        self,
        db_session,
        sample_source,
        sample_country,
        sample_politician,
        sample_wikipedia_link,
        create_citizenship,
        create_source,
        create_birth_date,
    ):
        """Test that store_extracted_data adds a reference to an existing matching property."""
        create_citizenship(sample_politician, sample_country)

        # Create an existing birth date property from a first source
        existing_prop = create_birth_date(
            sample_politician,
            value="+1970-01-15T00:00:00Z",
            source=sample_source,
            supporting_quotes=["born January 15, 1970"],
        )
        db_session.flush()

        # Create a second source
        second_source = create_source(url="https://example.com/other-article")

        # Extract the same birth date from the second source
        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["He was born on 15 January 1970"],
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            second_source,
            properties,
            None,
            None,
            None,
        )

        assert success is True

        # Should NOT create a new property — still just the one
        all_birth_dates = (
            db_session.query(Property)
            .filter_by(politician_id=sample_politician.id, type=PropertyType.BIRTH_DATE)
            .all()
        )
        assert len(all_birth_dates) == 1
        assert all_birth_dates[0].id == existing_prop.id

        # Should have two references: one from each source
        refs = (
            db_session.query(PropertyReference)
            .filter_by(property_id=existing_prop.id)
            .all()
        )
        assert len(refs) == 2
        source_ids = {ref.source_id for ref in refs}
        assert sample_source.id in source_ids
        assert second_source.id in source_ids

    def test_store_extracted_data_existing_position_adds_reference(
        self,
        db_session,
        sample_source,
        sample_country,
        sample_politician,
        sample_position,
        sample_wikipedia_link,
        create_citizenship,
        create_source,
        create_position,
    ):
        """Test that store_extracted_data adds a reference to an existing matching position."""
        create_citizenship(sample_politician, sample_country)

        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-00-00T00:00:00Z", "precision": 9}
                    }
                }
            ],
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-00-00T00:00:00Z", "precision": 9}
                    }
                }
            ],
        }
        existing_prop = create_position(
            sample_politician,
            sample_position,
            source=sample_source,
            qualifiers_json=qualifiers,
        )
        db_session.flush()

        second_source = create_source(url="https://example.com/other-article")

        positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2020",
                end_date="2024",
                supporting_quotes=["served as Mayor from 2020 to 2024"],
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            second_source,
            None,
            positions,
            None,
            None,
        )

        assert success is True

        # Should NOT create a new property
        all_positions = (
            db_session.query(Property)
            .filter_by(
                politician_id=sample_politician.id,
                type=PropertyType.POSITION,
                entity_id=sample_position.wikidata_id,
            )
            .all()
        )
        assert len(all_positions) == 1

        # Should have two references
        refs = (
            db_session.query(PropertyReference)
            .filter_by(property_id=existing_prop.id)
            .all()
        )
        assert len(refs) == 2

    def test_store_extracted_data_error_handling(
        self,
        db_session,
        sample_source,
        sample_country,
        sample_politician,
    ):
        """Test error handling in store_extracted_data."""

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        # Mock the session to raise an exception during add
        with patch.object(db_session, "add", side_effect=Exception("Database error")):
            success = store_extracted_data(
                db_session,
                sample_politician,
                sample_source,
                properties,
                None,
                None,
                None,  # citizenships
            )

        assert success is False
