"""Tests for applying accepted actions via the Wikibase REST API."""

from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import Mock, patch

import httpx2
import pytest

from poliloom.models import Action, ActionKind, Statement, WikidataEntity
from poliloom.wikidata.execution import (
    USER_AGENT,
    WIKIDATA_API_ROOT,
    apply_action,
)


def entity_statement_document(
    statement_id="Q123456$aaaaaaa1-b2c3-4d5e-6f70-809000000000",
    property_id="P39",
    content="Q30185",
    rank="normal",
):
    """Build a REST statement document for an entity-valued property."""
    return {
        "id": statement_id,
        "rank": rank,
        "property": {"id": property_id, "data_type": "wikibase-item"},
        "value": {"type": "value", "content": content},
    }


def time_statement_document(
    statement_id="Q123456$bbbbbbb1-b2c3-4d5e-6f70-809000000000",
):
    """Build a REST statement document for a time-valued property."""
    return {
        "id": statement_id,
        "rank": "normal",
        "property": {"id": "P569", "data_type": "time"},
        "value": {
            "type": "value",
            "content": {"time": "+1980-01-01T00:00:00Z", "precision": 11},
        },
    }


@contextmanager
def mock_api_response(status_code, body=None):
    """Patch the execution module's HTTP client to return a canned response."""
    with patch("poliloom.wikidata.execution.httpx2.AsyncClient") as mock_client:
        response = Mock()
        response.status_code = status_code
        response.json.return_value = body
        client = mock_client.return_value.__aenter__.return_value
        client.request.return_value = response
        yield client


@pytest.fixture
def position_entity(db_session):
    """Create the WikidataEntity backing generated entity_id foreign keys."""
    db_session.add(WikidataEntity(wikidata_id="Q30185", name="Test Position"))
    db_session.flush()


@pytest.fixture
def create_action(db_session, sample_politician):
    """Factory to create actions with defaults."""

    def _create(kind, payload, statement_id=None):
        action = Action(
            politician_id=sample_politician.id,
            kind=kind,
            payload=payload,
            statement_id=statement_id,
        )
        db_session.add(action)
        db_session.flush()
        return action

    return _create


@pytest.fixture
def target_statement(db_session, sample_politician):
    """Cached statement that an EDIT_STATEMENT action targets."""
    statement = Statement(
        politician_id=sample_politician.id,
        document=time_statement_document(),
    )
    db_session.add(statement)
    db_session.flush()
    return statement


class TestCreateStatement:
    async def test_create_success_caches_response_document(
        self, db_session, sample_politician, position_entity, create_action
    ):
        payload = {"statement": entity_statement_document()}
        action = create_action(ActionKind.CREATE_STATEMENT, payload)
        response_document = entity_statement_document()

        with mock_api_response(201, response_document) as client:
            assert await apply_action(db_session, action, "test_jwt_token") is True

        client.request.assert_called_once_with(
            "POST",
            f"{WIKIDATA_API_ROOT}/entities/items/Q123456/statements",
            json=payload,
            headers={
                "Authorization": "Bearer test_jwt_token",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

        statement = db_session.get(Statement, action.statement_id)
        assert statement.politician_id == sample_politician.id
        assert statement.document == response_document
        assert statement.wikidata_statement_id == response_document["id"]
        assert statement.property_id == "P39"
        assert statement.entity_id == "Q30185"
        assert action.applied_at is not None
        assert action.error is None

    async def test_create_failure_leaves_statement_null(
        self, db_session, sample_politician, position_entity, create_action
    ):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": entity_statement_document()}
        )

        with mock_api_response(
            422, {"error": {"code": "invalid-statement", "message": "Bad value"}}
        ):
            assert await apply_action(db_session, action, "test_jwt_token") is False

        assert action.statement_id is None
        assert action.applied_at is None
        assert "HTTP 422" in action.error
        assert (
            db_session.query(Statement)
            .filter_by(politician_id=sample_politician.id)
            .count()
            == 0
        )


class TestEditStatement:
    async def test_edit_success_replaces_document(
        self, db_session, sample_politician, target_statement, create_action
    ):
        payload = {"patch": [{"op": "replace", "path": "/rank", "value": "preferred"}]}
        action = create_action(
            ActionKind.EDIT_STATEMENT, payload, statement_id=target_statement.id
        )
        edited_document = time_statement_document()
        edited_document["rank"] = "preferred"

        with mock_api_response(200, edited_document) as client:
            assert await apply_action(db_session, action, "test_jwt_token") is True

        client.request.assert_called_once_with(
            "PATCH",
            f"{WIKIDATA_API_ROOT}/statements/{target_statement.wikidata_statement_id}",
            json=payload,
            headers={
                "Authorization": "Bearer test_jwt_token",
                "Content-Type": "application/json-patch+json",
                "User-Agent": USER_AGENT,
            },
        )

        db_session.refresh(target_statement)
        assert target_statement.document == edited_document
        assert action.applied_at is not None
        assert action.error is None

    @pytest.mark.parametrize(
        ("status_code", "error_code", "expected_error_parts"),
        [
            (409, "patch-test-failed", ["HTTP 409", "patch-test-failed"]),
            (409, "patch-target-not-found", ["HTTP 409", "patch-target-not-found"]),
            (422, "patch-result-invalid", ["HTTP 422"]),
            (404, "statement-not-found", ["HTTP 404"]),
        ],
    )
    async def test_failure_records_error_and_keeps_document(
        self,
        db_session,
        target_statement,
        create_action,
        status_code,
        error_code,
        expected_error_parts,
    ):
        original_document = deepcopy(target_statement.document)
        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"patch": [{"op": "test", "path": "/rank", "value": "normal"}]},
            statement_id=target_statement.id,
        )

        with mock_api_response(
            status_code, {"error": {"code": error_code, "message": "Rejected"}}
        ):
            assert await apply_action(db_session, action, "test_jwt_token") is False

        assert action.applied_at is None
        assert action.error is not None
        for part in expected_error_parts:
            assert part in action.error
        db_session.refresh(target_statement)
        assert target_statement.document == original_document

    async def test_network_error_records_error_and_keeps_document(
        self, db_session, target_statement, create_action
    ):
        original_document = deepcopy(target_statement.document)
        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"patch": [{"op": "replace", "path": "/rank", "value": "preferred"}]},
            statement_id=target_statement.id,
        )

        with mock_api_response(200) as client:
            client.request.side_effect = httpx2.RequestError("Connection reset")
            assert await apply_action(db_session, action, "test_jwt_token") is False

        assert action.applied_at is None
        assert "Connection reset" in action.error
        db_session.refresh(target_statement)
        assert target_statement.document == original_document

    async def test_edit_without_target_statement_raises(
        self, db_session, sample_politician, create_action
    ):
        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"patch": [{"op": "replace", "path": "/rank", "value": "preferred"}]},
        )

        with (
            mock_api_response(200),
            pytest.raises(ValueError, match="no target statement"),
        ):
            await apply_action(db_session, action, "test_jwt_token")

        assert action.applied_at is None
        assert action.error is None
