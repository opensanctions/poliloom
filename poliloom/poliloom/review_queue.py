"""Claim-based queries for the unevaluated politician review queue."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    Politician,
    Property,
    PropertyClaim,
    PropertyReference,
    PropertySkip,
    SourceLanguage,
)
from .models.property import active_citizenship_conditions


def get_claim_ttl() -> timedelta:
    """Return the amount of time a review claim remains live."""
    return timedelta(minutes=int(os.getenv("CLAIM_TTL_MINUTES", "30")))


def _claim_cutoff() -> datetime:
    return datetime.now(UTC) - get_claim_ttl()


def language_visible(property_model, languages: list[str] | None):
    """Return the shared property language-visibility SQL predicate."""
    if languages is None:
        return True

    has_reference = exists(
        select(1).where(PropertyReference.property_id == property_model.id)
    )
    has_requested_language = exists(
        select(1)
        .select_from(PropertyReference)
        .join(
            SourceLanguage,
            SourceLanguage.source_id == PropertyReference.source_id,
        )
        .where(
            PropertyReference.property_id == property_model.id,
            SourceLanguage.language_id.in_(languages),
        )
    )
    has_unknown_language_reference = exists(
        select(1).where(
            PropertyReference.property_id == property_model.id,
            ~exists(
                select(1).where(SourceLanguage.source_id == PropertyReference.source_id)
            ),
        )
    )
    return or_(~has_reference, has_requested_language, has_unknown_language_reference)


def unevaluated(property_model=Property):
    """Return the shared unevaluated-property SQL predicate."""
    return and_(
        property_model.deleted_at.is_(None), property_model.statement_id.is_(None)
    )


def not_skipped(property_model, user_id: str):
    """Return a predicate excluding properties skipped by ``user_id``."""
    return ~exists(
        select(1).where(
            PropertySkip.property_id == property_model.id,
            PropertySkip.user_id == user_id,
        )
    )


def no_live_claim(property_model=Property, *, cutoff=None):
    """Return a predicate excluding properties with any live claim."""
    cutoff = cutoff or _claim_cutoff()
    return ~exists(
        select(1).where(
            PropertyClaim.property_id == property_model.id,
            PropertyClaim.claimed_at > cutoff,
        )
    )


def available_to_user(property_model, user_id: str, *, cutoff=None):
    """Return a predicate allowing unclaimed properties or this user's claims."""
    cutoff = cutoff or _claim_cutoff()
    return or_(
        no_live_claim(property_model, cutoff=cutoff),
        exists(
            select(1).where(
                PropertyClaim.property_id == property_model.id,
                PropertyClaim.user_id == user_id,
            )
        ),
    )


def _serveable_properties(
    politician_id,
    languages: list[str] | None,
    *,
    user_id: str | None = None,
    cutoff=None,
):
    conditions = [
        Property.politician_id == politician_id,
        unevaluated(Property),
        language_visible(Property, languages),
        no_live_claim(Property, cutoff=cutoff),
    ]
    if user_id is not None:
        conditions.append(not_skipped(Property, user_id))
    return select(Property.id).where(*conditions)


def _candidate_query(
    languages: list[str] | None,
    countries: list[str] | None,
    *,
    user_id: str | None = None,
    cutoff=None,
):
    query = Politician.query_base().where(
        exists(
            _serveable_properties(
                Politician.id, languages, user_id=user_id, cutoff=cutoff
            )
        )
    )
    if countries:
        query = query.where(
            exists(
                select(1).where(
                    *active_citizenship_conditions(
                        Property,
                        politician_id=Politician.id,
                        countries=countries,
                    )
                )
            )
        )
    return query


def _prune_claims(db: Session, user_id: str, cutoff: datetime) -> None:
    db.execute(delete(PropertyClaim).where(PropertyClaim.claimed_at <= cutoff))

    recent_politicians = (
        db.execute(
            select(Property.politician_id)
            .join(PropertyClaim, PropertyClaim.property_id == Property.id)
            .where(PropertyClaim.user_id == user_id)
            .group_by(Property.politician_id)
            .order_by(func.max(PropertyClaim.claimed_at).desc())
            .limit(2)
        )
        .scalars()
        .all()
    )
    if len(recent_politicians) < 2:
        return
    db.execute(
        delete(PropertyClaim).where(
            PropertyClaim.user_id == user_id,
            PropertyClaim.property_id.in_(
                select(Property.id).where(
                    Property.politician_id.notin_(recent_politicians)
                )
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

            # Expired rows cannot retain the unique property_id slot.
            db.execute(delete(PropertyClaim).where(PropertyClaim.claimed_at <= cutoff))
            property_ids = db.scalars(
                _serveable_properties(
                    politician_id, languages, user_id=user_id, cutoff=cutoff
                )
            ).all()
            if not property_ids:
                db.rollback()
                continue

            db.add_all(
                [
                    PropertyClaim(property_id=property_id, user_id=user_id)
                    for property_id in property_ids
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
    """Claim all rendered unevaluated properties while its politician is locked."""
    cutoff = _claim_cutoff()
    politician_property_ids = select(Property.id).where(
        Property.politician_id == politician.id
    )
    db.execute(
        delete(PropertyClaim).where(
            PropertyClaim.property_id.in_(politician_property_ids),
            PropertyClaim.claimed_at <= cutoff,
        )
    )
    db.execute(
        update(PropertyClaim)
        .where(
            PropertyClaim.user_id == user_id,
            PropertyClaim.property_id.in_(politician_property_ids),
        )
        .values(claimed_at=func.now())
    )
    claimed_ids = select(PropertyClaim.property_id)
    property_ids = db.scalars(
        select(Property.id).where(
            Property.politician_id == politician.id,
            unevaluated(Property),
            language_visible(Property, languages),
            not_skipped(Property, user_id),
            Property.id.notin_(claimed_ids),
        )
    ).all()
    db.add_all(
        [
            PropertyClaim(property_id=property_id, user_id=user_id)
            for property_id in property_ids
        ]
    )


def refresh_claims(db: Session, user_id: str, politician_id) -> None:
    """Refresh this user's claims for one politician."""
    db.execute(
        update(PropertyClaim)
        .where(
            PropertyClaim.user_id == user_id,
            PropertyClaim.property_id.in_(
                select(Property.id).where(Property.politician_id == politician_id)
            ),
        )
        .values(claimed_at=func.now())
    )


def count_serveable(
    db: Session,
    languages: list[str] | None,
    countries: list[str] | None = None,
) -> int:
    """Count politicians with user-agnostic, currently serveable properties."""
    query = _candidate_query(languages, countries).with_only_columns(
        func.count(Politician.id)
    )
    return db.scalar(query) or 0
