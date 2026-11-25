"""Review decisions and skips for PATCH /politicians/{qid}/actions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from poliloom.models import Action, ActionClaim, ActionSkip, Politician
from poliloom.sse import DecisionCountEvent
from poliloom.wikidata.date import WikidataDate

from ..conftest import create_with_entity, make_terms


def birth_date(year="1970"):
    return {
        "property": {"id": "P569"},
        "value": {
            "type": "value",
            "content": WikidataDate.from_date_string(year).to_rest_time_content(),
        },
        "qualifiers": [],
    }


def cite(url):
    return [
        {
            "parts": [
                {"property": {"id": "P854"}, "value": {"type": "value", "content": url}}
            ]
        }
    ]


def decision(action, accept=True):
    return {"id": str(action.id), "is_accepted": accept}


@pytest.fixture
def create_action(db_session, sample_politician):
    def create(*, claim="12345", claimed_at=None, released_at=None, **fields):
        action = Action(
            **{
                "politician_id": sample_politician.id,
                "after": birth_date(),
                **fields,
            }
        )
        db_session.add(action)
        db_session.flush()
        if claim is not None:
            db_session.add(
                ActionClaim(
                    user_id=claim,
                    action_id=action.id,
                    claimed_at=claimed_at,
                    released_at=released_at,
                )
            )
        db_session.flush()
        return action

    return create


def submit(client, auth, actions, skips=None, qid="Q123456"):
    body = {"actions": actions}
    if skips is not None:
        body["skips"] = [str(action.id) for action in skips]
    return client.patch(f"/politicians/{qid}/actions", json=body, headers=auth)


@patch("poliloom.api.politicians.apply_action_group", new_callable=AsyncMock)
def test_accept_commits_decision_and_applies_stored_proposal(
    apply, client, mock_auth, db_session, create_action
):
    before = birth_date()
    after = birth_date("1970-01-15")
    references = cite("https://example.com/bio")
    action = create_action(
        target_wikidata_statement_id="Q123456$birth",
        before=before,
        after=after,
        references_to_add=references,
    )

    async def check_decision(db, group, jwt_token):
        assert group == [action]
        assert action.is_accepted is True
        assert action.decided_by_user_id == "12345"
        assert action.decided_at is not None
        assert jwt_token == "mock_jwt_token_for_testing"
        assert action.target_wikidata_statement_id == "Q123456$birth"
        assert (action.before, action.after, action.references_to_add) == (
            before,
            after,
            references,
        )
        return True

    apply.side_effect = check_decision
    response = submit(client, mock_auth, [decision(action)])

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["errors"] == []
    apply.assert_awaited_once()
    db_session.refresh(action)
    assert action.is_accepted is True


@patch("poliloom.api.politicians.apply_action_group", new_callable=AsyncMock)
def test_groups_only_approved_equivalent_proposals(
    apply, client, mock_auth, db_session, create_action
):
    apply.return_value = True
    first = create_action(references_to_add=cite("https://example.com/first"))
    second = create_action(references_to_add=cite("https://example.com/second"))
    discarded = create_action(references_to_add=cite("https://example.com/discarded"))
    skipped = create_action(references_to_add=cite("https://example.com/skipped"))
    other_user = create_action(
        claim="999", references_to_add=cite("https://example.com/other")
    )
    different = create_action(after=birth_date("1971"))

    response = submit(
        client,
        mock_auth,
        [
            decision(first),
            decision(second),
            decision(discarded, False),
            decision(different),
        ],
        skips=[skipped],
    )

    assert response.json()["errors"] == []
    assert [
        {action.id for action in call.args[1]} for call in apply.await_args_list
    ] == [{first.id, second.id}, {different.id}]
    for action in [discarded, skipped, other_user]:
        db_session.refresh(action)
    assert discarded.is_accepted is False
    assert discarded.decided_at is not None
    assert discarded.applied_at is None
    assert skipped.is_accepted is other_user.is_accepted is None
    assert (
        db_session.query(ActionSkip)
        .filter_by(user_id="12345", action_id=skipped.id)
        .count()
        == 1
    )


@pytest.mark.parametrize("failure", [False, ValueError("Wikidata API error")])
@patch("poliloom.api.politicians.apply_action_group", new_callable=AsyncMock)
def test_apply_failure_surfaces_but_keeps_approval(
    apply, failure, client, mock_auth, db_session, create_action
):
    if isinstance(failure, Exception):
        apply.side_effect = failure
    else:
        apply.return_value = failure
    action = create_action()

    response = submit(client, mock_auth, [decision(action)])

    assert response.status_code == 200
    result = response.json()
    assert result["success"] is False
    assert len(result["errors"]) == 1
    assert str(action.id) in result["errors"][0]
    db_session.refresh(action)
    if isinstance(failure, Exception):
        assert str(failure) in result["errors"][0]
        assert action.error == str(failure)
    assert action.is_accepted is True
    assert action.applied_at is action.applied_wikidata_statement_id is None


@pytest.mark.parametrize("claim", [None, "999", "12345"])
def test_decision_requires_an_unreleased_claim(
    claim, client, mock_auth, db_session, create_action
):
    action = create_action(
        claim=claim, released_at=datetime.now(UTC) if claim == "12345" else None
    )

    result = submit(client, mock_auth, [decision(action)]).json()

    assert result["success"] is False
    assert result["errors"] == [f"Action {action.id} is not claimed by user 12345"]
    db_session.refresh(action)
    assert action.is_accepted is action.decided_by_user_id is None


@patch("poliloom.api.politicians.apply_action_group", new_callable=AsyncMock)
def test_refreshes_an_expired_own_claim(
    apply, client, mock_auth, db_session, create_action
):
    apply.return_value = True
    action = create_action(claimed_at=datetime.now(UTC) - timedelta(hours=1))

    result = submit(client, mock_auth, [decision(action)]).json()

    assert result["errors"] == []
    db_session.refresh(action)
    assert action.is_accepted is True


@pytest.mark.parametrize("skip", [False, True])
@pytest.mark.parametrize("invalid", ["decided", "other politician", "unknown"])
def test_only_known_pending_actions_of_this_politician_are_decidable_or_skippable(
    skip, invalid, client, mock_auth, db_session, create_action
):
    if invalid == "decided":
        action = create_action(is_accepted=False)
        reason = "is not pending"
    elif invalid == "other politician":
        other = create_with_entity(
            Politician, db_session, "Q777777", make_terms("Other Politician")
        )
        db_session.flush()
        action = create_action(politician_id=other.id)
        reason = "does not belong to politician Q123456"
    else:
        action = Action(id=uuid4())
        reason = "not found"

    result = submit(
        client,
        mock_auth,
        [] if skip else [decision(action)],
        skips=[action] if skip else None,
    ).json()

    assert result["success"] is False
    assert result["errors"] == [f"Action {action.id} {reason}"]
    assert db_session.query(ActionSkip).count() == 0
    if invalid != "unknown":
        db_session.refresh(action)
        assert action.is_accepted is (False if invalid == "decided" else None)


@patch("poliloom.sse.EventBus.notify")
def test_skip_is_undecided_idempotent_and_does_not_broadcast(
    notify, client, mock_auth, db_session, create_action
):
    action = create_action(claim=None)

    for _ in range(2):
        result = submit(client, mock_auth, [], skips=[action]).json()
        assert result["success"] is True
        assert result["errors"] == []

    assert (
        db_session.query(ActionSkip)
        .filter_by(user_id="12345", action_id=action.id)
        .count()
        == 1
    )
    db_session.refresh(action)
    assert action.is_accepted is action.decided_by_user_id is action.decided_at is None
    notify.assert_not_called()


@patch("poliloom.sse.EventBus.notify")
@patch("poliloom.api.politicians.apply_action_group", new_callable=AsyncMock)
def test_broadcasts_decision_count_after_partial_success(
    apply, notify, client, mock_auth, db_session, create_action
):
    apply.return_value = True
    create_action(is_accepted=False)
    accepted = create_action()
    invalid = create_action(claim=None)

    result = submit(client, mock_auth, [decision(accepted), decision(invalid)]).json()

    assert result["success"] is False
    assert result["errors"] == [f"Action {invalid.id} is not claimed by user 12345"]
    db_session.refresh(accepted)
    db_session.refresh(invalid)
    assert accepted.is_accepted is True
    assert invalid.is_accepted is None
    notify.assert_called_once()
    assert notify.call_args.args[0] == DecisionCountEvent(total=2)


@pytest.mark.parametrize(
    "patch_body",
    [
        {"is_accepted": True},
        {"id": None, "is_accepted": True},
        {"is_accepted": None},
        {"after": {"rank": "deprecated"}},
        {"kind": "EDIT_STATEMENT", "payload": {"patch": []}},
        {"references_to_add": []},
    ],
)
def test_decisions_require_id_and_decision_and_cannot_replace_proposals(
    patch_body, client, mock_auth, db_session, create_action
):
    action = create_action(references_to_add=cite("https://example.com/bio"))
    body = {"id": str(action.id), **patch_body}
    if patch_body == {"is_accepted": True}:
        del body["id"]

    response = submit(client, mock_auth, [body])

    assert response.status_code == 422
    db_session.refresh(action)
    assert action.is_accepted is None
    assert action.after == birth_date()
    assert action.references_to_add == cite("https://example.com/bio")


def test_empty_request_is_noop(client, mock_auth, sample_politician):
    response = submit(client, mock_auth, [])
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["errors"] == []


def test_nonexistent_politician_returns_404(client, mock_auth):
    assert submit(client, mock_auth, [], qid="Q999999").status_code == 404


def test_requires_authentication(client):
    assert submit(client, None, []).status_code in [401, 403]
