"""Database models for the PoliLoom project."""

import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import exists
from pgvector.sqlalchemy import Vector

Base = declarative_base()


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
    wikidata_id = Column(String, unique=True, index=True)

    @property
    def is_deceased(self) -> bool:
        """Check if politician is deceased based on DeathDate property."""
        return any(prop.type == "DeathDate" for prop in self.properties)

    @hybrid_property
    def has_unevaluated_extracted_data(self) -> bool:
        """Check if politician has any unevaluated extracted data."""
        return (
            any(prop.is_extracted and not prop.evaluations for prop in self.properties)
            or any(
                pos.is_extracted and not pos.evaluations for pos in self.positions_held
            )
            or any(bp.is_extracted and not bp.evaluations for bp in self.birthplaces)
        )

    @has_unevaluated_extracted_data.expression
    def has_unevaluated_extracted_data(cls):
        """SQL expression for has_unevaluated_extracted_data."""
        return (
            (
                exists()
                .where(Property.politician_id == cls.id)
                .where(Property.archived_page_id.isnot(None))
                .where(~exists().where(PropertyEvaluation.property_id == Property.id))
            )
            | (
                exists()
                .where(HoldsPosition.politician_id == cls.id)
                .where(HoldsPosition.archived_page_id.isnot(None))
                .where(
                    ~exists().where(
                        PositionEvaluation.holds_position_id == HoldsPosition.id
                    )
                )
            )
            | (
                exists()
                .where(BornAt.politician_id == cls.id)
                .where(BornAt.archived_page_id.isnot(None))
                .where(~exists().where(BirthplaceEvaluation.born_at_id == BornAt.id))
            )
        )

    @property
    def unevaluated_properties(self):
        """Get unevaluated extracted properties."""
        return [
            prop
            for prop in self.properties
            if prop.is_extracted and not prop.evaluations
        ]

    @property
    def unevaluated_positions(self):
        """Get unevaluated extracted positions."""
        return [
            pos
            for pos in self.positions_held
            if pos.is_extracted and not pos.evaluations
        ]

    @property
    def unevaluated_birthplaces(self):
        """Get unevaluated extracted birthplaces."""
        return [bp for bp in self.birthplaces if bp.is_extracted and not bp.evaluations]

    @property
    def wikidata_properties(self):
        """Get Wikidata (non-extracted) properties."""
        return [prop for prop in self.properties if not prop.is_extracted]

    @property
    def wikidata_positions(self):
        """Get Wikidata (non-extracted) positions."""
        return [pos for pos in self.positions_held if not pos.is_extracted]

    @property
    def wikidata_birthplaces(self):
        """Get Wikidata (non-extracted) birthplaces."""
        return [bp for bp in self.birthplaces if not bp.is_extracted]

    # Relationships
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
    """Archived page entity for storing fetched web page metadata and file paths."""

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

    @staticmethod
    def _create_archive_directory(timestamp: datetime) -> Path:
        """Create archive directory structure and return the path."""
        archive_root = os.getenv("POLILOOM_ARCHIVE_ROOT", "./archives")
        date_path = f"{timestamp.year:04d}/{timestamp.month:02d}/{timestamp.day:02d}"
        archive_dir = Path(archive_root) / date_path
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir

    def _get_archive_directory(self) -> Path:
        """Get the archive directory for this archived page."""
        return self._create_archive_directory(self.fetch_timestamp)

    @hybrid_property
    def mhtml_path(self) -> Path:
        """Get the MHTML file path for this archived page."""
        return self._get_archive_directory() / f"{self.content_hash}.mhtml"

    @hybrid_property
    def html_path(self) -> Path:
        """Get the HTML file path for this archived page."""
        return self._get_archive_directory() / f"{self.content_hash}.html"

    @hybrid_property
    def markdown_path(self) -> Path:
        """Get the markdown file path for this archived page."""
        return self._get_archive_directory() / f"{self.content_hash}.md"

    def get_file_paths(self) -> dict:
        """Get all file paths for this archived page."""
        return {
            "mhtml": self.mhtml_path,
            "html": self.html_path,
            "markdown": self.markdown_path,
        }

    def read_markdown_content(self) -> str:
        """Read the markdown content from disk."""
        try:
            with open(self.markdown_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Archived markdown file not found: {self.markdown_path}"
            )

    def read_html_content(self) -> str:
        """Read the HTML content from disk."""
        try:
            with open(self.html_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Archived HTML file not found: {self.html_path}")

    def save_mhtml(self, content: str) -> None:
        """Save MHTML content to disk."""
        with open(self.mhtml_path, "w", encoding="utf-8") as f:
            f.write(content)

    def save_html(self, content: str) -> None:
        """Save HTML content to disk."""
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(content)

    def save_markdown(self, content: str) -> None:
        """Save markdown content to disk."""
        with open(self.markdown_path, "w", encoding="utf-8") as f:
            f.write(content)


@event.listens_for(ArchivedPage, "before_insert")
def generate_archived_page_content_hash(mapper, connection, target):
    """Auto-generate content_hash before inserting ArchivedPage."""
    if target.url and not target.content_hash:
        # Generate content hash from URL
        target.content_hash = ArchivedPage._generate_content_hash(target.url)


@event.listens_for(ArchivedPage, "after_insert")
def create_archive_directory(mapper, connection, target):
    """Create archive directory structure after inserting ArchivedPage."""
    target._get_archive_directory().mkdir(parents=True, exist_ok=True)


class WikipediaLink(Base, TimestampMixin):
    """Wikipedia link entity for storing politician Wikipedia article URLs."""

    __tablename__ = "wikipedia_links"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
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
            "uq_property_wikidata_only",
            "politician_id",
            "type",
            unique=True,
            postgresql_where=Column("archived_page_id").is_(None),
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
    )
    type = Column(String, nullable=False)  # e.g., 'BirthDate'
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

    wikidata_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)  # Country name in English
    iso_code = Column(String, unique=True, index=True)  # ISO 3166-1 alpha-2 code

    # Relationships
    citizens = relationship(
        "HasCitizenship", back_populates="country", cascade="all, delete-orphan"
    )


class LocationClass(Base):
    """Junction table for Location-WikidataClass many-to-many relationship."""

    __tablename__ = "location_classes"

    location_id = Column(String, ForeignKey("locations.wikidata_id"), primary_key=True)
    class_id = Column(
        String, ForeignKey("wikidata_classes.wikidata_id"), primary_key=True
    )


class Location(Base, TimestampMixin):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    wikidata_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    born_here = relationship(
        "BornAt", back_populates="location", cascade="all, delete-orphan"
    )
    wikidata_classes = relationship(
        "WikidataClass", secondary="location_classes", back_populates="locations"
    )


class PositionClass(Base):
    """Junction table for Position-WikidataClass many-to-many relationship."""

    __tablename__ = "position_classes"

    position_id = Column(String, ForeignKey("positions.wikidata_id"), primary_key=True)
    class_id = Column(
        String, ForeignKey("wikidata_classes.wikidata_id"), primary_key=True
    )


class Position(Base, TimestampMixin):
    """Position entity for political positions."""

    __tablename__ = "positions"

    wikidata_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    held_by = relationship(
        "HoldsPosition", back_populates="position", cascade="all, delete-orphan"
    )
    wikidata_classes = relationship(
        "WikidataClass", secondary="position_classes", back_populates="positions"
    )


class HoldsPosition(Base, TimestampMixin):
    """HoldsPosition entity for politician-position relationships."""

    __tablename__ = "holds_position"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    politician_id = Column(
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
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

    @hybrid_property
    def is_extracted(self) -> bool:
        """Check if this position was extracted from a web source."""
        return self.archived_page_id is not None

    @is_extracted.expression
    def is_extracted(cls):
        """SQL expression for is_extracted."""
        return cls.archived_page_id.isnot(None)

    # Constraints - unique constraint including dates to allow multiple time periods
    __table_args__ = (
        Index(
            "uq_holds_position_wikidata_only",
            "politician_id",
            "position_id",
            "start_date",
            "end_date",
            unique=True,
            postgresql_where=Column("archived_page_id").is_(None),
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
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
    )
    location_id = Column(String, ForeignKey("locations.wikidata_id"), nullable=False)
    archived_page_id = Column(
        UUID(as_uuid=True), ForeignKey("archived_pages.id"), nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    proof_line = Column(
        String, nullable=True
    )  # NULL for Wikidata imports, set for extracted data

    @hybrid_property
    def is_extracted(self) -> bool:
        """Check if this birthplace was extracted from a web source."""
        return self.archived_page_id is not None

    @is_extracted.expression
    def is_extracted(cls):
        """SQL expression for is_extracted."""
        return cls.archived_page_id.isnot(None)

    # Constraints - only one non-extracted (Wikidata) relationship per politician-location pair
    __table_args__ = (
        Index(
            "uq_born_at_wikidata_only",
            "politician_id",
            "location_id",
            unique=True,
            postgresql_where=Column("archived_page_id").is_(None),
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
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
    )
    country_id = Column(String, ForeignKey("countries.wikidata_id"), nullable=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint("politician_id", "country_id", name="uq_politician_country"),
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


class WikidataClass(Base, TimestampMixin):
    """Wikidata class entity for hierarchy storage."""

    __tablename__ = "wikidata_classes"

    wikidata_id = Column(String, primary_key=True)  # Wikidata QID as primary key
    name = Column(
        String, nullable=True
    )  # Class name from Wikidata labels (can be None)

    # Relationships
    parent_relations = relationship(
        "SubclassRelation",
        foreign_keys="SubclassRelation.child_class_id",
        back_populates="child_class",
        cascade="all, delete-orphan",
    )
    child_relations = relationship(
        "SubclassRelation",
        foreign_keys="SubclassRelation.parent_class_id",
        back_populates="parent_class",
        cascade="all, delete-orphan",
    )
    locations = relationship(
        "Location", secondary="location_classes", back_populates="wikidata_classes"
    )
    positions = relationship(
        "Position", secondary="position_classes", back_populates="wikidata_classes"
    )


class SubclassRelation(Base, TimestampMixin):
    """Subclass relationship between Wikidata classes (P279)."""

    __tablename__ = "subclass_relations"
    __table_args__ = (
        UniqueConstraint(
            "parent_class_id", "child_class_id", name="uq_subclass_parent_child"
        ),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    parent_class_id = Column(
        String,
        ForeignKey("wikidata_classes.wikidata_id"),
        nullable=False,
        index=True,
    )
    child_class_id = Column(
        String,
        ForeignKey("wikidata_classes.wikidata_id"),
        nullable=False,
        index=True,
    )

    # Relationships
    parent_class = relationship(
        "WikidataClass",
        foreign_keys=[parent_class_id],
        back_populates="child_relations",
    )
    child_class = relationship(
        "WikidataClass",
        foreign_keys=[child_class_id],
        back_populates="parent_relations",
    )
