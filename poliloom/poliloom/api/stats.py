"""API endpoint for community statistics."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, case, exists, func, literal_column, select
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import Country, Evaluation, Politician, Property
from ..models.base import PropertyType
from ..models.wikidata import WikidataEntity
from .auth import User, get_current_user

router = APIRouter()


class EvaluationCountResponse(BaseModel):
    """Response schema for total evaluation count."""

    total: int


@router.get("/count", response_model=EvaluationCountResponse)
async def get_evaluation_count(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get total number of evaluations.
    """
    total = db.execute(select(func.count()).select_from(Evaluation)).scalar() or 0
    return EvaluationCountResponse(total=total)


class EvaluationTimeseriesPoint(BaseModel):
    """Single point in the evaluation timeseries."""

    date: str  # ISO date string (YYYY-MM-DD) - start of week
    accepted: int
    rejected: int


class CountryCoverage(BaseModel):
    """Coverage statistics for a single country."""

    wikidata_id: str
    name: str
    evaluated_count: int
    total_count: int


class StatsResponse(BaseModel):
    """Response schema for stats endpoint."""

    evaluations_timeseries: List[EvaluationTimeseriesPoint]
    country_coverage: List[CountryCoverage]
    stateless_evaluated_count: int
    stateless_total_count: int
    cooldown_days: int


@router.get("", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get community statistics including evaluation timeseries and country coverage.

    Returns:
    - evaluations_timeseries: Weekly counts of accepted/rejected evaluations for cooldown period
    - country_coverage: For each country, count of politicians with evaluated extractions vs total
    - stateless_evaluated_count: Politicians with only extracted citizenships that have evaluations
    - stateless_total_count: Total politicians without Wikidata citizenship
    - cooldown_days: The current cooldown period setting in days
    """
    cooldown_days = Politician.get_enrichment_cooldown_days()
    cooldown_cutoff = Politician.get_enrichment_cooldown_cutoff()

    # 1. Evaluations timeseries - weeks within cooldown period
    # Generate all weeks in the range, then fill with data
    num_weeks = cooldown_days // 7

    # Get the start of the current week (Monday)
    now = datetime.now(timezone.utc)
    current_week_start = now - timedelta(days=now.weekday())
    current_week_start = current_week_start.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Generate all week starts
    all_weeks = [
        current_week_start - timedelta(weeks=i) for i in range(num_weeks - 1, -1, -1)
    ]

    # Query actual evaluation data
    week_column = func.date_trunc("week", Evaluation.created_at).label("week")
    timeseries_query = (
        select(
            week_column,
            func.sum(case((Evaluation.is_accepted == True, 1), else_=0)).label(  # noqa: E712
                "accepted"
            ),
            func.sum(case((Evaluation.is_accepted == False, 1), else_=0)).label(  # noqa: E712
                "rejected"
            ),
        )
        .where(Evaluation.created_at >= cooldown_cutoff)
        .group_by(literal_column("week"))
        .order_by(literal_column("week"))
    )

    timeseries_results = db.execute(timeseries_query).all()

    # Build lookup from query results
    data_by_week: Dict[str, tuple] = {
        row.week.strftime("%Y-%m-%d"): (int(row.accepted or 0), int(row.rejected or 0))
        for row in timeseries_results
    }

    # Fill in all weeks, using 0 for missing data
    evaluations_timeseries = [
        EvaluationTimeseriesPoint(
            date=week.strftime("%Y-%m-%d"),
            accepted=data_by_week.get(week.strftime("%Y-%m-%d"), (0, 0))[0],
            rejected=data_by_week.get(week.strftime("%Y-%m-%d"), (0, 0))[1],
        )
        for week in all_weeks
    ]

    # 2. Country coverage - politicians with evaluated extractions vs total per country
    # A politician is "evaluated" if they have any extracted property with an evaluation
    # created within the cooldown period

    # Pre-compute evaluated politician IDs (CTE for reuse)
    evaluated_politicians_cte = (
        select(Property.politician_id)
        .join(Evaluation, Evaluation.property_id == Property.id)
        .where(
            and_(
                Property.archived_page_id.isnot(None),  # Extracted property
                Property.deleted_at.is_(None),
                Evaluation.created_at >= cooldown_cutoff,
            )
        )
        .distinct()
        .cte("evaluated_politicians")
    )

    # Subquery to get all country wikidata_ids for filtering
    country_ids_subquery = select(Country.wikidata_id).scalar_subquery()

    # CTE 1: Total politicians per country (optimized - aggregate first, then join)
    # Uses idx_properties_type_entity index efficiently by filtering to country IDs
    country_totals_cte = (
        select(
            Property.entity_id.label("wikidata_id"),
            func.count(Property.politician_id).label("total_count"),
        )
        .where(
            and_(
                Property.type == PropertyType.CITIZENSHIP,
                Property.deleted_at.is_(None),
                Property.entity_id.in_(country_ids_subquery),
            )
        )
        .group_by(Property.entity_id)
        .cte("country_totals")
    )

    # CTE 2: Evaluated politicians per country (join citizenship with evaluated)
    citizenship_prop = Property.__table__.alias("citizenship_prop")
    country_evaluated_cte = (
        select(
            citizenship_prop.c.entity_id.label("wikidata_id"),
            func.count(citizenship_prop.c.politician_id).label("evaluated_count"),
        )
        .select_from(citizenship_prop)
        .join(
            evaluated_politicians_cte,
            evaluated_politicians_cte.c.politician_id
            == citizenship_prop.c.politician_id,
        )
        .where(
            and_(
                citizenship_prop.c.type == PropertyType.CITIZENSHIP,
                citizenship_prop.c.deleted_at.is_(None),
                citizenship_prop.c.entity_id.in_(country_ids_subquery),
            )
        )
        .group_by(citizenship_prop.c.entity_id)
        .cte("country_evaluated")
    )

    # Final query: join totals with evaluated counts and country names
    country_stats_query = (
        select(
            country_totals_cte.c.wikidata_id,
            WikidataEntity.name,
            country_totals_cte.c.total_count,
            func.coalesce(country_evaluated_cte.c.evaluated_count, 0).label(
                "evaluated_count"
            ),
        )
        .select_from(country_totals_cte)
        .join(
            WikidataEntity,
            and_(
                WikidataEntity.wikidata_id == country_totals_cte.c.wikidata_id,
                WikidataEntity.deleted_at.is_(None),
            ),
        )
        .outerjoin(
            country_evaluated_cte,
            country_evaluated_cte.c.wikidata_id == country_totals_cte.c.wikidata_id,
        )
        .order_by(country_totals_cte.c.total_count.desc())
    )

    country_results = db.execute(country_stats_query).all()

    country_coverage = [
        CountryCoverage(
            wikidata_id=row.wikidata_id,
            name=row.name,
            evaluated_count=int(row.evaluated_count or 0),
            total_count=int(row.total_count or 0),
        )
        for row in country_results
    ]

    # 3. Stateless politicians - those without Wikidata citizenship (only extracted)
    # has_wikidata_citizenship: politician has a citizenship from Wikidata (has statement_id)
    has_wikidata_citizenship = exists(
        select(1).where(
            and_(
                Property.politician_id == Politician.id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.statement_id.isnot(None),
                Property.deleted_at.is_(None),
            )
        )
    )

    # has_evaluated_extracted_citizenship: politician has an extracted citizenship with evaluation
    has_evaluated_extracted_citizenship = exists(
        select(1)
        .select_from(Property)
        .join(Evaluation, Evaluation.property_id == Property.id)
        .where(
            and_(
                Property.politician_id == Politician.id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.archived_page_id.isnot(None),  # Extracted
                Property.deleted_at.is_(None),
                Evaluation.created_at >= cooldown_cutoff,
            )
        )
    )

    # Count total stateless (no Wikidata citizenship)
    stateless_total_count = (
        db.execute(
            select(func.count())
            .select_from(Politician)
            .join(WikidataEntity, Politician.wikidata_id == WikidataEntity.wikidata_id)
            .where(
                and_(
                    WikidataEntity.deleted_at.is_(None),
                    ~has_wikidata_citizenship,
                )
            )
        ).scalar()
        or 0
    )

    # Count stateless with evaluated extracted citizenships
    stateless_evaluated_count = (
        db.execute(
            select(func.count())
            .select_from(Politician)
            .join(WikidataEntity, Politician.wikidata_id == WikidataEntity.wikidata_id)
            .where(
                and_(
                    WikidataEntity.deleted_at.is_(None),
                    ~has_wikidata_citizenship,
                    has_evaluated_extracted_citizenship,
                )
            )
        ).scalar()
        or 0
    )

    return StatsResponse(
        evaluations_timeseries=evaluations_timeseries,
        country_coverage=country_coverage,
        stateless_evaluated_count=stateless_evaluated_count,
        stateless_total_count=stateless_total_count,
        cooldown_days=cooldown_days,
    )
