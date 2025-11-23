"""Politician domain models: Politician, Property, WikipediaLink, ArchivedPage."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import List

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Row
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, relationship
from sqlalchemy import event
from sqlalchemy.orm import aliased

from ..wikidata_date import WikidataDate
from .base import (
    Base,
    EntityCreationMixin,
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

    @property
    def is_deceased(self) -> bool:
        """Check if politician is deceased based on death_date property."""
        return any(prop.type == PropertyType.DEATH_DATE for prop in self.properties)

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

    def create_references_json(self) -> list:
        """Create references_json for this Wikipedia source."""
        return [
            {
                "property": {"id": "P854"},  # Reference URL
                "value": {"type": "value", "content": self.url},
            }
        ]


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
    proof_line = Column(
        String, nullable=True
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

    def should_store(self, db: Session) -> bool:
        """Check if this property should be stored based on existing data.

        For positions: only store if we have more precise or different timeframe data.
        For value properties (dates): only store if we have more precise data.
        For other entity properties: only store if no duplicate exists.
        """
        if self.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
            # For date properties, check for more precise data
            existing_dates = (
                db.query(Property)
                .filter_by(
                    politician_id=self.politician_id,
                    type=self.type,
                )
                .all()
            )

            if not existing_dates:
                return True

            # Convert our date to WikidataDate
            new_date = WikidataDate.from_wikidata_time(self.value, self.value_precision)

            # Check against existing dates
            for existing in existing_dates:
                existing_date = WikidataDate.from_wikidata_time(
                    existing.value, existing.value_precision
                )

                # If dates could be the same, check precision
                if WikidataDate.dates_could_be_same(new_date, existing_date):
                    more_precise = WikidataDate.more_precise_date(
                        new_date, existing_date
                    )
                    # Only store if we're more precise
                    if more_precise != new_date:
                        return False
            return True

        elif self.type != PropertyType.POSITION:
            # For non-position entity properties, check for exact duplicates
            existing = (
                db.query(Property)
                .filter_by(
                    politician_id=self.politician_id,
                    type=self.type,
                    entity_id=self.entity_id,
                )
                .first()
            )
            return existing is None

        # For positions, use sophisticated timeframe comparison
        existing_positions = (
            db.query(Property)
            .filter_by(
                politician_id=self.politician_id,
                type=PropertyType.POSITION,
                entity_id=self.entity_id,
            )
            .all()
        )

        if not existing_positions:
            return True

        # Extract our dates from qualifiers
        new_start = None
        new_end = None

        if self.qualifiers_json:
            if "P580" in self.qualifiers_json:
                start_data = self.qualifiers_json["P580"][0]["datavalue"]["value"]
                new_start = WikidataDate.from_wikidata_time(
                    start_data["time"], start_data["precision"]
                )
            if "P582" in self.qualifiers_json:
                end_data = self.qualifiers_json["P582"][0]["datavalue"]["value"]
                new_end = WikidataDate.from_wikidata_time(
                    end_data["time"], end_data["precision"]
                )

        # Check against each existing position
        for existing in existing_positions:
            existing_start = None
            existing_end = None

            if existing.qualifiers_json:
                if "P580" in existing.qualifiers_json:
                    start_data = existing.qualifiers_json["P580"][0]["datavalue"][
                        "value"
                    ]
                    existing_start = WikidataDate.from_wikidata_time(
                        start_data["time"], start_data["precision"]
                    )
                if "P582" in existing.qualifiers_json:
                    end_data = existing.qualifiers_json["P582"][0]["datavalue"]["value"]
                    existing_end = WikidataDate.from_wikidata_time(
                        end_data["time"], end_data["precision"]
                    )

            # Don't store position without dates when we already have position with dates
            new_has_no_dates = new_start is None and new_end is None
            existing_has_dates = existing_start is not None or existing_end is not None
            if new_has_no_dates and existing_has_dates:
                return False

            # Check if timeframes could be the same
            start_same = WikidataDate.dates_could_be_same(new_start, existing_start)
            end_same = WikidataDate.dates_could_be_same(new_end, existing_end)

            if start_same and end_same:
                # Same timeframe - check if new data is more precise
                start_more_precise = WikidataDate.more_precise_date(
                    new_start, existing_start
                )
                end_more_precise = WikidataDate.more_precise_date(new_end, existing_end)

                # Check if we have more precise data
                # more_precise_date returns None when dates have equal precision or both are None
                has_more_precise_start = (
                    start_more_precise is not None and start_more_precise == new_start
                )
                has_more_precise_end = (
                    end_more_precise is not None and end_more_precise == new_end
                )

                # If we don't have more precise data for any date, don't store
                if not has_more_precise_start and not has_more_precise_end:
                    return False

        return True  # New timeframe or more precise data
