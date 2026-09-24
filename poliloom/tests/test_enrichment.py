"""Tests for enrichment module functionality."""

from unittest.mock import Mock, patch

import pytest
from openai import OpenAIError
from sqlalchemy.exc import SQLAlchemyError

from poliloom.enrichment import (
    BIRTHPLACES_CONFIG,
    DATES_CONFIG,
    POSITIONS_CONFIG,
    ExtractedCitizenship,
    ExtractedPosition,
    ExtractedProperty,
    FreeFormBirthplace,
    FreeFormBirthplaceResult,
    FreeFormPosition,
    FreeFormPositionResult,
    PropertyType,
    extract_properties_generic,
    extract_two_stage_generic,
    store_extracted_data,
)
from poliloom.models import (
    Action,
    ActionKind,
    Location,
    Position,
    Statement,
)
from poliloom.wikidata.date import WikidataDate

from .conftest import create_with_entity, make_terms


class TestEnrichment:
    """Test enrichment module functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.mark.asyncio
    async def test_extract_properties_generic_returns_parsed_dates(
        self, mock_openai_client, sample_politician
    ):
        """extract_properties_generic returns the parsed date properties."""
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
    async def test_extract_properties_generic_returns_none_when_nothing_parsed(
        self, mock_openai_client, sample_politician
    ):
        """extract_properties_generic returns None when the LLM parses nothing."""
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
    async def test_extract_properties_generic_returns_none_on_error(
        self, mock_openai_client, sample_politician
    ):
        """extract_properties_generic returns None when the LLM call raises."""

        # Make the mock async and raise exception
        async def mock_parse(*args, **kwargs):
            raise OpenAIError("API Error")

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_two_stage_generic_maps_positions(
        self, mock_openai_client, db_session, sample_politician
    ):
        """extract_two_stage_generic extracts positions free-form and maps them to QIDs."""
        # Create position in database with labels matching the search query
        create_with_entity(
            Position,
            db_session,
            "Q30185",
            make_terms("Mayor of Springfield", aliases=["Mayor"]),
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
    async def test_extract_two_stage_generic_returns_empty_when_no_positions_extracted(
        self, mock_openai_client, db_session, sample_politician
    ):
        """extract_two_stage_generic returns an empty list when no positions are extracted."""
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
    async def test_extract_two_stage_generic_maps_birthplaces(
        self, mock_openai_client, db_session, sample_politician
    ):
        """extract_two_stage_generic extracts birthplaces free-form and maps them to QIDs."""
        # Create location in database with labels for fuzzy search
        create_with_entity(
            Location,
            db_session,
            "Q28513",
            make_terms("Springfield, Illinois", aliases=["Springfield"]),
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


def time_content(date_string: str) -> dict:
    """REST time content for a YYYY[-MM[-DD]] string."""
    return WikidataDate.from_date_string(date_string).to_rest_time_content()


def rest_statement(
    statement_id: str,
    property_id: str,
    content,
    data_type: str = "time",
    qualifiers: list[dict] | None = None,
    references: list[dict] | None = None,
) -> dict:
    """Build a cached REST statement document."""
    document = {
        "id": statement_id,
        "rank": "normal",
        "property": {"id": property_id, "data_type": data_type},
        "value": {"type": "value", "content": content},
    }
    if qualifiers is not None:
        document["qualifiers"] = qualifiers
    if references is not None:
        document["references"] = references
    return document


def add_statement(db_session, politician, document) -> Statement:
    """Insert a cached statement for a politician."""
    statement = Statement(politician_id=politician.id, document=document)
    db_session.add(statement)
    db_session.flush()
    return statement


class TestStoreExtractedData:
    """store_extracted_data persists decisions as Actions."""

    def test_create_persisted_with_references(
        self, db_session, sample_politician, sample_source
    ):
        """A new date extraction becomes a CREATE_STATEMENT action referencing the source."""
        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        success = store_extracted_data(
            db_session, sample_politician, sample_source, properties, None, None, None
        )

        assert success is True

        actions = db_session.query(Action).all()
        assert len(actions) == 1
        action = actions[0]
        assert action.kind == ActionKind.CREATE_STATEMENT
        assert action.politician_id == sample_politician.id
        assert action.statement_id is None

        statement = action.payload["statement"]
        assert statement["property"] == {"id": "P569"}
        assert statement["value"] == {
            "type": "value",
            "content": time_content("1970-01-15"),
        }
        assert statement["rank"] == "normal"
        assert statement["references"] == [
            {"parts": sample_source.create_references_json()}
        ]

        assert len(action.evidence) == 1
        assert action.evidence[0].source_id == sample_source.id
        assert action.evidence[0].supporting_quotes == ["born January 15, 1970"]

    def test_position_create_carries_timeframe_qualifiers(
        self, db_session, sample_politician, sample_source, sample_position
    ):
        """A position extraction carries its P580/P582 timeframe as REST qualifiers."""
        positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2020",
                end_date="2024",
                supporting_quotes=["served as Mayor"],
            )
        ]

        success = store_extracted_data(
            db_session, sample_politician, sample_source, None, positions, None, None
        )

        assert success is True

        actions = db_session.query(Action).all()
        assert len(actions) == 1
        statement = actions[0].payload["statement"]
        assert statement["property"] == {"id": "P39"}
        assert statement["value"] == {"type": "value", "content": "Q30185"}
        assert statement["qualifiers"] == [
            {
                "property": {"id": "P580"},
                "value": {"type": "value", "content": time_content("2020")},
            },
            {
                "property": {"id": "P582"},
                "value": {"type": "value", "content": time_content("2024")},
            },
        ]

    def test_edit_persisted_against_target(
        self, db_session, sample_politician, sample_source
    ):
        """A more precise date becomes an EDIT_STATEMENT action on the cached statement."""
        statement = add_statement(
            db_session,
            sample_politician,
            rest_statement("Q123456$birth-1", "P569", time_content("1950")),
        )

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1950-05-15",
                supporting_quotes=["born May 15, 1950"],
            )
        ]

        success = store_extracted_data(
            db_session, sample_politician, sample_source, properties, None, None, None
        )

        assert success is True

        actions = db_session.query(Action).all()
        assert len(actions) == 1
        action = actions[0]
        assert action.kind == ActionKind.EDIT_STATEMENT
        assert action.statement_id == statement.id

        old_value = {"type": "value", "content": time_content("1950")}
        new_value = {"type": "value", "content": time_content("1950-05-15")}
        assert action.payload["patch"] == [
            {"op": "test", "path": "/value", "value": old_value},
            {"op": "replace", "path": "/value", "value": new_value},
        ]

        assert len(action.evidence) == 1
        assert action.evidence[0].source_id == sample_source.id

    def test_duplicate_extractions_merge_into_one_action(
        self, db_session, sample_politician, sample_source, sample_country
    ):
        """Duplicate extractions in one run dedup onto one action with merged quotes."""
        citizenships = [
            ExtractedCitizenship(
                wikidata_id=sample_country.wikidata_id,
                supporting_quotes=["is an American politician"],
            ),
            ExtractedCitizenship(
                wikidata_id=sample_country.wikidata_id,
                supporting_quotes=["a United States senator"],
            ),
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_source,
            None,
            None,
            None,
            citizenships,
        )

        assert success is True

        actions = db_session.query(Action).all()
        assert len(actions) == 1

        evidence = actions[0].evidence
        assert len(evidence) == 1
        assert evidence[0].source_id == sample_source.id
        assert set(evidence[0].supporting_quotes) == {
            "is an American politician",
            "a United States senator",
        }

    def test_pending_action_dedup_across_sources(
        self, db_session, sample_politician, sample_source, create_source
    ):
        """The same source-independent decision from a second source dedups onto
        the pending action and attaches the new source as evidence."""
        add_statement(
            db_session,
            sample_politician,
            rest_statement("Q123456$birth-1", "P569", time_content("1950")),
        )
        second_source = create_source(url="https://example.com/other-article")
        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1950-05-15",
                supporting_quotes=["born May 15, 1950"],
            )
        ]

        assert store_extracted_data(
            db_session, sample_politician, sample_source, properties, None, None, None
        )
        assert store_extracted_data(
            db_session,
            sample_politician,
            second_source,
            properties,
            None,
            None,
            None,
        )

        actions = db_session.query(Action).all()
        assert len(actions) == 1

        evidence = actions[0].evidence
        assert {row.source_id for row in evidence} == {
            sample_source.id,
            second_source.id,
        }

    def test_decided_action_is_not_dedup_target(
        self, db_session, sample_politician, sample_source, create_source
    ):
        """Decided actions are immutable: an identical new decision creates a
        new pending action."""
        add_statement(
            db_session,
            sample_politician,
            rest_statement("Q123456$birth-1", "P569", time_content("1950")),
        )
        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1950-05-15",
                supporting_quotes=["born May 15, 1950"],
            )
        ]

        assert store_extracted_data(
            db_session, sample_politician, sample_source, properties, None, None, None
        )
        decided = db_session.query(Action).one()
        decided.is_accepted = True
        db_session.flush()

        second_source = create_source(url="https://example.com/other-article")
        assert store_extracted_data(
            db_session,
            sample_politician,
            second_source,
            properties,
            None,
            None,
            None,
        )

        actions = db_session.query(Action).all()
        assert len(actions) == 2
        pending = [action for action in actions if action.is_accepted is None]
        assert len(pending) == 1
        assert pending[0].evidence[0].source_id == second_source.id

    def test_store_extracted_data_error_handling(
        self,
        db_session,
        sample_source,
        sample_politician,
    ):
        """Database errors during persistence surface as a False return."""

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        # Mock the session to raise an exception during add
        with patch.object(
            db_session, "add", side_effect=SQLAlchemyError("Database error")
        ):
            success = store_extracted_data(
                db_session,
                sample_politician,
                sample_source,
                properties,
                None,
                None,
                None,
            )

        assert success is False
