"""Tests for enrichment module functionality."""

import pytest
from unittest.mock import Mock, patch

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
    FreeFormPosition,
    FreeFormPositionResult,
    FreeFormBirthplace,
    FreeFormBirthplaceResult,
)
from poliloom.models import (
    Location,
    Position,
    Property,
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
        # Create position in database
        position = Position.create_with_entity(db_session, "Q30185", "Test Position")
        position.embedding = [0.1] * 384
        db_session.flush()

        # Mock Stage 1: Free-form extraction (using actual model from enrichment)
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

        # Make the mock async with side_effect
        call_count = [0]

        async def mock_parse(*args, **kwargs):
            result = [mock_response1, mock_response2][call_count[0]]
            call_count[0] += 1
            return result

        mock_openai_client.responses.parse = mock_parse

        # No embedding mock needed - locations use pg_trgm fuzzy search
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
        sample_archived_page,
        sample_country,
        sample_politician,
        sample_wikipedia_link,
    ):
        """Test storing extracted properties."""
        # Add citizenship as Property (Wikipedia link already created by fixture)
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        db_session.add(citizenship)
        db_session.flush()

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
        # Add citizenship as Property (Wikipedia link created by sample_wikipedia_link fixture)
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        db_session.add(citizenship)
        db_session.flush()

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
        sample_archived_page,
        sample_country,
        sample_politician,
    ):
        """Test storing extracted birthplaces."""
        # Add citizenship as Property
        citizenship = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        db_session.add(citizenship)
        db_session.flush()

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
        assert birthplace_property.archived_page_id == sample_archived_page.id

    def test_store_extracted_data_error_handling(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
    ):
        """Test error handling in store_extracted_data."""

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
                None,  # citizenships
            )

        assert success is False

    @pytest.mark.asyncio
    async def test_enrich_politician_no_wikipedia_links(
        self, db_session, sample_politician
    ):
        """Test enrichment when no politicians have Wikipedia links."""
        # The sample_politician fixture by default has no Wikipedia links
        # The function should filter these out and return False

        with patch("poliloom.enrichment.AsyncOpenAI"):
            politician_found = await enrich_politician_from_wikipedia()

        # Should find no politicians to enrich since they're filtered out by the query
        assert politician_found is False

        # The enriched_at timestamp should remain None since the politician was never processed
        db_session.refresh(sample_politician)
        assert sample_politician.enriched_at is None


class TestCountPoliticiansWithUnevaluated:
    """Test count_politicians_with_unevaluated function."""

    def test_count_with_unevaluated_properties(
        self, db_session, sample_politician, sample_archived_page
    ):
        """Test counting politicians with unevaluated properties."""
        from poliloom.enrichment import count_politicians_with_unevaluated

        # Add unevaluated property
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
        )
        db_session.add(prop)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session)
        assert count == 1

    def test_count_excludes_evaluated_properties(
        self, db_session, sample_politician, sample_archived_page
    ):
        """Test that count excludes properties with statement_id."""
        from poliloom.enrichment import count_politicians_with_unevaluated

        # Add property with statement_id
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(prop)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session)
        assert count == 0

    def test_count_with_language_filter(
        self, db_session, sample_politician, sample_language
    ):
        """Test counting with language filter."""
        from poliloom.enrichment import count_politicians_with_unevaluated
        from poliloom.models import ArchivedPage

        # Create English archived page
        en_page = ArchivedPage(
            url="https://en.example.com/test", content_hash="en123", iso_639_1="en"
        )
        db_session.add(en_page)
        db_session.flush()

        # Add English property
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=en_page.id,
        )
        db_session.add(prop)
        db_session.flush()

        # Count with English filter
        count = count_politicians_with_unevaluated(db_session, languages=["Q1860"])
        assert count == 1

        # Count with different language filter
        count = count_politicians_with_unevaluated(db_session, languages=["Q188"])
        assert count == 0

    def test_count_with_country_filter(
        self, db_session, sample_politician, sample_country, sample_archived_page
    ):
        """Test counting with country filter."""
        from poliloom.enrichment import count_politicians_with_unevaluated

        # Add citizenship and unevaluated property
        citizenship_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
            archived_page_id=sample_archived_page.id,
        )
        birth_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
        )
        db_session.add_all([citizenship_prop, birth_prop])
        db_session.flush()

        # Count with USA filter
        count = count_politicians_with_unevaluated(db_session, countries=["Q30"])
        assert count == 1

        # Count with different country filter
        count = count_politicians_with_unevaluated(db_session, countries=["Q183"])
        assert count == 0


class TestEnrichUntilTarget:
    """Test enrich_until_target function."""

    def test_enrich_until_target_already_met(
        self, db_session, sample_politician, sample_archived_page
    ):
        """Test when target is already met."""
        from poliloom.enrichment import enrich_until_target

        # Add unevaluated property to meet target
        prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=sample_archived_page.id,
        )
        db_session.add(prop)
        db_session.flush()

        # Target is 1, already met
        enriched_count = enrich_until_target(target_politicians=1)
        assert enriched_count == 0

    def test_enrich_until_target_enriches_one(
        self, db_session, sample_politician, sample_wikipedia_link, sample_archived_page
    ):
        """Test enriching until target is reached."""
        from poliloom.enrichment import enrich_until_target

        # No unevaluated properties initially, target is 1
        # Mock the enrichment process
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:
            # First call: no unevaluated politicians yet, enriches 1
            # After enrichment, add property to satisfy target
            async def mock_enrich_func(languages=None, countries=None):
                # Simulate adding an unevaluated property
                prop = Property(
                    politician_id=sample_politician.id,
                    type=PropertyType.BIRTH_DATE,
                    value="1980-01-01",
                    value_precision=11,
                    archived_page_id=sample_archived_page.id,
                )
                db_session.add(prop)
                db_session.flush()
                return True  # politician_found

            mock_enrich.side_effect = mock_enrich_func

            enriched_count = enrich_until_target(target_politicians=1)

        assert enriched_count == 1

    def test_enrich_until_target_no_more_politicians(self, db_session):
        """Test when no more politicians available to enrich."""
        from poliloom.enrichment import enrich_until_target

        # No politicians in database, target cannot be met
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:
            # Mock returns False indicating no politicians to enrich
            async def mock_enrich_func(languages=None, countries=None):
                return False

            mock_enrich.side_effect = mock_enrich_func

            enriched_count = enrich_until_target(target_politicians=5)

        assert enriched_count == 0

    def test_enrich_until_target_with_filters(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_language,
        sample_wikipedia_link,
        sample_archived_page,
    ):
        """Test enrich_until_target with language and country filters."""
        from poliloom.enrichment import enrich_until_target
        from poliloom.models import ArchivedPage

        # Add citizenship
        citizenship_prop = Property(
            politician_id=sample_politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=sample_country.wikidata_id,
        )
        db_session.add(citizenship_prop)
        db_session.flush()

        # Mock enrichment
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                # Create English archived page
                en_page = ArchivedPage(
                    url="https://en.example.com/test",
                    content_hash="en123",
                    iso_639_1="en",
                )
                db_session.add(en_page)
                db_session.flush()

                # Add property matching filters
                prop = Property(
                    politician_id=sample_politician.id,
                    type=PropertyType.BIRTH_DATE,
                    value="1980-01-01",
                    value_precision=11,
                    archived_page_id=en_page.id,
                )
                db_session.add(prop)
                db_session.flush()
                return True

            mock_enrich.side_effect = mock_enrich_func

            enriched_count = enrich_until_target(
                target_politicians=1, languages=["Q1860"], countries=["Q30"]
            )

        assert enriched_count == 1
        # Verify mock was called with correct filters
        mock_enrich.assert_called_with(languages=["Q1860"], countries=["Q30"])
