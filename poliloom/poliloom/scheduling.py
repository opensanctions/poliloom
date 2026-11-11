"""Scheduling: orchestration of the enrichment pipeline."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from .archiving import process_source
from .database import get_engine
from .enrichment_queue import create_enrichment_sources, enrichment_candidates_query
from .models import (
    Politician,
    Source,
)
from .review_queue import count_serveable

logger = logging.getLogger(__name__)


@dataclass
class ScheduledEnrichment:
    """Result of scheduling a politician for enrichment."""

    politician_id: Any
    wikidata_id: str
    source_ids: list


def schedule_enrichment(
    db: Session,
    languages: list[str],
    countries: list[str] | None = None,
) -> ScheduledEnrichment | None:
    """Pick the next politician and create sources for its Wikipedia links.

    Returns:
        ScheduledEnrichment if a politician was found, None otherwise.
    """
    query = (
        enrichment_candidates_query(
            languages=languages,
            countries=countries,
        )
        .order_by(Politician.wikidata_id_numeric.desc())
        .limit(1)
        .with_for_update(of=Politician, skip_locked=True)
    )

    politician = db.scalars(query).first()

    if not politician:
        return None

    try:
        sources = create_enrichment_sources(politician, db, languages=languages)

        if not sources:
            db.commit()
            return None

        logger.info(
            f"Processing {len(sources)} Wikipedia sources for "
            f"{politician.wikidata_entity.resolved_label}: "
            f"{[f'{s.wikipedia_project_id} ({s.url})' for s in sources]}"
        )

        db.commit()

        return ScheduledEnrichment(
            politician_id=politician.id,
            wikidata_id=politician.wikidata_id,
            source_ids=[s.id for s in sources],
        )

    except SQLAlchemyError as e:
        logger.error(
            f"Error scheduling enrichment for politician {politician.wikidata_id}: {e}"
        )
        db.rollback()
        return None


async def process_source_task(source_id, politician_id) -> int:
    """Background task entry point: opens a session and processes a source.

    Args:
        source_id: Source UUID
        politician_id: Politician UUID to extract properties for

    Returns:
        Number of properties extracted.
    """
    with Session(get_engine()) as db:
        source = db.execute(
            select(Source)
            .where(Source.id == source_id)
            .options(selectinload(Source.politicians))
        ).scalar_one()

        politician = db.execute(
            select(Politician)
            .where(Politician.id == politician_id)
            .options(
                selectinload(Politician.wikidata_entity),
                selectinload(Politician.statements),
            )
        ).scalar_one()

        return await process_source(db, source, politician)


async def process_enrichment(scheduled: ScheduledEnrichment) -> None:
    """Process all sources for a scheduled politician concurrently."""
    await asyncio.gather(
        *(
            process_source_task(source_id, scheduled.politician_id)
            for source_id in scheduled.source_ids
        )
    )


def _schedule_unless_serveable(
    languages: list[str], countries: list[str] | None
) -> ScheduledEnrichment | None:
    with Session(get_engine()) as db:
        if count_serveable(db, languages, countries) > 0:
            return None
        return schedule_enrichment(db, languages, countries)


async def enrich_until_serveable(
    languages: list[str],
    countries: list[str] | None = None,
) -> None:
    """Maintain a floor of one serveable politician for the given filters."""
    while True:
        scheduled = await run_in_threadpool(
            _schedule_unless_serveable, languages, countries
        )
        if scheduled is None:
            return
        await process_enrichment(scheduled)
