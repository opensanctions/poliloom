"""Tests for applying accepted actions via the Wikibase REST API."""

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import Mock, patch

import httpx2
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from poliloom.models import (
    Action,
    ActionKind,
    Politician,
    Statement,
    WikidataEntity,
)
from poliloom.payloads import (
    append_qualifier_patch,
    refine_qualifier_patch,
    refine_value_patch,
    statement_fact_guards,
)
from poliloom.wikidata.execution import (
    USER_AGENT,
    WIKIDATA_API_ROOT,
    apply_action_group,
)

from .conftest import create_with_entity, make_terms


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
        "qualifiers": [],
        "references": [],
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
        "qualifiers": [],
        "references": [],
    }


def url_reference(url):
    return {
        "parts": [
            {"property": {"id": "P854"}, "value": {"type": "value", "content": url}}
        ]
    }


def cite(reference):
    return {"op": "add", "path": "/references/-", "value": reference}


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
    db_session.add(WikidataEntity(wikidata_id="Q30185"))
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
        payload = {"statement": {**entity_statement_document(), "references": []}}
        action = create_action(ActionKind.CREATE_STATEMENT, payload)
        response_document = entity_statement_document()

        with mock_api_response(201, response_document) as client:
            assert (
                await apply_action_group(db_session, [action], "test_jwt_token") is True
            )

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

    async def test_equivalent_creates_share_one_post_with_distinct_source_references(
        self,
        db_session,
        position_entity,
        create_action,
    ):
        first_reference = url_reference("https://example.com/first")
        second_reference = url_reference("https://example.com/second")
        duplicate = {
            "parts": [
                *first_reference["parts"],
                {
                    "property": {"id": "P813"},
                    "value": {
                        "type": "value",
                        "content": {"time": "+2024-01-01T00:00:00Z", "precision": 11},
                    },
                },
            ]
        }
        first_payload = {
            "statement": {
                **entity_statement_document(),
                "references": [first_reference],
            }
        }
        second_payload = {
            "statement": {
                **entity_statement_document(),
                "references": [duplicate, second_reference],
            }
        }
        first = create_action(ActionKind.CREATE_STATEMENT, first_payload)
        second = create_action(ActionKind.CREATE_STATEMENT, second_payload)

        with mock_api_response(201, entity_statement_document()) as client:
            assert (
                await apply_action_group(db_session, [first, second], "test_jwt_token")
                is True
            )

        expected_payload = {
            "statement": {
                **entity_statement_document(),
                "references": [first_reference, second_reference],
            }
        }
        client.request.assert_called_once_with(
            "POST",
            f"{WIKIDATA_API_ROOT}/entities/items/Q123456/statements",
            json=expected_payload,
            headers={
                "Authorization": "Bearer test_jwt_token",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        assert first.payload == first_payload
        assert second.payload == second_payload
        assert first.statement_id == second.statement_id
        assert first.applied_at is not None
        assert second.applied_at == first.applied_at

    async def test_concurrent_creates_write_one_statement_with_only_approved_references(
        self, setup_test_database
    ):
        engine = setup_test_database
        qid = "Q987654"
        first_reference = url_reference("https://example.com/first")
        second_reference = url_reference("https://example.com/second")
        pending_reference = url_reference("https://example.com/pending")
        created = time_statement_document(f"{qid}$created")
        proposal = {
            "rank": created["rank"],
            "property": {"id": "P569"},
            "value": created["value"],
            "qualifiers": [],
        }

        with Session(engine) as seed:
            politician = create_with_entity(Politician, seed, qid, make_terms())
            seed.flush()
            politician_id = politician.id
            actions = [
                Action(
                    politician_id=politician_id,
                    kind=ActionKind.CREATE_STATEMENT,
                    payload={"statement": {**proposal, "references": [reference]}},
                    is_accepted=accepted,
                )
                for reference, accepted in (
                    (first_reference, True),
                    (second_reference, True),
                    (pending_reference, None),
                )
            ]
            seed.add_all(actions)
            seed.flush()
            first_id, second_id, pending_id = [action.id for action in actions]
            seed.commit()

        created["references"] = [first_reference]
        updated = {**created, "references": [first_reference, second_reference]}
        entered_post = asyncio.Event()
        release_post = asyncio.Event()

        async def respond(method, url, *, json, headers):
            if headers["Authorization"] == "Bearer first":
                entered_post.set()
                await release_post.wait()
                return Mock(status_code=201, json=Mock(return_value=created))
            return Mock(status_code=200, json=Mock(return_value=updated))

        try:
            with (
                Session(engine) as first,
                Session(engine) as second,
                mock_api_response(201) as client,
            ):
                client.request.side_effect = respond
                async with asyncio.TaskGroup() as tasks:
                    first_write = tasks.create_task(
                        apply_action_group(
                            first, [first.get(Action, first_id)], "first"
                        )
                    )
                    await asyncio.wait_for(entered_post.wait(), timeout=5)
                    second_write = tasks.create_task(
                        apply_action_group(
                            second, [second.get(Action, second_id)], "second"
                        )
                    )
                    await asyncio.sleep(0)
                    assert client.request.await_count == 1
                    release_post.set()

                assert first_write.result() and second_write.result()
                post, edit = client.request.await_args_list
                assert post.args == (
                    "POST",
                    f"{WIKIDATA_API_ROOT}/entities/items/{qid}/statements",
                )
                assert post.kwargs["json"] == {
                    "statement": {**proposal, "references": [first_reference]}
                }
                assert edit.args == (
                    "PATCH",
                    f"{WIKIDATA_API_ROOT}/statements/{qid}$created",
                )
                assert edit.kwargs["json"] == {
                    "patch": [
                        {"op": "test", "path": "/value", "value": created["value"]},
                        {"op": "test", "path": "/qualifiers", "value": []},
                        {
                            "op": "test",
                            "path": "/references",
                            "value": [first_reference],
                        },
                        cite(second_reference),
                    ]
                }
                statement = second.scalars(
                    select(Statement).where(Statement.politician_id == politician_id)
                ).one()
                assert statement.document == updated
                assert first.get(Action, first_id).statement_id == statement.id
                assert second.get(Action, second_id).statement_id == statement.id
                assert second.get(Action, pending_id).is_accepted is None
        finally:
            with Session(engine) as cleanup:
                cleanup.execute(
                    delete(WikidataEntity).where(WikidataEntity.wikidata_id == qid)
                )
                cleanup.commit()

    async def test_create_failure_leaves_statement_null(
        self, db_session, sample_politician, position_entity, create_action
    ):
        action = create_action(
            ActionKind.CREATE_STATEMENT,
            {"statement": {**entity_statement_document(), "references": []}},
        )

        with mock_api_response(
            422, {"error": {"code": "invalid-statement", "message": "Bad value"}}
        ):
            assert (
                await apply_action_group(db_session, [action], "test_jwt_token")
                is False
            )

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
            assert (
                await apply_action_group(db_session, [action], "test_jwt_token") is True
            )

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

    async def test_equivalent_edits_share_one_patch_with_only_missing_references(
        self,
        db_session,
        target_statement,
        create_action,
    ):
        cited_reference = url_reference("https://example.com/cited")
        new_reference = url_reference("https://example.com/new")
        data_operations = [
            {"op": "test", "path": "/rank", "value": "normal"},
            {"op": "replace", "path": "/rank", "value": "preferred"},
        ]
        first_payload = {
            "patch": [*data_operations, cite(cited_reference), cite(new_reference)]
        }
        second_payload = {"patch": [*data_operations, cite(new_reference)]}
        first = create_action(
            ActionKind.EDIT_STATEMENT, first_payload, target_statement.id
        )
        second = create_action(
            ActionKind.EDIT_STATEMENT, second_payload, target_statement.id
        )
        # The citation appeared after the proposals and has a server-provided hash.
        existing_references = [{**cited_reference, "hash": "1" * 40}]
        target_statement.document = {
            **target_statement.document,
            "references": existing_references,
        }
        edited_document = {
            **target_statement.document,
            "rank": "preferred",
            "references": [
                *existing_references,
                new_reference,
            ],
        }

        with mock_api_response(200, edited_document) as client:
            assert (
                await apply_action_group(db_session, [first, second], "test_jwt_token")
                is True
            )

        client.request.assert_called_once_with(
            "PATCH",
            f"{WIKIDATA_API_ROOT}/statements/{target_statement.wikidata_statement_id}",
            json={
                "patch": [
                    *data_operations,
                    {"op": "test", "path": "/references", "value": existing_references},
                    cite(new_reference),
                ]
            },
            headers={
                "Authorization": "Bearer test_jwt_token",
                "Content-Type": "application/json-patch+json",
                "User-Agent": USER_AGENT,
            },
        )
        assert first.payload == first_payload
        assert second.payload == second_payload
        assert first.applied_at is not None
        assert second.applied_at == first.applied_at
        db_session.refresh(target_statement)
        assert target_statement.document == edited_document

    @pytest.mark.parametrize(
        ("change", "already_cited"),
        [
            ("date", False),
            ("date", True),
            ("append qualifier", False),
            ("refine qualifier", False),
        ],
    )
    async def test_later_equivalent_edit_adds_only_its_missing_reference(
        self,
        db_session,
        target_statement,
        create_action,
        position_entity,
        change,
        already_cited,
    ):
        original = target_statement.document
        year = {
            "type": "value",
            "content": {"time": "+1950-01-01T00:00:00Z", "precision": 9},
        }
        full_date = {
            "type": "value",
            "content": {"time": "+1950-05-15T00:00:00Z", "precision": 11},
        }
        if change == "date":
            original = {**original, "value": year}
            data_patch = refine_value_patch(original, full_date)["patch"]
            refined = {**original, "value": full_date}
        else:
            proposed_start = {"property": {"id": "P580"}, "value": full_date}
            cached_start = {
                **proposed_start,
                "property": {"id": "P580", "data_type": "time"},
            }
            original = entity_statement_document(statement_id=original["id"])
            if change == "append qualifier":
                end = {
                    "property": {"id": "P582", "data_type": "time"},
                    "value": {"type": "novalue"},
                }
                original["qualifiers"] = [end]
                data_patch = append_qualifier_patch(original, proposed_start)["patch"]
                refined = {**original, "qualifiers": [cached_start, end]}
            else:
                original["qualifiers"] = [{**cached_start, "value": year}]
                data_patch = refine_qualifier_patch(original, 0, proposed_start)[
                    "patch"
                ]
                refined = {**original, "qualifiers": [cached_start]}
        target_statement.document = original

        first_reference = url_reference("https://example.com/first")
        second_reference = (
            first_reference
            if already_cited
            else url_reference("https://example.com/second")
        )
        first, second = [
            create_action(
                ActionKind.EDIT_STATEMENT,
                {"patch": [*data_patch, cite(reference)]},
                target_statement.id,
            )
            for reference in (first_reference, second_reference)
        ]
        first_result = {**refined, "references": [first_reference]}
        final_result = (
            first_result
            if already_cited
            else {
                **refined,
                "references": [first_reference, second_reference],
            }
        )

        with mock_api_response(200, first_result) as client:
            assert await apply_action_group(db_session, [first], "first") is True
            assert client.request.await_args.kwargs["json"]["patch"] == [
                *data_patch,
                {"op": "test", "path": "/references", "value": []},
                cite(first_reference),
            ]
        with mock_api_response(200, final_result) as client:
            assert await apply_action_group(db_session, [second], "second") is True
            if already_cited:
                client.request.assert_not_called()
            else:
                assert client.request.await_args.kwargs["json"]["patch"] == [
                    *statement_fact_guards(refined),
                    {"op": "test", "path": "/references", "value": [first_reference]},
                    cite(second_reference),
                ]
        assert target_statement.document == final_result
        assert second.applied_at is not None
        assert second.payload == {"patch": [*data_patch, cite(second_reference)]}

    async def test_stale_qualifier_edit_is_not_cited_on_a_different_office(
        self, db_session, target_statement, create_action, position_entity
    ):
        original = entity_statement_document(
            statement_id=target_statement.document["id"]
        )
        qualifier = {"property": {"id": "P580"}, "value": {"type": "somevalue"}}
        data_patch = append_qualifier_patch(original, qualifier)["patch"]
        reference = url_reference("https://example.com/source")
        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"patch": [*data_patch, cite(reference)]},
            target_statement.id,
        )
        db_session.add(WikidataEntity(wikidata_id="Q30186"))
        db_session.flush()
        changed = {
            **original,
            "value": {"type": "value", "content": "Q30186"},
            "qualifiers": [qualifier],
        }
        target_statement.document = changed

        with mock_api_response(409, {"error": {"code": "patch-test-failed"}}) as client:
            assert await apply_action_group(db_session, [action], "reviewer") is False
            assert (
                client.request.await_args.kwargs["json"]["patch"][: len(data_patch)]
                == data_patch
            )

        assert action.applied_at is None
        assert target_statement.document == changed

    @pytest.mark.parametrize("already_cited", [False, True])
    async def test_source_only_edit_writes_only_a_missing_reference(
        self, db_session, target_statement, create_action, already_cited
    ):
        reference = url_reference("https://example.com/source")
        guards = [
            {
                "op": "test",
                "path": "/value",
                "value": target_statement.document["value"],
            },
            {"op": "test", "path": "/qualifiers", "value": []},
        ]
        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"patch": [*guards, cite(reference)]},
            target_statement.id,
        )
        edited_document = {**target_statement.document, "references": [reference]}
        if already_cited:
            target_statement.document = edited_document

        with mock_api_response(200, edited_document) as client:
            assert (
                await apply_action_group(db_session, [action], "test_jwt_token") is True
            )

        if already_cited:
            client.request.assert_not_called()
        else:
            assert client.request.await_args.kwargs["json"]["patch"] == [
                *guards,
                {"op": "test", "path": "/references", "value": []},
                cite(reference),
            ]
        assert action.applied_at is not None
        assert target_statement.document == edited_document

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
            {
                "patch": [
                    {"op": "test", "path": "/rank", "value": "normal"},
                    {"op": "replace", "path": "/rank", "value": "preferred"},
                ]
            },
            statement_id=target_statement.id,
        )

        with mock_api_response(
            status_code, {"error": {"code": error_code, "message": "Rejected"}}
        ):
            assert (
                await apply_action_group(db_session, [action], "test_jwt_token")
                is False
            )

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
            assert (
                await apply_action_group(db_session, [action], "test_jwt_token")
                is False
            )

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
            await apply_action_group(db_session, [action], "test_jwt_token")

        assert action.applied_at is None
        assert action.error is None
