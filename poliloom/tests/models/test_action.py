"""Tests for the Action models."""

import pytest
from sqlalchemy.exc import IntegrityError

from poliloom.models import (
    Action,
    ActionClaim,
    ActionEvidence,
    ActionSkip,
    Statement,
    WikidataEntity,
)
from poliloom.proposals import statement_fact


def fact(property_id, content=None, data_type=None, qualifiers=None):
    """Build the property/value/qualifiers fact carried by an Action."""
    value = {"type": "value"}
    if content is not None:
        value["content"] = content
    property = {"id": property_id}
    if data_type is not None:
        property["data_type"] = data_type
    return {
        "property": property,
        "value": value,
        "qualifiers": qualifiers or [],
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

    def _create(after, *, target_wikidata_statement_id=None, before=None):
        action = Action(
            politician_id=sample_politician.id,
            target_wikidata_statement_id=target_wikidata_statement_id,
            before=before,
            after=after,
        )
        db_session.add(action)
        db_session.flush()
        db_session.refresh(action)
        return action

    return _create


class TestActionCreation:
    """Actions carry an untargeted or targeted fact proposal."""

    def test_create_statement_action(
        self, db_session, sample_politician, position_entity, create_action
    ):
        after = fact("P39", "Q30185")
        action = create_action(after)

        assert action.target_wikidata_statement_id is None
        assert action.before is None
        assert action.after == after
        assert action.references_to_add == []
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
                "qualifiers": [],
                "references": [],
            },
        )
        db_session.add(statement)
        db_session.flush()

        after = fact(
            "P569",
            {"time": "+1980-01-01T00:00:00Z", "precision": 11},
            qualifiers=[
                {
                    "property": {"id": "P585", "data_type": "time"},
                    "value": {
                        "type": "value",
                        "content": {"time": "+1980-01-01T00:00:00Z", "precision": 11},
                    },
                }
            ],
        )
        action = create_action(
            after,
            target_wikidata_statement_id=statement.wikidata_statement_id,
            before=statement_fact(statement.document),
        )

        assert action.target_wikidata_statement_id == "Q42$birth-1"
        assert action.before == statement_fact(statement.document)
        assert action.after == after
        assert action.applied_wikidata_statement_id is None

    @pytest.mark.parametrize("has_target", [True, False])
    def test_target_and_before_must_be_paired(
        self, db_session, create_action, has_target
    ):
        after = fact("P569", {"time": "+1980-01-01T00:00:00Z", "precision": 11})
        with (
            pytest.raises(IntegrityError, match="ck_actions_target_before"),
            db_session.begin_nested(),
        ):
            create_action(
                after,
                target_wikidata_statement_id="Q42$birth-1" if has_target else None,
                before=None if has_target else after,
            )

    def test_lifecycle_fields_default_null(
        self, db_session, sample_politician, create_action
    ):
        action = create_action(
            fact(
                "P569",
                {"time": "+1980-01-01T00:00:00Z", "precision": 11},
                "time",
            )
        )

        assert action.is_accepted is None
        assert action.decided_by_user_id is None
        assert action.decided_at is None
        assert action.applied_at is None
        assert action.applied_wikidata_statement_id is None
        assert action.error is None


class TestActionGeneratedEntityId:
    """entity_id derives from the after value of untargeted actions only."""

    def test_non_entity_create_body_entity_id_null(self, db_session, create_action):
        action = create_action(
            fact(
                "P569",
                {"time": "+1980-01-01T00:00:00Z", "precision": 11},
                "time",
            )
        )
        assert action.entity_id is None

    def test_targeted_action_entity_id_null_even_for_entity_property(
        self, db_session, position_entity, create_action
    ):
        action = create_action(
            fact("P39", "Q30185"),
            target_wikidata_statement_id="Q42$p39-1",
            before=fact("P39", "Q30185"),
        )
        assert action.entity_id is None


class TestActionEvidence:
    """Evidence pairs are unique per (action, source)."""

    def test_multiple_sources_allowed(self, db_session, create_action, create_source):
        action = create_action(fact("P569"))
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
        action = create_action(fact("P569"))
        db_session.add(ActionEvidence(action_id=action.id, source_id=sample_source.id))
        db_session.flush()
        db_session.add(ActionEvidence(action_id=action.id, source_id=sample_source.id))

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestActionClaims:
    """Unreleased claims are unique per action; released claims remain as history."""

    def test_claim_created(self, db_session, create_action):
        action = create_action(fact("P569"))
        claim = ActionClaim(action_id=action.id, user_id="user123")
        db_session.add(claim)
        db_session.flush()
        db_session.refresh(claim)

        assert claim.user_id == "user123"
        assert claim.claimed_at is not None

    def test_second_unreleased_claim_for_same_action_rejected(
        self, db_session, create_action
    ):
        action = create_action(fact("P569"))
        db_session.add(ActionClaim(action_id=action.id, user_id="user123"))
        db_session.flush()
        db_session.add(ActionClaim(action_id=action.id, user_id="user456"))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_released_claim_allows_new_claim_for_same_action(
        self, db_session, create_action
    ):
        action = create_action(fact("P569"))
        first = ActionClaim(action_id=action.id, user_id="user123")
        db_session.add(first)
        db_session.flush()
        first.released_at = first.claimed_at
        db_session.add(ActionClaim(action_id=action.id, user_id="user456"))
        db_session.flush()

        assert db_session.query(ActionClaim).filter_by(action_id=action.id).count() == 2


class TestActionSkips:
    """Skips are unique per (user, action)."""

    def test_skip_created(self, db_session, create_action):
        action = create_action(fact("P569"))
        skip = ActionSkip(user_id="user123", action_id=action.id)
        db_session.add(skip)
        db_session.flush()

        assert skip.user_id == "user123"

    def test_duplicate_skip_rejected(self, db_session, create_action):
        action = create_action(fact("P569"))
        db_session.add(ActionSkip(user_id="user123", action_id=action.id))
        db_session.flush()
        db_session.add(ActionSkip(user_id="user123", action_id=action.id))

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_other_users_and_actions_allowed(self, db_session, create_action):
        action = create_action(fact("P569"))
        other_action = create_action(fact("P570"))
        db_session.add_all(
            [
                ActionSkip(user_id="user123", action_id=action.id),
                ActionSkip(user_id="user456", action_id=action.id),
                ActionSkip(user_id="user123", action_id=other_action.id),
            ]
        )
        db_session.flush()

        assert db_session.query(ActionSkip).count() == 3
