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
)
from sqlalchemy.orm import Session, relationship, declarative_base, declared_attr
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property
from pgvector.sqlalchemy import Vector
from dicttoxml import dicttoxml

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

    deleted_at = Column(DateTime, nullable=True)

    def soft_delete(self):
        """Mark the entity as deleted by setting the deleted_at timestamp."""
        self.deleted_at = datetime.now(timezone.utc)


class UpsertMixin:
    """Mixin for adding batch upsert functionality."""

    # Override this in subclasses to specify which columns to update on conflict
    _upsert_update_columns = []
    # Override this in subclasses to specify the conflict columns (defaults to primary key)
    _upsert_conflict_columns = None

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

        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(cls).values(data)

        # Use specified conflict columns or default to primary key
        conflict_columns = cls._upsert_conflict_columns
        if conflict_columns is None:
            conflict_columns = [col.name for col in cls.__table__.primary_key.columns]

        # Update specified columns on conflict
        if cls._upsert_update_columns:
            update_dict = {
                col: getattr(stmt.excluded, col) for col in cls._upsert_update_columns
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=update_dict,
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)

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
        from collections import defaultdict

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
    user_id = Column(String, nullable=False)
    preference_type = Column(SQLEnum(PreferenceType), nullable=False)
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

    def get_priority_wikipedia_links(self, db: Session) -> List[tuple]:
        """
        Get top 3 most popular Wikipedia links for a politician, optionally filtered by citizenship languages.

        If politician has citizenships, only considers links in official languages of those countries,
        then returns the 3 most popular among those.
        Otherwise returns the 3 most popular languages overall for the politician.
        Uses proper ISO codes from languages table (no fallbacks).

        Args:
            db: Database session

        Returns:
            List of (url, iso1_code, iso3_code) tuples, limited to top 3 by popularity
        """
        from sqlalchemy import text

        query = text(
            """
            WITH politician_citizenships AS (
                SELECT p.entity_id as country_id
                FROM properties p
                WHERE p.politician_id = :politician_id
                AND p.type = :citizenship_type
                AND p.entity_id IS NOT NULL
            ),
            language_popularity AS (
                SELECT iso_code, COUNT(*) as global_count
                FROM wikipedia_links
                GROUP BY iso_code
            ),
            filtered_links AS (
                SELECT DISTINCT wl.url, l.iso1_code, l.iso3_code,
                       lp.global_count as language_popularity
                FROM wikipedia_links wl
                JOIN languages l ON (wl.iso_code = l.iso1_code OR wl.iso_code = l.iso3_code)
                JOIN language_popularity lp ON lp.iso_code = wl.iso_code
                WHERE wl.politician_id = :politician_id
                AND (
                    NOT EXISTS (SELECT 1 FROM politician_citizenships)
                    OR EXISTS (
                        SELECT 1 FROM wikidata_relations wr
                        JOIN politician_citizenships pc ON wr.child_entity_id = pc.country_id
                        WHERE wr.parent_entity_id = l.wikidata_id
                        AND wr.relation_type = 'OFFICIAL_LANGUAGE'
                    )
                )
            )
            SELECT url, iso1_code, iso3_code
            FROM filtered_links
            ORDER BY language_popularity DESC
            LIMIT 3
        """
        )

        result = db.execute(
            query,
            {
                "politician_id": str(self.id),
                "citizenship_type": PropertyType.CITIZENSHIP.name,
            },
        )

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


class WikipediaLink(Base, TimestampMixin):
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


class Property(Base, TimestampMixin, SoftDeleteMixin):
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
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
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


class WikidataRelation(Base, TimestampMixin, SoftDeleteMixin, UpsertMixin):
    """Wikidata relationship between entities."""

    __tablename__ = "wikidata_relations"

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
