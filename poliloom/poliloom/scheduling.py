"""Scheduling: orchestration of the enrichment pipeline."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .archiving import process_source
from .database import get_engine
from .enrichment_queue import create_enrichment_sources, enrichment_candidates_query
from .models import (
    Politician,
    Property,
    Source,
    WikidataEntity,
    WikidataRelation,
)
from .review_queue import count_serveable
from .sse import EnrichmentCompleteEvent, event_bus

logger = logging.getLogger(__name__)


@dataclass
class ScheduledEnrichment:
    """Result of scheduling a politician for enrichment."""

    politician_id: Any
    source_ids: list


def has_enrichment_candidate(
    db: Session,
    languages: list[str] | None = None,
    countries: list[str] | None = None,
) -> bool:
    """Return True if any politician is currently eligible for enrichment."""
    query = enrichment_candidates_query(languages=languages, countries=countries)
    return (
        db.scalars(query.with_only_columns(Politician.id).limit(1)).first() is not None
    )


def schedule_enrichment(
    db: Session,
    languages: list[str] | None = None,
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
        .options(
            selectinload(Politician.wikipedia_links),
        )
        .order_by(Politician.wikidata_id_numeric.desc())
        .limit(1)
        .with_for_update(skip_locked=True)
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
            f"Processing {len(sources)} Wikipedia sources for {politician.name}: "
            f"{[f'{s.wikipedia_project_id} ({s.url})' for s in sources]}"
        )

        db.commit()

        return ScheduledEnrichment(
            politician_id=politician.id,
            source_ids=[s.id for s in sources],
        )

    except Exception as e:
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
                selectinload(Politician.properties.and_(Property.deleted_at.is_(None)))
                .selectinload(Property.entity)
                .selectinload(
                    WikidataEntity.parent_relations.and_(
                        WikidataRelation.deleted_at.is_(None)
                    )
                )
                .selectinload(WikidataRelation.parent_entity),
            )
        ).scalar_one()

        return await process_source(db, source, politician)


async def process_next_politician(
    languages: list[str] | None = None,
    countries: list[str] | None = None,
) -> int | None:
    """Schedule and process enrichment for a single politician.

    Broadcasts EnrichmentCompleteEvent only when there's something for waiting
    clients to act on: new unevaluated data (clients re-check /next and find
    the politician) or no candidate available (clients settle on the
    all-caught-up state). Dry passes stay silent — callers chain the next
    candidate themselves, so waking clients would only trigger
    redundant /next polls.

    Returns:
        Number of properties extracted, or None if no politician was available.
    """
    with Session(get_engine()) as db:
        scheduled = schedule_enrichment(db, languages, countries)

    extracted = None
    try:
        if scheduled:
            counts = await asyncio.gather(
                *(
                    process_source_task(source_id, scheduled.politician_id)
                    for source_id in scheduled.source_ids
                )
            )
            extracted = sum(counts)
    finally:
        if extracted is None or extracted > 0:
            with Session(get_engine()) as db:
                event_bus.notify(
                    EnrichmentCompleteEvent(
                        languages=languages or [],
                        countries=countries or [],
                    ),
                    db,
                )
                db.commit()

    return extracted


async def enrich_until_serveable(
    languages: list[str] | None = None,
    countries: list[str] | None = None,
) -> int:
    """Maintain a floor of one serveable politician for the given filters."""
    enriched = 0

    while True:
        with Session(get_engine()) as db:
            if count_serveable(db, languages, countries) > 0:
                break
        if await process_next_politician(languages, countries) is None:
            break
        enriched += 1

    return enriched
