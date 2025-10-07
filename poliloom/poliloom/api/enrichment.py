"""Enrichment API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ..enrichment import enrich_until_target
from .auth import get_current_user, User

router = APIRouter()


@router.post("/enrich")
async def enrich_politicians(
    background_tasks: BackgroundTasks,
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter by language QIDs - enrich politicians with Wikipedia links in these languages",
    ),
    countries: Optional[List[str]] = Query(
        default=None,
        description="Filter by country QIDs - enrich politicians with citizenship for these countries",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Enrich politicians until at least one has unevaluated statements, then continue in background.

    This endpoint will:
    1. Enrich politicians until at least 1 has unevaluated statements (fast response)
    2. Queue a background task to continue enriching until 10 have unevaluated statements

    Returns:
        JSON with enriched_count showing how many politicians were enriched before returning
    """
    # Enrich until at least 1 politician has unevaluated statements
    count = await enrich_until_target(1, languages, countries)

    # Queue background task to reach target of 10
    background_tasks.add_task(enrich_until_target, 10, languages, countries)

    return {"enriched_count": count}
