"""Enrichment candidate selection and source creation.

This module deliberately retains separate set-based scheduler and correlated
early-exit existence query shapes.
"""

from datetime import datetime, timezone

from sqlalchemy import and_, case, exists, func, select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, aliased

from .models.base import PropertyType, RelationType
from .models.entities import Language, WikipediaProject
from .models.politician import Politician, WikipediaLink
from .models.property import Property
from .models.source import Source
from .models.wikidata import WikidataRelation


PRIORITY_WIKIPEDIA_LINK_LIMIT = 3


def count_stateless_with_unevaluated_citizenship(db: Session) -> int:
    """Count stateless politicians with unevaluated extracted citizenship.

    A politician is counted when they have an active extracted citizenship
    (no statement ID) but no active Wikidata citizenship (a statement ID).
    The result is the review buffer used to throttle stateless enrichment.
    """
    # Subquery: politicians with Wikidata citizenship (should be excluded)
    has_wikidata_citizenship = (
        select(Property.politician_id)
        .where(
            and_(
                Property.type == PropertyType.CITIZENSHIP,
                Property.statement_id.isnot(None),
                Property.deleted_at.is_(None),
            )
        )
        .distinct()
    )

    # Subquery: politicians with unevaluated extracted citizenship
    has_unevaluated_extracted_citizenship = (
        select(Property.politician_id)
        .where(
            and_(
                Property.type == PropertyType.CITIZENSHIP,
                Property.statement_id.is_(None),
                Property.deleted_at.is_(None),
            )
        )
        .distinct()
    )

    # Count politicians who have unevaluated extracted citizenship but no
    # Wikidata citizenship.
    count_query = (
        select(func.count())
        .select_from(Politician)
        .where(
            and_(
                Politician.id.in_(has_unevaluated_extracted_citizenship),
                ~Politician.id.in_(has_wikidata_citizenship),
            )
        )
    )

    result = db.execute(count_query).scalar()
    return result or 0


def _ranking_order_by(matches_citizenship, language_popularity):
    """Return the two ranking keys shared by both link-ranking query shapes."""
    return (matches_citizenship.desc(), language_popularity.desc())


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


def _active_citizenship_conditions(
    citizenship, *, politician_id=None, countries=None, require_entity=False
):
    """Return common active-citizenship predicates for a Property table or alias."""
    conditions = []
    if politician_id is not None:
        conditions.append(citizenship.politician_id == politician_id)
    conditions.append(citizenship.type == PropertyType.CITIZENSHIP)
    if require_entity:
        conditions.append(citizenship.entity_id.isnot(None))
        conditions.append(citizenship.deleted_at.is_(None))
        if countries:
            conditions.append(citizenship.entity_id.in_(countries))
    else:
        if countries:
            conditions.append(citizenship.entity_id.in_(countries))
        conditions.append(citizenship.deleted_at.is_(None))
    return conditions


def _active_citizenship_exists(politician_id=Politician.id, *, countries=None):
    """Return an EXISTS expression for an active citizenship, optionally in countries."""
    return exists(
        select(1).where(
            *_active_citizenship_conditions(
                Property, politician_id=politician_id, countries=countries
            )
        )
    )


def _politicians_with_citizenship(countries):
    """Select politicians with an active citizenship in ``countries``."""
    return select(Property.politician_id).where(
        *_active_citizenship_conditions(Property, countries=countries)
    )


def get_priority_wikipedia_links(politician: Politician, db: Session) -> list[Row]:
    """
    Get the highest-priority Wikipedia links for a politician.

    Ranking prioritizes:
    1. Languages that are official in the politician's citizenship countries
    2. Global popularity (count of Wikipedia links in that language)

    Args:
        politician: Politician whose Wikipedia links to rank.
        db: Database session

    Returns:
        List of Row objects containing (url, wikipedia_project_id), limited to the
        priority link limit
    """
    ranked_links = _get_ranked_wikipedia_links_cte()

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


def _get_ranked_wikipedia_links_cte(countries: list[str] | None = None):
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
    citizenship_where = _active_citizenship_conditions(
        Property, countries=countries, require_entity=True
    )

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
            language_popularity.c.global_count.label("language_popularity"),
            func.row_number()
            .over(
                partition_by=Politician.id,
                order_by=_ranking_order_by(
                    matches_citizenship, language_popularity.c.global_count
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
        country_filter = _politicians_with_citizenship(countries)
        ranked_links_query = ranked_links_query.where(Politician.id.in_(country_filter))

    return ranked_links_query.distinct().cte("ranked_wikipedia_links")


def _query_enrichable_base():
    """Build the filters shared by enrichment selection and existence checks."""
    return Politician.query_base().where(
        Politician.wikidata_id.isnot(None),
        Politician.needs_enrichment,
        exists(select(1).where(WikipediaLink.politician_id == Politician.id)),
    )


def enrichment_candidates_query(
    languages: list[str] | None = None,
    countries: list[str] | None = None,
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
        query = query.where(~_active_citizenship_exists())
        return query

    # Apply language filtering using shared ranking logic
    # Pass countries to the CTE for early filtering (major performance optimization)
    if languages:
        ranked_links = _get_ranked_wikipedia_links_cte(countries=countries)

        # Politicians where the filtered language is within the priority link limit.
        priority_languages = select(ranked_links.c.politician_id.distinct()).where(
            and_(
                ranked_links.c.language_qid.in_(languages),
                ranked_links.c.rank <= PRIORITY_WIKIPEDIA_LINK_LIMIT,
            )
        )

        query = query.where(Politician.id.in_(priority_languages))

    # Apply country filtering (only if not already applied via language CTE)
    elif countries:
        query = query.where(Politician.id.in_(_politicians_with_citizenship(countries)))

    return query


def _query_has_enrichment_candidate(
    languages: list[str] | None = None,
    countries: list[str] | None = None,
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
        return query.where(~_active_citizenship_exists())

    if countries:
        query = query.where(_active_citizenship_exists(countries=countries))

    if not languages:
        return query

    link = aliased(WikipediaLink)
    project = aliased(WikipediaProject)
    link_language_relation = aliased(WikidataRelation)
    language = aliased(Language)
    citizenship = aliased(Property)
    official_language_relation = aliased(WikidataRelation)
    language_popularity = _get_language_popularity_cte()

    citizenship_conditions = _active_citizenship_conditions(
        citizenship,
        politician_id=Politician.id,
        countries=countries,
        require_entity=True,
    ) + [
        official_language_relation.parent_entity_id
        == link_language_relation.parent_entity_id,
    ]

    matches_citizenship = exists(
        select(1)
        .select_from(citizenship)
        .join(
            official_language_relation,
            _official_language_join_conditions(citizenship, official_language_relation),
        )
        .where(*citizenship_conditions)
        .correlate(Politician, link_language_relation)
    )

    ranked_links = select(
        language.wikidata_id.label("language_qid"),
        func.row_number()
        .over(
            order_by=_ranking_order_by(
                matches_citizenship, language_popularity.c.global_count
            )
        )
        .label("rank"),
    ).select_from(link)
    ranked_links = (
        _join_project_language_path(
            ranked_links,
            link,
            project,
            link_language_relation,
            language,
        )
        .join(
            language_popularity,
            language_popularity.c.wikipedia_project_id == link.wikipedia_project_id,
        )
        .where(link.politician_id == Politician.id)
        .correlate(Politician)
        .subquery("ranked_links_for_politician")
    )

    requested_language_is_prioritized = exists(
        select(1)
        .select_from(ranked_links)
        .where(
            ranked_links.c.language_qid.in_(languages),
            ranked_links.c.rank <= PRIORITY_WIKIPEDIA_LINK_LIMIT,
        )
    )

    # Give the planner a cheap way to narrow the outer candidates before it
    # evaluates the correlated ranking subquery.
    candidate_link = aliased(WikipediaLink)
    candidate_project = aliased(WikipediaProject)
    candidate_relation = aliased(WikidataRelation)
    candidate_language = aliased(Language)
    politicians_with_requested_link = _join_project_language_path(
        select(candidate_link.politician_id).select_from(candidate_link),
        candidate_link,
        candidate_project,
        candidate_relation,
        candidate_language,
    ).where(candidate_language.wikidata_id.in_(languages))

    return query.where(
        Politician.id.in_(politicians_with_requested_link),
        requested_language_is_prioritized,
    )


def has_enrichment_candidate(
    db: Session,
    languages: list[str] | None = None,
    countries: list[str] | None = None,
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
