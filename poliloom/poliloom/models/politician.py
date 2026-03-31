"""Politician domain models: Politician, WikipediaLink."""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from dicttoxml import dicttoxml
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    and_,
    case,
    exists,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Row
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, relationship
from .base import (
    Base,
    EntityCreationMixin,
    PropertyType,
    RelationType,
    TimestampMixin,
    UpsertMixin,
)
from .entities import Language, WikipediaProject
from .property import Property, PropertyReference
from .wikidata import (
    WikidataEntity,
    WikidataEntityLabel,
    WikidataEntityMixin,
    WikidataRelation,
)
from .source import Source, SourceLanguage


class Politician(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Politician entity."""

    __tablename__ = "politicians"

    _search_indexed = True
    # UpsertMixin configuration
    _upsert_update_columns = ["name"]
    _upsert_conflict_columns = ["wikidata_id"]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name = Column(String, nullable=False)
    # Override wikidata_id from WikidataEntityMixin to not be primary key
    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), unique=True, index=True
    )
    wikidata_id_numeric = Column(Integer, nullable=True, index=True)
    enriched_at = Column(
        DateTime, nullable=True
    )  # Timestamp of last enrichment attempt

    def get_properties_by_types(
        self, property_types: List[PropertyType]
    ) -> List["Property"]:
        """Get all properties of the specified types."""
        return [prop for prop in self.properties if prop.type in property_types]

    def get_priority_wikipedia_links(self, db: Session) -> List[Row]:
        """
        Get top 3 most popular Wikipedia links for a politician.

        Ranking prioritizes:
        1. Languages that are official in the politician's citizenship countries
        2. Global popularity (count of Wikipedia links in that language)

        Args:
            db: Database session

        Returns:
            List of Row objects containing (url, wikipedia_project_id), limited to top 3
        """
        ranked_links = self._get_ranked_wikipedia_links_cte()

        query = (
            select(ranked_links.c.url, ranked_links.c.wikipedia_project_id)
            .where(
                and_(
                    ranked_links.c.politician_id == self.id,
                    ranked_links.c.rank <= 3,
                )
            )
            .order_by(ranked_links.c.rank)
        )

        result = db.execute(query)
        return result.fetchall()

    def schedule_enrichment(self, db: Session) -> list["Source"]:
        """Create sources for this politician's priority Wikipedia links.

        Sets enriched_at to now to prevent re-selection.
        Caller manages commit/rollback.

        Returns:
            List of newly created Source objects (empty if no suitable links).
        """
        sources = []
        for url, wikipedia_project_id in self.get_priority_wikipedia_links(db):
            source = Source(url=url, wikipedia_project_id=wikipedia_project_id)
            db.add(source)
            db.flush()
            self.sources.append(source)
            sources.append(source)

        self.enriched_at = datetime.now(timezone.utc)
        return sources

    def to_xml_context(self, focus_property_types=None) -> str:
        """Build comprehensive politician context as XML structure for LLM prompts.

        Args:
            focus_property_types: Optional list of PropertyType values to include in context.
                                If None, includes all available properties.

        Returns:
            XML formatted politician context string
        """
        context_data = {
            "name": self.name,
            "wikidata_id": self.wikidata_id,
        }

        # Add existing Wikidata properties based on focus or all available
        if self.properties:
            # Filter focus types if specified
            relevant_types = (
                focus_property_types
                if focus_property_types
                else [
                    PropertyType.BIRTH_DATE,
                    PropertyType.DEATH_DATE,
                    PropertyType.POSITION,
                    PropertyType.BIRTHPLACE,
                    PropertyType.CITIZENSHIP,
                ]
            )

            # Add date properties section
            if any(
                t in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]
                for t in relevant_types
            ):
                date_properties = self.get_properties_by_types(
                    [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]
                )
                date_items = [
                    f"{prop.type.value}: {prop.value}" for prop in date_properties
                ]
                if date_items:
                    context_data["existing_wikidata"] = date_items

            # Add positions section
            if PropertyType.POSITION in relevant_types:
                position_properties = self.get_properties_by_types(
                    [PropertyType.POSITION]
                )
                position_items = [
                    f"{prop.entity.name}{prop.format_timeframe()}"
                    for prop in position_properties
                ]
                if position_items:
                    context_data["existing_wikidata_positions"] = position_items

            # Add birthplaces section
            if PropertyType.BIRTHPLACE in relevant_types:
                birthplace_properties = self.get_properties_by_types(
                    [PropertyType.BIRTHPLACE]
                )
                birthplace_items = [prop.entity.name for prop in birthplace_properties]
                if birthplace_items:
                    context_data["existing_wikidata_birthplaces"] = birthplace_items

            # Add citizenships section
            if PropertyType.CITIZENSHIP in relevant_types:
                citizenship_properties = self.get_properties_by_types(
                    [PropertyType.CITIZENSHIP]
                )
                citizenship_items = [
                    prop.entity.name for prop in citizenship_properties
                ]
                if citizenship_items:
                    context_data["existing_wikidata_citizenships"] = citizenship_items

        xml_bytes = dicttoxml(
            context_data,
            custom_root="politician_context",
            attr_type=False,
            xml_declaration=False,
        )
        return xml_bytes.decode("utf-8")

    @classmethod
    def create_with_entity(
        cls,
        session,
        wikidata_id: str,
        name: str,
        labels: List[str] = None,
        description: str = None,
    ):
        """Create a Politician with its associated WikidataEntity."""
        # Use EntityCreationMixin pattern but override for Politician
        # Create WikidataEntity first
        wikidata_entity = WikidataEntity(
            wikidata_id=wikidata_id,
            name=name,
            description=description,
        )
        session.add(wikidata_entity)

        # Create WikidataEntityLabel records if labels provided
        if labels:
            for label in labels:
                label_record = WikidataEntityLabel(
                    entity_id=wikidata_id,
                    label=label,
                )
                session.add(label_record)

        # Create the politician instance
        politician = cls(wikidata_id=wikidata_id, name=name)
        session.add(politician)

        return politician

    @staticmethod
    def _get_language_popularity_cte():
        """
        Create CTE for global language popularity based on Wikipedia link counts.

        Returns:
            SQLAlchemy CTE with columns: wikipedia_project_id, global_count
        """
        return (
            select(
                WikipediaLink.wikipedia_project_id, func.count().label("global_count")
            )
            .group_by(WikipediaLink.wikipedia_project_id)
            .cte("language_popularity")
            .prefix_with("MATERIALIZED")
        )

    @classmethod
    def _get_ranked_wikipedia_links_cte(cls, countries: List[str] = None):
        """
        Create CTE for ranking Wikipedia links by citizenship match and global popularity.

        This is the shared ranking logic used by both get_priority_wikipedia_links
        and query_for_enrichment to ensure consistent behavior.

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
        language_popularity = cls._get_language_popularity_cte()

        # CTE 2: Politician-language citizenship matches
        # Pre-compute which (politician, language) pairs have a citizenship match
        # by joining citizenships with official languages
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
            .where(
                and_(
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.isnot(None),
                    Property.deleted_at.is_(None),
                )
            )
            .distinct()
            .cte("citizenship_language_matches")
        )

        # CTE 3: Ranked Wikipedia links
        # Use LEFT JOIN to citizenship_language_matches to determine match flag
        ranked_links_query = (
            select(
                cls.id.label("politician_id"),
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
                    partition_by=cls.id,
                    order_by=[
                        case(
                            (
                                citizenship_language_matches.c.politician_id.isnot(
                                    None
                                ),
                                1,
                            ),
                            else_=0,
                        ).desc(),
                        language_popularity.c.global_count.desc(),
                    ],
                )
                .label("rank"),
            )
            .select_from(cls)
            .join(WikipediaLink, WikipediaLink.politician_id == cls.id)
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
                    citizenship_language_matches.c.politician_id == cls.id,
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
            ranked_links_query = ranked_links_query.where(cls.id.in_(country_filter))

        return ranked_links_query.distinct().cte("ranked_wikipedia_links")

    @staticmethod
    def get_enrichment_cooldown_days() -> int:
        """
        Get the enrichment cooldown period in days.

        Uses ENRICHMENT_COOLDOWN_DAYS environment variable (default: 365).

        Returns:
            int: The cooldown period in days
        """
        return int(os.getenv("ENRICHMENT_COOLDOWN_DAYS", "365"))

    @staticmethod
    def get_enrichment_cooldown_cutoff() -> datetime:
        """
        Get the cutoff datetime for enrichment cooldown period.

        Uses ENRICHMENT_COOLDOWN_DAYS environment variable (default: 365).

        Returns:
            datetime: The cutoff date - politicians enriched after this are considered "recently enriched"
        """
        cooldown_days = Politician.get_enrichment_cooldown_days()
        return datetime.now(timezone.utc) - timedelta(days=cooldown_days)

    @hybrid_property
    def needs_enrichment(self) -> bool:
        if self.enriched_at is None:
            return True
        enriched_at = self.enriched_at.replace(tzinfo=timezone.utc)
        return enriched_at < self.get_enrichment_cooldown_cutoff()

    @needs_enrichment.expression
    def needs_enrichment(cls):
        cutoff = cls.get_enrichment_cooldown_cutoff()
        return or_(
            cls.enriched_at.is_(None),
            cls.enriched_at < cutoff,
        )

    @classmethod
    def query_base(cls):
        """
        Build base query for politicians, filtering out soft-deleted entities.

        Returns:
            SQLAlchemy select statement for Politician entities
        """
        return (
            select(cls)
            .join(WikidataEntity, cls.wikidata_id == WikidataEntity.wikidata_id)
            .where(WikidataEntity.deleted_at.is_(None))
        )

    @classmethod
    def filter_by_unevaluated_properties(cls, query, languages: List[str] = None):
        """
        Apply unevaluated properties filter to a politician query.

        Filters for politicians with properties that have no statement_id (unevaluated).
        Optionally filters by language via sources.

        Args:
            query: Existing select statement for Politician entities
            languages: Optional list of language QIDs to filter by

        Returns:
            Modified select statement with unevaluated filter applied
        """
        # Build existence subquery for unevaluated properties
        unevaluated_exists = exists(
            select(1)
            .select_from(Property)
            .where(
                and_(
                    Property.politician_id == cls.id,
                    Property.statement_id.is_(None),
                    Property.deleted_at.is_(None),
                )
            )
        )

        # Apply language filtering via PropertyReference → SourceLanguage
        # Skip the Source join — PropertyReference.source_id links directly
        if languages:
            unevaluated_exists = exists(
                select(1)
                .select_from(Property)
                .join(
                    PropertyReference,
                    PropertyReference.property_id == Property.id,
                )
                .join(
                    SourceLanguage,
                    SourceLanguage.source_id == PropertyReference.source_id,
                )
                .where(
                    and_(
                        Property.politician_id == cls.id,
                        Property.statement_id.is_(None),
                        Property.deleted_at.is_(None),
                        SourceLanguage.language_id.in_(languages),
                    )
                )
            )

        return query.where(unevaluated_exists)

    @classmethod
    def filter_by_countries(cls, query, countries: List[str]):
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
                    Property.politician_id == cls.id,
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.in_(countries),
                    Property.deleted_at.is_(None),
                )
            )
        )
        return query.where(citizenship_exists)

    @classmethod
    def query_for_enrichment(
        cls,
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

        query = (
            select(cls)
            .join(WikidataEntity, cls.wikidata_id == WikidataEntity.wikidata_id)
            .where(
                and_(
                    exists(select(1).where(WikipediaLink.politician_id == cls.id)),
                    WikidataEntity.deleted_at.is_(None),
                    cls.wikidata_id.isnot(None),
                    cls.needs_enrichment,
                )
            )
        )

        # Stateless mode: filter for politicians without citizenship
        # Uses idx_properties_citizenship_lookup for efficient NOT EXISTS check
        if stateless:
            has_citizenship = exists(
                select(1).where(
                    and_(
                        Property.politician_id == cls.id,
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
            ranked_links = cls._get_ranked_wikipedia_links_cte(countries=countries)

            # Subquery: Politicians where filtered language is in top 3 by rank
            top_3_languages = select(ranked_links.c.politician_id.distinct()).where(
                and_(
                    ranked_links.c.language_qid.in_(languages),
                    ranked_links.c.rank <= 3,
                )
            )

            query = query.where(cls.id.in_(top_3_languages))

        # Apply country filtering (only if not already applied via language CTE)
        elif countries:
            citizenship_subquery = select(Property.politician_id).where(
                and_(
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.in_(countries),
                    Property.deleted_at.is_(None),
                )
            )
            query = query.where(cls.id.in_(citizenship_subquery))

        return query

    @classmethod
    def count_unevaluated(
        cls,
        db: Session,
        languages: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
    ) -> int:
        """Count politicians that have unevaluated extracted properties."""
        query = cls.query_base()
        query = cls.filter_by_unevaluated_properties(query, languages=languages)

        if countries:
            query = cls.filter_by_countries(query, countries)

        count_query = select(func.count()).select_from(query.subquery())
        result = db.execute(count_query).scalar()
        return result or 0

    @classmethod
    def has_enrichable(
        cls,
        db: Session,
        languages: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        stateless: bool = False,
    ) -> bool:
        """Check if there are politicians available to enrich."""
        query = cls.query_for_enrichment(
            languages=languages,
            countries=countries,
            stateless=stateless,
        ).limit(1)

        result = db.execute(query).first()
        return result is not None

    @classmethod
    def count_stateless_with_unevaluated_citizenship(cls, db: Session) -> int:
        """
        Count politicians without Wikidata citizenship who have unevaluated extracted citizenship.

        These are politicians where:
        1. No citizenship property exists from Wikidata (source_id IS NULL)
        2. At least one extracted citizenship exists (source_id IS NOT NULL, statement_id IS NULL)

        This count represents the "buffer" of stateless politicians whose extracted
        citizenship is waiting for review. Used to throttle stateless enrichment.

        Args:
            db: Database session

        Returns:
            Count of stateless politicians with unevaluated extracted citizenship
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

        # Count politicians who:
        # - Have unevaluated extracted citizenship
        # - Don't have Wikidata citizenship
        count_query = (
            select(func.count())
            .select_from(cls)
            .where(
                and_(
                    cls.id.in_(has_unevaluated_extracted_citizenship),
                    ~cls.id.in_(has_wikidata_citizenship),
                )
            )
        )

        result = db.execute(count_query).scalar()
        return result or 0

    # Relationships
    wikidata_entity = relationship("WikidataEntity", back_populates="politician")
    properties = relationship(
        "Property", back_populates="politician", cascade="all, delete-orphan"
    )
    wikipedia_links = relationship(
        "WikipediaLink", back_populates="politician", cascade="all, delete-orphan"
    )
    sources = relationship(
        "Source",
        secondary="politician_sources",
        back_populates="politicians",
    )


class WikipediaLink(Base, TimestampMixin, UpsertMixin):
    """Wikipedia link entity for storing politician Wikipedia article URLs."""

    __tablename__ = "wikipedia_links"
    __table_args__ = (
        Index(
            "idx_wikipedia_links_politician_project",
            "politician_id",
            "wikipedia_project_id",
            unique=True,
        ),
    )

    # UpsertMixin configuration
    _upsert_conflict_columns = ["politician_id", "wikipedia_project_id"]
    _upsert_update_columns = ["url"]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
    )
    url = Column(String, nullable=False)
    wikipedia_project_id = Column(
        String,
        ForeignKey("wikipedia_projects.wikidata_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    politician = relationship("Politician", back_populates="wikipedia_links")
    wikipedia_project = relationship("WikipediaProject")
