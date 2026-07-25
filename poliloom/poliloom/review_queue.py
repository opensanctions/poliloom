"""Queries for the unevaluated politician review queue."""

from dataclasses import dataclass

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from .models import Politician, Property, PropertyReference, SourceLanguage
from .models.property import active_citizenship_conditions


@dataclass(frozen=True)
class ReviewQueueResult:
    """A randomly selected review candidate and the full matching pool size."""

    wikidata_id: str | None
    total: int


def _unevaluated_pool(
    languages: list[str] | None = None,
    countries: list[str] | None = None,
):
    """CTE of politicians with unevaluated extracted properties.

    Shared by candidate selection and buffer counting so both measure the
    same review pool.
    """
    unevaluated_conditions = [
        Property.politician_id == Politician.id,
        Property.statement_id.is_(None),
        Property.deleted_at.is_(None),
    ]

    unevaluated_query = select(1).select_from(Property)
    if languages:
        unevaluated_query = unevaluated_query.join(
            PropertyReference,
            PropertyReference.property_id == Property.id,
        ).join(
            SourceLanguage,
            SourceLanguage.source_id == PropertyReference.source_id,
        )
        unevaluated_conditions.append(SourceLanguage.language_id.in_(languages))

    pool_query = Politician.query_base().where(
        exists(unevaluated_query.where(and_(*unevaluated_conditions)))
    )

    if countries:
        pool_query = pool_query.where(
            exists(
                select(1).where(
                    *active_citizenship_conditions(
                        Property, politician_id=Politician.id, countries=countries
                    )
                )
            )
        )

    return (
        pool_query.with_only_columns(Politician.wikidata_id)
        .cte("unevaluated_pool")
        .prefix_with("MATERIALIZED")
    )


def count_unevaluated(
    db: Session,
    languages: list[str] | None = None,
    countries: list[str] | None = None,
) -> int:
    """Count politicians with unevaluated extracted properties (the review buffer)."""
    pool = _unevaluated_pool(languages, countries)
    return db.execute(select(func.count()).select_from(pool)).scalar() or 0


def get_random_unevaluated(
    db: Session,
    languages: list[str] | None = None,
    countries: list[str] | None = None,
    exclude_ids: list[str] | None = None,
) -> ReviewQueueResult:
    """Select a random candidate and count the full matching review pool.

    ``exclude_ids`` affects candidate selection only, not the total.
    """
    pool = _unevaluated_pool(languages, countries)

    candidate_query = select(pool.c.wikidata_id)
    if exclude_ids:
        candidate_query = candidate_query.where(pool.c.wikidata_id.notin_(exclude_ids))

    candidate_qid = candidate_query.order_by(func.random()).limit(1).scalar_subquery()
    total = select(func.count()).select_from(pool).scalar_subquery()
    wikidata_id, count = db.execute(select(candidate_qid, total)).one()

    return ReviewQueueResult(wikidata_id=wikidata_id, total=count or 0)
