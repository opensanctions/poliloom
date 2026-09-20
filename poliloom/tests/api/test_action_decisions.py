"""Tests for PATCH /politicians/{qid}/actions (decisions and skips)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from poliloom.models import (
    Action,
    ActionClaim,
    ActionKind,
    ActionSkip,
    Politician,
)
from poliloom.sse import EvaluationCountEvent
from poliloom.wikidata.statement import WikidataApiError


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


def claim_action(db_session, action, user_id="12345", *, claimed_at=None):
    """Create an ActionClaim row for the given action."""
    db_session.add(
        ActionClaim(user_id=user_id, action_id=action.id, claimed_at=claimed_at)
    )
    db_session.flush()


@pytest.fixture
def create_action(db_session, sample_politician):
    """Factory to create actions on the sample politician."""

    def _create(*, payload=None, is_accepted=None):
        action = Action(
            politician_id=sample_politician.id,
            kind=ActionKind.CREATE_STATEMENT,
            payload=payload or birth_date_create_payload(),
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


def decide(client, decisions, skips=None, qid="Q123456", headers=None):
    """Issue a PATCH /politicians/{qid}/actions request."""
    body = {"decisions": decisions}
    if skips is not None:
        body["skips"] = skips
    return client.patch(f"/politicians/{qid}/actions", json=body, headers=headers)


class TestAcceptDecisions:
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_accept_executes_synchronously(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.return_value = True

        response = decide(
            client,
            [{"id": str(claimed_action.id), "is_accepted": True}],
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
    def test_apply_failure_appends_error_but_keeps_decision(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.return_value = False

        response = decide(
            client,
            [{"id": str(claimed_action.id), "is_accepted": True}],
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
    def test_apply_exception_appends_error_but_keeps_decision(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        mock_apply.side_effect = WikidataApiError("Wikidata API error")

        response = decide(
            client,
            [{"id": str(claimed_action.id), "is_accepted": True}],
            headers=mock_auth,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "Wikidata API error" in result["errors"][0]

        db_session.refresh(claimed_action)
        assert claimed_action.is_accepted is True


class TestDiscardDecisions:
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_discard_persists_false_without_execution(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        response = decide(
            client,
            [{"id": str(claimed_action.id), "is_accepted": False}],
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


class TestDecisionValidation:
    def test_unclaimed_action_rejected(
        self, client, mock_auth, db_session, create_action
    ):
        action = create_action()

        response = decide(
            client, [{"id": str(action.id), "is_accepted": True}], headers=mock_auth
        )
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

        response = decide(
            client, [{"id": str(action.id), "is_accepted": True}], headers=mock_auth
        )
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

        response = decide(
            client, [{"id": str(action.id), "is_accepted": True}], headers=mock_auth
        )
        assert response.json()["errors"] == []

        db_session.refresh(action)
        assert action.is_accepted is True

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_non_pending_action_rejected(
        self, mock_apply, client, mock_auth, db_session, create_action
    ):
        action = create_action(is_accepted=True)
        claim_action(db_session, action)

        response = decide(
            client, [{"id": str(action.id), "is_accepted": True}], headers=mock_auth
        )
        result = response.json()
        assert result["errors"] == [f"Action {action.id} is not pending"]

        mock_apply.assert_not_awaited()
        db_session.refresh(action)
        assert action.is_accepted is True  # unchanged

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_action_of_other_politician_rejected(
        self, mock_apply, client, mock_auth, db_session, sample_politician
    ):
        other = Politician.create_with_entity(db_session, "Q777777", "Other Politician")
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

        response = decide(
            client, [{"id": str(action.id), "is_accepted": True}], headers=mock_auth
        )
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

        response = decide(
            client, [{"id": fake_uuid, "is_accepted": True}], headers=mock_auth
        )
        result = response.json()
        assert result["success"] is True
        assert result["errors"] == [f"Action {fake_uuid} not found"]

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_mixed_valid_and_invalid_decisions(
        self, mock_apply, client, mock_auth, db_session, claimed_action, create_action
    ):
        mock_apply.return_value = True
        unclaimed = create_action()

        response = decide(
            client,
            [
                {"id": str(claimed_action.id), "is_accepted": True},
                {"id": str(unclaimed.id), "is_accepted": True},
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

    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_decision_cannot_alter_payload(
        self, mock_apply, client, mock_auth, db_session, claimed_action
    ):
        """A decision only records the review outcome; payload/kind are immutable."""
        mock_apply.return_value = True
        payload_before = dict(claimed_action.payload)
        kind_before = claimed_action.kind
        statement_id_before = claimed_action.statement_id

        response = decide(
            client,
            [
                {
                    "id": str(claimed_action.id),
                    "is_accepted": True,
                    "payload": {"statement": {"tampered": True}},
                    "kind": "EDIT_STATEMENT",
                }
            ],
            headers=mock_auth,
        )
        assert response.status_code == 200

        db_session.refresh(claimed_action)
        assert claimed_action.payload == payload_before
        assert claimed_action.kind is kind_before
        assert claimed_action.statement_id == statement_id_before
        assert claimed_action.is_accepted is True


class TestSkips:
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_skip_leaves_action_pending_and_records_once(
        self, mock_apply, client, mock_auth, db_session, create_action
    ):
        action = create_action()

        first = decide(client, [], skips=[str(action.id)], headers=mock_auth)
        second = decide(client, [], skips=[str(action.id)], headers=mock_auth)

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

        response = decide(client, [], skips=[str(action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [f"Action {action.id} is not pending"]
        assert db_session.query(ActionSkip).filter_by(action_id=action.id).count() == 0

    def test_skip_action_of_other_politician_rejected(
        self, client, mock_auth, db_session, sample_politician
    ):
        other = Politician.create_with_entity(db_session, "Q777777", "Other Politician")
        db_session.add(other)
        db_session.flush()
        action = Action(
            politician_id=other.id,
            kind=ActionKind.CREATE_STATEMENT,
            payload=birth_date_create_payload(),
        )
        db_session.add(action)
        db_session.flush()

        response = decide(client, [], skips=[str(action.id)], headers=mock_auth)
        result = response.json()
        assert result["errors"] == [
            f"Action {action.id} does not belong to politician Q123456"
        ]
        assert db_session.query(ActionSkip).count() == 0

    def test_skip_unknown_action_id_reports_error(
        self, client, mock_auth, sample_politician
    ):
        fake_uuid = "99999999-9999-9999-9999-999999999999"

        response = decide(client, [], skips=[fake_uuid], headers=mock_auth)
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

        response = decide(
            client,
            [
                {"id": str(accepted.id), "is_accepted": True},
                {"id": str(discarded.id), "is_accepted": False},
            ],
            headers=mock_auth,
        )
        assert response.status_code == 200

        mock_notify.assert_called_once()
        event = mock_notify.call_args[0][0]
        assert isinstance(event, EvaluationCountEvent)
        decided_count = (
            db_session.query(Action).filter(Action.is_accepted.isnot(None)).count()
        )
        assert event.total == decided_count == 3

    @patch("poliloom.sse.EventBus.notify")
    @patch("poliloom.api.politicians.apply_action", new_callable=AsyncMock)
    def test_skip_only_does_not_broadcast(
        self, mock_apply, mock_notify, client, mock_auth, db_session, create_action
    ):
        action = create_action()

        response = decide(client, [], skips=[str(action.id)], headers=mock_auth)
        assert response.status_code == 200

        mock_notify.assert_not_called()


class TestRequestValidation:
    def test_empty_request_is_noop(self, client, mock_auth, sample_politician):
        response = decide(client, [], skips=[], headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "Successfully processed 0 items" in result["message"]
        assert result["errors"] == []

    def test_skips_default_to_empty(self, client, mock_auth, sample_politician):
        response = client.patch(
            "/politicians/Q123456/actions", json={"decisions": []}, headers=mock_auth
        )
        assert response.status_code == 200

    def test_decision_missing_is_accepted_returns_422(
        self, client, mock_auth, sample_politician
    ):
        response = decide(
            client, [{"id": "11111111-1111-1111-1111-111111111111"}], headers=mock_auth
        )
        assert response.status_code == 422

    def test_decision_missing_id_returns_422(
        self, client, mock_auth, sample_politician
    ):
        response = decide(client, [{"is_accepted": True}], headers=mock_auth)
        assert response.status_code == 422

    def test_nonexistent_politician_returns_404(self, client, mock_auth):
        response = decide(
            client,
            [{"id": "11111111-1111-1111-1111-111111111111", "is_accepted": True}],
            qid="Q999999",
            headers=mock_auth,
        )
        assert response.status_code == 404

    def test_requires_authentication(self, client):
        response = client.patch(
            "/politicians/Q123456/actions",
            json={"decisions": []},
        )
        assert response.status_code in [401, 403]
