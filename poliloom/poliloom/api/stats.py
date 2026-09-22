"""API endpoint for community statistics."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, case, exists, func, literal_column, select
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..enrichment_queue import (
    get_enrichment_cooldown_cutoff,
    get_enrichment_cooldown_days,
)
from ..models import Action, Politician
from ..models.source import PoliticianSource, Source
from ..models.statement import Statement, active_citizenship_conditions
from ..models.wikidata import WikidataEntity
from .auth import User, get_current_user
from .schemas import TermMaps

router = APIRouter()


class DecisionCountResponse(BaseModel):
    """Response schema for total decided-action count."""

    total: int


@router.get("/count", response_model=DecisionCountResponse)
async def get_decision_count(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get total number of decided actions (accepted or discarded).
    """
    total = (
        db.execute(
            select(func.count())
            .select_from(Action)
            .where(Action.is_accepted.isnot(None))
        ).scalar()
        or 0
    )
    return DecisionCountResponse(total=total)


class DecisionTimeseriesPoint(BaseModel):
    """Single point in the decision timeseries."""

    date: str  # ISO date string (YYYY-MM-DD) - start of week
    accepted: int
    discarded: int


class CountryCoverage(BaseModel):
    """Coverage statistics for a country or politicians without citizenship."""

    wikidata_id: str | None  # None for politicians without citizenship
    terms: TermMaps | None  # None for politicians without citizenship
    decided_count: int  # Politicians with actions decided within cooldown period
    enriched_count: int  # Politicians enriched within cooldown period
    total_count: int  # Total politicians (all, regardless of enrichment)


class StatsResponse(BaseModel):
    """Response schema for stats endpoint."""

    decisions_timeseries: list[DecisionTimeseriesPoint]
    country_coverage: list[CountryCoverage]  # Includes a no-citizenship group
    cooldown_days: int


@router.get("", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get community statistics including decision timeseries and country coverage.

    Returns:
    - decisions_timeseries: Weekly counts of accepted/discarded actions
      (keyed by decided_at) for the cooldown period
    - country_coverage: Politicians grouped by live P27 citizenship statements,
      plus a null-terms bucket for politicians without citizenship
    - cooldown_days: The current cooldown period setting in days
    """
    cooldown_days = get_enrichment_cooldown_days()
    cooldown_cutoff = get_enrichment_cooldown_cutoff()

    # 1. Decisions timeseries - weeks within cooldown period
    # Generate all weeks in the range, then fill with data
    num_weeks = cooldown_days // 7

    # Get the start of the current week (Monday)
    now = datetime.now(UTC)
    current_week_start = now - timedelta(days=now.weekday())
    current_week_start = current_week_start.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Generate all week starts
    all_weeks = [
        current_week_start - timedelta(weeks=i) for i in range(num_weeks - 1, -1, -1)
    ]

    # Query actual decision data
    week_column = func.date_trunc("week", Action.decided_at).label("week")
    timeseries_query = (
        select(
            week_column,
            func.sum(case((Action.is_accepted == True, 1), else_=0)).label("accepted"),
            func.sum(case((Action.is_accepted == False, 1), else_=0)).label(
                "discarded"
            ),
        )
        .where(
            Action.is_accepted.isnot(None),
            Action.decided_at >= cooldown_cutoff,
        )
        .group_by(literal_column("week"))
        .order_by(literal_column("week"))
    )

    timeseries_results = db.execute(timeseries_query).all()

    # Build lookup from query results
    data_by_week: dict[str, tuple] = {
        row.week.strftime("%Y-%m-%d"): (int(row.accepted or 0), int(row.discarded or 0))
        for row in timeseries_results
    }

    # Fill in all weeks, using 0 for missing data
    decisions_timeseries = [
        DecisionTimeseriesPoint(
            date=week.strftime("%Y-%m-%d"),
            accepted=data_by_week.get(week.strftime("%Y-%m-%d"), (0, 0))[0],
            discarded=data_by_week.get(week.strftime("%Y-%m-%d"), (0, 0))[1],
        )
        for week in all_weeks
    ]

    # 2. Country coverage - all politicians grouped by live P27 citizenship
    # statements. Shows total, enriched (within cooldown), and decided counts.

    # CTE: Politicians with actions decided within cooldown
    decided_politicians_cte = (
        select(Action.politician_id)
        .where(
            Action.is_accepted.isnot(None),
            Action.decided_at >= cooldown_cutoff,
        )
        .distinct()
        .cte("decided_politicians")
    )

    # Alias for country WikidataEntity (to avoid conflict with politician's entity)
    country_entity = WikidataEntity.__table__.alias("country_entity")
    enriched_recently = exists(
        select(1)
        .select_from(PoliticianSource)
        .join(Source, Source.id == PoliticianSource.source_id)
        .where(
            PoliticianSource.politician_id == Politician.id,
            Source.fetch_timestamp >= cooldown_cutoff,
        )
    )

    # Main query: Start from ALL politicians, LEFT JOIN to citizenship statements
    # Use conditional counting for enriched and decided
    coverage_query = (
        select(
            Statement.entity_id.label("wikidata_id"),
            country_entity.c.labels,
            country_entity.c.descriptions,
            country_entity.c.aliases,
            func.count(func.distinct(Politician.id)).label("total_count"),
            func.count(func.distinct(case((enriched_recently, Politician.id)))).label(
                "enriched_count"
            ),
            func.count(
                func.distinct(
                    case(
                        (
                            decided_politicians_cte.c.politician_id.isnot(None),
                            Politician.id,
                        )
                    )
                )
            ).label("decided_count"),
        )
        .select_from(Politician)
        # Join to the politician's WikidataEntity
        .join(
            WikidataEntity,
            WikidataEntity.wikidata_id == Politician.wikidata_id,
        )
        # LEFT JOIN to live Wikidata P27 citizenship statements
        .outerjoin(
            Statement,
            and_(
                *active_citizenship_conditions(Statement, politician_id=Politician.id),
            ),
        )
        # LEFT JOIN to get country terms (NULL when citizenship is absent)
        .outerjoin(
            country_entity,
            country_entity.c.wikidata_id == Statement.entity_id,
        )
        # LEFT JOIN to decided politicians CTE
        .outerjoin(
            decided_politicians_cte,
            decided_politicians_cte.c.politician_id == Politician.id,
        )
        .group_by(
            Statement.entity_id,
            country_entity.c.labels,
            country_entity.c.descriptions,
            country_entity.c.aliases,
        )
        .order_by(func.count(func.distinct(Politician.id)).desc())
    )

    country_results = db.execute(coverage_query).all()

    country_coverage = [
        CountryCoverage(
            wikidata_id=row.wikidata_id,
            terms=(
                TermMaps(
                    labels=row.labels,
                    descriptions=row.descriptions,
                    aliases=row.aliases,
                )
                if row.labels is not None
                else None
            ),
            decided_count=int(row.decided_count or 0),
            enriched_count=int(row.enriched_count or 0),
            total_count=int(row.total_count or 0),
        )
        for row in country_results
    ]

    return StatsResponse(
        decisions_timeseries=decisions_timeseries,
        country_coverage=country_coverage,
        cooldown_days=cooldown_days,
    )
