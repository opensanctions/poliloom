"""Tests for applying accepted statement proposals via the Wikibase REST API."""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

import httpx2
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from poliloom.models import Action, Politician, Statement, WikidataEntity
from poliloom.proposals import statement_fact
from poliloom.wikidata.execution import (
    USER_AGENT,
    WIKIDATA_API_ROOT,
    apply_action_group,
    group_actions,
)

from .conftest import create_with_entity, make_terms

CALENDAR_MODEL = "http://www.wikidata.org/entity/Q1985727"


def time_content(time, precision):
    return {
        "time": time,
        "precision": precision,
        "calendarmodel": CALENDAR_MODEL,
    }


def time_value(time, precision):
    return {"type": "value", "content": time_content(time, precision)}


def time_qualifier(property_id, time, precision):
    return {
        "property": {"id": property_id, "data_type": "time"},
        "value": time_value(time, precision),
    }


def statement_document(
    statement_id="Q123456$aaaaaaa1-b2c3-4d5e-6f70-809000000000",
    property_id="P569",
    value=None,
    qualifiers=None,
    references=None,
    rank="normal",
):
    return {
        "id": statement_id,
        "rank": rank,
        "property": {"id": property_id, "data_type": "time"},
        "value": value or time_value("+1950-01-01T00:00:00Z", 9),
        "qualifiers": qualifiers or [],
        "references": references or [],
    }


def position_document(
    statement_id="Q123456$bbbbbbb1-b2c3-4d5e-6f70-809000000000",
    qualifiers=None,
    references=None,
    rank="normal",
):
    return {
        "id": statement_id,
        "rank": rank,
        "property": {"id": "P39", "data_type": "wikibase-item"},
        "value": {"type": "value", "content": "Q30185"},
        "qualifiers": qualifiers or [],
        "references": references or [],
    }


def url_reference(url):
    return {
        "parts": [
            {
                "property": {"id": "P854", "data_type": "url"},
                "value": {"type": "value", "content": url},
            }
        ]
    }


def wikimedia_import_reference():
    return {
        "parts": [
            {
                "property": {"id": "P143", "data_type": "wikibase-item"},
                "value": {"type": "value", "content": "Q123"},
            }
        ]
    }


def response(status_code, body=None):
    result = Mock(status_code=status_code)
    result.json.return_value = body
    return result


@contextmanager
def mock_api_response(*responses):
    """Patch the execution module's HTTP client with canned responses."""
    with patch("poliloom.wikidata.execution.httpx2.AsyncClient") as mock_client:
        client = mock_client.return_value.__aenter__.return_value
        if len(responses) == 1 and not isinstance(responses[0], BaseException):
            client.request = AsyncMock(return_value=responses[0])
        else:
            client.request = AsyncMock(side_effect=list(responses))
        yield client


@pytest.fixture
def position_entity(db_session):
    """Create the WikidataEntity backing generated P39 statement entity IDs."""
    db_session.add(WikidataEntity(wikidata_id="Q30185"))
    db_session.flush()


@pytest.fixture
def create_action(db_session, sample_politician):
    """Factory to create accepted statement proposals."""

    def _create(
        after,
        *,
        before=None,
        target=None,
        references=None,
    ):
        action = Action(
            politician_id=sample_politician.id,
            target_wikidata_statement_id=target,
            before=before,
            after=after,
            references_to_add=references or [],
            is_accepted=True,
        )
        db_session.add(action)
        db_session.flush()
        return action

    return _create


def cached_statement(db_session, document):
    return db_session.scalar(
        select(Statement).where(Statement.wikidata_statement_id == document["id"])
    )


class TestGrouping:
    def test_equivalent_proposals_group_ignoring_references(self, create_action):
        after = statement_fact(statement_document())
        first = create_action(
            after, references=[url_reference("https://example.com/first")]
        )
        second = create_action(
            after, references=[url_reference("https://example.com/second")]
        )
        different = create_action(
            {
                **after,
                "value": time_value("+1950-05-15T00:00:00Z", 11),
            }
        )

        groups = group_actions([first, second, different])

        assert groups == [[first, second], [different]]


class TestUntargetedProposal:
    async def test_no_match_posts_normal_statement_with_all_references(
        self, db_session, sample_politician, create_action
    ):
        preferred = statement_document(rank="preferred")
        deprecated = statement_document(rank="deprecated")
        after = statement_fact(statement_document())
        first_reference = url_reference("https://example.com/first")
        second_reference = url_reference("https://example.com/second")
        imported_reference = wikimedia_import_reference()
        action = create_action(
            after,
            references=[first_reference, imported_reference, first_reference],
        )
        other = create_action(after, references=[second_reference])
        created = statement_document(
            references=[first_reference, imported_reference, second_reference]
        )

        with mock_api_response(
            response(200, {"P569": [preferred, deprecated]}),
            response(201, created),
        ) as client:
            assert (
                await apply_action_group(db_session, [action, other], "test_jwt_token")
                is True
            )

        get, post = client.request.await_args_list
        assert get.args == (
            "GET",
            f"{WIKIDATA_API_ROOT}/entities/items/Q123456/statements",
        )
        assert get.kwargs["params"] == {"property": "P569"}
        assert post.args == (
            "POST",
            f"{WIKIDATA_API_ROOT}/entities/items/Q123456/statements",
        )
        assert post.kwargs["json"] == {
            "statement": {
                "property": after["property"],
                "value": after["value"],
                "qualifiers": [],
                "rank": "normal",
                "references": [
                    first_reference,
                    imported_reference,
                    second_reference,
                ],
            }
        }
        assert post.kwargs["headers"] == {
            "Authorization": "Bearer test_jwt_token",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }
        assert action.applied_at is not None
        assert action.applied_at == other.applied_at
        assert action.applied_wikidata_statement_id == created["id"]
        assert other.applied_wikidata_statement_id == created["id"]
        assert action.error is None
        assert cached_statement(db_session, created).document == created

    async def test_live_cache_is_not_used_to_decide_an_add(
        self, db_session, sample_politician, create_action
    ):
        after = statement_fact(statement_document())
        created = statement_document()
        db_session.add(Statement(politician_id=sample_politician.id, document=created))
        db_session.flush()
        action = create_action(after)

        with mock_api_response(
            response(200, {}),
            response(201, created),
        ) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        assert [call.args[0] for call in client.request.await_args_list] == [
            "GET",
            "POST",
        ]

    async def test_unique_normal_match_adds_only_missing_eligible_references(
        self, db_session, create_action
    ):
        existing_reference = url_reference("https://example.com/existing")
        new_reference = url_reference("https://example.com/new")
        imported_reference = wikimedia_import_reference()
        live = statement_document(references=[existing_reference])
        after = statement_fact(live)
        updated = statement_document(references=[existing_reference, new_reference])
        first = create_action(
            after,
            references=[existing_reference, new_reference, imported_reference],
        )
        second = create_action(
            after,
            references=[new_reference],
        )

        with mock_api_response(
            response(200, {"P569": [live]}),
            response(200, updated),
        ) as client:
            assert (
                await apply_action_group(db_session, [first, second], "test_jwt_token")
                is True
            )

        get, patch = client.request.await_args_list
        assert get.kwargs["params"] == {"property": "P569"}
        assert patch.args == (
            "PATCH",
            f"{WIKIDATA_API_ROOT}/statements/{live['id']}",
        )
        assert patch.kwargs["json"] == {
            "patch": [
                {"op": "test", "path": "/property", "value": live["property"]},
                {"op": "test", "path": "/value", "value": live["value"]},
                {"op": "test", "path": "/qualifiers", "value": live["qualifiers"]},
                {"op": "test", "path": "/rank", "value": live["rank"]},
                {
                    "op": "test",
                    "path": "/references",
                    "value": [existing_reference],
                },
                {"op": "add", "path": "/references/-", "value": new_reference},
            ]
        }
        assert first.applied_wikidata_statement_id == live["id"]
        assert second.applied_wikidata_statement_id == live["id"]
        assert first.applied_at == second.applied_at
        assert cached_statement(db_session, updated).document == updated

    @pytest.mark.parametrize(
        "references",
        [
            [],
            [url_reference("https://example.com/existing")],
            [wikimedia_import_reference()],
        ],
    )
    async def test_unique_match_with_no_missing_reference_marks_satisfied_without_write(
        self, db_session, create_action, references
    ):
        existing_reference = url_reference("https://example.com/existing")
        live = statement_document(references=[existing_reference])
        action = create_action(statement_fact(live), references=references)

        with mock_api_response(response(200, {"P569": [live]})) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        client.request.assert_awaited_once()
        assert action.applied_at is not None
        assert action.applied_wikidata_statement_id == live["id"]
        assert action.error is None

    async def test_multiple_normal_matches_are_a_conflict_without_write(
        self, db_session, create_action
    ):
        live = statement_document()
        duplicate = statement_document("Q123456$duplicate")
        action = create_action(statement_fact(live))

        with mock_api_response(response(200, {"P569": [live, duplicate]})) as client:
            assert await apply_action_group(db_session, [action], "token") is False

        client.request.assert_awaited_once()
        assert "Multiple current statements" in action.error
        assert action.applied_at is None
        assert action.applied_wikidata_statement_id is None
        assert cached_statement(db_session, live) is None


class TestTargetedProposal:
    async def test_target_prefix_can_be_lowercase(self, db_session, create_action):
        live = statement_document("q123456$legacy")
        fact = statement_fact(live)
        action = create_action(fact, before=fact, target=live["id"])

        with mock_api_response(response(200, live)) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        client.request.assert_awaited_once()
        assert action.applied_wikidata_statement_id == live["id"]

    async def test_other_politicians_target_is_rejected_before_get(
        self, db_session, create_action
    ):
        fact = statement_fact(statement_document())
        action = create_action(fact, before=fact, target="Q888$birth")

        with (
            mock_api_response() as client,
            pytest.raises(ValueError, match="does not belong"),
        ):
            await apply_action_group(db_session, [action], "token")

        client.request.assert_not_awaited()
        assert action.applied_wikidata_statement_id is None

    @pytest.mark.parametrize("invalid", ["rank", "property", "two changes"])
    async def test_unsupported_proposal_is_rejected_before_get(
        self, db_session, create_action, invalid
    ):
        live = statement_document(
            qualifiers=[time_qualifier("P580", "+1950-01-01T00:00:00Z", 9)]
        )
        before = statement_fact(live)
        after = {**before, "value": time_value("+1950-05-15T00:00:00Z", 11)}
        if invalid == "rank":
            after["rank"] = "deprecated"
            error = "fact must have"
        elif invalid == "property":
            after["property"] = {"id": "P570"}
            error = "cannot change the statement property"
        else:
            after["qualifiers"] = []
            error = "Only one supported"
        action = create_action(after, before=before, target=live["id"])

        with mock_api_response() as client, pytest.raises(ValueError, match=error):
            await apply_action_group(db_session, [action], "token")

        client.request.assert_not_awaited()

    async def test_citation_conflicts_when_a_qualifier_multiplicity_changes(
        self, db_session, create_action
    ):
        qualifier = {
            "property": {"id": "P1545"},
            "value": {"type": "value", "content": "1"},
        }
        live = statement_document(qualifiers=[qualifier, qualifier])
        fact = {**statement_fact(live), "qualifiers": [qualifier]}
        action = create_action(
            fact,
            before=fact,
            target=live["id"],
            references=[url_reference("https://example.org")],
        )

        with mock_api_response(response(200, live)) as client:
            assert await apply_action_group(db_session, [action], "token") is False

        client.request.assert_awaited_once()
        assert "no longer matches" in action.error
        assert action.applied_at is None

    async def test_missing_target_is_a_conflict(self, db_session, create_action):
        fact = statement_fact(statement_document())
        action = create_action(
            fact,
            before=fact,
            target="Q123456$missing",
            references=[url_reference("https://example.com/source")],
        )

        with mock_api_response(response(404)) as client:
            assert await apply_action_group(db_session, [action], "token") is False

        client.request.assert_awaited_once()
        assert "no longer exists" in action.error
        assert action.applied_at is None
        assert action.applied_wikidata_statement_id is None

    async def test_deprecated_target_is_a_conflict(self, db_session, create_action):
        live = statement_document(rank="deprecated")
        fact = statement_fact(live)
        action = create_action(fact, before=fact, target=live["id"])

        with mock_api_response(response(200, live)) as client:
            assert await apply_action_group(db_session, [action], "token") is False

        client.request.assert_awaited_once()
        assert "deprecated" in action.error
        assert action.applied_at is None

    async def test_target_mismatching_before_and_after_is_a_conflict(
        self, db_session, create_action
    ):
        live = statement_document(value=time_value("+1940-01-01T00:00:00Z", 9))
        before = statement_fact(statement_document())
        after = {**before, "value": time_value("+1950-05-15T00:00:00Z", 11)}
        action = create_action(after, before=before, target=live["id"])

        with mock_api_response(response(200, live)) as client:
            assert await apply_action_group(db_session, [action], "token") is False

        client.request.assert_awaited_once()
        assert "no longer matches" in action.error
        assert action.applied_at is None

    async def test_value_refinement_uses_live_metadata_for_guards(
        self, db_session, create_action
    ):
        existing_reference = url_reference("https://example.com/existing")
        new_reference = url_reference("https://example.com/new")
        live = statement_document(
            rank="preferred",
            qualifiers=[time_qualifier("P580", "+1950-01-01T00:00:00Z", 9)],
            references=[existing_reference],
        )
        before = statement_fact(live)
        after = {**before, "value": time_value("+1950-05-15T00:00:00Z", 11)}
        updated = {
            **live,
            "value": after["value"],
            "references": [existing_reference, new_reference],
        }
        action = create_action(
            after,
            before=before,
            target=live["id"],
            references=[
                url_reference("https://example.com/existing"),
                new_reference,
                wikimedia_import_reference(),
            ],
        )

        with mock_api_response(
            response(200, live),
            response(200, updated),
        ) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        _, patch = client.request.await_args_list
        assert patch.kwargs["json"] == {
            "patch": [
                {"op": "test", "path": "/property", "value": live["property"]},
                {"op": "test", "path": "/value", "value": live["value"]},
                {"op": "test", "path": "/qualifiers", "value": live["qualifiers"]},
                {"op": "test", "path": "/rank", "value": "preferred"},
                {"op": "replace", "path": "/value", "value": after["value"]},
                {
                    "op": "test",
                    "path": "/references",
                    "value": [existing_reference],
                },
                {"op": "add", "path": "/references/-", "value": new_reference},
            ]
        }
        assert action.applied_at is not None
        assert action.applied_wikidata_statement_id == live["id"]
        assert cached_statement(db_session, updated).document == updated

    async def test_qualifier_replacement_uses_live_index(
        self,
        db_session,
        create_action,
        position_entity,
    ):
        old_start = time_qualifier("P580", "+1950-01-01T00:00:00Z", 9)
        new_start = time_qualifier("P580", "+1950-05-15T00:00:00Z", 11)
        end = time_qualifier("P582", "+1951-01-01T00:00:00Z", 9)
        # The live qualifier order differs from the proposal snapshot order.
        live = position_document(qualifiers=[end, old_start])
        before = statement_fact(position_document(qualifiers=[old_start, end]))
        after = statement_fact(position_document(qualifiers=[new_start, end]))
        updated = {**live, "qualifiers": [end, new_start]}
        action = create_action(after, before=before, target=live["id"])

        with mock_api_response(
            response(200, live),
            response(200, updated),
        ) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        _, patch = client.request.await_args_list
        assert patch.kwargs["json"]["patch"] == [
            {"op": "test", "path": "/property", "value": live["property"]},
            {"op": "test", "path": "/value", "value": live["value"]},
            {"op": "test", "path": "/qualifiers", "value": live["qualifiers"]},
            {"op": "test", "path": "/rank", "value": live["rank"]},
            {"op": "replace", "path": "/qualifiers/1", "value": new_start},
        ]
        assert cached_statement(db_session, updated).document == updated

    async def test_qualifier_append_uses_live_fact_guards(
        self,
        db_session,
        create_action,
        position_entity,
    ):
        start = time_qualifier("P580", "+1950-01-01T00:00:00Z", 9)
        end = time_qualifier("P582", "+1951-01-01T00:00:00Z", 9)
        live = position_document(qualifiers=[start])
        before = statement_fact(live)
        after = statement_fact(position_document(qualifiers=[start, end]))
        updated = {**live, "qualifiers": [start, end]}
        action = create_action(after, before=before, target=live["id"])

        with mock_api_response(
            response(200, live),
            response(200, updated),
        ) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        _, patch = client.request.await_args_list
        assert patch.kwargs["json"]["patch"] == [
            {"op": "test", "path": "/property", "value": live["property"]},
            {"op": "test", "path": "/value", "value": live["value"]},
            {"op": "test", "path": "/qualifiers", "value": live["qualifiers"]},
            {"op": "test", "path": "/rank", "value": live["rank"]},
            {"op": "add", "path": "/qualifiers/-", "value": end},
        ]

    async def test_already_after_adds_only_missing_eligible_references(
        self, db_session, create_action
    ):
        existing_reference = url_reference("https://example.com/existing")
        new_reference = url_reference("https://example.com/new")
        live = statement_document(references=[existing_reference])
        fact = statement_fact(live)
        updated = statement_document(references=[existing_reference, new_reference])
        action = create_action(
            fact,
            before=fact,
            target=live["id"],
            references=[new_reference, wikimedia_import_reference()],
        )

        with mock_api_response(
            response(200, live),
            response(200, updated),
        ) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        _, patch = client.request.await_args_list
        assert patch.kwargs["json"]["patch"] == [
            {"op": "test", "path": "/property", "value": live["property"]},
            {"op": "test", "path": "/value", "value": live["value"]},
            {"op": "test", "path": "/qualifiers", "value": live["qualifiers"]},
            {"op": "test", "path": "/rank", "value": live["rank"]},
            {"op": "test", "path": "/references", "value": [existing_reference]},
            {"op": "add", "path": "/references/-", "value": new_reference},
        ]

    async def test_already_after_with_reference_already_present_marks_satisfied_without_write(
        self, db_session, sample_politician, create_action
    ):
        existing_reference = url_reference("https://example.com/existing")
        old = statement_document()
        db_session.add(Statement(politician_id=sample_politician.id, document=old))
        live = {
            **old,
            "value": time_value("+1950-05-15T00:00:00Z", 11),
            "references": [existing_reference],
        }
        action = create_action(
            statement_fact(live),
            before=statement_fact(old),
            target=live["id"],
            references=[existing_reference, wikimedia_import_reference()],
        )

        with mock_api_response(response(200, live)) as client:
            assert await apply_action_group(db_session, [action], "token") is True

        client.request.assert_awaited_once()
        assert action.applied_at is not None
        assert action.applied_wikidata_statement_id == live["id"]
        assert cached_statement(db_session, live).document == live

    async def test_patch_conflict_records_error_without_caching(
        self, db_session, create_action
    ):
        live = statement_document()
        fact = statement_fact(live)
        action = create_action(
            fact,
            before=fact,
            target=live["id"],
            references=[url_reference("https://example.com/new")],
        )

        with mock_api_response(
            response(200, live),
            response(409, {"code": "patch-test-failed"}),
        ):
            assert await apply_action_group(db_session, [action], "token") is False

        assert "HTTP 409" in action.error
        assert "patch-test-failed" in action.error
        assert action.applied_at is None
        assert action.applied_wikidata_statement_id is None
        assert cached_statement(db_session, live) is None

    async def test_read_failure_records_error(self, db_session, create_action):
        fact = statement_fact(statement_document())
        action = create_action(fact, before=fact, target="Q123456$target")

        with mock_api_response(httpx2.RequestError("Connection reset")) as client:
            assert await apply_action_group(db_session, [action], "token") is False

        client.request.assert_awaited_once()
        assert "Connection reset" in action.error
        assert action.applied_at is None


class TestConcurrentAdds:
    async def test_concurrent_equivalent_adds_write_one_statement(
        self, setup_test_database
    ):
        engine = setup_test_database
        qid = "Q987654"
        first_reference = url_reference("https://example.com/first")
        second_reference = url_reference("https://example.com/second")
        created = statement_document(
            f"{qid}$created",
            references=[first_reference],
        )
        updated = {**created, "references": [first_reference, second_reference]}
        after = statement_fact(statement_document())
        entered_post = asyncio.Event()
        release_post = asyncio.Event()

        with Session(engine) as seed:
            politician = create_with_entity(Politician, seed, qid, make_terms())
            seed.flush()
            politician_id = politician.id
            actions = [
                Action(
                    politician_id=politician_id,
                    before=None,
                    after=after,
                    references_to_add=[reference],
                    is_accepted=True,
                )
                for reference in (first_reference, second_reference)
            ]
            seed.add_all(actions)
            seed.flush()
            first_id, second_id = [action.id for action in actions]
            seed.commit()

        async def respond(method, url, *, params=None, json=None, headers):
            if method == "GET" and headers["Authorization"] == "Bearer first":
                return response(200, {})
            if method == "GET":
                return response(200, {"P569": [created]})
            if method == "POST":
                entered_post.set()
                await release_post.wait()
                return response(201, created)
            return response(200, updated)

        try:
            with (
                Session(engine) as first,
                Session(engine) as second,
                mock_api_response() as client,
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
                    assert client.request.await_count == 2
                    release_post.set()

                assert first_write.result() and second_write.result()
                post = next(
                    call
                    for call in client.request.await_args_list
                    if call.args[0] == "POST"
                )
                assert post.kwargs["json"] == {
                    "statement": {
                        "property": after["property"],
                        "value": after["value"],
                        "qualifiers": [],
                        "rank": "normal",
                        "references": [first_reference],
                    }
                }
                patch = next(
                    call
                    for call in client.request.await_args_list
                    if call.args[0] == "PATCH"
                )
                assert patch.args == (
                    "PATCH",
                    f"{WIKIDATA_API_ROOT}/statements/{created['id']}",
                )
                assert patch.kwargs["json"]["patch"][-2:] == [
                    {
                        "op": "test",
                        "path": "/references",
                        "value": [first_reference],
                    },
                    {"op": "add", "path": "/references/-", "value": second_reference},
                ]
                statement = second.scalar(
                    select(Statement).where(Statement.politician_id == politician_id)
                )
                assert statement.document == updated
                assert (
                    first.get(Action, first_id).applied_wikidata_statement_id
                    == (created["id"])
                )
                assert (
                    second.get(Action, second_id).applied_wikidata_statement_id
                    == (created["id"])
                )
        finally:
            with Session(engine) as cleanup:
                cleanup.execute(
                    delete(WikidataEntity).where(WikidataEntity.wikidata_id == qid)
                )
                cleanup.commit()
