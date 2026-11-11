"""Enrichment candidate selection and source creation."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from .models.base import RelationType
from .models.politician import Politician, WikipediaLink
from .models.source import PoliticianSource, Source
from .models.statement import Statement, active_citizenship_conditions
from .models.wikidata import WikidataRelation

MAX_ENRICHMENT_SOURCES = 3


def get_enrichment_cooldown_days() -> int:
    """Return the snapshot re-enrichment cooldown in days."""
    return int(os.getenv("ENRICHMENT_COOLDOWN_DAYS", "365"))


def get_enrichment_cooldown_cutoff() -> datetime:
    """Return the oldest timestamp that still blocks re-enrichment."""
    return datetime.now(UTC) - timedelta(days=get_enrichment_cooldown_days())


def _politicians_with_citizenship(countries):
    """Select politicians with a live citizenship in ``countries``."""
    return select(Statement.politician_id).where(
        *active_citizenship_conditions(Statement, countries=countries)
    )


def _eligible_links_query(languages: list[str]):
    """Select Wikipedia links in requested languages that need a fresh snapshot."""
    language_of_work = exists(
        select(1).where(
            WikidataRelation.child_entity_id == WikipediaLink.wikipedia_project_id,
            WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
            WikidataRelation.parent_entity_id.in_(languages),
        )
    )
    recent_source = exists(
        select(1)
        .select_from(PoliticianSource)
        .join(Source, Source.id == PoliticianSource.source_id)
        .where(
            PoliticianSource.politician_id == WikipediaLink.politician_id,
            Source.wikipedia_project_id == WikipediaLink.wikipedia_project_id,
            Source.fetch_timestamp >= get_enrichment_cooldown_cutoff(),
        )
    )
    return select(WikipediaLink).where(language_of_work, ~recent_source)


def create_enrichment_sources(
    politician: Politician, db: Session, languages: list[str]
) -> list[Source]:
    """Create fresh source snapshots for requested languages.

    Re-enrichment adds a new snapshot and never mutates old sources. The limit
    bounds one user's fan-out; project QID order makes the selection stable.
    """
    links = db.scalars(
        _eligible_links_query(languages)
        .where(WikipediaLink.politician_id == politician.id)
        .order_by(WikipediaLink.wikipedia_project_id)
        .limit(MAX_ENRICHMENT_SOURCES)
    ).all()
    sources = []
    for link in links:
        source = Source(url=link.url, wikipedia_project_id=link.wikipedia_project_id)
        db.add(source)
        db.flush()
        politician.sources.append(source)
        sources.append(source)
    return sources


def enrichment_candidates_query(
    languages: list[str],
    countries: list[str] | None = None,
):
    """
    Build a query for politicians that should be enriched.

    A candidate has at least one Wikipedia link in a requested language with no
    source snapshot newer than the cooldown window for that politician and project.
    Re-enrichment creates a new snapshot; old snapshots are never mutated, and
    failed snapshots become eligible again after the window.

    Args:
        languages: Language QIDs to enrich
        countries: Optional list of country QIDs to filter by

    Returns:
        SQLAlchemy select statement for Politician entities
    """
    eligible_links = _eligible_links_query(languages).where(
        WikipediaLink.politician_id == Politician.id
    )
    query = Politician.query_base().where(
        Politician.wikidata_id.isnot(None), exists(eligible_links)
    )
    if countries:
        query = query.where(Politician.id.in_(_politicians_with_citizenship(countries)))
    return query
