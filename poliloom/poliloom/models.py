"""Database models for the PoliLoom project."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import List, Set
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    Index,
    text,
    func,
    Enum as SQLEnum,
    select,
    and_,
    or_,
    exists,
    case,
    literal,
)
from sqlalchemy.orm import Session, relationship, declarative_base, declared_attr
from sqlalchemy.engine import Row
from sqlalchemy.dialects.postgresql import UUID, JSONB, insert
from sqlalchemy import event
from collections import defaultdict
from sqlalchemy.ext.hybrid import hybrid_property
from pgvector.sqlalchemy import Vector
from dicttoxml import dicttoxml
from .wikidata_date import WikidataDate

Base = declarative_base()


class PropertyType(str, Enum):
    """Enumeration of allowed property types for politician properties."""

    BIRTH_DATE = "P569"
    DEATH_DATE = "P570"
    BIRTHPLACE = "P19"
    POSITION = "P39"
    CITIZENSHIP = "P27"


class PreferenceType(str, Enum):
    """Enumeration of user preference types."""

    LANGUAGE = "language"
    COUNTRY = "country"


class RelationType(str, Enum):
    """Enumeration of Wikidata relation types."""

    SUBCLASS_OF = "P279"  # Subclass of relation
    INSTANCE_OF = "P31"  # Instance of relation
    PART_OF = "P361"  # Part of relation
    LOCATED_IN = "P131"  # Located in administrative territorial entity
    COUNTRY = "P17"  # Country relation
    APPLIES_TO_JURISDICTION = "P1001"  # Applies to jurisdiction relation
    OFFICIAL_LANGUAGE = "P37"  # Official language relation


class TimestampMixin:
    """Mixin for adding timestamp fields."""

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for adding soft delete functionality."""

    deleted_at = Column(DateTime, nullable=True, index=True)

    def soft_delete(self):
        """Mark the entity as deleted by setting the deleted_at timestamp."""
        self.deleted_at = datetime.now(timezone.utc)


class UpsertMixin:
    """Mixin for adding batch upsert functionality."""

    # Override this in subclasses to specify which columns to update on conflict
    _upsert_update_columns = []
    # Override this in subclasses to specify the conflict columns (defaults to primary key)
    _upsert_conflict_columns = None
    # Override this in subclasses to specify the index WHERE clause for partial indexes
    _upsert_index_where = None

    @classmethod
    def upsert_batch(cls, session: Session, data: List[dict], returning_columns=None):
        """
        Upsert a batch of records.

        Args:
            session: Database session
            data: List of dicts with column data
            returning_columns: Optional list of columns to return from the upsert

        Returns:
            List of inserted/updated records if returning_columns specified, None otherwise
        """
        if not data:
            return [] if returning_columns else None

        stmt = insert(cls).values(data)

        # Use specified conflict columns or default to primary key
        conflict_columns = cls._upsert_conflict_columns
        if conflict_columns is None:
            conflict_columns = [col.name for col in cls.__table__.primary_key.columns]

        # Build conflict handling kwargs
        conflict_kwargs = {"index_elements": conflict_columns}
        if cls._upsert_index_where is not None:
            conflict_kwargs["index_where"] = cls._upsert_index_where

        # Update specified columns on conflict
        if cls._upsert_update_columns:
            update_dict = {
                col: getattr(stmt.excluded, col) for col in cls._upsert_update_columns
            }
            stmt = stmt.on_conflict_do_update(set_=update_dict, **conflict_kwargs)
        else:
            stmt = stmt.on_conflict_do_nothing(**conflict_kwargs)

        # Add RETURNING clause if requested
        if returning_columns:
            stmt = stmt.returning(*returning_columns)
            result = session.execute(stmt)
            return result.fetchall()
        else:
            session.execute(stmt)
            return None


class WikidataEntityMixin:
    """Mixin for entities that have a wikidata_id and wikidata_entity relationship."""

    @declared_attr
    def wikidata_id(cls):
        return Column(
            String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
        )

    @declared_attr
    def wikidata_entity(cls):
        return relationship("WikidataEntity", lazy="joined")

    @property
    def name(self) -> str:
        """Get the name from the associated WikidataEntity."""
        return self.wikidata_entity.name

    @property
    def description(self) -> str:
        """Build rich description from WikidataRelations dynamically.

        Returns:
            Rich description string built from relations
        """

        if not hasattr(self, "wikidata_entity") or not self.wikidata_entity:
            return ""

        # Use preloaded relations instead of querying database
        relations = self.wikidata_entity.parent_relations

        # Group relations by type using defaultdict
        relations_by_type = defaultdict(list)
        for relation in relations:
            if relation.parent_entity and relation.parent_entity.name:
                relations_by_type[relation.relation_type].append(
                    relation.parent_entity.name
                )

        description_parts = []

        # Add Wikidata description if available
        if self.wikidata_entity.description:
            description_parts.append(self.wikidata_entity.description)

        # Build description based on available relations
        if relations_by_type[RelationType.INSTANCE_OF]:
            instances = relations_by_type[RelationType.INSTANCE_OF]
            description_parts.append(", ".join(instances))

        if relations_by_type[RelationType.SUBCLASS_OF]:
            subclasses = relations_by_type[RelationType.SUBCLASS_OF]
            description_parts.append(f"subclass of {', '.join(subclasses)}")

        if relations_by_type[RelationType.PART_OF]:
            parts = relations_by_type[RelationType.PART_OF]
            description_parts.append(f"part of {', '.join(parts)}")

        if relations_by_type[RelationType.APPLIES_TO_JURISDICTION]:
            jurisdictions = relations_by_type[RelationType.APPLIES_TO_JURISDICTION]
            description_parts.append(
                f"applies to jurisdiction {', '.join(jurisdictions)}"
            )

        if relations_by_type[RelationType.LOCATED_IN]:
            locations = relations_by_type[RelationType.LOCATED_IN]
            description_parts.append(f"located in {', '.join(locations)}")

        if relations_by_type[RelationType.COUNTRY]:
            countries = relations_by_type[RelationType.COUNTRY]
            description_parts.append(f"country {', '.join(countries)}")

        return ", ".join(description_parts) if description_parts else ""


class EntityCreationMixin:
    """Mixin for entities that can be created with their associated WikidataEntity."""

    @classmethod
    def create_with_entity(cls, session, wikidata_id: str, name: str):
        """Create an entity with its associated WikidataEntity.

        Args:
            session: Database session
            wikidata_id: Wikidata ID for the entity
            name: Name of the entity

        Returns:
            The created entity instance (other properties can be set after creation)
        """
        # Create WikidataEntity first
        wikidata_entity = WikidataEntity(wikidata_id=wikidata_id, name=name)
        session.add(wikidata_entity)

        # Create the entity instance
        entity = cls(wikidata_id=wikidata_id)
        session.add(entity)

        return entity


class LanguageCodeMixin:
    """Mixin for adding language code fields."""

    iso1_code = Column(String, index=True)  # ISO 639-1 language code (2 characters)
    iso3_code = Column(String, index=True)  # ISO 639-3 language code (3 characters)


class Evaluation(Base, TimestampMixin):
    """Evaluation entity for tracking user evaluations of extracted properties."""

    __tablename__ = "evaluations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False)
    is_confirmed = Column(Boolean, nullable=False)
    property_id = Column(
        UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False
    )

    # Relationships
    property = relationship("Property", back_populates="evaluations")


class Preference(Base, TimestampMixin):
    """User preference entity for storing user language and country preferences."""

    __tablename__ = "preferences"
    __table_args__ = (
        Index(
            "uq_preferences_user_type_entity",
            "user_id",
            "preference_type",
            "entity_id",
            unique=True,
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False, index=True)
    preference_type = Column(SQLEnum(PreferenceType), nullable=False, index=True)
    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), nullable=False
    )

    # Relationships
    entity = relationship("WikidataEntity")


class Politician(Base, TimestampMixin, UpsertMixin, EntityCreationMixin):
    """Politician entity."""

    __tablename__ = "politicians"

    # UpsertMixin configuration
    _upsert_update_columns = ["name"]
    _upsert_conflict_columns = ["wikidata_id"]

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name = Column(String, nullable=False)
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
            List of Row objects containing (url, iso1_code, iso3_code), limited to top 3 by popularity
        """

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

        # CTE 2: language_popularity - count global usage of each language
        language_popularity = self._get_language_popularity_cte()

        # Subquery for checking if politician has any citizenships
        politician_has_citizenships = exists(
            select(literal(1)).select_from(politician_citizenships)
        )

        # Subquery for checking if language is official language of citizenship country
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
        links_with_citizenship_flag = (
            select(
                WikipediaLink.url,
                Language.iso1_code,
                Language.iso3_code,
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
                Language,
                or_(
                    WikipediaLink.iso_code == Language.iso1_code,
                    WikipediaLink.iso_code == Language.iso3_code,
                ),
            )
            .join(
                language_popularity,
                language_popularity.c.iso_code == WikipediaLink.iso_code,
            )
            .where(WikipediaLink.politician_id == str(self.id))
            .distinct()
            .cte("links_with_citizenship_flag")
        )

        # Final query: select and order by citizenship match, then popularity
        query = (
            select(
                links_with_citizenship_flag.c.url,
                links_with_citizenship_flag.c.iso1_code,
                links_with_citizenship_flag.c.iso3_code,
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
    def create_with_entity(cls, session, wikidata_id: str, name: str):
        """Create a Politician with its associated WikidataEntity."""
        # Call parent mixin method
        politician = super().create_with_entity(session, wikidata_id, name)
        # Set the name directly on the politician (since it doesn't inherit from WikidataEntityMixin)
        politician.name = name
        return politician

    @staticmethod
    def _get_language_popularity_cte():
        """
        Create CTE for global language popularity based on Wikipedia link counts.

        Used by both get_priority_wikipedia_links and query_for_enrichment to ensure
        consistent popularity calculations.

        Returns:
            SQLAlchemy CTE with columns: iso_code, global_count
        """
        return (
            select(WikipediaLink.iso_code, func.count().label("global_count"))
            .group_by(WikipediaLink.iso_code)
            .cte("language_popularity")
        )

    @classmethod
    def query_with_unevaluated_properties(
        cls,
        languages: List[str] = None,
        countries: List[str] = None,
    ):
        """
        Build a query for politician IDs that have unevaluated properties.

        This is the canonical query logic for API endpoints (evaluation workflow).
        Uses archived page language filtering as optimization since pages already exist.

        Args:
            languages: Optional list of language QIDs to filter by
            countries: Optional list of country QIDs to filter by

        Returns:
            SQLAlchemy select statement for politician IDs
        """
        from sqlalchemy import select, and_, or_

        # Find politician IDs that have unevaluated properties
        politician_ids_query = (
            select(cls.id.distinct())
            .join(Property)
            .where(and_(Property.statement_id.is_(None), Property.deleted_at.is_(None)))
        )

        # Apply language filtering via archived pages (performance optimization)
        if languages:
            politician_ids_query = (
                politician_ids_query.join(
                    ArchivedPage, Property.archived_page_id == ArchivedPage.id
                )
                .join(
                    Language,
                    or_(
                        and_(
                            ArchivedPage.iso1_code.isnot(None),
                            ArchivedPage.iso1_code == Language.iso1_code,
                        ),
                        and_(
                            ArchivedPage.iso3_code.isnot(None),
                            ArchivedPage.iso3_code == Language.iso3_code,
                        ),
                    ),
                )
                .where(Language.wikidata_id.in_(languages))
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
        # Base query: politicians with Wikipedia links
        politician_ids_query = select(cls.id.distinct()).where(
            exists(select(1).where(WikipediaLink.politician_id == cls.id))
        )

        # Apply language filtering using citizenship-based matching with top-3 popularity limit
        if languages:
            # Strategy: Match politicians where filtered language would be in top 3 selected by get_priority_wikipedia_links
            # Mimics get_priority_wikipedia_links logic: citizenship match + global popularity, top 3

            # CTE 1: Global language popularity (count of Wikipedia links per language)
            language_popularity = cls._get_language_popularity_cte()

            # CTE 2: For each politician, their citizenship-matched languages with links, ranked by global popularity
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
                    Language,
                    or_(
                        WikipediaLink.iso_code == Language.iso1_code,
                        WikipediaLink.iso_code == Language.iso3_code,
                    ),
                )
                .join(
                    language_popularity,
                    language_popularity.c.iso_code == WikipediaLink.iso_code,
                )
                .join(
                    Property,
                    and_(
                        Property.politician_id == cls.id,
                        Property.type == PropertyType.CITIZENSHIP,
                    ),
                )
                .join(
                    WikidataRelation,
                    and_(
                        Property.entity_id == WikidataRelation.child_entity_id,
                        WikidataRelation.relation_type == "OFFICIAL_LANGUAGE",
                        WikidataRelation.parent_entity_id == Language.wikidata_id,
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


class ArchivedPage(Base, TimestampMixin, LanguageCodeMixin):
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

    # Relationships
    properties = relationship("Property", back_populates="archived_page")

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
            "idx_wikipedia_links_politician_iso_code",
            "politician_id",
            "iso_code",
            unique=True,
        ),
    )

    # UpsertMixin configuration
    _upsert_conflict_columns = ["politician_id", "iso_code"]
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
    iso_code = Column(String, nullable=False, index=True)  # e.g., 'en', 'de', 'fr'

    # Relationships
    politician = relationship("Politician", back_populates="wikipedia_links")


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
    type = Column(SQLEnum(PropertyType), nullable=False)
    value = Column(String, nullable=True)  # NULL for entity relationships
    value_precision = Column(
        Integer
    )  # Wikidata precision integer for date properties (9=year, 10=month, 11=day)
    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), nullable=True
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


class Country(
    Base, TimestampMixin, UpsertMixin, WikidataEntityMixin, EntityCreationMixin
):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    # UpsertMixin configuration
    _upsert_update_columns = ["iso_code"]

    iso_code = Column(String, index=True)  # ISO 3166-1 alpha-2 code
    embedding = Column(Vector(384), nullable=True)


class Language(
    Base,
    TimestampMixin,
    LanguageCodeMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Language entity for storing language information."""

    __tablename__ = "languages"
    __table_args__ = (
        Index("idx_languages_iso1_code", "iso1_code"),
        Index("idx_languages_iso3_code", "iso3_code"),
    )

    # UpsertMixin configuration
    _upsert_update_columns = ["iso1_code", "iso3_code"]


class Location(
    Base, TimestampMixin, UpsertMixin, WikidataEntityMixin, EntityCreationMixin
):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    embedding = Column(Vector(384), nullable=True)


class Position(
    Base, TimestampMixin, UpsertMixin, WikidataEntityMixin, EntityCreationMixin
):
    """Position entity for political positions."""

    __tablename__ = "positions"

    embedding = Column(Vector(384), nullable=True)


class WikidataDump(Base, TimestampMixin):
    """WikidataDump entity for tracking dump download and processing stages."""

    __tablename__ = "wikidata_dumps"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    url = Column(String, nullable=False)  # Full URL to the dump file
    last_modified = Column(
        DateTime, nullable=False
    )  # From HEAD request Last-Modified header

    # Processing timestamps
    downloaded_at = Column(DateTime, nullable=True)  # When download completed
    extracted_at = Column(DateTime, nullable=True)  # When extraction completed
    imported_hierarchy_at = Column(
        DateTime, nullable=True
    )  # When hierarchy import completed
    imported_entities_at = Column(
        DateTime, nullable=True
    )  # When entities import completed
    imported_politicians_at = Column(
        DateTime, nullable=True
    )  # When politicians import completed


class WikidataEntity(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Wikidata entity for hierarchy storage."""

    __tablename__ = "wikidata_entities"
    __table_args__ = (Index("idx_wikidata_entities_updated_at", "updated_at"),)

    # UpsertMixin configuration
    _upsert_update_columns = ["name", "description"]

    wikidata_id = Column(String, primary_key=True)  # Wikidata QID as primary key
    name = Column(
        String, nullable=True
    )  # Entity name from Wikidata labels (can be None)
    description = Column(
        String, nullable=True
    )  # Entity description from Wikidata descriptions (can be None)

    # Relationships
    parent_relations = relationship(
        "WikidataRelation",
        foreign_keys="WikidataRelation.child_entity_id",
        back_populates="child_entity",
        cascade="all, delete-orphan",
    )
    child_relations = relationship(
        "WikidataRelation",
        foreign_keys="WikidataRelation.parent_entity_id",
        back_populates="parent_entity",
        cascade="all, delete-orphan",
    )
    politician = relationship("Politician", back_populates="wikidata_entity")
    location = relationship("Location", back_populates="wikidata_entity")
    position = relationship("Position", back_populates="wikidata_entity")
    country = relationship("Country", back_populates="wikidata_entity")
    language = relationship("Language", back_populates="wikidata_entity")

    @classmethod
    def query_hierarchy_descendants(
        cls,
        session: Session,
        root_ids: List[str],
        ignore_ids: List[str] = None,
        relation_type: RelationType = RelationType.SUBCLASS_OF,
    ) -> Set[str]:
        """
        Query all descendants of multiple root entities from database using recursive SQL.
        Only returns classes that have names and excludes ignored IDs and their descendants.

        Args:
            session: Database session
            root_ids: List of root entity QIDs
            ignore_ids: List of entity QIDs to exclude along with their descendants
            relation_type: Type of relation to follow (defaults to SUBCLASS_OF)

        Returns:
            Set of all descendant QIDs (including the roots) that have names
        """
        if not root_ids:
            return set()

        ignore_ids = ignore_ids or []

        # Use recursive CTEs - one for descendants, one for ignored descendants
        sql = text(
            """
            WITH RECURSIVE descendants AS (
                -- Base case: start with all root entities
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities 
                WHERE wikidata_id = ANY(:root_ids)
                UNION
                -- Recursive case: find all children
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
                WHERE sr.relation_type = :relation_type
            ),
            ignored_descendants AS (
                -- Base case: start with ignored IDs
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities 
                WHERE wikidata_id = ANY(:ignore_ids)
                UNION
                -- Recursive case: find all children of ignored IDs
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN ignored_descendants id ON sr.parent_entity_id = id.wikidata_id
                WHERE sr.relation_type = :relation_type
            )
            SELECT DISTINCT d.wikidata_id 
            FROM descendants d
            JOIN wikidata_entities wc ON d.wikidata_id = wc.wikidata_id
            WHERE wc.name IS NOT NULL
            AND d.wikidata_id NOT IN (SELECT wikidata_id FROM ignored_descendants)
        """
        )

        result = session.execute(
            sql,
            {
                "root_ids": root_ids,
                "ignore_ids": ignore_ids,
                "relation_type": relation_type.name,
            },
        )
        return {row[0] for row in result.fetchall()}


class CurrentImportEntity(Base):
    """Temporary tracking table for entities seen during current import."""

    __tablename__ = "current_import_entities"

    entity_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )

    @classmethod
    def cleanup_missing(
        cls, session: Session, previous_dump_timestamp: datetime
    ) -> dict:
        """
        Soft-delete entities using two-dump validation strategy.
        Only deletes entities missing from current dump AND older than previous dump.
        This prevents race conditions from incorrectly deleting recently added entities.

        Args:
            session: Database session
            previous_dump_timestamp: Last modified timestamp of the previous dump.

        Returns:
            dict: Count of entities that were soft-deleted
        """
        # Only delete if: NOT in current dump AND older than previous dump
        # Convert timezone-aware timestamp to naive for database comparison
        previous_dump_naive = previous_dump_timestamp.replace(tzinfo=None)
        deleted_result = session.execute(
            text(
                """
            UPDATE wikidata_entities
            SET deleted_at = NOW()
            WHERE wikidata_id NOT IN (SELECT entity_id FROM current_import_entities)
            AND updated_at <= :previous_dump_timestamp
            AND deleted_at IS NULL
        """
            ),
            {"previous_dump_timestamp": previous_dump_naive},
        )

        return {
            "entities_marked_deleted": deleted_result.rowcount,
        }

    @classmethod
    def clear_tracking_table(cls, session: Session) -> None:
        """Clear the entity tracking table."""
        session.execute(text("TRUNCATE current_import_entities"))


class CurrentImportStatement(Base):
    """Temporary tracking table for statements seen during current import."""

    __tablename__ = "current_import_statements"

    statement_id = Column(String, primary_key=True)

    @classmethod
    def cleanup_missing(
        cls, session: Session, previous_dump_timestamp: datetime
    ) -> dict:
        """
        Soft-delete statements using two-dump validation strategy.
        Only deletes statements missing from current dump AND older than previous dump.
        This prevents race conditions from incorrectly deleting recently added statements.

        Args:
            session: Database session
            previous_dump_timestamp: Last modified timestamp of the previous dump.

        Returns:
            dict: Counts of statements that were soft-deleted
        """
        # Only delete properties if: NOT in current dump AND older than previous dump
        # Convert timezone-aware timestamp to naive for database comparison
        previous_dump_naive = previous_dump_timestamp.replace(tzinfo=None)
        properties_deleted_result = session.execute(
            text(
                """
            UPDATE properties
            SET deleted_at = NOW()
            WHERE statement_id IS NOT NULL
            AND statement_id NOT IN (SELECT statement_id FROM current_import_statements)
            AND updated_at <= :previous_dump_timestamp
            AND deleted_at IS NULL
        """
            ),
            {"previous_dump_timestamp": previous_dump_naive},
        )

        # Only delete relations if: NOT in current dump AND older than previous dump
        relations_deleted_result = session.execute(
            text(
                """
            UPDATE wikidata_relations
            SET deleted_at = NOW()
            WHERE statement_id NOT IN (SELECT statement_id FROM current_import_statements)
            AND updated_at <= :previous_dump_timestamp
            AND deleted_at IS NULL
        """
            ),
            {"previous_dump_timestamp": previous_dump_naive},
        )

        return {
            "properties_marked_deleted": properties_deleted_result.rowcount,
            "relations_marked_deleted": relations_deleted_result.rowcount,
        }

    @classmethod
    def clear_tracking_table(cls, session: Session) -> None:
        """Clear the statement tracking table."""
        session.execute(text("TRUNCATE current_import_statements"))


class WikidataRelation(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Wikidata relationship between entities."""

    __tablename__ = "wikidata_relations"
    __table_args__ = (Index("idx_wikidata_relations_updated_at", "updated_at"),)

    # UpsertMixin configuration
    _upsert_update_columns = ["parent_entity_id", "child_entity_id", "relation_type"]

    parent_entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id"),
        nullable=False,
    )
    child_entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id"),
        nullable=False,
    )
    relation_type = Column(
        SQLEnum(RelationType), nullable=False, default=RelationType.SUBCLASS_OF
    )
    statement_id = Column(String, primary_key=True)

    # Relationships
    parent_entity = relationship(
        "WikidataEntity",
        foreign_keys=[parent_entity_id],
        back_populates="child_relations",
    )
    child_entity = relationship(
        "WikidataEntity",
        foreign_keys=[child_entity_id],
        back_populates="parent_relations",
    )
