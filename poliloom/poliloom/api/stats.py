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


class EvaluationTimeseriesPoint(BaseModel):
    """Single point in the evaluation timeseries."""

    date: str  # ISO date string (YYYY-MM-DD) - start of week
    accepted: int
    rejected: int


class CountryCoverage(BaseModel):
    """Coverage statistics for a single country."""

    wikidata_id: str
    name: str
    enriched_count: int
    total_count: int


class StatsResponse(BaseModel):
    """Response schema for stats endpoint."""

    evaluations_timeseries: List[EvaluationTimeseriesPoint]
    country_coverage: List[CountryCoverage]
    stateless_enriched_count: int
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
    - country_coverage: For each country, count of recently enriched vs total politicians
    - stateless_enriched_count: Politicians without citizenship who were recently enriched
    - stateless_total_count: Total politicians without citizenship
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

    # 2. Country coverage - recently enriched vs total politicians per country
    country_stats_query = (
        select(
            Country.wikidata_id,
            WikidataEntity.name,
            func.count(func.distinct(Property.politician_id)).label("total_count"),
            func.count(
                func.distinct(
                    case(
                        (
                            Politician.enriched_at >= cooldown_cutoff,
                            Property.politician_id,
                        ),
                        else_=None,
                    )
                )
            ).label("enriched_count"),
        )
        .select_from(Country)
        .join(WikidataEntity, Country.wikidata_id == WikidataEntity.wikidata_id)
        .join(
            Property,
            and_(
                Property.entity_id == Country.wikidata_id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.deleted_at.is_(None),
            ),
        )
        .join(Politician, Property.politician_id == Politician.id)
        .where(WikidataEntity.deleted_at.is_(None))
        .group_by(Country.wikidata_id, WikidataEntity.name)
        .order_by(func.count(func.distinct(Property.politician_id)).desc())
    )

    country_results = db.execute(country_stats_query).all()

    country_coverage = [
        CountryCoverage(
            wikidata_id=row.wikidata_id,
            name=row.name,
            enriched_count=int(row.enriched_count or 0),
            total_count=int(row.total_count or 0),
        )
        for row in country_results
    ]

    # 3. Stateless politicians (no citizenship property)
    # Use NOT EXISTS with correlated subquery for efficiency (same pattern as enrichment logic)
    has_citizenship = exists(
        select(1).where(
            and_(
                Property.politician_id == Politician.id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.deleted_at.is_(None),
            )
        )
    )

    # Count total stateless
    stateless_total_count = (
        db.execute(
            select(func.count())
            .select_from(Politician)
            .join(WikidataEntity, Politician.wikidata_id == WikidataEntity.wikidata_id)
            .where(
                and_(
                    WikidataEntity.deleted_at.is_(None),
                    ~has_citizenship,
                )
            )
        ).scalar()
        or 0
    )

    # Count recently enriched stateless
    stateless_enriched_count = (
        db.execute(
            select(func.count())
            .select_from(Politician)
            .join(WikidataEntity, Politician.wikidata_id == WikidataEntity.wikidata_id)
            .where(
                and_(
                    WikidataEntity.deleted_at.is_(None),
                    ~has_citizenship,
                    Politician.enriched_at >= cooldown_cutoff,
                )
            )
        ).scalar()
        or 0
    )

    return StatsResponse(
        evaluations_timeseries=evaluations_timeseries,
        country_coverage=country_coverage,
        stateless_enriched_count=stateless_enriched_count,
        stateless_total_count=stateless_total_count,
        cooldown_days=cooldown_days,
    )
