"""Tests for enrichment module functionality."""

from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from poliloom.enrichment import (
    enrich_politician_from_wikipedia,
    extract_properties_generic,
    extract_two_stage_generic,
    store_extracted_data,
    count_politicians_with_unevaluated,
    enrich_batch,
    extract_permanent_url,
    fetch_and_archive_page,
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
    ArchivedPage,
    ArchivedPageLanguage,
    Country,
    Language,
    Location,
    Politician,
    Position,
    Property,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
    RelationType,
)


class TestEnrichment:
    """Test enrichment module functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.mark.asyncio
    async def test_extract_dates_success(self, db_session, mock_openai_client):
        """Test successful date extraction."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

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

        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", politician, DATES_CONFIG
        )

        assert properties is not None
        assert len(properties) == 2
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == "1970-01-15"
        assert properties[1].type == PropertyType.DEATH_DATE

    @pytest.mark.asyncio
    async def test_extract_dates_none_parsed(self, db_session, mock_openai_client):
        """Test date extraction when LLM returns None."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        mock_response = Mock()
        mock_response.output_parsed = None

        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_dates_exception(self, db_session, mock_openai_client):
        """Test date extraction handles exceptions."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        async def mock_parse(*args, **kwargs):
            raise Exception("API Error")

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_positions_success(self, db_session, mock_openai_client):
        """Test successful position extraction and mapping."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )

        position = Position.create_with_entity(db_session, "Q30185", "Test Position")
        position.embedding = [0.1] * 384
        db_session.flush()

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
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_position_qid = "Q30185"

        mock_response1 = Mock()
        mock_response1.output_parsed = mock_parsed1
        mock_response2 = Mock()
        mock_response2.output_parsed = mock_parsed2

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
            politician,
            POSITIONS_CONFIG,
        )

        assert positions is not None
        assert len(positions) == 1
        assert positions[0].wikidata_id == "Q30185"
        assert positions[0].start_date == "2020"
        assert positions[0].end_date == "2024"

    @pytest.mark.asyncio
    async def test_extract_positions_no_results(self, db_session, mock_openai_client):
        """Test position extraction with no results."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        mock_parsed = Mock()
        mock_parsed.positions = []
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed

        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        positions = await extract_two_stage_generic(
            mock_openai_client,
            db_session,
            "test content",
            politician,
            POSITIONS_CONFIG,
        )

        assert positions == []

    @pytest.mark.asyncio
    async def test_extract_birthplaces_success(self, db_session, mock_openai_client):
        """Test successful birthplace extraction and mapping."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )

        Location.create_with_entity(
            db_session,
            "Q28513",
            "Springfield, Illinois",
            labels=["Springfield, Illinois", "Springfield"],
        )
        db_session.flush()

        mock_parsed1 = FreeFormBirthplaceResult(
            birthplaces=[
                FreeFormBirthplace(
                    name="Springfield, Illinois",
                    supporting_quotes=["born in Springfield, Illinois"],
                )
            ]
        )
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_location_qid = "Q28513"

        mock_response1 = Mock()
        mock_response1.output_parsed = mock_parsed1
        mock_response2 = Mock()
        mock_response2.output_parsed = mock_parsed2

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
            politician,
            BIRTHPLACES_CONFIG,
        )

        assert birthplaces is not None
        assert len(birthplaces) == 1
        assert birthplaces[0].wikidata_id == "Q28513"

    def test_store_extracted_data_properties(self, db_session):
        """Test storing extracted properties."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)

        # Add citizenship property
        citizenship_prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(citizenship_prop)
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
            politician,
            archived_page,
            properties,
            None,
            None,
            None,
        )

        assert success is True

        property_obj = (
            db_session.query(Property)
            .filter_by(politician_id=politician.id, type=PropertyType.BIRTH_DATE)
            .first()
        )
        assert property_obj is not None
        assert property_obj.value == "+1970-01-15T00:00:00Z"
        assert property_obj.value_precision == 11
        assert property_obj.archived_page_id == archived_page.id

    def test_store_extracted_data_positions(self, db_session):
        """Test storing extracted positions."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)

        # Add citizenship property
        citizenship_prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(citizenship_prop)
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
            politician,
            archived_page,
            None,
            positions,
            None,
            None,
        )

        assert success is True

        position_property = (
            db_session.query(Property)
            .filter_by(
                politician_id=politician.id,
                type=PropertyType.POSITION,
                entity_id=position.wikidata_id,
            )
            .first()
        )
        assert position_property is not None
        assert position_property.qualifiers_json is not None
        assert "P580" in position_property.qualifiers_json
        assert "P582" in position_property.qualifiers_json

    def test_store_extracted_data_birthplaces(self, db_session):
        """Test storing extracted birthplaces."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        location = Location.create_with_entity(db_session, "Q28513", "Springfield")
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)

        # Add citizenship property
        citizenship_prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(citizenship_prop)
        db_session.flush()

        birthplaces = [
            ExtractedBirthplace(
                wikidata_id="Q28513", supporting_quotes=["born in Springfield"]
            )
        ]

        success = store_extracted_data(
            db_session,
            politician,
            archived_page,
            None,
            None,
            birthplaces,
            None,
        )

        assert success is True

        birthplace_property = (
            db_session.query(Property)
            .filter_by(
                politician_id=politician.id,
                type=PropertyType.BIRTHPLACE,
                entity_id=location.wikidata_id,
            )
            .first()
        )
        assert birthplace_property is not None
        assert birthplace_property.archived_page_id == archived_page.id

    def test_store_extracted_data_error_handling(self, db_session):
        """Test error handling in store_extracted_data."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        with patch.object(db_session, "add", side_effect=Exception("Database error")):
            success = store_extracted_data(
                db_session,
                politician,
                archived_page,
                properties,
                None,
                None,
                None,
            )

        assert success is False

    @pytest.mark.asyncio
    async def test_enrich_politician_no_wikipedia_sources(self, db_session):
        """Test enrichment when no politicians have Wikipedia links."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        with patch("poliloom.enrichment.AsyncOpenAI"):
            politician_found = await enrich_politician_from_wikipedia()

        assert politician_found is False

        db_session.refresh(politician)
        assert politician.enriched_at is None


class TestCountPoliticiansWithUnevaluated:
    """Test count_politicians_with_unevaluated function."""

    def test_count_with_unevaluated_properties(self, db_session):
        """Test counting politicians with unevaluated properties."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add property with archived_page (extracted, unevaluated)
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(prop)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session)
        assert count == 1

    def test_count_excludes_evaluated_properties(self, db_session):
        """Test that count excludes properties with statement_id."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add property with statement_id (already in Wikidata)
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(prop)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session)
        assert count == 0

    def test_count_with_language_filter(self, db_session):
        """Test counting with language filter."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        en_page = ArchivedPage(
            url="https://en.example.com/test",
            content_hash="en123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(en_page)
        db_session.flush()

        # Link language to archived page
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=en_page.id,
                language_id=language.wikidata_id,
            )
        )

        # Add property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=en_page.id,
        )
        db_session.add(prop)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session, languages=["Q1860"])
        assert count == 1

        count = count_politicians_with_unevaluated(db_session, languages=["Q188"])
        assert count == 0

    def test_count_with_country_filter(self, db_session):
        """Test counting with country filter."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Add citizenship property
        citizenship_prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(citizenship_prop)

        # Add birth date property
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(birth_prop)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session, countries=["Q30"])
        assert count == 1

        count = count_politicians_with_unevaluated(db_session, countries=["Q183"])
        assert count == 0


class TestEnrichBatch:
    """Test enrich_batch function."""

    def test_enrich_batch_enriches_n_politicians(self, db_session):
        """Test enriching a batch of politicians."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                return True

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "3"}):
                enriched_count = enrich_batch()

        assert enriched_count == 3
        assert mock_enrich.call_count == 3

    def test_enrich_batch_no_more_politicians(self, db_session):
        """Test when no more politicians available to enrich."""
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                return False

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "5"}):
                enriched_count = enrich_batch()

        assert enriched_count == 0
        assert mock_enrich.call_count == 1

    def test_enrich_batch_with_filters(self, db_session):
        """Test enrich_batch with language and country filters."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=ws.id,
        )
        db_session.add(archived_page)

        citizenship_prop = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )
        db_session.add(citizenship_prop)
        db_session.flush()

        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                return True

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "2"}):
                enriched_count = enrich_batch(languages=["Q1860"], countries=["Q30"])

        assert enriched_count == 2
        mock_enrich.assert_called_with(languages=["Q1860"], countries=["Q30"])

    def test_enrich_batch_stops_early_when_no_politicians(self, db_session):
        """Test that batch stops early if politicians run out."""
        call_count = [0]

        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                call_count[0] += 1
                return call_count[0] <= 2

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "5"}):
                enriched_count = enrich_batch()

        assert enriched_count == 2
        assert mock_enrich.call_count == 3


class TestExtractPermanentUrl:
    """Test extract_permanent_url function using t-permalink element."""

    def test_extract_permanent_url_basic(self):
        """Test extracting permanent URL from t-permalink element."""
        html_snippet = """
        <li id="t-permalink" class="mw-list-item">
            <a href="https://en.wikipedia.org/w/index.php?title=Mirjam_Blaak&oldid=1314222018"
               title="Permanent link to this revision of this page">
                <span>Permanent link</span>
            </a>
        </li>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert (
            permanent_url
            == "https://en.wikipedia.org/w/index.php?title=Mirjam_Blaak&oldid=1314222018"
        )

    def test_extract_permanent_url_uses_t_permalink_not_other_links(self):
        """Test that only the t-permalink element is used, not other oldid links."""
        html_snippet = """
        <a href="https://en.wikipedia.org/w/index.php?title=Other_Page&oldid=9999999">Other</a>
        <li id="t-permalink" class="mw-list-item">
            <a href="https://en.wikipedia.org/w/index.php?title=Petra_Butler&oldid=1292404970">Correct</a>
        </li>
        <a href="https://en.wikipedia.org/w/index.php?title=Another_Page&oldid=8888888">Another</a>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert (
            permanent_url
            == "https://en.wikipedia.org/w/index.php?title=Petra_Butler&oldid=1292404970"
        )

    def test_extract_permanent_url_no_t_permalink_returns_none(self):
        """Test that None is returned when no t-permalink element exists."""
        html_snippet = """
        <a href="https://en.wikipedia.org/w/index.php?title=Mirjam_Blaak&oldid=1234567890">Link</a>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert permanent_url is None

    def test_extract_permanent_url_no_anchor_in_t_permalink(self):
        """Test when t-permalink exists but has no anchor tag."""
        html_snippet = """
        <li id="t-permalink" class="mw-list-item">
            <span>Permanent link</span>
        </li>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert permanent_url is None

    def test_extract_permanent_url_with_fragment(self):
        """Test that URL fragments are preserved in permanent URL."""
        html_snippet = """
        <li id="t-permalink" class="mw-list-item">
            <a href="https://en.wikipedia.org/w/index.php?title=2025_shootings&oldid=1321768448#Accused">Link</a>
        </li>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert (
            permanent_url
            == "https://en.wikipedia.org/w/index.php?title=2025_shootings&oldid=1321768448#Accused"
        )


class TestConvertMhtmlToHtml:
    """Test convert_mhtml_to_html function from page_fetcher."""

    def test_convert_mhtml_to_html_success(self):
        """Test successful MHTML to HTML conversion."""
        from poliloom.page_fetcher import convert_mhtml_to_html

        mhtml_content = "MHTML content here"
        expected_html = "<html>Converted content</html>"

        with patch("poliloom.page_fetcher.MHTMLConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.return_value = expected_html
            mock_converter_class.return_value = mock_converter

            result = convert_mhtml_to_html(mhtml_content)

            assert result == expected_html
            mock_converter.convert.assert_called_once_with(mhtml_content)

    def test_convert_mhtml_to_html_none_input(self):
        """Test that None input returns None."""
        from poliloom.page_fetcher import convert_mhtml_to_html

        result = convert_mhtml_to_html(None)
        assert result is None

    def test_convert_mhtml_to_html_conversion_error(self):
        """Test that conversion errors return None."""
        from poliloom.page_fetcher import convert_mhtml_to_html

        mhtml_content = "MHTML content"

        with patch("poliloom.page_fetcher.MHTMLConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.side_effect = Exception("Conversion failed")
            mock_converter_class.return_value = mock_converter

            result = convert_mhtml_to_html(mhtml_content)
            assert result is None


class TestFetchAndArchivePage:
    """Test fetch_and_archive_page function."""

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_success(self, db_session):
        """Test successful page fetch and archive with permanent URL extraction."""
        from poliloom.page_fetcher import FetchedPage

        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        url = "https://en.wikipedia.org/wiki/Test_Page"
        permanent_url = "https://en.wikipedia.org/w/index.php?title=Test_Page&oldid=123"

        mock_fetched = FetchedPage(mhtml="MHTML content", html="<html>Converted</html>")

        async def mock_fetch_page(url):
            return mock_fetched

        with patch("poliloom.enrichment.fetch_page", side_effect=mock_fetch_page):
            with patch("poliloom.enrichment.extract_permanent_url") as mock_extract:
                mock_extract.return_value = permanent_url

                archived_page = await fetch_and_archive_page(
                    url,
                    db_session,
                    wikipedia_source_id=ws.id,
                )

                assert archived_page.url == permanent_url
                assert archived_page.wikipedia_source_id == ws.id
                mock_extract.assert_called_once_with("<html>Converted</html>")

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_without_wikipedia_source(self, db_session):
        """Test fetch and archive without Wikipedia source (campaign source instead)."""
        from poliloom.page_fetcher import FetchedPage

        url = "https://example.com/article"

        mock_fetched = FetchedPage(mhtml="MHTML content", html="<html>Converted</html>")

        async def mock_fetch_page(url):
            return mock_fetched

        with patch("poliloom.enrichment.fetch_page", side_effect=mock_fetch_page):
            with pytest.raises(Exception):
                await fetch_and_archive_page(url, db_session)

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_http_error(self, db_session):
        """Test handling of HTTP error response."""
        from poliloom.page_fetcher import PageFetchError

        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        url = "https://example.com/article"

        async def mock_fetch_page(url):
            raise PageFetchError(f"HTTP 404 for {url}")

        with patch("poliloom.enrichment.fetch_page", side_effect=mock_fetch_page):
            with pytest.raises(PageFetchError, match="HTTP 404"):
                await fetch_and_archive_page(url, db_session, wikipedia_source_id=ws.id)

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_timeout(self, db_session):
        """Test handling of timeout."""
        from poliloom.page_fetcher import PageFetchError

        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wp.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        url = "https://example.com/slow-page"

        async def mock_fetch_page(url):
            raise PageFetchError(f"Timeout after 60000ms: {url}")

        with patch("poliloom.enrichment.fetch_page", side_effect=mock_fetch_page):
            with pytest.raises(PageFetchError, match="Timeout"):
                await fetch_and_archive_page(url, db_session, wikipedia_source_id=ws.id)
