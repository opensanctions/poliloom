"""Politician domain models: Politician, Property, WikipediaLink, ArchivedPage."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from dicttoxml import dicttoxml
from sqlalchemy import (
    CheckConstraint,
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
    literal,
    or_,
    select,
    text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.engine import Row
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, relationship
from sqlalchemy import event
from sqlalchemy.orm import aliased

from ..wikidata_date import WikidataDate
from .base import (
    Base,
    EntityCreationMixin,
    PropertyComparisonResult,
    PropertyType,
    RelationType,
    SoftDeleteMixin,
    TimestampMixin,
    UpsertMixin,
)
from .entities import Language, WikipediaProject
from .wikidata import WikidataEntity, WikidataEntityMixin


class Politician(
    Base, TimestampMixin, UpsertMixin, WikidataEntityMixin, EntityCreationMixin
):
    """Politician entity."""

    __tablename__ = "politicians"

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
        Get top 3 most popular Wikipedia links for a politician, optionally filtered by citizenship languages.

        If politician has citizenships, prefers links in official languages of those countries.
        If no links match official languages, falls back to all available links.
        Otherwise returns the 3 most popular languages overall for the politician.
        Uses proper ISO codes from languages table (no fallbacks).

        Args:
            db: Database session

        Returns:
            List of Row objects containing (url, wikipedia_project_id), limited to top 3 by popularity
        """
        from .wikidata import WikidataRelation

        # CTE 1: politician_citizenships - get all citizenship country IDs
        politician_citizenships = (
            select(Property.entity_id.label("country_id"))
            .where(
                and_(
                    Property.politician_id == str(self.id),
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.isnot(None),
                )
            )
            .cte("politician_citizenships")
        )

        # CTE 2: language_popularity - count global usage of each wikipedia project
        language_popularity = self._get_language_popularity_cte()

        # Subquery for checking if politician has any citizenships
        politician_has_citizenships = exists(
            select(literal(1)).select_from(politician_citizenships)
        )

        # Subquery for checking if language is official language of citizenship country
        # Join through WikipediaProject to get the language via P407 (language of work)
        citizenship_match_exists = exists(
            select(literal(1))
            .select_from(WikidataRelation)
            .join(
                politician_citizenships,
                WikidataRelation.child_entity_id
                == politician_citizenships.c.country_id,
            )
            .where(
                and_(
                    WikidataRelation.parent_entity_id == Language.wikidata_id,
                    WikidataRelation.relation_type == "OFFICIAL_LANGUAGE",
                )
            )
        )

        # CTE 3: links_with_citizenship_flag - join all data and compute citizenship match
        # Join WikipediaLink -> WikipediaProject -> Language (via P407 relation)
        links_with_citizenship_flag = (
            select(
                WikipediaLink.url,
                WikipediaLink.wikipedia_project_id,
                language_popularity.c.global_count.label("language_popularity"),
                case(
                    (
                        and_(politician_has_citizenships, citizenship_match_exists),
                        1,
                    ),
                    else_=0,
                ).label("matches_citizenship"),
            )
            .select_from(WikipediaLink)
            .join(
                WikipediaProject,
                WikipediaLink.wikipedia_project_id == WikipediaProject.wikidata_id,
            )
            .join(
                WikidataRelation,
                and_(
                    WikidataRelation.child_entity_id == WikipediaProject.wikidata_id,
                    WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
                ),
            )
            .join(Language, WikidataRelation.parent_entity_id == Language.wikidata_id)
            .join(
                language_popularity,
                language_popularity.c.wikipedia_project_id
                == WikipediaLink.wikipedia_project_id,
            )
            .where(WikipediaLink.politician_id == str(self.id))
            .distinct()
            .cte("links_with_citizenship_flag")
        )

        # Final query: select and order by citizenship match, then popularity
        query = (
            select(
                links_with_citizenship_flag.c.url,
                links_with_citizenship_flag.c.wikipedia_project_id,
            )
            .select_from(links_with_citizenship_flag)
            .order_by(
                links_with_citizenship_flag.c.matches_citizenship.desc(),
                links_with_citizenship_flag.c.language_popularity.desc(),
            )
            .limit(3)
        )

        result = db.execute(query)
        return result.fetchall()

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
        from .wikidata import WikidataEntity, WikidataEntityLabel

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

        Used by both get_priority_wikipedia_links and query_for_enrichment to ensure
        consistent popularity calculations.

        Returns:
            SQLAlchemy CTE with columns: wikipedia_project_id, global_count
        """
        return (
            select(
                WikipediaLink.wikipedia_project_id, func.count().label("global_count")
            )
            .group_by(WikipediaLink.wikipedia_project_id)
            .cte("language_popularity")
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
        Optionally filters by language via archived pages.

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

        # Apply language filtering via archived pages if specified
        if languages:
            unevaluated_exists = exists(
                select(1)
                .select_from(Property)
                .join(ArchivedPage, Property.archived_page_id == ArchivedPage.id)
                .join(
                    ArchivedPageLanguage,
                    ArchivedPageLanguage.archived_page_id == ArchivedPage.id,
                )
                .where(
                    and_(
                        Property.politician_id == cls.id,
                        Property.statement_id.is_(None),
                        Property.deleted_at.is_(None),
                        ArchivedPageLanguage.language_id.in_(languages),
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
    ):
        """
        Build a query for politicians that should be enriched.

        Uses citizenship-based language filtering that mirrors get_priority_wikipedia_links logic,
        considering both citizenship matching and language popularity.

        This ensures that filtered languages would actually be selected by get_priority_wikipedia_links.

        Args:
            languages: Optional list of language QIDs to filter by
            countries: Optional list of country QIDs to filter by

        Returns:
            SQLAlchemy select statement for politician IDs
        """
        from .wikidata import WikidataRelation

        # Calculate 6-month cooldown threshold
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)

        # Base query: politicians with Wikipedia links and non-soft-deleted WikidataEntity
        # Exclude politicians enriched within the last 6 months to prevent rapid re-enrichment
        politician_ids_query = (
            select(cls.id.distinct())
            .join(WikidataEntity, cls.wikidata_id == WikidataEntity.wikidata_id)
            .where(
                and_(
                    exists(select(1).where(WikipediaLink.politician_id == cls.id)),
                    WikidataEntity.deleted_at.is_(None),
                    or_(
                        cls.enriched_at.is_(None),  # Never enriched
                        cls.enriched_at
                        < six_months_ago,  # Or enriched more than 6 months ago
                    ),
                )
            )
        )

        # Apply language filtering using citizenship-based matching with top-3 popularity limit
        if languages:
            # Strategy: Match politicians where filtered language would be in top 3 selected by get_priority_wikipedia_links
            # Mimics get_priority_wikipedia_links logic: citizenship match + global popularity, top 3

            # CTE 1: Global language popularity (count of Wikipedia links per wikipedia project)
            language_popularity = cls._get_language_popularity_cte()

            # CTE 2: For each politician, their citizenship-matched languages with links, ranked by global popularity
            # Join through WikipediaProject -> Language (via P407 relation)
            # Use aliased WikidataRelation for country->language to avoid ambiguous joins
            CountryLanguageRelation = aliased(WikidataRelation)

            politician_language_ranks = (
                select(
                    cls.id.label("politician_id"),
                    Language.wikidata_id.label("language_qid"),
                    func.row_number()
                    .over(
                        partition_by=cls.id,
                        order_by=language_popularity.c.global_count.desc(),
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
                        WikidataRelation.child_entity_id
                        == WikipediaProject.wikidata_id,
                        WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
                    ),
                )
                .join(
                    Language, WikidataRelation.parent_entity_id == Language.wikidata_id
                )
                .join(
                    language_popularity,
                    language_popularity.c.wikipedia_project_id
                    == WikipediaLink.wikipedia_project_id,
                )
                .join(
                    Property,
                    and_(
                        Property.politician_id == cls.id,
                        Property.type == PropertyType.CITIZENSHIP,
                    ),
                )
                .join(
                    CountryLanguageRelation,
                    and_(
                        Property.entity_id == CountryLanguageRelation.child_entity_id,
                        CountryLanguageRelation.relation_type
                        == RelationType.OFFICIAL_LANGUAGE,
                        CountryLanguageRelation.parent_entity_id
                        == Language.wikidata_id,
                    ),
                )
                .distinct()
                .cte("politician_language_ranks")
            )

            # Subquery: Politicians where filtered language is in top 3 by rank
            top_3_languages = select(
                politician_language_ranks.c.politician_id.distinct()
            ).where(
                and_(
                    politician_language_ranks.c.language_qid.in_(languages),
                    politician_language_ranks.c.rank <= 3,
                )
            )

            politician_ids_query = politician_ids_query.where(
                cls.id.in_(top_3_languages)
            )

        # Apply country filtering
        if countries:
            citizenship_subquery = select(Property.politician_id).where(
                and_(
                    Property.type == PropertyType.CITIZENSHIP,
                    Property.entity_id.in_(countries),
                )
            )
            politician_ids_query = politician_ids_query.where(
                cls.id.in_(citizenship_subquery)
            )

        return politician_ids_query

    # Relationships
    wikidata_entity = relationship("WikidataEntity", back_populates="politician")
    properties = relationship(
        "Property", back_populates="politician", cascade="all, delete-orphan"
    )
    wikipedia_links = relationship(
        "WikipediaLink", back_populates="politician", cascade="all, delete-orphan"
    )


class ArchivedPageLanguage(Base, TimestampMixin):
    """Link table between archived pages and language entities."""

    __tablename__ = "archived_page_languages"

    archived_page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("archived_pages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    language_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )

    # Relationships
    archived_page = relationship(
        "ArchivedPage", back_populates="archived_page_languages"
    )
    language_entity = relationship("WikidataEntity")


class ArchivedPage(Base, TimestampMixin):
    """Archived page entity for storing fetched web page metadata."""

    __tablename__ = "archived_pages"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    url = Column(String, nullable=False)
    permanent_url = Column(String, nullable=True)  # Wikipedia oldid URL for references
    content_hash = Column(
        String, nullable=False, index=True
    )  # SHA256 hash for deduplication
    fetch_timestamp = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    wikipedia_project_id = Column(
        String,
        ForeignKey("wikipedia_projects.wikidata_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    properties = relationship("Property", back_populates="archived_page")
    archived_page_languages = relationship(
        "ArchivedPageLanguage",
        back_populates="archived_page",
        cascade="all, delete-orphan",
    )
    language_entities = relationship(
        "WikidataEntity", secondary="archived_page_languages", viewonly=True
    )
    wikipedia_project = relationship("WikipediaProject")

    @staticmethod
    def _generate_content_hash(url: str) -> str:
        """Generate a content hash for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @property
    def path_root(self) -> str:
        """Get the path root (timestamp/content_hash structure) for this archived page."""
        date_path = f"{self.fetch_timestamp.year:04d}/{self.fetch_timestamp.month:02d}/{self.fetch_timestamp.day:02d}"
        return f"{date_path}/{self.content_hash}"

    def link_languages_from_project(self, db) -> None:
        """Link languages from Wikipedia project's LANGUAGE_OF_WORK relations.

        Args:
            db: Database session for querying language relations
        """
        if not self.wikipedia_project_id:
            return

        from sqlalchemy import select
        from .wikidata import WikidataRelation, RelationType

        language_query = select(WikidataRelation.parent_entity_id).where(
            WikidataRelation.child_entity_id == self.wikipedia_project_id,
            WikidataRelation.relation_type == RelationType.LANGUAGE_OF_WORK,
        )
        language_ids = db.execute(language_query).scalars().all()

        for language_id in language_ids:
            self.archived_page_languages.append(
                ArchivedPageLanguage(language_id=language_id)
            )

    def save_archived_files(
        self,
        mhtml_content: Optional[str],
        html_content: Optional[str],
        markdown_content: Optional[str],
    ) -> None:
        """Save archived content files (MHTML, HTML, markdown) to storage.

        Args:
            mhtml_content: MHTML content to save
            html_content: HTML content to save
            markdown_content: Markdown content to save
        """
        from .. import archive
        import logging

        logger = logging.getLogger(__name__)

        if mhtml_content:
            mhtml_path = archive.save_archived_content(
                self.path_root, "mhtml", mhtml_content
            )
            logger.info(f"Saved MHTML archive: {mhtml_path}")

        if html_content:
            html_path = archive.save_archived_content(
                self.path_root, "html", html_content
            )
            logger.info(f"Saved HTML from MHTML: {html_path}")

        if markdown_content:
            markdown_path = archive.save_archived_content(
                self.path_root, "md", markdown_content
            )
            logger.info(f"Saved markdown content: {markdown_path}")

    def create_references_json(self) -> list:
        """Create references_json for this archived page source.

        For Wikipedia sources (when wikipedia_project_id exists):
        - P4656 (Wikimedia import URL) if permanent_url exists
        - P143 (imported from): Wikipedia project (e.g., Q328 for English Wikipedia)
        - P813 (retrieved): Date when the page was fetched

        For non-Wikipedia sources:
        - P854 (reference URL): The page URL
        - P813 (retrieved): Date when the page was fetched
        """
        from ..wikidata_date import WikidataDate

        references = []

        if self.wikipedia_project_id:
            # Wikipedia source - use permanent_url with P4656 if available
            if self.permanent_url:
                references.append(
                    {
                        "property": {"id": "P4656"},  # Wikimedia import URL
                        "value": {"type": "value", "content": self.permanent_url},
                    }
                )

            # Always add P143 (imported from) for Wikipedia sources
            references.append(
                {
                    "property": {"id": "P143"},  # Imported from
                    "value": {"type": "value", "content": self.wikipedia_project_id},
                }
            )
        else:
            # Non-Wikipedia source - use P854 (reference URL)
            references.append(
                {
                    "property": {"id": "P854"},  # Reference URL
                    "value": {"type": "value", "content": self.url},
                }
            )

        fetch_date_str = self.fetch_timestamp.strftime("%Y-%m-%d")
        wikidata_date = WikidataDate.from_date_string(fetch_date_str)
        if wikidata_date:
            references.append(
                {
                    "property": {"id": "P813"},
                    "value": {
                        "type": "value",
                        "content": wikidata_date.to_wikidata_value(),
                    },
                }
            )

        return references


@event.listens_for(ArchivedPage, "before_insert")
def generate_archived_page_content_hash(mapper, connection, target):
    """Auto-generate content_hash before inserting ArchivedPage."""
    if target.url and not target.content_hash:
        # Generate content hash from URL
        target.content_hash = ArchivedPage._generate_content_hash(target.url)


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


class Property(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Property entity for storing extracted politician properties."""

    statement_id = Column(String, nullable=True)
    qualifiers_json = Column(JSONB, nullable=True)  # Store all qualifiers as JSON
    references_json = Column(JSONB, nullable=True)  # Store all references as JSON

    __tablename__ = "properties"
    __table_args__ = (
        Index(
            "uq_properties_statement_id",
            "statement_id",
            unique=True,
            postgresql_where=Column("statement_id").isnot(None),
        ),
        Index("idx_properties_updated_at", "updated_at"),
        Index(
            "idx_properties_unevaluated",
            "politician_id",
            "archived_page_id",
            postgresql_where=text("statement_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "idx_properties_type_entity",
            "type",
            "entity_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_properties_citizenship_lookup",
            "politician_id",
            "type",
            "entity_id",
            postgresql_where=text("type = 'CITIZENSHIP' AND deleted_at IS NULL"),
        ),
        CheckConstraint(
            "(type IN ('BIRTH_DATE', 'DEATH_DATE') AND value IS NOT NULL AND value_precision IS NOT NULL AND entity_id IS NULL) "
            "OR (type IN ('BIRTHPLACE', 'POSITION', 'CITIZENSHIP') AND entity_id IS NOT NULL AND value IS NULL)",
            name="check_property_fields",
        ),
    )

    # UpsertMixin configuration
    _upsert_conflict_columns = ["statement_id"]
    _upsert_index_where = text("statement_id IS NOT NULL")
    _upsert_update_columns = [
        "value",
        "value_precision",
        "entity_id",
        "qualifiers_json",
        "references_json",
    ]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(SQLEnum(PropertyType), nullable=False, index=True)
    value = Column(String, nullable=True)  # NULL for entity relationships
    value_precision = Column(
        Integer
    )  # Wikidata precision integer for date properties (9=year, 10=month, 11=day)
    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), nullable=True, index=True
    )  # For entity relationships (birthplace, position, citizenship)
    archived_page_id = Column(
        UUID(as_uuid=True), ForeignKey("archived_pages.id"), nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    supporting_quotes = Column(
        ARRAY(String), nullable=True
    )  # NULL for Wikidata imports, set for extracted data

    @hybrid_property
    def is_extracted(self) -> bool:
        """Check if this property was extracted from a web source."""
        return self.archived_page_id is not None

    @is_extracted.expression
    def is_extracted(cls):
        """SQL expression for is_extracted."""
        return cls.archived_page_id.isnot(None)

    # Relationships
    politician = relationship("Politician", back_populates="properties")
    archived_page = relationship("ArchivedPage", back_populates="properties")
    entity = relationship("WikidataEntity")
    evaluations = relationship(
        "Evaluation", back_populates="property", cascade="all, delete-orphan"
    )

    def format_timeframe(self) -> str:
        """Extract formatted date range from qualifiers_json.

        Returns:
            Formatted date range string like " (2020 - 2023)" or empty string
        """
        if not self.qualifiers_json:
            return ""

        start_date = None
        end_date = None

        # Extract P580 (start date) and P582 (end date) from qualifiers
        if "P580" in self.qualifiers_json:
            start_qual = self.qualifiers_json["P580"][0]
            if "datavalue" in start_qual and "value" in start_qual["datavalue"]:
                time_val = start_qual["datavalue"]["value"]["time"]
                # Parse time format like "+2020-01-00T00:00:00Z"
                if time_val.startswith("+"):
                    start_date = time_val[1:5]  # Extract year

        if "P582" in self.qualifiers_json:
            end_qual = self.qualifiers_json["P582"][0]
            if "datavalue" in end_qual and "value" in end_qual["datavalue"]:
                time_val = end_qual["datavalue"]["value"]["time"]
                if time_val.startswith("+"):
                    end_date = time_val[1:5]  # Extract year

        if start_date:
            date_range = f" ({start_date}"
            if end_date:
                date_range += f" - {end_date})"
            else:
                date_range += " - present)"
            return date_range
        elif end_date:
            return f" (until {end_date})"

        return ""

    @staticmethod
    def _extract_timeframe_from_qualifiers(
        qualifiers_json: dict | None,
    ) -> tuple[WikidataDate | None, WikidataDate | None]:
        """Extract start and end dates from position qualifiers.

        Args:
            qualifiers_json: Qualifiers dict containing P580 (start) and P582 (end)

        Returns:
            Tuple of (start_date, end_date) as WikidataDate objects or None
        """
        start_date = None
        end_date = None

        if qualifiers_json:
            if "P580" in qualifiers_json:
                start_data = qualifiers_json["P580"][0]["datavalue"]["value"]
                start_date = WikidataDate.from_wikidata_time(
                    start_data["time"], start_data["precision"]
                )
            if "P582" in qualifiers_json:
                end_data = qualifiers_json["P582"][0]["datavalue"]["value"]
                end_date = WikidataDate.from_wikidata_time(
                    end_data["time"], end_data["precision"]
                )

        return start_date, end_date

    def _compare_to(self, other: "Property") -> PropertyComparisonResult:
        """Compare this property to another to determine if they match and which is more precise.

        Args:
            other: Another Property to compare against

        Returns:
            PropertyComparisonResult indicating match status and precision comparison
        """
        # Must be same type
        if self.type != other.type:
            return PropertyComparisonResult.NO_MATCH

        if self.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            # For date properties, compare values
            self_date = WikidataDate.from_wikidata_time(
                self.value, self.value_precision
            )
            other_date = WikidataDate.from_wikidata_time(
                other.value, other.value_precision
            )

            if not WikidataDate.dates_could_be_same(self_date, other_date):
                return PropertyComparisonResult.NO_MATCH

            more_precise = WikidataDate.more_precise_date(self_date, other_date)
            if more_precise is None:
                return PropertyComparisonResult.EQUAL
            if more_precise == self_date:
                return PropertyComparisonResult.SELF_MORE_PRECISE
            return PropertyComparisonResult.OTHER_MORE_PRECISE

        elif self.type == PropertyType.POSITION:
            # For positions, must have same entity_id
            if self.entity_id != other.entity_id:
                return PropertyComparisonResult.NO_MATCH

            # Compare timeframes
            self_start, self_end = self._extract_timeframe_from_qualifiers(
                self.qualifiers_json
            )
            other_start, other_end = self._extract_timeframe_from_qualifiers(
                other.qualifiers_json
            )

            # Special case: position with dates is considered more precise than without
            # Must check this before dates_could_be_same since None vs date returns False
            self_has_dates = self_start is not None or self_end is not None
            other_has_dates = other_start is not None or other_end is not None
            if self_has_dates and not other_has_dates:
                return PropertyComparisonResult.SELF_MORE_PRECISE
            if other_has_dates and not self_has_dates:
                return PropertyComparisonResult.OTHER_MORE_PRECISE

            # Check if timeframes could be the same
            start_same = WikidataDate.dates_could_be_same(self_start, other_start)
            end_same = WikidataDate.dates_could_be_same(self_end, other_end)

            if not (start_same and end_same):
                return PropertyComparisonResult.NO_MATCH

            # Compare precision of start and end dates
            start_more_precise = WikidataDate.more_precise_date(self_start, other_start)
            end_more_precise = WikidataDate.more_precise_date(self_end, other_end)

            # Determine overall precision comparison
            self_more_precise_start = (
                start_more_precise is not None and start_more_precise == self_start
            )
            self_more_precise_end = (
                end_more_precise is not None and end_more_precise == self_end
            )
            other_more_precise_start = (
                start_more_precise is not None and start_more_precise == other_start
            )
            other_more_precise_end = (
                end_more_precise is not None and end_more_precise == other_end
            )

            # Self is more precise if it has more precise data for at least one date
            # and other doesn't have more precise data for any date
            if (self_more_precise_start or self_more_precise_end) and not (
                other_more_precise_start or other_more_precise_end
            ):
                return PropertyComparisonResult.SELF_MORE_PRECISE
            if (other_more_precise_start or other_more_precise_end) and not (
                self_more_precise_start or self_more_precise_end
            ):
                return PropertyComparisonResult.OTHER_MORE_PRECISE

            return PropertyComparisonResult.EQUAL

        else:
            # For BIRTHPLACE, CITIZENSHIP - exact entity_id match, no precision concept
            if self.entity_id != other.entity_id:
                return PropertyComparisonResult.NO_MATCH
            return PropertyComparisonResult.EQUAL

    def should_store(self, db: Session) -> bool:
        """Check if this property should be stored based on existing data.

        Uses _compare_to() to check against existing properties. Only stores if:
        - No matching property exists, OR
        - This property is more precise than the existing match

        Returns False if an existing property matches and is same or more precise.
        """
        # Query for potential matching properties
        query = db.query(Property).filter_by(
            politician_id=self.politician_id,
            type=self.type,
        )

        # For entity-linked properties, also filter by entity_id
        if self.type not in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            query = query.filter_by(entity_id=self.entity_id)

        existing_properties = query.all()

        if not existing_properties:
            return True

        # Check against each existing property
        for existing in existing_properties:
            comparison = self._compare_to(existing)
            # If properties match and existing is same or more precise, don't store
            if comparison in [
                PropertyComparisonResult.OTHER_MORE_PRECISE,
                PropertyComparisonResult.EQUAL,
            ]:
                return False

        return True  # No match found, or this property is more precise

    @classmethod
    def soft_delete_matching_extracted(
        cls,
        db: Session,
        politician_id,
        property_type: PropertyType,
        value: str | None = None,
        value_precision: int | None = None,
        entity_id: str | None = None,
        qualifiers_json: dict | None = None,
    ) -> int:
        """Soft-delete extracted properties that match the given Wikidata statement.

        This method is called during import to remove unevaluated extracted properties
        that match an incoming Wikidata statement, preventing duplicates.

        Only soft-deletes if the imported statement is same or more precise than the
        extracted property.

        Args:
            db: Database session
            politician_id: UUID of the politician
            property_type: Type of property (BIRTH_DATE, POSITION, etc.)
            value: Value for date properties
            value_precision: Precision for date properties
            entity_id: Entity ID for entity-linked properties
            qualifiers_json: Qualifiers for position properties (contains P580/P582 dates)

        Returns:
            Number of properties soft-deleted
        """
        # Create a temporary Property object to use _compare_to
        imported_property = cls(
            politician_id=politician_id,
            type=property_type,
            value=value,
            value_precision=value_precision,
            entity_id=entity_id,
            qualifiers_json=qualifiers_json,
        )

        # Find extracted properties (statement_id IS NULL, archived_page_id IS NOT NULL)
        # that are not already deleted
        query = db.query(cls).filter(
            cls.politician_id == politician_id,
            cls.type == property_type,
            cls.statement_id.is_(None),  # Extracted (not from Wikidata)
            cls.archived_page_id.isnot(None),  # Has source
            cls.deleted_at.is_(None),  # Not already deleted
        )

        # For entity-linked properties, also filter by entity_id
        if property_type not in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            query = query.filter(cls.entity_id == entity_id)

        candidates = query.all()

        # Soft-delete matching properties where imported is same or more precise
        deleted_count = 0
        for candidate in candidates:
            comparison = imported_property._compare_to(candidate)
            # Soft-delete if imported is more precise or equal
            if comparison in [
                PropertyComparisonResult.SELF_MORE_PRECISE,
                PropertyComparisonResult.EQUAL,
            ]:
                candidate.soft_delete()
                deleted_count += 1

        return deleted_count
