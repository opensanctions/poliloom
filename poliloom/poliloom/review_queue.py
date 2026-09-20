"""Claim-based queries for the pending-action review queue."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    Action,
    ActionClaim,
    ActionEvidence,
    ActionSkip,
    Politician,
    SourceLanguage,
    Statement,
)
from .models.statement import active_citizenship_conditions


def get_claim_ttl() -> timedelta:
    """Return the amount of time a review claim remains live."""
    return timedelta(minutes=int(os.getenv("CLAIM_TTL_MINUTES", "30")))


def _claim_cutoff() -> datetime:
    return datetime.now(UTC) - get_claim_ttl()


def language_visible(action_model, languages: list[str] | None):
    """Return the shared action language-visibility SQL predicate."""
    if languages is None:
        return True

    has_evidence = exists(select(1).where(ActionEvidence.action_id == action_model.id))
    has_requested_language = exists(
        select(1)
        .select_from(ActionEvidence)
        .join(
            SourceLanguage,
            SourceLanguage.source_id == ActionEvidence.source_id,
        )
        .where(
            ActionEvidence.action_id == action_model.id,
            SourceLanguage.language_id.in_(languages),
        )
    )
    has_unknown_language_evidence = exists(
        select(1).where(
            ActionEvidence.action_id == action_model.id,
            ~exists(
                select(1).where(SourceLanguage.source_id == ActionEvidence.source_id)
            ),
        )
    )
    return or_(~has_evidence, has_requested_language, has_unknown_language_evidence)


def pending(action_model=Action):
    """Return the shared pending-action SQL predicate."""
    return action_model.is_accepted.is_(None)


def not_skipped(action_model, user_id: str):
    """Return a predicate excluding actions skipped by ``user_id``."""
    return ~exists(
        select(1).where(
            ActionSkip.action_id == action_model.id,
            ActionSkip.user_id == user_id,
        )
    )


def no_live_claim(action_model=Action, *, cutoff=None):
    """Return a predicate excluding actions with any live claim."""
    cutoff = cutoff or _claim_cutoff()
    return ~exists(
        select(1).where(
            ActionClaim.action_id == action_model.id,
            ActionClaim.claimed_at > cutoff,
        )
    )


def available_to_user(action_model, user_id: str, *, cutoff=None):
    """Return a predicate allowing unclaimed actions or this user's claims."""
    cutoff = cutoff or _claim_cutoff()
    return or_(
        no_live_claim(action_model, cutoff=cutoff),
        exists(
            select(1).where(
                ActionClaim.action_id == action_model.id,
                ActionClaim.user_id == user_id,
            )
        ),
    )


def _serveable_actions(
    politician_id,
    languages: list[str] | None,
    *,
    user_id: str | None = None,
    cutoff=None,
):
    conditions = [
        Action.politician_id == politician_id,
        pending(Action),
        language_visible(Action, languages),
        no_live_claim(Action, cutoff=cutoff),
    ]
    if user_id is not None:
        conditions.append(not_skipped(Action, user_id))
    return select(Action.id).where(*conditions)


def _candidate_query(
    languages: list[str] | None,
    countries: list[str] | None,
    *,
    user_id: str | None = None,
    cutoff=None,
):
    query = Politician.query_base().where(
        exists(
            _serveable_actions(Politician.id, languages, user_id=user_id, cutoff=cutoff)
        )
    )
    if countries:
        query = query.where(
            exists(
                select(1).where(
                    *active_citizenship_conditions(
                        Statement,
                        politician_id=Politician.id,
                        countries=countries,
                    )
                )
            )
        )
    return query


def _prune_claims(db: Session, user_id: str, cutoff: datetime) -> None:
    db.execute(delete(ActionClaim).where(ActionClaim.claimed_at <= cutoff))

    recent_politicians = (
        db.execute(
            select(Action.politician_id)
            .join(ActionClaim, ActionClaim.action_id == Action.id)
            .where(ActionClaim.user_id == user_id)
            .group_by(Action.politician_id)
            .order_by(func.max(ActionClaim.claimed_at).desc())
            .limit(2)
        )
        .scalars()
        .all()
    )
    if len(recent_politicians) < 2:
        return
    db.execute(
        delete(ActionClaim).where(
            ActionClaim.user_id == user_id,
            ActionClaim.action_id.in_(
                select(Action.id).where(Action.politician_id.notin_(recent_politicians))
            ),
        )
    )


def claim_next(
    db: Session,
    user_id: str,
    languages: list[str],
    countries: list[str] | None = None,
) -> str | None:
    """Atomically claim and return the next deterministic review candidate."""
    cutoff = _claim_cutoff()
    candidates = db.execute(
        _candidate_query(languages, countries, user_id=user_id, cutoff=cutoff)
        .with_only_columns(Politician.id, Politician.wikidata_id)
        .order_by(Politician.wikidata_id_numeric.asc())
        .limit(5)
    ).all()

    for politician_id, wikidata_id in candidates:
        try:
            locked = db.scalar(
                select(Politician.id)
                .where(Politician.id == politician_id)
                .with_for_update(of=Politician)
            )
            if locked is None:
                db.rollback()
                continue

            # Expired rows cannot retain the unique action_id slot.
            db.execute(delete(ActionClaim).where(ActionClaim.claimed_at <= cutoff))
            action_ids = db.scalars(
                _serveable_actions(
                    politician_id, languages, user_id=user_id, cutoff=cutoff
                )
            ).all()
            if not action_ids:
                db.rollback()
                continue

            db.add_all(
                [
                    ActionClaim(action_id=action_id, user_id=user_id)
                    for action_id in action_ids
                ]
            )
            db.flush()
            _prune_claims(db, user_id, cutoff)
            db.commit()
            return wikidata_id
        except IntegrityError:
            db.rollback()

    return None


def claim_visible_properties(
    db: Session,
    user_id: str,
    politician: Politician,
    languages: list[str],
) -> None:
    """Claim all rendered pending actions while its politician is locked."""
    cutoff = _claim_cutoff()
    politician_action_ids = select(Action.id).where(
        Action.politician_id == politician.id
    )
    db.execute(
        delete(ActionClaim).where(
            ActionClaim.action_id.in_(politician_action_ids),
            ActionClaim.claimed_at <= cutoff,
        )
    )
    db.execute(
        update(ActionClaim)
        .where(
            ActionClaim.user_id == user_id,
            ActionClaim.action_id.in_(politician_action_ids),
        )
        .values(claimed_at=func.now())
    )
    claimed_ids = select(ActionClaim.action_id)
    action_ids = db.scalars(
        select(Action.id).where(
            Action.politician_id == politician.id,
            pending(Action),
            language_visible(Action, languages),
            not_skipped(Action, user_id),
            Action.id.notin_(claimed_ids),
        )
    ).all()
    db.add_all(
        [ActionClaim(action_id=action_id, user_id=user_id) for action_id in action_ids]
    )


def refresh_claims(db: Session, user_id: str, politician_id) -> None:
    """Refresh this user's claims for one politician."""
    db.execute(
        update(ActionClaim)
        .where(
            ActionClaim.user_id == user_id,
            ActionClaim.action_id.in_(
                select(Action.id).where(Action.politician_id == politician_id)
            ),
        )
        .values(claimed_at=func.now())
    )


def count_serveable(
    db: Session,
    languages: list[str] | None,
    countries: list[str] | None = None,
) -> int:
    """Count politicians with user-agnostic, currently serveable actions."""
    query = _candidate_query(languages, countries).with_only_columns(
        func.count(Politician.id)
    )
    return db.scalar(query) or 0
