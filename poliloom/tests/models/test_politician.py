"""Tests for the Politician model."""

from poliloom.models import (
    Politician,
    PropertyType,
    Statement,
)
from poliloom.wikidata.date import WikidataDate


def statement_document(
    statement_id: str,
    property_id: str,
    content,
    data_type: str = "time",
    qualifiers: list[dict] | None = None,
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
    return document


def time_content(date_string: str) -> dict:
    return WikidataDate.from_date_string(date_string).to_rest_time_content()


def time_qualifier(property_id: str, date_string: str) -> dict:
    return {
        "property": {"id": property_id, "data_type": "time"},
        "value": {"type": "value", "content": time_content(date_string)},
    }


def add_statement(db_session, politician, document) -> Statement:
    """Insert a cached statement for a politician."""
    statement = Statement(politician_id=politician.id, document=document)
    db_session.add(statement)
    db_session.flush()
    return statement


class TestPoliticianStatements:
    """Statement-based context and lookups."""

    def test_get_statements_by_types_filters_type_and_deletion(
        self, db_session, sample_politician, sample_position
    ):
        birth = add_statement(
            db_session,
            sample_politician,
            statement_document("Q123456$birth-1", "P569", time_content("1970-01-15")),
        )
        deleted = add_statement(
            db_session,
            sample_politician,
            statement_document("Q123456$p39-1", "P39", "Q30185", "wikibase-item"),
        )
        deleted.soft_delete()
        db_session.flush()

        statements = sample_politician.get_statements_by_types(
            [PropertyType.BIRTH_DATE, PropertyType.POSITION]
        )

        assert statements == [birth]

    def test_to_xml_context_renders_statements(
        self,
        db_session,
        sample_politician,
        sample_position,
        sample_location,
        sample_country,
    ):
        politician = sample_politician
        politician.wikidata_entity.labels = {"mul": "Jane Doe"}
        sample_position.wikidata_entity.labels = {"mul": "Prime Minister"}

        add_statement(
            db_session,
            politician,
            statement_document("Q123456$birth-1", "P569", time_content("1970-01-15")),
        )
        add_statement(
            db_session,
            politician,
            statement_document(
                "Q123456$death-1", "P570", time_content("2020"), qualifiers=None
            ),
        )
        add_statement(
            db_session,
            politician,
            statement_document(
                "Q123456$p39-1",
                "P39",
                sample_position.wikidata_id,
                "wikibase-item",
                qualifiers=[
                    time_qualifier("P580", "2020"),
                    time_qualifier("P582", "2024"),
                ],
            ),
        )
        add_statement(
            db_session,
            politician,
            statement_document(
                "Q123456$birthplace-1",
                "P19",
                sample_location.wikidata_id,
                "wikibase-item",
            ),
        )
        add_statement(
            db_session,
            politician,
            statement_document(
                "Q123456$citizenship-1",
                "P27",
                sample_country.wikidata_id,
                "wikibase-item",
            ),
        )
        db_session.flush()

        xml = politician.to_xml_context()

        assert "<name>Jane Doe</name>" in xml
        assert "P569: 1970-01-15" in xml
        assert "P570: 2020" in xml  # precision-aware display
        assert "Prime Minister (2020 - 2024)" in xml  # resolved_label + timeframe
        assert "Test Location" in xml
        assert "United States" in xml

    def test_to_xml_context_focus_filters_sections(
        self, db_session, sample_politician, sample_position
    ):
        add_statement(
            db_session,
            sample_politician,
            statement_document("Q123456$birth-1", "P569", time_content("1970-01-15")),
        )
        add_statement(
            db_session,
            sample_politician,
            statement_document(
                "Q123456$p39-1",
                "P39",
                sample_position.wikidata_id,
                "wikibase-item",
            ),
        )

        xml = sample_politician.to_xml_context(
            focus_property_types=[PropertyType.POSITION]
        )

        assert "existing_wikidata_positions" in xml
        assert "P569" not in xml

    def test_to_xml_context_name_falls_back_to_qid(self, db_session, sample_politician):
        sample_politician.wikidata_entity.labels = {}
        db_session.flush()

        xml = sample_politician.to_xml_context()

        assert "<name>Q123456</name>" in xml


class TestPoliticianQueryBase:
    """Test cases for Politician.query_base method."""

    def test_query_base_returns_non_deleted_politicians(
        self, db_session, sample_politician
    ):
        """Test that query_base returns non-soft-deleted politicians."""
        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == sample_politician.id

    def test_query_base_excludes_soft_deleted_politicians(
        self, db_session, sample_politician
    ):
        """Test that query_base excludes soft-deleted politicians."""
        # Soft-delete the WikidataEntity
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0
