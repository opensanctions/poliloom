"""Enrichment candidate selection and source creation."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from .models.base import RelationType
from .models.entities import Language, WikipediaProject
from .models.politician import Politician, WikipediaLink
from .models.property import Property, active_citizenship_conditions
from .models.source import PoliticianSource, Source
from .models.wikidata import WikidataRelation

PRIORITY_WIKIPEDIA_LINK_LIMIT = 3


def get_enrichment_cooldown_days() -> int:
    """Return the snapshot re-enrichment cooldown in days."""
    return int(os.getenv("ENRICHMENT_COOLDOWN_DAYS", "365"))


def get_enrichment_cooldown_cutoff() -> datetime:
    """Return the oldest timestamp that still blocks re-enrichment."""
    return datetime.now(UTC) - timedelta(days=get_enrichment_cooldown_days())


def _ranking_order_by(
    matches_citizenship, wikipedia_project_popularity, wikipedia_project_id
):
    """Return the shared deterministic ranking keys for Wikipedia links."""
    return (
        matches_citizenship.desc(),
        wikipedia_project_popularity.desc(),
        wikipedia_project_id.asc(),
    )


def _join_project_language_path(query, link, project, relation, language):
    """Join a link through its project to its active language-of-work relation."""
    return (
        query.join(project, link.wikipedia_project_id == project.wikidata_id)
        .join(
            relation,
            and_(
                relation.child_entity_id == project.wikidata_id,
                relation.relation_type == RelationType.LANGUAGE_OF_WORK,
                relation.deleted_at.is_(None),
            ),
        )
        .join(language, relation.parent_entity_id == language.wikidata_id)
    )


def _official_language_join_conditions(citizenship, relation):
    """Return active OFFICIAL_LANGUAGE conditions for a citizenship join."""
    return and_(
        citizenship.entity_id == relation.child_entity_id,
        relation.relation_type == RelationType.OFFICIAL_LANGUAGE,
        relation.deleted_at.is_(None),
    )


def _politicians_with_citizenship(countries):
    """Select politicians with an active citizenship in ``countries``."""
    return select(Property.politician_id).where(
        *active_citizenship_conditions(Property, countries=countries)
    )


def get_priority_wikipedia_links(
    politician: Politician,
    db: Session,
    *,
    languages: list[str] | None = None,
    eligible_only: bool = False,
) -> list[Row]:
    """
    Get the highest-priority Wikipedia links for a politician.

    Ranking prioritizes:
    1. Languages that are official in the politician's citizenship countries
    2. Wikipedia-project popularity (count of links for that project)

    Args:
        politician: Politician whose Wikipedia links to rank.
        db: Database session
        languages: Optional language QIDs to include before ranking.
        eligible_only: Exclude projects with a snapshot newer than the cooldown window.

    Returns:
        List of Row objects containing (url, wikipedia_project_id), limited to the
        priority link limit
    """
    ranked_links = _get_ranked_wikipedia_links_cte(
        languages=languages, eligible_only=eligible_only
    )

    query = (
        select(ranked_links.c.url, ranked_links.c.wikipedia_project_id)
        .where(
            and_(
                ranked_links.c.politician_id == politician.id,
                ranked_links.c.rank <= PRIORITY_WIKIPEDIA_LINK_LIMIT,
            )
        )
        .order_by(ranked_links.c.rank)
    )

    result = db.execute(query)
    return result.fetchall()


def create_enrichment_sources(
    politician: Politician, db: Session, languages: list[str] | None = None
) -> list[Source]:
    """Create fresh source snapshots for links without a recent project snapshot.

    Re-enrichment adds a new snapshot and never mutates old sources.
    """
    links = get_priority_wikipedia_links(
        politician, db, languages=languages, eligible_only=True
    )
    sources = []
    for url, wikipedia_project_id in links:
        source = Source(url=url, wikipedia_project_id=wikipedia_project_id)
        db.add(source)
        db.flush()
        politician.sources.append(source)
        sources.append(source)
    return sources


def _get_wikipedia_project_popularity_cte():
    """Create a CTE for global Wikipedia-project popularity by link count.

    Returns:
        SQLAlchemy CTE with columns: wikipedia_project_id, global_count
    """
    return (
        select(WikipediaLink.wikipedia_project_id, func.count().label("global_count"))
        .group_by(WikipediaLink.wikipedia_project_id)
        .cte("wikipedia_project_popularity")
        .prefix_with("MATERIALIZED")
    )


def _get_ranked_wikipedia_links_cte(
    countries: list[str] | None = None,
    languages: list[str] | None = None,
    eligible_only: bool = False,
):
    """
    Create CTE for ranking Wikipedia links by citizenship match and project popularity.

    This is the shared ranking logic used by both get_priority_wikipedia_links
    and enrichment_candidates_query to ensure consistent behavior.

    The ranking orders by:
    1. Citizenship match (1 if language is official in a citizenship country, else 0)
    2. Wikipedia-project popularity (count of links for that project across all politicians)
    3. Wikipedia project ID ascending (deterministic tiebreaker)

    Args:
        countries: Optional list of country QIDs to pre-filter politicians.
                   This dramatically improves performance when filtering by country.

    Returns:
        SQLAlchemy CTE with columns: politician_id, language_qid, wikipedia_project_id,
                                     url, matches_citizenship,
                                     wikipedia_project_popularity, rank
    """
    # CTE 1: Global Wikipedia-project popularity
    wikipedia_project_popularity = _get_wikipedia_project_popularity_cte()

    # CTE 2: Politician-language citizenship matches
    # Pre-compute which (politician, language) pairs have a citizenship match
    # by joining citizenships with official languages
    # When countries is provided, scope to those countries for early filtering
    citizenship_where = active_citizenship_conditions(Property, countries=countries)

    citizenship_language_matches = (
        select(
            Property.politician_id.label("politician_id"),
            WikidataRelation.parent_entity_id.label("language_id"),
        )
        .select_from(Property)
        .join(
            WikidataRelation,
            _official_language_join_conditions(Property, WikidataRelation),
        )
        .where(and_(*citizenship_where))
        .distinct()
        .cte("citizenship_language_matches")
    )

    # CTE 3: Ranked Wikipedia links
    # Use LEFT JOIN to citizenship_language_matches to determine match flag
    matches_citizenship = case(
        (citizenship_language_matches.c.politician_id.isnot(None), 1),
        else_=0,
    )
    ranked_links_query = (
        select(
            Politician.id.label("politician_id"),
            Language.wikidata_id.label("language_qid"),
            WikipediaLink.wikipedia_project_id,
            WikipediaLink.url,
            matches_citizenship.label("matches_citizenship"),
            wikipedia_project_popularity.c.global_count.label(
                "wikipedia_project_popularity"
            ),
            func.row_number()
            .over(
                partition_by=Politician.id,
                order_by=_ranking_order_by(
                    matches_citizenship,
                    wikipedia_project_popularity.c.global_count,
                    WikipediaLink.wikipedia_project_id,
                ),
            )
            .label("rank"),
        )
        .select_from(Politician)
        .join(WikipediaLink, WikipediaLink.politician_id == Politician.id)
    )
    ranked_links_query = (
        _join_project_language_path(
            ranked_links_query,
            WikipediaLink,
            WikipediaProject,
            WikidataRelation,
            Language,
        )
        .join(
            wikipedia_project_popularity,
            wikipedia_project_popularity.c.wikipedia_project_id
            == WikipediaLink.wikipedia_project_id,
        )
        .outerjoin(
            citizenship_language_matches,
            and_(
                citizenship_language_matches.c.politician_id == Politician.id,
                citizenship_language_matches.c.language_id == Language.wikidata_id,
            ),
        )
    )

    # Apply filters before ranking so the limit is over selectable links.
    if countries:
        ranked_links_query = ranked_links_query.where(
            Politician.id.in_(_politicians_with_citizenship(countries))
        )
    if languages:
        ranked_links_query = ranked_links_query.where(
            Language.wikidata_id.in_(languages)
        )
    if eligible_only:
        existing_source_for_project = (
            select(1)
            .select_from(PoliticianSource)
            .join(Source, Source.id == PoliticianSource.source_id)
            .where(
                PoliticianSource.politician_id == Politician.id,
                Source.wikipedia_project_id == WikipediaLink.wikipedia_project_id,
                Source.fetch_timestamp >= get_enrichment_cooldown_cutoff(),
            )
        )
        ranked_links_query = ranked_links_query.where(
            ~exists(existing_source_for_project)
        )

    return ranked_links_query.distinct().cte("ranked_wikipedia_links")


def _eligible_link_exists(languages: list[str] | None = None):
    """Return EXISTS for a link without a snapshot newer than the cooldown window.

    Re-enrichment creates a new snapshot without changing old sources; failed sources
    are therefore eligible again after the cooldown window.
    """
    link = WikipediaLink
    existing_source = (
        select(1)
        .select_from(PoliticianSource)
        .join(Source, Source.id == PoliticianSource.source_id)
        .where(
            PoliticianSource.politician_id == Politician.id,
            Source.wikipedia_project_id == link.wikipedia_project_id,
            Source.fetch_timestamp >= get_enrichment_cooldown_cutoff(),
        )
    )
    query = _join_project_language_path(
        select(1).select_from(link),
        link,
        WikipediaProject,
        WikidataRelation,
        Language,
    ).where(
        link.politician_id == Politician.id,
        ~exists(existing_source),
    )
    if languages:
        query = query.where(Language.wikidata_id.in_(languages))
    return exists(query)


def enrichment_candidates_query(
    languages: list[str] | None = None,
    countries: list[str] | None = None,
):
    """
    Build a query for politicians that should be enriched.

    A candidate has at least one Wikipedia project link with no source snapshot newer
    than the cooldown window for that project. Re-enrichment creates a new snapshot;
    old snapshots are never mutated, and failed snapshots become eligible again after
    the window. Requested languages restrict that eligible-link check.

    Args:
        languages: Optional list of language QIDs to filter by
        countries: Optional list of country QIDs to filter by

    Returns:
        SQLAlchemy select statement for Politician entities
    """

    query = Politician.query_base().where(
        Politician.wikidata_id.isnot(None), _eligible_link_exists(languages)
    )
    if countries:
        query = query.where(Politician.id.in_(_politicians_with_citizenship(countries)))
    return query
