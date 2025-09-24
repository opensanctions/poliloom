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
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class PropertyType(str, Enum):
    """Enumeration of allowed property types for politician properties."""

    BIRTH_DATE = "P569"
    DEATH_DATE = "P570"
    BIRTHPLACE = "P19"
    POSITION = "P39"
    CITIZENSHIP = "P27"


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


class StatementMixin:
    """Mixin for adding Wikidata statement metadata fields."""

    statement_id = Column(String, nullable=True)
    qualifiers_json = Column(JSONB, nullable=True)  # Store all qualifiers as JSON
    references_json = Column(JSONB, nullable=True)  # Store all references as JSON


class UpsertMixin:
    """Mixin for adding batch upsert functionality."""

    # Override this in subclasses to specify which columns to update on conflict
    _upsert_update_columns = []
    # Override this in subclasses to specify the conflict columns (defaults to primary key)
    _upsert_conflict_columns = None

    @classmethod
    def upsert_batch(cls, session: Session, data: List[dict]) -> None:
        """
        Upsert a batch of records.

        Args:
            session: Database session
            data: List of dicts with column data
        """
        if not data:
            return

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

        session.execute(stmt)


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


class Politician(Base, TimestampMixin):
    """Politician entity."""

    __tablename__ = "politicians"

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

    def get_properties_by_type(self, property_type: PropertyType) -> List["Property"]:
        """Get all properties of a specific type."""
        return [prop for prop in self.properties if prop.type == property_type]

    def get_citizenship_names(self) -> List[str]:
        """Get list of citizenship country names."""
        citizenship_props = self.get_properties_by_type(PropertyType.CITIZENSHIP)
        return [
            prop.entity.name
            for prop in citizenship_props
            if prop.entity and prop.entity.name
        ]

    def get_position_names_with_dates(self) -> List[str]:
        """Get list of position names with date ranges."""
        position_props = self.get_properties_by_type(PropertyType.POSITION)
        items = []
        for prop in position_props:
            position_name = prop.entity.name if prop.entity else prop.entity_id
            date_range = self._extract_date_range_from_qualifiers(prop.qualifiers_json)
            items.append(f"{position_name}{date_range}")
        return items

    def get_birthplace_names(self) -> List[str]:
        """Get list of birthplace names."""
        birthplace_props = self.get_properties_by_type(PropertyType.BIRTHPLACE)
        return [
            prop.entity.name if prop.entity else prop.entity_id
            for prop in birthplace_props
        ]

    def get_date_properties_formatted(self) -> List[str]:
        """Get formatted date properties (birth_date, death_date)."""
        date_props = [
            prop
            for prop in self.properties
            if prop.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]
        ]
        return [f"{prop.type.value}: {prop.value}" for prop in date_props]

    def _extract_date_range_from_qualifiers(self, qualifiers_json):
        """Extract formatted date range from qualifiers_json.

        Args:
            qualifiers_json: Dict containing Wikidata qualifiers

        Returns:
            Formatted date range string like " (2020 - 2023)" or empty string
        """
        if not qualifiers_json:
            return ""

        start_date = None
        end_date = None

        # Extract P580 (start date) and P582 (end date) from qualifiers
        if "P580" in qualifiers_json:
            start_qual = qualifiers_json["P580"][0]
            if "datavalue" in start_qual and "value" in start_qual["datavalue"]:
                time_val = start_qual["datavalue"]["value"]["time"]
                # Parse time format like "+2020-01-00T00:00:00Z"
                if time_val.startswith("+"):
                    start_date = time_val[1:5]  # Extract year

        if "P582" in qualifiers_json:
            end_qual = qualifiers_json["P582"][0]
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

    @classmethod
    def create_with_entity(cls, session, wikidata_id: str, name: str):
        """Create a Politician with its associated WikidataEntity."""
        # Create WikidataEntity first
        wikidata_entity = WikidataEntity(wikidata_id=wikidata_id, name=name)
        session.add(wikidata_entity)

        # Create Politician
        politician = cls(name=name, wikidata_id=wikidata_id)
        session.add(politician)

        return politician

    # Relationships
    wikidata_entity = relationship("WikidataEntity", back_populates="politician")
    properties = relationship(
        "Property", back_populates="politician", cascade="all, delete-orphan"
    )
    wikipedia_links = relationship(
        "WikipediaLink", back_populates="politician", cascade="all, delete-orphan"
    )


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
            "idx_wikipedia_links_politician_language",
            "politician_id",
            "language_code",
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
    language_code = Column(String, nullable=False)  # e.g., 'en', 'de', 'fr'

    # Relationships
    politician = relationship("Politician", back_populates="wikipedia_links")


class Property(Base, TimestampMixin, StatementMixin):
    """Property entity for storing extracted politician properties."""

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


class Country(Base, TimestampMixin, UpsertMixin):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    # UpsertMixin configuration
    _upsert_update_columns = ["iso_code"]

    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )
    iso_code = Column(String, index=True)  # ISO 3166-1 alpha-2 code

    # Relationships
    wikidata_entity = relationship(
        "WikidataEntity", back_populates="country", lazy="joined"
    )

    @hybrid_property
    def name(self) -> str:
        """Get the country name from the related WikidataEntity."""
        return self.wikidata_entity.name if self.wikidata_entity else None

    @classmethod
    def create_with_entity(
        cls, session, wikidata_id: str, name: str, iso_code: str = None
    ):
        """Create a Country with its associated WikidataEntity."""
        # Create WikidataEntity first
        wikidata_entity = WikidataEntity(wikidata_id=wikidata_id, name=name)
        session.add(wikidata_entity)

        # Create Country
        country = cls(wikidata_id=wikidata_id, iso_code=iso_code)
        session.add(country)

        return country


class Location(Base, TimestampMixin, UpsertMixin):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    wikidata_entity = relationship(
        "WikidataEntity", back_populates="location", lazy="joined"
    )

    @property
    def name(self) -> str:
        """Get the name from the associated WikidataEntity."""
        return self.wikidata_entity.name

    @classmethod
    def create_with_entity(cls, session, wikidata_id: str, name: str, embedding=None):
        """Create a Location with its associated WikidataEntity."""
        # Create WikidataEntity first
        wikidata_entity = WikidataEntity(wikidata_id=wikidata_id, name=name)
        session.add(wikidata_entity)

        # Create Location
        location = cls(wikidata_id=wikidata_id)
        if embedding is not None:
            location.embedding = embedding
        session.add(location)

        return location


class Position(Base, TimestampMixin, UpsertMixin):
    """Position entity for political positions."""

    __tablename__ = "positions"

    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    wikidata_entity = relationship(
        "WikidataEntity", back_populates="position", lazy="joined"
    )

    @property
    def name(self) -> str:
        """Get the name from the associated WikidataEntity."""
        return self.wikidata_entity.name

    @classmethod
    def create_with_entity(cls, session, wikidata_id: str, name: str, embedding=None):
        """Create a Position with its associated WikidataEntity."""
        # Create WikidataEntity first
        wikidata_entity = WikidataEntity(wikidata_id=wikidata_id, name=name)
        session.add(wikidata_entity)

        # Create Position
        position = cls(wikidata_id=wikidata_id)
        if embedding is not None:
            position.embedding = embedding
        session.add(position)

        return position


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


class WikidataEntity(Base, TimestampMixin, UpsertMixin):
    """Wikidata entity for hierarchy storage."""

    __tablename__ = "wikidata_entities"

    # UpsertMixin configuration
    _upsert_update_columns = ["name"]

    wikidata_id = Column(String, primary_key=True)  # Wikidata QID as primary key
    name = Column(
        String, nullable=True
    )  # Entity name from Wikidata labels (can be None)

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


class WikidataRelation(Base, TimestampMixin, UpsertMixin):
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
