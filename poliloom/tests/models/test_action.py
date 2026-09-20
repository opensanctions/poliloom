"""Tests for the Action models."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import (
    Action,
    ActionClaim,
    ActionEvidence,
    ActionKind,
    ActionSkip,
    Statement,
    WikidataEntity,
)


def statement_body(property_id, content=None, data_type="wikibase-item"):
    """Build the statement document of a create-action payload."""
    value = {"type": "value"}
    if content is not None:
        value["content"] = content
    return {
        "id": f"Q42${property_id.lower()}-new",
        "rank": "normal",
        "property": {"id": property_id, "data_type": data_type},
        "value": value,
    }


@pytest.fixture
def position_entity(db_session):
    """Create the WikidataEntity backing generated entity_id foreign keys."""
    entity = WikidataEntity(wikidata_id="Q30185")
    db_session.add(entity)
    db_session.flush()
    return entity


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
        db_session.refresh(action)
        return action

    return _create


class TestActionCreation:
    """Actions can be created with both kinds; lifecycle fields default NULL."""

    def test_create_statement_action(
        self, db_session, sample_politician, position_entity, create_action
    ):
        action = create_action(
            ActionKind.CREATE_STATEMENT,
            {"statement": statement_body("P39", "Q30185")},
        )

        assert action.kind == ActionKind.CREATE_STATEMENT
        assert action.statement_id is None
        assert action.entity_id == "Q30185"
        assert action in sample_politician.actions

    def test_edit_statement_action(self, db_session, sample_politician, create_action):
        statement = Statement(
            politician_id=sample_politician.id,
            document={
                "id": "Q42$birth-1",
                "rank": "normal",
                "property": {"id": "P569", "data_type": "time"},
                "value": {
                    "type": "value",
                    "content": {"time": "+1980-01-01T00:00:00Z", "precision": 11},
                },
            },
        )
        db_session.add(statement)
        db_session.flush()

        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"patch": [{"op": "replace", "path": "/rank", "value": "preferred"}]},
            statement_id=statement.id,
        )

        assert action.kind == ActionKind.EDIT_STATEMENT
        assert action.statement_id == statement.id
        assert action.statement == statement

    def test_lifecycle_fields_default_null(
        self, db_session, sample_politician, create_action
    ):
        action = create_action(
            ActionKind.CREATE_STATEMENT,
            {
                "statement": statement_body(
                    "P569", {"time": "+1980-01-01T00:00:00Z", "precision": 11}, "time"
                )
            },
        )

        assert action.is_accepted is None
        assert action.decided_by_user_id is None
        assert action.decided_at is None
        assert action.applied_at is None
        assert action.error is None


class TestActionGeneratedEntityId:
    """entity_id derives from the payload of creates only."""

    def test_non_entity_create_body_entity_id_null(self, db_session, create_action):
        action = create_action(
            ActionKind.CREATE_STATEMENT,
            {
                "statement": statement_body(
                    "P569", {"time": "+1980-01-01T00:00:00Z", "precision": 11}, "time"
                )
            },
        )
        assert action.entity_id is None

    def test_edit_body_entity_id_null_even_for_entity_property(
        self, db_session, position_entity, create_action
    ):
        action = create_action(
            ActionKind.EDIT_STATEMENT,
            {"statement": statement_body("P39", "Q30185")},
        )
        assert action.entity_id is None


class TestActionEvidence:
    """Evidence pairs are unique per (action, source)."""

    def test_multiple_sources_allowed(self, db_session, create_action, create_source):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        source_a = create_source("https://example.org/a")
        source_b = create_source("https://example.org/b")

        db_session.add_all(
            [
                ActionEvidence(
                    action_id=action.id,
                    source_id=source_a.id,
                    supporting_quotes=["quote a"],
                ),
                ActionEvidence(action_id=action.id, source_id=source_b.id),
            ]
        )
        db_session.flush()

        assert len(action.evidence) == 2
        assert action.evidence[0].supporting_quotes == ["quote a"]

    def test_duplicate_pair_rejected(self, db_session, create_action, sample_source):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        db_session.add(ActionEvidence(action_id=action.id, source_id=sample_source.id))
        db_session.flush()
        db_session.add(ActionEvidence(action_id=action.id, source_id=sample_source.id))

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestActionClaims:
    """Claims are unique per action."""

    def test_claim_created(self, db_session, create_action):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        claim = ActionClaim(action_id=action.id, user_id="user123")
        db_session.add(claim)
        db_session.flush()
        db_session.refresh(claim)

        assert claim.user_id == "user123"
        assert claim.claimed_at is not None

    def test_second_claim_for_same_action_rejected(self, db_session, create_action):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        db_session.add(ActionClaim(action_id=action.id, user_id="user123"))
        db_session.flush()
        db_session.add(ActionClaim(action_id=action.id, user_id="user456"))

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestActionSkips:
    """Skips are unique per (user, action)."""

    def test_skip_created(self, db_session, create_action):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        skip = ActionSkip(user_id="user123", action_id=action.id)
        db_session.add(skip)
        db_session.flush()

        assert skip.user_id == "user123"

    def test_duplicate_skip_rejected(self, db_session, create_action):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        db_session.add(ActionSkip(user_id="user123", action_id=action.id))
        db_session.flush()
        db_session.add(ActionSkip(user_id="user123", action_id=action.id))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_other_users_and_actions_allowed(self, db_session, create_action):
        action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P569")}
        )
        other_action = create_action(
            ActionKind.CREATE_STATEMENT, {"statement": statement_body("P570")}
        )
        db_session.add_all(
            [
                ActionSkip(user_id="user123", action_id=action.id),
                ActionSkip(user_id="user456", action_id=action.id),
                ActionSkip(user_id="user123", action_id=other_action.id),
            ]
        )
        db_session.flush()

        assert db_session.query(ActionSkip).count() == 3
