"""Tests for the claim-based action review queue."""

import uuid
from datetime import UTC, datetime, timedelta

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
from poliloom.review_queue import claim_next, count_serveable

from .conftest import make_terms


def birth_date_payload():
    """Build a CREATE_STATEMENT payload for a birth-date statement."""
    return {
        "statement": {
            "id": "Q42$birth-new",
            "rank": "normal",
            "property": {"id": "P569", "data_type": "time"},
            "value": {
                "type": "value",
                "content": {"time": "+1980-01-01T00:00:00Z", "precision": 11},
            },
        }
    }


@pytest.fixture
def create_action(db_session):
    """Factory to create actions with optional evidence sources."""

    def _create(politician, *, sources=(), is_accepted=None):
        action = Action(
            politician_id=politician.id,
            kind=ActionKind.CREATE_STATEMENT,
            payload=birth_date_payload(),
            is_accepted=is_accepted,
        )
        if sources:
            action.evidence = [
                ActionEvidence(source_id=source.id) for source in sources
            ]
        db_session.add(action)
        db_session.flush()
        return action

    return _create


@pytest.fixture
def create_citizenship(db_session):
    """Factory to create live P27 citizenship statements."""

    def _create(politician, country):
        statement = Statement(
            politician_id=politician.id,
            document={
                "id": f"{politician.wikidata_id}$p27-{uuid.uuid4()}",
                "rank": "normal",
                "property": {"id": "P27", "data_type": "wikibase-item"},
                "value": {"type": "value", "content": country.wikidata_id},
            },
        )
        db_session.add(statement)
        db_session.flush()
        return statement

    return _create


class TestReviewQueue:
    def test_claims_basic_serve(
        self, db_session, sample_politician, sample_source, create_action
    ):
        action = create_action(sample_politician, sources=[sample_source])

        assert claim_next(db_session, "user-a", ["Q1860"]) == "Q123456"
        claim = db_session.query(ActionClaim).filter_by(action_id=action.id).one()
        assert claim.user_id == "user-a"
        assert claim_next(db_session, "user-a", ["Q1860"]) is None

    def test_excludes_decided_actions_and_soft_deleted_entities(
        self, db_session, sample_politician, sample_source, create_action
    ):
        create_action(sample_politician, is_accepted=True)
        create_action(sample_politician, is_accepted=False)
        assert claim_next(db_session, "user", ["Q1860"]) is None

        create_action(sample_politician, sources=[sample_source])
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()
        assert claim_next(db_session, "user", ["Q1860"]) is None

    def test_language_filter_and_evidenceless_visibility(
        self,
        db_session,
        sample_politician,
        sample_language,
        create_source,
        create_action,
    ):
        source = create_source(
            url="https://en.example/test",
            url_hash="english",
            languages=[sample_language],
        )
        create_action(sample_politician, sources=[source])
        assert count_serveable(db_session, ["Q188"]) == 0
        assert count_serveable(db_session, ["Q1860"]) == 1

        create_action(sample_politician)
        assert count_serveable(db_session, ["Q188"]) == 1

    def test_unknown_source_language_is_visible_to_everyone(
        self, db_session, sample_politician, sample_source, create_action
    ):
        create_action(sample_politician, sources=[sample_source])
        assert count_serveable(db_session, ["Q188"]) == 1

    def test_country_filter(
        self,
        db_session,
        sample_politician,
        sample_country,
        create_action,
        create_citizenship,
    ):
        create_citizenship(sample_politician, sample_country)
        create_action(sample_politician)
        assert count_serveable(db_session, ["Q1860"], ["Q30"]) == 1
        assert count_serveable(db_session, ["Q1860"], ["Q183"]) == 0

    def test_skips_are_per_user_but_count_is_user_agnostic(
        self, db_session, sample_politician, sample_source, create_action
    ):
        action = create_action(sample_politician, sources=[sample_source])
        db_session.add(ActionSkip(user_id="user-a", action_id=action.id))
        db_session.flush()
        assert count_serveable(db_session, ["Q1860"]) == 1
        assert claim_next(db_session, "user-a", ["Q1860"]) is None
        assert claim_next(db_session, "user-b", ["Q1860"]) == "Q123456"

    def test_disjoint_languages_can_claim_same_politician(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_german_language,
        create_source,
        create_action,
    ):
        english = create_source(
            url="https://en.example/claim",
            url_hash="claim-en",
            languages=[sample_language],
        )
        german = create_source(
            url="https://de.example/claim",
            url_hash="claim-de",
            languages=[sample_german_language],
        )
        create_action(sample_politician, sources=[english])
        create_action(sample_politician, sources=[german])

        assert claim_next(db_session, "user-a", ["Q1860"]) == "Q123456"
        assert claim_next(db_session, "user-b", ["Q188"]) == "Q123456"
        assert claim_next(db_session, "user-c", ["Q1860"]) is None

    def test_housekeeping_keeps_two_most_recent_politicians(
        self, db_session, sample_source, create_action
    ):
        politicians = []
        for number in (7001, 7002, 7003):
            politician = Politician.create_with_entity(
                db_session, f"Q{number}", make_terms(f"Politician {number}")
            )
            db_session.add(politician)
            db_session.flush()
            create_action(politician, sources=[sample_source])
            politicians.append(politician)
        db_session.flush()

        served = []
        for index in range(3):
            served.append(claim_next(db_session, "user-a", ["Q1860"]))
            if index < 2:
                claim = (
                    db_session.query(ActionClaim)
                    .join(Action, ActionClaim.action_id == Action.id)
                    .join(Politician, Action.politician_id == Politician.id)
                    .filter(Politician.wikidata_id == served[-1])
                    .one()
                )
                claim.claimed_at = datetime.now(UTC) - timedelta(minutes=3 - index)
                db_session.commit()
        assert set(served) == {politician.wikidata_id for politician in politicians}

        claimed_politicians = {
            politician_id
            for (politician_id,) in db_session.query(Action.politician_id)
            .join(ActionClaim, ActionClaim.action_id == Action.id)
            .filter(ActionClaim.user_id == "user-a")
            .all()
        }
        ids_by_qid = {
            politician.wikidata_id: politician.id for politician in politicians
        }
        assert claimed_politicians == {ids_by_qid[qid] for qid in served[-2:]}

    def test_other_and_own_live_claims_exclude_but_expired_claim_does_not(
        self, db_session, sample_politician, sample_source, create_action
    ):
        action = create_action(sample_politician, sources=[sample_source])
        db_session.add(ActionClaim(user_id="user-a", action_id=action.id))
        db_session.commit()
        assert claim_next(db_session, "user-b", ["Q1860"]) is None
        assert claim_next(db_session, "user-a", ["Q1860"]) is None

        claim = db_session.query(ActionClaim).filter_by(action_id=action.id).one()
        claim.claimed_at = datetime.now(UTC) - timedelta(hours=1)
        db_session.commit()
        assert claim_next(db_session, "user-b", ["Q1860"]) == "Q123456"
        assert (
            db_session.query(ActionClaim).filter_by(action_id=action.id).one().user_id
            == "user-b"
        )
