"""Enrichment candidate selection and source creation."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, func, select
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
    """Select fresh Wikipedia link/language pairs in the requested languages."""
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
    return (
        select(
            WikipediaLink,
            WikidataRelation.parent_entity_id.label("language_id"),
        )
        .join(
            WikidataRelation,
            and_(
                WikidataRelation.child_entity_id == WikipediaLink.wikipedia_project_id,
                WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
                WikidataRelation.parent_entity_id.in_(languages),
            ),
        )
        .where(~recent_source)
    )


def create_enrichment_sources(
    politician: Politician, db: Session, languages: list[str]
) -> list[Source]:
    """Create fresh source snapshots for requested languages.

    Re-enrichment adds a new snapshot and never mutates old sources. The limit
    bounds one user's fan-out; project QID order makes the selection stable.
    """
    links = db.scalars(
        _eligible_links_query(languages)
        .with_only_columns(WikipediaLink)
        .where(WikipediaLink.politician_id == politician.id)
        .distinct()
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

    A candidate has at least one eligible link in a requested language.
    Candidates are ordered by distinct requested-language coverage, then by
    descending Wikidata QID. A source snapshot newer than the cooldown window
    makes its politician/project pair ineligible. Re-enrichment creates a new
    snapshot; old snapshots are never mutated, and failed snapshots become
    eligible again after the window.

    Args:
        languages: Language QIDs to enrich
        countries: Optional list of country QIDs to filter by

    Returns:
        SQLAlchemy select statement for Politician entities
    """
    eligible_links = (
        _eligible_links_query(languages)
        .with_only_columns(
            WikipediaLink.politician_id,
            WikidataRelation.parent_entity_id.label("language_id"),
        )
        .subquery()
    )
    language_coverage = func.count(eligible_links.c.language_id.distinct())
    coverage = (
        select(eligible_links.c.politician_id, language_coverage.label("coverage"))
        .select_from(eligible_links)
        .group_by(eligible_links.c.politician_id)
        .subquery()
    )
    query = (
        Politician.query_base()
        .join(coverage, coverage.c.politician_id == Politician.id)
        .where(Politician.wikidata_id.isnot(None))
        .order_by(coverage.c.coverage.desc(), Politician.wikidata_id_numeric.desc())
    )
    if countries:
        query = query.where(Politician.id.in_(_politicians_with_citizenship(countries)))
    return query
