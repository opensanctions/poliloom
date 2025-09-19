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
    UniqueConstraint,
    Index,
    text,
    func,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class PropertyType(str, Enum):
    """Enumeration of allowed property types for politician properties."""

    BIRTH_DATE = "birth_date"
    DEATH_DATE = "death_date"


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


class PropertyEvaluation(Base, TimestampMixin):
    """Property evaluation entity for tracking user evaluations of extracted properties."""

    __tablename__ = "property_evaluations"

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


class PositionEvaluation(Base, TimestampMixin):
    """Position evaluation entity for tracking user evaluations of extracted positions."""

    __tablename__ = "position_evaluations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False)
    is_confirmed = Column(Boolean, nullable=False)
    holds_position_id = Column(
        UUID(as_uuid=True), ForeignKey("holds_position.id"), nullable=False
    )

    # Relationships
    holds_position = relationship("HoldsPosition", back_populates="evaluations")


class BirthplaceEvaluation(Base, TimestampMixin):
    """Birthplace evaluation entity for tracking user evaluations of extracted birthplaces."""

    __tablename__ = "birthplace_evaluations"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id = Column(String, nullable=False)
    is_confirmed = Column(Boolean, nullable=False)
    born_at_id = Column(UUID(as_uuid=True), ForeignKey("born_at.id"), nullable=False)

    # Relationships
    born_at = relationship("BornAt", back_populates="evaluations")


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
        """Check if politician is deceased based on DeathDate property."""
        return any(prop.type == "DeathDate" for prop in self.properties)

    @property
    def wikidata_positions(self):
        """Get Wikidata (non-extracted) positions."""
        return [pos for pos in self.positions_held if not pos.is_extracted]

    @property
    def wikidata_birthplaces(self):
        """Get Wikidata (non-extracted) birthplaces."""
        return [bp for bp in self.birthplaces if not bp.is_extracted]

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
    positions_held = relationship(
        "HoldsPosition", back_populates="politician", cascade="all, delete-orphan"
    )
    citizenships = relationship(
        "HasCitizenship", back_populates="politician", cascade="all, delete-orphan"
    )
    birthplaces = relationship(
        "BornAt", back_populates="politician", cascade="all, delete-orphan"
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
    positions_held = relationship("HoldsPosition", back_populates="archived_page")
    birthplaces = relationship("BornAt", back_populates="archived_page")

    @staticmethod
    def _generate_content_hash(url: str) -> str:
        """Generate a content hash for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    @property
    def path_root(self) -> str:
        """Get the path root (timestamp/content_hash structure) for this archived page."""
        date_path = f"{self.fetch_timestamp.year:04d}/{self.fetch_timestamp.month:02d}/{self.fetch_timestamp.day:02d}"
        return f"{date_path}/{self.content_hash}"


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


class Property(Base, TimestampMixin):
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
    value = Column(String, nullable=False)
    value_precision = Column(
        Integer
    )  # Wikidata precision integer for date properties (9=year, 10=month, 11=day)
    archived_page_id = Column(
        UUID(as_uuid=True), ForeignKey("archived_pages.id"), nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    proof_line = Column(
        String, nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    statement_id = Column(String, nullable=True)

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
    evaluations = relationship(
        "PropertyEvaluation", back_populates="property", cascade="all, delete-orphan"
    )


class Country(Base, TimestampMixin):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )
    iso_code = Column(String, unique=True, index=True)  # ISO 3166-1 alpha-2 code

    # Relationships
    citizens = relationship(
        "HasCitizenship", back_populates="country", cascade="all, delete-orphan"
    )
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


class Location(Base, TimestampMixin):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    born_here = relationship(
        "BornAt", back_populates="location", cascade="all, delete-orphan"
    )
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


class Position(Base, TimestampMixin):
    """Position entity for political positions."""

    __tablename__ = "positions"

    wikidata_id = Column(
        String, ForeignKey("wikidata_entities.wikidata_id"), primary_key=True
    )
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    held_by = relationship(
        "HoldsPosition", back_populates="position", cascade="all, delete-orphan"
    )
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


class HoldsPosition(Base, TimestampMixin):
    """HoldsPosition entity for politician-position relationships."""

    __tablename__ = "holds_position"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
    )
    position_id = Column(String, ForeignKey("positions.wikidata_id"), nullable=False)
    start_date = Column(String)  # Allowing incomplete dates as strings
    start_date_precision = Column(
        Integer
    )  # Wikidata precision integer (9=year, 10=month, 11=day)
    end_date = Column(String)  # Allowing incomplete dates as strings
    end_date_precision = Column(
        Integer
    )  # Wikidata precision integer (9=year, 10=month, 11=day)
    archived_page_id = Column(
        UUID(as_uuid=True), ForeignKey("archived_pages.id"), nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    proof_line = Column(
        String, nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    statement_id = Column(String, nullable=True)

    @hybrid_property
    def is_extracted(self) -> bool:
        """Check if this position was extracted from a web source."""
        return self.archived_page_id is not None

    @is_extracted.expression
    def is_extracted(cls):
        """SQL expression for is_extracted."""
        return cls.archived_page_id.isnot(None)

    # Constraints
    __table_args__ = (
        Index(
            "uq_holds_position_statement_id",
            "statement_id",
            unique=True,
            postgresql_where=Column("statement_id").isnot(None),
        ),
    )

    # Relationships
    politician = relationship("Politician", back_populates="positions_held")
    position = relationship("Position", back_populates="held_by")
    archived_page = relationship("ArchivedPage", back_populates="positions_held")
    evaluations = relationship(
        "PositionEvaluation",
        back_populates="holds_position",
        cascade="all, delete-orphan",
    )


class BornAt(Base, TimestampMixin):
    """BornAt entity for politician-location birth relationships."""

    __tablename__ = "born_at"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id = Column(String, ForeignKey("locations.wikidata_id"), nullable=False)
    archived_page_id = Column(
        UUID(as_uuid=True), ForeignKey("archived_pages.id"), nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    proof_line = Column(
        String, nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    statement_id = Column(String, nullable=True)

    @hybrid_property
    def is_extracted(self) -> bool:
        """Check if this birthplace was extracted from a web source."""
        return self.archived_page_id is not None

    @is_extracted.expression
    def is_extracted(cls):
        """SQL expression for is_extracted."""
        return cls.archived_page_id.isnot(None)

    # Constraints
    __table_args__ = (
        Index(
            "uq_born_at_statement_id",
            "statement_id",
            unique=True,
            postgresql_where=Column("statement_id").isnot(None),
        ),
    )

    # Relationships
    politician = relationship("Politician", back_populates="birthplaces")
    location = relationship("Location", back_populates="born_here")
    archived_page = relationship("ArchivedPage", back_populates="birthplaces")
    evaluations = relationship(
        "BirthplaceEvaluation", back_populates="born_at", cascade="all, delete-orphan"
    )


class HasCitizenship(Base, TimestampMixin):
    """HasCitizenship entity for politician-country citizenship relationships."""

    __tablename__ = "has_citizenship"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True),
        ForeignKey("politicians.id", ondelete="CASCADE"),
        nullable=False,
    )
    country_id = Column(
        String, ForeignKey("countries.wikidata_id", ondelete="CASCADE"), nullable=False
    )
    statement_id = Column(String, nullable=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint("politician_id", "country_id", name="uq_politician_country"),
        Index(
            "uq_has_citizenship_statement_id",
            "statement_id",
            unique=True,
            postgresql_where=Column("statement_id").isnot(None),
        ),
    )

    # Relationships
    politician = relationship("Politician", back_populates="citizenships")
    country = relationship("Country", back_populates="citizens")


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


class WikidataEntity(Base, TimestampMixin):
    """Wikidata entity for hierarchy storage."""

    __tablename__ = "wikidata_entities"

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


class WikidataRelation(Base, TimestampMixin):
    """Wikidata relationship between entities."""

    __tablename__ = "wikidata_relations"

    parent_entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id"),
        primary_key=True,
    )
    child_entity_id = Column(
        String,
        ForeignKey("wikidata_entities.wikidata_id"),
        primary_key=True,
    )
    relation_type = Column(
        SQLEnum(RelationType), primary_key=True, default=RelationType.SUBCLASS_OF
    )

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
