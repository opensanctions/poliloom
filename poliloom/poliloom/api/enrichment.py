"""Enrichment API endpoints."""

import os
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
    1. Enrich politicians until immediate target has unevaluated statements (fast response)
    2. Queue a background task to continue enriching until background target have unevaluated statements

    Environment variables:
        ENRICH_IMMEDIATE_TARGET: Number of politicians to enrich before responding (default: 1)
        ENRICH_BACKGROUND_TARGET: Number of politicians to enrich in background (default: 10)

    Returns:
        JSON with enriched_count showing how many politicians were enriched before returning
    """
    # Get targets from environment variables with defaults
    immediate_target = int(os.getenv("ENRICH_IMMEDIATE_TARGET", "1"))
    background_target = int(os.getenv("ENRICH_BACKGROUND_TARGET", "10"))

    # Enrich until immediate target is reached
    count = await enrich_until_target(immediate_target, languages, countries)

    # Queue background task to reach background target
    background_tasks.add_task(
        enrich_until_target, background_target, languages, countries
    )

    return {"enriched_count": count}
