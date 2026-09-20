"""Tests for the Statement model."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import Statement, WikidataEntity


def rest_document(statement_id, property_id, content=None, data_type="wikibase-item"):
    """Build a minimal REST API statement document."""
    value = {"type": "value"}
    if content is not None:
        value["content"] = content
    return {
        "id": statement_id,
        "rank": "normal",
        "property": {"id": property_id, "data_type": data_type},
        "value": value,
    }


@pytest.fixture
def statement_entities(db_session):
    """Create WikidataEntity rows backing generated entity_id foreign keys."""
    entities = [
        WikidataEntity(wikidata_id="Q28513", name="Test Location"),
        WikidataEntity(wikidata_id="Q30", name="United States"),
        WikidataEntity(wikidata_id="Q30185", name="Test Position"),
    ]
    db_session.add_all(entities)
    db_session.flush()
    return entities


class TestStatementGeneratedColumns:
    """Generated columns derive from the stored REST document."""

    @pytest.mark.parametrize(
        ("property_id", "expected_entity_id"),
        [
            ("P19", "Q28513"),  # birthplace
            ("P27", "Q30"),  # citizenship
            ("P39", "Q30185"),  # position
        ],
    )
    def test_entity_properties_generate_entity_id(
        self,
        db_session,
        sample_politician,
        statement_entities,
        property_id,
        expected_entity_id,
    ):
        statement = Statement(
            politician_id=sample_politician.id,
            document=rest_document(
                f"Q42${property_id.lower()}-1", property_id, expected_entity_id
            ),
        )
        db_session.add(statement)
        db_session.flush()
        db_session.refresh(statement)

        assert statement.wikidata_statement_id == f"Q42${property_id.lower()}-1"
        assert statement.property_id == property_id
        assert statement.entity_id == expected_entity_id
        assert statement in sample_politician.statements

    def test_date_property_entity_id_is_null(self, db_session, sample_politician):
        statement = Statement(
            politician_id=sample_politician.id,
            document=rest_document(
                "Q42$birth-1",
                "P569",
                {"time": "+1980-01-01T00:00:00Z", "precision": 11},
                data_type="time",
            ),
        )
        db_session.add(statement)
        db_session.flush()
        db_session.refresh(statement)

        assert statement.wikidata_statement_id == "Q42$birth-1"
        assert statement.property_id == "P569"
        assert statement.entity_id is None


class TestStatementUniqueness:
    """wikidata_statement_id is unique across all statements."""

    def test_duplicate_wikidata_statement_id_rejected(
        self, db_session, sample_politician
    ):
        time_content = {"time": "+1980-01-01T00:00:00Z", "precision": 11}
        db_session.add(
            Statement(
                politician_id=sample_politician.id,
                document=rest_document("Q42$dup-1", "P569", time_content, "time"),
            )
        )
        db_session.flush()
        db_session.add(
            Statement(
                politician_id=sample_politician.id,
                document=rest_document("Q42$dup-1", "P569", time_content, "time"),
            )
        )

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestStatementUpsert:
    """upsert_batch conflicts on wikidata_statement_id and replaces the document."""

    def test_upsert_batch_replaces_document(self, db_session, sample_politician):
        original = rest_document(
            "Q42$birth-1",
            "P569",
            {"time": "+1980-01-01T00:00:00Z", "precision": 11},
            "time",
        )
        Statement.upsert_batch(
            db_session, [{"politician_id": sample_politician.id, "document": original}]
        )
        db_session.flush()

        replaced = rest_document(
            "Q42$birth-1",
            "P569",
            {"time": "+1980-06-01T00:00:00Z", "precision": 9},
            "time",
        )
        Statement.upsert_batch(
            db_session, [{"politician_id": sample_politician.id, "document": replaced}]
        )
        db_session.flush()

        statements = db_session.query(Statement).all()
        assert len(statements) == 1
        assert statements[0].document == replaced
        assert statements[0].property_id == "P569"


class TestStatementEntityForeignKey:
    """entity_id references wikidata_entities.wikidata_id."""

    def test_unknown_entity_rejected(self, db_session, sample_politician):
        statement = Statement(
            politician_id=sample_politician.id,
            document=rest_document("Q42$birthplace-9", "P19", "Q999999"),
        )
        db_session.add(statement)

        with pytest.raises(IntegrityError):
            db_session.flush()
