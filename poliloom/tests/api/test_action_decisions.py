"""Tests for PATCH /politicians/{qid}/actions (submissions and skips)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from poliloom.models import (
    Action,
    ActionClaim,
    ActionEvidence,
    ActionKind,
    ActionSkip,
    Politician,
    Statement,
)
from poliloom.sse import DecisionCountEvent

from ..conftest import make_terms


def birth_date_create_payload(statement_id="Q123456$birth-new"):
    """Build a CREATE_STATEMENT payload for a birth-date statement."""
    return {
        "statement": {
            "id": statement_id,
            "rank": "normal",
            "property": {"id": "P569", "data_type": "time"},
            "value": {
                "type": "value",
                "content": {"time": "+1970-01-15T00:00:00Z", "precision": 11},
            },
        }
    }


def rank_edit_payload():
    """Build an EDIT_STATEMENT payload promoting a statement's rank."""
    return {"patch": [{"op": "replace", "path": "/rank", "value": "preferred"}]}


def claim_action(db_session, action, user_id="12345", *, claimed_at=None):
    """Create an ActionClaim row for the given action."""
    db_session.add(
        ActionClaim(user_id=user_id, action_id=action.id, claimed_at=claimed_at)
    )
    db_session.flush()


def action_body(
    *,
    id=None,
    kind="CREATE_STATEMENT",
    payload=None,
    statement_id=None,
    is_accepted=True,
    **overrides,
):
    """Build a SubmittedAction request body with kind-appropriate defaults."""
    if payload is None:
        if kind == "EDIT_STATEMENT":
            payload = rank_edit_payload()
        else:
            payload = birth_date_create_payload()
    body = {
        "id": str(id) if id else None,
        "kind": kind,
        "statement_id": str(statement_id) if statement_id else None,
        "payload": payload,
        "is_accepted": is_accepted,
    }
    body.update(overrides)
    return body


@pytest.fixture
def target_statement(db_session, sample_politician):
    """Cached statement that EDIT_STATEMENT submissions target."""
    statement = Statement(
        politician_id=sample_politician.id,
        document={
            "id": "Q123456$birth-existing",
            "rank": "normal",
            "property": {"id": "P569", "data_type": "time"},
            "value": {
                "type": "value",
                "content": {"time": "+1970-01-15T00:00:00Z", "precision": 11},
            },
        },
    )
    db_session.add(statement)
    db_session.flush()
    return statement


@pytest.fixture
def create_action(db_session, sample_politician):
    """Factory to create actions on the sample politician."""

    def _create(
        *,
        kind=ActionKind.CREATE_STATEMENT,
        payload=None,
        statement_id=None,
        is_accepted=None,
    ):
        action = Action(
            politician_id=sample_politician.id,
            kind=kind,
            payload=payload if payload is not None else birth_date_create_payload(),
            statement_id=statement_id,
            is_accepted=is_accepted,
        )
        db_session.add(action)
        db_session.flush()
        return action

    return _create


@pytest.fixture
def claimed_action(db_session, create_action):
    """Pending action with a live claim by the authenticated user (12345)."""
    action = create_action()
    claim_action(db_session, action)
    return action


def submit(client, actions, skips=None, qid="Q123456", headers=None):
    """Issue a PATCH /politicians/{qid}/actions request."""
    body = {"actions": actions}
    if skips is not None:
        body["skips"] = skips
    return client.patch(f"/politicians/{qid}/actions", json=body, headers=headers)


class TestAcceptSubmissions:
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_accept_executes_synchronously(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.return_value = True

        response = submit(
            client,
            [action_body(id=claimed_action.id)],
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["errors"] == []
        assert "Successfully processed 1 items" in result["message"]

        mock_apply.assert_awaited_once()
        applied_action, jwt_token = mock_apply.call_args.args[1:]
        assert applied_action.id == claimed_action.id
        assert jwt_token == "mock_jwt_token_for_testing"

        db_session.refresh(claimed_action)
        assert claimed_action.is_accepted is True
        assert claimed_action.decided_by_user_id == "12345"
        assert claimed_action.decided_at is not None

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_apply_failure_appends_error_but_keeps_submission(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.return_value = False

        response = submit(
            client,
            [action_body(id=claimed_action.id)],
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert len(result["errors"]) == 1
        assert f"Failed to apply action {claimed_action.id}" in result["errors"][0]
        assert "1 apply errors" in result["message"]

        db_session.refresh(claimed_action)
        assert claimed_action.is_accepted is True

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_apply_exception_appends_error_but_keeps_submission(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.side_effect = ValueError("Wikidata API error")

        response = submit(
            client,
            [action_body(id=claimed_action.id)],
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "Wikidata API error" in result["errors"][0]

        db_session.refresh(claimed_action)
        assert claimed_action.is_accepted is True


class TestDiscardSubmissions:
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_discard_persists_false_without_execution(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        response = submit(
            client,
            [action_body(id=claimed_action.id, is_accepted=False)],
            headers=mock_auth,
        )
        assert response.status_code == 200
        assert response.json()["errors"] == []

        mock_apply.assert_not_awaited()

        db_session.refresh(claimed_action)
        assert claimed_action.is_accepted is False
        assert claimed_action.decided_by_user_id == "12345"
        assert claimed_action.decided_at is not None
        assert claimed_action.applied_at is None


class TestSubmissionValidation:
    def test_unclaimed_action_rejected(
        self, client, mock_auth, db_session, create_action
    ):
        action = create_action()

        response = submit(client, [action_body(id=action.id)], headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["errors"] == [f"Action {action.id} is not claimed by user 12345"]

        db_session.refresh(action)
        assert action.is_accepted is None
        assert action.decided_by_user_id is None

    def test_other_users_claim_is_not_sufficient(
        self, client, mock_auth, db_session, create_action
    ):
        action = create_action()
        claim_action(db_session, action, user_id="999")

        response = submit(client, [action_body(id=action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [f"Action {action.id} is not claimed by user 12345"]

        db_session.refresh(action)
        assert action.is_accepted is None

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_expired_own_claim_is_refreshed(
        self, mock_apply, client, mock_auth, db_session, create_action
    ):
        """Refreshing claims revives the user's expired claim for this politician."""
        mock_apply.return_value = True
        action = create_action()
        claim_action(
            db_session,
            action,
            claimed_at=datetime.now(UTC) - timedelta(hours=1),
        )

        response = submit(client, [action_body(id=action.id)], headers=mock_auth)
        assert response.json()["errors"] == []

        db_session.refresh(action)
        assert action.is_accepted is True

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_non_pending_action_rejected(
        self, mock_apply, client, mock_auth, db_session, create_action
    ):
        action = create_action(is_accepted=True)
        claim_action(db_session, action)

        response = submit(client, [action_body(id=action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [f"Action {action.id} is not pending"]

        mock_apply.assert_not_awaited()
        db_session.refresh(action)
        assert action.is_accepted is True  # unchanged

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_action_of_other_politician_rejected(
        self, mock_apply, client, mock_auth, db_session, sample_politician
    ):
        other = Politician.create_with_entity(
            db_session, "Q777777", make_terms("Other Politician")
        )
        db_session.add(other)
        db_session.flush()
        action = Action(
            politician_id=other.id,
            kind=ActionKind.CREATE_STATEMENT,
            payload=birth_date_create_payload(),
        )
        db_session.add(action)
        db_session.flush()
        claim_action(db_session, action)

        response = submit(client, [action_body(id=action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [
            f"Action {action.id} does not belong to politician Q123456"
        ]

        db_session.refresh(action)
        assert action.is_accepted is None

    def test_unknown_action_id_reports_error(
        self, client, mock_auth, sample_politician
    ):
        fake_uuid = "99999999-9999-9999-9999-999999999999"

        response = submit(client, [action_body(id=fake_uuid)], headers=mock_auth)
        result = response.json()
        assert result["success"] is True
        assert result["errors"] == [f"Action {fake_uuid} not found"]

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_mixed_valid_and_invalid_submissions(
        self, mock_apply, client, mock_auth, db_session, claimed_action, create_action
    ):
        mock_apply.return_value = True
        unclaimed = create_action()

        response = submit(
            client,
            [
                action_body(id=claimed_action.id),
                action_body(id=unclaimed.id),
            ],
            headers=mock_auth,
        )
        result = response.json()
        assert result["success"] is True
        assert "Successfully processed 1 items" in result["message"]
        assert len(result["errors"]) == 1

        db_session.refresh(claimed_action)
        db_session.refresh(unclaimed)
        assert claimed_action.is_accepted is True
        assert unclaimed.is_accepted is None


class TestSubmittedObjectIsTruth:
    """For existing actions the submitted kind, statement_id and payload win."""

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_modified_payload_overwrites_stored_payload(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.return_value = True
        modified = birth_date_create_payload()
        modified["statement"]["value"]["content"]["time"] = "+1971-06-30T00:00:00Z"

        response = submit(
            client,
            [action_body(id=claimed_action.id, payload=modified)],
            headers=mock_auth,
        )
        assert response.status_code == 200
        assert response.json()["errors"] == []

        db_session.refresh(claimed_action)
        assert claimed_action.payload == modified
        assert claimed_action.is_accepted is True
        applied_action = mock_apply.call_args.args[1]
        assert applied_action.payload == modified

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_kind_change_with_valid_envelope(
        self,
        mock_apply,
        client,
        mock_auth,
        db_session,
        claimed_action,
        target_statement,
    ):
        mock_apply.return_value = True

        response = submit(
            client,
            [
                action_body(
                    id=claimed_action.id,
                    kind="EDIT_STATEMENT",
                    statement_id=target_statement.id,
                )
            ],
            headers=mock_auth,
        )
        assert response.status_code == 200
        assert response.json()["errors"] == []

        db_session.refresh(claimed_action)
        assert claimed_action.kind is ActionKind.EDIT_STATEMENT
        assert claimed_action.statement_id == target_statement.id
        assert claimed_action.payload == rank_edit_payload()
        assert claimed_action.is_accepted is True

    def test_invalid_envelope_on_existing_action_rejected(
        self, client, mock_auth, db_session, claimed_action
    ):
        original_payload = dict(claimed_action.payload)

        response = submit(
            client,
            [action_body(id=claimed_action.id, payload={"statement": {}})],
            headers=mock_auth,
        )
        result = response.json()
        assert result["errors"] == [
            f"Action {claimed_action.id}: CREATE_STATEMENT statement.property.id is required"
        ]

        db_session.refresh(claimed_action)
        assert claimed_action.payload == original_payload
        assert claimed_action.is_accepted is None


class TestNewActions:
    """Submissions without an id insert user-authored actions."""

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_accepted_new_action_inserted_and_applied(
        self, mock_apply, client, mock_auth, db_session, sample_politician
    ):
        mock_apply.return_value = True
        payload = birth_date_create_payload()

        response = submit(client, [action_body(payload=payload)], headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["errors"] == []
        assert "Successfully processed 1 items" in result["message"]

        actions = (
            db_session.query(Action).filter_by(politician_id=sample_politician.id).all()
        )
        assert len(actions) == 1
        action = actions[0]
        assert action.kind is ActionKind.CREATE_STATEMENT
        assert action.statement_id is None
        assert action.payload == payload
        assert action.is_accepted is True
        assert action.decided_by_user_id == "12345"
        assert action.decided_at is not None
        # User-authored actions carry no evidence rows
        assert (
            db_session.query(ActionEvidence).filter_by(action_id=action.id).count() == 0
        )

        mock_apply.assert_awaited_once()
        applied_action, jwt_token = mock_apply.call_args.args[1:]
        assert applied_action.id == action.id
        assert jwt_token == "mock_jwt_token_for_testing"

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_discarded_new_action_just_marked(
        self, mock_apply, client, mock_auth, db_session, sample_politician
    ):
        response = submit(client, [action_body(is_accepted=False)], headers=mock_auth)
        assert response.status_code == 200
        assert response.json()["errors"] == []

        mock_apply.assert_not_awaited()

        actions = (
            db_session.query(Action).filter_by(politician_id=sample_politician.id).all()
        )
        assert len(actions) == 1
        action = actions[0]
        assert action.is_accepted is False
        assert action.decided_by_user_id == "12345"
        assert action.decided_at is not None
        assert action.applied_at is None

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_new_edit_action_persists_statement_id(
        self,
        mock_apply,
        client,
        mock_auth,
        db_session,
        sample_politician,
        target_statement,
    ):
        mock_apply.return_value = True

        response = submit(
            client,
            [action_body(kind="EDIT_STATEMENT", statement_id=target_statement.id)],
            headers=mock_auth,
        )
        assert response.status_code == 200
        assert response.json()["errors"] == []

        action = (
            db_session.query(Action).filter_by(politician_id=sample_politician.id).one()
        )
        assert action.kind is ActionKind.EDIT_STATEMENT
        assert action.statement_id == target_statement.id
        assert action.is_accepted is True

        mock_apply.assert_awaited_once()


class TestEnvelopeValidation:
    def test_edit_without_statement_id_reports_error(
        self, client, mock_auth, db_session, sample_politician
    ):
        response = submit(
            client,
            [action_body(kind="EDIT_STATEMENT", statement_id=None)],
            headers=mock_auth,
        )
        result = response.json()
        assert result["success"] is True
        assert result["errors"] == [
            "actions[0]: EDIT_STATEMENT statement_id is required"
        ]
        assert db_session.query(Action).count() == 0

    def test_edit_with_malformed_payload_reports_error(
        self, client, mock_auth, db_session, sample_politician
    ):
        response = submit(
            client,
            [
                action_body(
                    kind="EDIT_STATEMENT",
                    statement_id="11111111-1111-1111-1111-111111111111",
                    payload={"patch": "not-a-list"},
                )
            ],
            headers=mock_auth,
        )
        result = response.json()
        assert result["errors"] == [
            'actions[0]: EDIT_STATEMENT payload must be {"patch": [...]}'
        ]
        assert db_session.query(Action).count() == 0

    def test_edit_with_missing_patch_reports_error(
        self, client, mock_auth, db_session, sample_politician
    ):
        response = submit(
            client,
            [
                action_body(
                    kind="EDIT_STATEMENT",
                    statement_id="11111111-1111-1111-1111-111111111111",
                    payload={},
                )
            ],
            headers=mock_auth,
        )
        result = response.json()
        assert result["errors"] == [
            'actions[0]: EDIT_STATEMENT payload must be {"patch": [...]}'
        ]
        assert db_session.query(Action).count() == 0

    def test_create_without_statement_reports_error(
        self, client, mock_auth, db_session, sample_politician
    ):
        response = submit(
            client,
            [action_body(payload={"statement": "not-a-dict"})],
            headers=mock_auth,
        )
        result = response.json()
        assert result["errors"] == [
            'actions[0]: CREATE_STATEMENT payload must be {"statement": {...}}'
        ]
        assert db_session.query(Action).count() == 0

    def test_create_without_property_id_reports_error(
        self, client, mock_auth, db_session, sample_politician
    ):
        response = submit(
            client, [action_body(payload={"statement": {}})], headers=mock_auth
        )
        result = response.json()
        assert result["errors"] == [
            "actions[0]: CREATE_STATEMENT statement.property.id is required"
        ]
        assert db_session.query(Action).count() == 0

    def test_create_without_value_reports_error(
        self, client, mock_auth, db_session, sample_politician
    ):
        response = submit(
            client,
            [
                action_body(
                    payload={
                        "statement": {"property": {"id": "P569", "data_type": "time"}}
                    }
                )
            ],
            headers=mock_auth,
        )
        result = response.json()
        assert result["errors"] == [
            "actions[0]: CREATE_STATEMENT statement.value is required"
        ]
        assert db_session.query(Action).count() == 0


class TestSkips:
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_skip_leaves_action_pending_and_records_once(
        self, mock_apply, client, mock_auth, db_session, create_action
    ):
        action = create_action()

        first = submit(client, [], skips=[str(action.id)], headers=mock_auth)
        second = submit(client, [], skips=[str(action.id)], headers=mock_auth)

        assert first.status_code == second.status_code == 200
        assert first.json()["success"] is second.json()["success"] is True
        assert first.json()["errors"] == []

        assert (
            db_session.query(ActionSkip)
            .filter_by(user_id="12345", action_id=action.id)
            .count()
            == 1
        )

        db_session.refresh(action)
        assert action.is_accepted is None
        assert action.decided_by_user_id is None
        assert action.decided_at is None
        mock_apply.assert_not_awaited()

    def test_skip_decided_action_rejected(
        self, client, mock_auth, db_session, create_action
    ):
        action = create_action(is_accepted=False)

        response = submit(client, [], skips=[str(action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [f"Action {action.id} is not pending"]
        assert db_session.query(ActionSkip).filter_by(action_id=action.id).count() == 0

    def test_skip_action_of_other_politician_rejected(
        self, client, mock_auth, db_session, sample_politician
    ):
        other = Politician.create_with_entity(
            db_session, "Q777777", make_terms("Other Politician")
        )
        db_session.add(other)
        db_session.flush()
        action = Action(
            politician_id=other.id,
            kind=ActionKind.CREATE_STATEMENT,
            payload=birth_date_create_payload(),
        )
        db_session.add(action)
        db_session.flush()

        response = submit(client, [], skips=[str(action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [
            f"Action {action.id} does not belong to politician Q123456"
        ]
        assert db_session.query(ActionSkip).count() == 0

    def test_skip_unknown_action_id_reports_error(
        self, client, mock_auth, sample_politician
    ):
        fake_uuid = "99999999-9999-9999-9999-999999999999"

        response = submit(client, [], skips=[fake_uuid], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [f"Action {fake_uuid} not found"]


class TestEvaluationCountBroadcast:
    @patch("poliloom.sse.EventBus.notify")
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_broadcasts_decided_action_count(
        self, mock_apply, mock_notify, client, mock_auth, db_session, create_action
    ):
        mock_apply.return_value = True
        create_action(is_accepted=False)  # already decided before the request
        accepted = create_action()
        discarded = create_action()
        claim_action(db_session, accepted)
        claim_action(db_session, discarded)

        response = submit(
            client,
            [
                action_body(id=accepted.id),
                action_body(id=discarded.id, is_accepted=False),
            ],
            headers=mock_auth,
        )
        assert response.status_code == 200

        mock_notify.assert_called_once()
        event = mock_notify.call_args[0][0]
        assert isinstance(event, DecisionCountEvent)
        decided_count = (
            db_session.query(Action).filter(Action.is_accepted.isnot(None)).count()
        )
        assert event.total == decided_count == 3

    @patch("poliloom.sse.EventBus.notify")
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_new_action_broadcasts_decided_action_count(
        self, mock_apply, mock_notify, client, mock_auth, db_session, sample_politician
    ):
        mock_apply.return_value = True

        response = submit(client, [action_body()], headers=mock_auth)
        assert response.status_code == 200

        mock_notify.assert_called_once()
        event = mock_notify.call_args[0][0]
        assert isinstance(event, DecisionCountEvent)
        decided_count = (
            db_session.query(Action).filter(Action.is_accepted.isnot(None)).count()
        )
        assert event.total == decided_count == 1

    @patch("poliloom.sse.EventBus.notify")
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_skip_only_does_not_broadcast(
        self, mock_apply, mock_notify, client, mock_auth, db_session, create_action
    ):
        action = create_action()

        response = submit(client, [], skips=[str(action.id)], headers=mock_auth)
        assert response.status_code == 200

        mock_notify.assert_not_called()


class TestRequestValidation:
    def test_empty_request_is_noop(self, client, mock_auth, sample_politician):
        response = submit(client, [], skips=[], headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "Successfully processed 0 items" in result["message"]
        assert result["errors"] == []

    def test_skips_default_to_empty(self, client, mock_auth, sample_politician):
        response = client.patch(
            "/politicians/Q123456/actions", json={"actions": []}, headers=mock_auth
        )
        assert response.status_code == 200

    def test_missing_is_accepted_returns_422(
        self, client, mock_auth, sample_politician
    ):
        body = action_body()
        del body["is_accepted"]
        response = submit(client, [body], headers=mock_auth)
        assert response.status_code == 422

    def test_null_is_accepted_returns_422(self, client, mock_auth, sample_politician):
        response = submit(client, [action_body(is_accepted=None)], headers=mock_auth)
        assert response.status_code == 422

    def test_missing_kind_returns_422(self, client, mock_auth, sample_politician):
        body = action_body()
        del body["kind"]
        response = submit(client, [body], headers=mock_auth)
        assert response.status_code == 422

    def test_invalid_kind_returns_422(self, client, mock_auth, sample_politician):
        response = submit(
            client, [action_body(kind="DELETE_STATEMENT")], headers=mock_auth
        )
        assert response.status_code == 422

    def test_missing_payload_returns_422(self, client, mock_auth, sample_politician):
        body = action_body()
        del body["payload"]
        response = submit(client, [body], headers=mock_auth)
        assert response.status_code == 422

    def test_nonexistent_politician_returns_404(self, client, mock_auth):
        response = submit(
            client,
            [action_body(id="11111111-1111-1111-1111-111111111111")],
            qid="Q999999",
            headers=mock_auth,
        )
        assert response.status_code == 404

    def test_requires_authentication(self, client):
        response = client.patch(
            "/politicians/Q123456/actions",
            json={"actions": []},
        )
        assert response.status_code in [401, 403]
