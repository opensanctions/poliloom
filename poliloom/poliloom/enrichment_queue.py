"""Enrichment candidate selection and source creation.

This module deliberately retains separate set-based scheduler and correlated
early-exit existence query shapes.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, aliased

from .models.base import PropertyType, RelationType
from .models.entities import Language, WikipediaProject
from .models.politician import Politician, WikipediaLink
from .models.property import Property
from .models.source import Source
from .models.wikidata import WikidataRelation


def get_priority_wikipedia_links(politician: Politician, db: Session) -> List[Row]:
    """
    Get top 3 most popular Wikipedia links for a politician.

    Ranking prioritizes:
    1. Languages that are official in the politician's citizenship countries
    2. Global popularity (count of Wikipedia links in that language)

    Args:
        politician: Politician whose Wikipedia links to rank.
        db: Database session

    Returns:
        List of Row objects containing (url, wikipedia_project_id), limited to top 3
    """
    ranked_links = _get_ranked_wikipedia_links_cte()

    query = (
        select(ranked_links.c.url, ranked_links.c.wikipedia_project_id)
        .where(
            and_(
                ranked_links.c.politician_id == politician.id,
                ranked_links.c.rank <= 3,
            )
        )
        .order_by(ranked_links.c.rank)
    )

    result = db.execute(query)
    return result.fetchall()


def create_enrichment_sources(politician: Politician, db: Session) -> list["Source"]:
    """Create sources for this politician's priority Wikipedia links.

    Sets enriched_at to now to prevent re-selection.
    Caller manages commit/rollback.

    Returns:
        List of newly created Source objects (empty if no suitable links).
    """
    sources = []
    for url, wikipedia_project_id in get_priority_wikipedia_links(politician, db):
        source = Source(url=url, wikipedia_project_id=wikipedia_project_id)
        db.add(source)
        db.flush()
        politician.sources.append(source)
        sources.append(source)

    politician.enriched_at = datetime.now(timezone.utc)
    return sources


def _get_language_popularity_cte():
    """
    Create CTE for global language popularity based on Wikipedia link counts.

    Returns:
        SQLAlchemy CTE with columns: wikipedia_project_id, global_count
    """
    return (
        select(WikipediaLink.wikipedia_project_id, func.count().label("global_count"))
        .group_by(WikipediaLink.wikipedia_project_id)
        .cte("language_popularity")
        .prefix_with("MATERIALIZED")
    )


def _get_ranked_wikipedia_links_cte(countries: List[str] = None):
    """
    Create CTE for ranking Wikipedia links by citizenship match and global popularity.

    This is the shared ranking logic used by both get_priority_wikipedia_links
    and enrichment_candidates_query to ensure consistent behavior.

    The ranking orders by:
    1. Citizenship match (1 if language is official in a citizenship country, else 0)
    2. Global popularity (count of Wikipedia links in that language across all politicians)

    Args:
        countries: Optional list of country QIDs to pre-filter politicians.
                   This dramatically improves performance when filtering by country.

    Returns:
        SQLAlchemy CTE with columns: politician_id, language_qid, wikipedia_project_id,
                                     url, matches_citizenship, language_popularity, rank
    """
    # CTE 1: Global language popularity
    language_popularity = _get_language_popularity_cte()

    # CTE 2: Politician-language citizenship matches
    # Pre-compute which (politician, language) pairs have a citizenship match
    # by joining citizenships with official languages
    # When countries is provided, scope to those countries for early filtering
    citizenship_where = [
        Property.type == PropertyType.CITIZENSHIP,
        Property.entity_id.isnot(None),
        Property.deleted_at.is_(None),
    ]
    if countries:
        citizenship_where.append(Property.entity_id.in_(countries))

    citizenship_language_matches = (
        select(
            Property.politician_id.label("politician_id"),
            WikidataRelation.parent_entity_id.label("language_id"),
        )
        .select_from(Property)
        .join(
            WikidataRelation,
            and_(
                Property.entity_id == WikidataRelation.child_entity_id,
                WikidataRelation.relation_type == RelationType.OFFICIAL_LANGUAGE,
                WikidataRelation.deleted_at.is_(None),
            ),
        )
        .where(and_(*citizenship_where))
        .distinct()
        .cte("citizenship_language_matches")
    )

    # CTE 3: Ranked Wikipedia links
    # Use LEFT JOIN to citizenship_language_matches to determine match flag
    ranked_links_query = (
        select(
            Politician.id.label("politician_id"),
            Language.wikidata_id.label("language_qid"),
            WikipediaLink.wikipedia_project_id,
            WikipediaLink.url,
            case(
                (citizenship_language_matches.c.politician_id.isnot(None), 1),
                else_=0,
            ).label("matches_citizenship"),
            language_popularity.c.global_count.label("language_popularity"),
            func.row_number()
            .over(
                partition_by=Politician.id,
                order_by=[
                    case(
                        (
                            citizenship_language_matches.c.politician_id.isnot(None),
                            1,
                        ),
                        else_=0,
                    ).desc(),
                    language_popularity.c.global_count.desc(),
                ],
            )
            .label("rank"),
        )
        .select_from(Politician)
        .join(WikipediaLink, WikipediaLink.politician_id == Politician.id)
        .join(
            WikipediaProject,
            WikipediaLink.wikipedia_project_id == WikipediaProject.wikidata_id,
        )
        .join(
            WikidataRelation,
            and_(
                WikidataRelation.child_entity_id == WikipediaProject.wikidata_id,
                WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
                WikidataRelation.deleted_at.is_(None),
            ),
        )
        .join(Language, WikidataRelation.parent_entity_id == Language.wikidata_id)
        .join(
            language_popularity,
            language_popularity.c.wikipedia_project_id
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

    # Apply country filter early to reduce the number of politicians we rank
    if countries:
        country_filter = select(Property.politician_id).where(
            and_(
                Property.type == PropertyType.CITIZENSHIP,
                Property.entity_id.in_(countries),
                Property.deleted_at.is_(None),
            )
        )
        ranked_links_query = ranked_links_query.where(Politician.id.in_(country_filter))

    return ranked_links_query.distinct().cte("ranked_wikipedia_links")


def _filter_by_countries(query, countries: List[str]):
    """
    Apply country citizenship filter to a politician query.

    Args:
        query: Existing select statement for Politician entities
        countries: List of country QIDs to filter by

    Returns:
        Modified select statement with country filter applied
    """
    citizenship_exists = exists(
        select(1).where(
            and_(
                Property.politician_id == Politician.id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.entity_id.in_(countries),
                Property.deleted_at.is_(None),
            )
        )
    )
    return query.where(citizenship_exists)


def _query_enrichable_base():
    """Build the filters shared by enrichment selection and existence checks."""
    return Politician.query_base().where(
        Politician.wikidata_id.isnot(None),
        Politician.needs_enrichment,
        exists(select(1).where(WikipediaLink.politician_id == Politician.id)),
    )


def enrichment_candidates_query(
    languages: List[str] = None,
    countries: List[str] = None,
    stateless: bool = False,
):
    """
    Build a query for politicians that should be enriched.

    Uses citizenship-based language filtering that mirrors get_priority_wikipedia_links logic,
    considering both citizenship matching and language popularity.

    This ensures that filtered languages would actually be selected by get_priority_wikipedia_links.

    Args:
        languages: Optional list of language QIDs to filter by
        countries: Optional list of country QIDs to filter by
        stateless: If True, only return politicians without any citizenship property.
                   This addresses bias where politicians without citizenship are never
                   enriched by normal user-driven filters. Mutually exclusive with
                   languages/countries filters.

    Returns:
        SQLAlchemy select statement for Politician entities
    """

    query = _query_enrichable_base()

    # Stateless mode: filter for politicians without citizenship
    # Uses idx_properties_citizenship_lookup for efficient NOT EXISTS check
    if stateless:
        has_citizenship = exists(
            select(1).where(
                and_(
                    Property.politician_id == Politician.id,
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.deleted_at.is_(None),
                )
            )
        )
        query = query.where(~has_citizenship)
        return query

    # Apply language filtering using shared ranking logic
    # Pass countries to the CTE for early filtering (major performance optimization)
    if languages:
        ranked_links = _get_ranked_wikipedia_links_cte(countries=countries)

        # Subquery: Politicians where filtered language is in top 3 by rank
        top_3_languages = select(ranked_links.c.politician_id.distinct()).where(
            and_(
                ranked_links.c.language_qid.in_(languages),
                ranked_links.c.rank <= 3,
            )
        )

        query = query.where(Politician.id.in_(top_3_languages))

    # Apply country filtering (only if not already applied via language CTE)
    elif countries:
        citizenship_subquery = select(Property.politician_id).where(
            and_(
                Property.type == PropertyType.CITIZENSHIP,
                Property.entity_id.in_(countries),
                Property.deleted_at.is_(None),
            )
        )
        query = query.where(Politician.id.in_(citizenship_subquery))

    return query


def _query_has_enrichment_candidate(
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
):
    """Build the query used by :func:`has_enrichment_candidate`.

    Unlike :func:`enrichment_candidates_query`, this query is shaped purely as an
    existence check. When languages are requested, each candidate's links are
    ranked in a correlated subquery instead of ranking links for every politician.
    The ordering mirrors :func:`_get_ranked_wikipedia_links_cte`, while allowing
    PostgreSQL to stop as soon as one eligible politician is found.
    """
    query = _query_enrichable_base()

    # Stateless mode is mutually exclusive with language and country filters.
    if stateless:
        has_citizenship = exists(
            select(1).where(
                Property.politician_id == Politician.id,
                Property.type == PropertyType.CITIZENSHIP,
                Property.deleted_at.is_(None),
            )
        )
        return query.where(~has_citizenship)

    if countries:
        query = _filter_by_countries(query, countries)

    if not languages:
        return query

    link = aliased(WikipediaLink)
    project = aliased(WikipediaProject)
    link_language_relation = aliased(WikidataRelation)
    language = aliased(Language)
    citizenship = aliased(Property)
    official_language_relation = aliased(WikidataRelation)
    language_popularity = _get_language_popularity_cte()

    citizenship_conditions = [
        citizenship.politician_id == Politician.id,
        citizenship.type == PropertyType.CITIZENSHIP,
        citizenship.entity_id.isnot(None),
        citizenship.deleted_at.is_(None),
        official_language_relation.parent_entity_id
        == link_language_relation.parent_entity_id,
    ]
    if countries:
        citizenship_conditions.append(citizenship.entity_id.in_(countries))

    matches_citizenship = exists(
        select(1)
        .select_from(citizenship)
        .join(
            official_language_relation,
            and_(
                citizenship.entity_id == official_language_relation.child_entity_id,
                official_language_relation.relation_type
                == RelationType.OFFICIAL_LANGUAGE,
                official_language_relation.deleted_at.is_(None),
            ),
        )
        .where(*citizenship_conditions)
        .correlate(Politician, link_language_relation)
    )

    ranked_links = (
        select(
            language.wikidata_id.label("language_qid"),
            func.row_number()
            .over(
                order_by=(
                    matches_citizenship.desc(),
                    language_popularity.c.global_count.desc(),
                )
            )
            .label("rank"),
        )
        .select_from(link)
        .join(project, link.wikipedia_project_id == project.wikidata_id)
        .join(
            link_language_relation,
            and_(
                link_language_relation.child_entity_id == project.wikidata_id,
                link_language_relation.relation_type == RelationType.LANGUAGE_OF_WORK,
                link_language_relation.deleted_at.is_(None),
            ),
        )
        .join(
            language,
            link_language_relation.parent_entity_id == language.wikidata_id,
        )
        .join(
            language_popularity,
            language_popularity.c.wikipedia_project_id == link.wikipedia_project_id,
        )
        .where(link.politician_id == Politician.id)
        .correlate(Politician)
        .subquery("ranked_links_for_politician")
    )

    requested_language_is_top_three = exists(
        select(1)
        .select_from(ranked_links)
        .where(
            ranked_links.c.language_qid.in_(languages),
            ranked_links.c.rank <= 3,
        )
    )

    # Give the planner a cheap way to narrow the outer candidates before it
    # evaluates the correlated ranking subquery.
    candidate_link = aliased(WikipediaLink)
    candidate_project = aliased(WikipediaProject)
    candidate_relation = aliased(WikidataRelation)
    candidate_language = aliased(Language)
    politicians_with_requested_link = (
        select(candidate_link.politician_id)
        .select_from(candidate_link)
        .join(
            candidate_project,
            candidate_link.wikipedia_project_id == candidate_project.wikidata_id,
        )
        .join(
            candidate_relation,
            and_(
                candidate_relation.child_entity_id == candidate_project.wikidata_id,
                candidate_relation.relation_type == RelationType.LANGUAGE_OF_WORK,
                candidate_relation.deleted_at.is_(None),
            ),
        )
        .join(
            candidate_language,
            candidate_relation.parent_entity_id == candidate_language.wikidata_id,
        )
        .where(candidate_language.wikidata_id.in_(languages))
    )

    return query.where(
        Politician.id.in_(politicians_with_requested_link),
        requested_language_is_top_three,
    )


def has_enrichment_candidate(
    db: Session,
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
) -> bool:
    """Return whether at least one politician is available to enrich."""
    query = _query_has_enrichment_candidate(
        languages=languages,
        countries=countries,
        stateless=stateless,
    )
    return (
        db.execute(query.with_only_columns(Politician.id).limit(1)).first() is not None
    )
