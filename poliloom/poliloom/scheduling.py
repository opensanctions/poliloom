"""Scheduling: orchestration of the enrichment pipeline."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .archiving import process_source
from .database import get_engine
from .models import (
    Politician,
    Property,
    Source,
    WikidataEntity,
    WikidataRelation,
)
from .sse import EnrichmentCompleteEvent, notify

logger = logging.getLogger(__name__)


@dataclass
class ScheduledEnrichment:
    """Result of scheduling a politician for enrichment."""

    politician_id: Any
    source_ids: list


def schedule_enrichment(
    db: Session,
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
) -> Optional[ScheduledEnrichment]:
    """Pick the next politician and create sources for its Wikipedia links.

    Sets enriched_at immediately to prevent re-selection by other workers.

    Returns:
        ScheduledEnrichment if a politician was found, None otherwise.
    """
    query = (
        Politician.query_for_enrichment(
            languages=languages,
            countries=countries,
            stateless=stateless,
        )
        .options(
            selectinload(Politician.wikipedia_links),
        )
        .order_by(
            Politician.enriched_at.asc().nullsfirst(),
            Politician.wikidata_id_numeric.desc(),
        )
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    politician = db.scalars(query).first()

    if not politician:
        return None

    try:
        sources = politician.schedule_enrichment(db)

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
        politician.enriched_at = datetime.now(timezone.utc)
        db.commit()
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
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
) -> bool:
    """Schedule and process enrichment for a single politician.

    Returns:
        True if a politician was found, False if no politician available.
    """
    with Session(get_engine()) as db:
        scheduled = schedule_enrichment(db, languages, countries, stateless)

    if not scheduled:
        return False

    counts = await asyncio.gather(
        *(
            process_source_task(source_id, scheduled.politician_id)
            for source_id in scheduled.source_ids
        )
    )

    if sum(counts) > 0:
        notify(
            EnrichmentCompleteEvent(
                languages=languages or [],
                countries=countries or [],
            )
        )

    return True
