"""Database models for the PoliLoom project."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from uuid import uuid4
from pgvector.sqlalchemy import Vector
import enum

Base = declarative_base()


class EvaluationResult(enum.Enum):
    """Enum for evaluation results."""

    CONFIRMED = "confirmed"
    DISCARDED = "discarded"


class TimestampMixin:
    """Mixin for adding timestamp fields."""

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Evaluation(Base, TimestampMixin):
    """Evaluation entity for tracking user evaluations of extracted data."""

    __tablename__ = "evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String, nullable=False)  # ID of user who made the evaluation
    result = Column(Enum(EvaluationResult), nullable=False)  # CONFIRMED or DISCARDED

    # Polymorphic foreign keys to the entities being evaluated
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=True)
    holds_position_id = Column(
        UUID(as_uuid=True), ForeignKey("holds_position.id"), nullable=True
    )
    born_at_id = Column(UUID(as_uuid=True), ForeignKey("born_at.id"), nullable=True)

    # Relationships
    property = relationship("Property", back_populates="evaluations")
    holds_position = relationship("HoldsPosition", back_populates="evaluations")
    born_at = relationship("BornAt", back_populates="evaluations")


class Politician(Base, TimestampMixin):
    """Politician entity."""

    __tablename__ = "politicians"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)

    @property
    def is_deceased(self) -> bool:
        """Check if politician is deceased based on DeathDate property."""
        return any(prop.type == "DeathDate" for prop in self.properties)

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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    url = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Path to MHTML file on disk
    content_hash = Column(
        String, nullable=False, index=True
    )  # SHA256 hash for deduplication
    fetch_timestamp = Column(DateTime, nullable=False)

    # Relationships
    properties = relationship("Property", back_populates="archived_page")
    positions_held = relationship("HoldsPosition", back_populates="archived_page")
    birthplaces = relationship("BornAt", back_populates="archived_page")


class WikipediaLink(Base, TimestampMixin):
    """Wikipedia link entity for storing politician Wikipedia article URLs."""

    __tablename__ = "wikipedia_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
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

    # Relationships
    politician = relationship("Politician", back_populates="properties")
    archived_page = relationship("ArchivedPage", back_populates="properties")
    evaluations = relationship(
        "Evaluation", back_populates="property", cascade="all, delete-orphan"
    )


class Country(Base, TimestampMixin):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)  # Country name in English
    iso_code = Column(String, unique=True, index=True)  # ISO 3166-1 alpha-2 code
    wikidata_id = Column(String, unique=True, index=True)

    # Relationships
    citizens = relationship(
        "HasCitizenship", back_populates="country", cascade="all, delete-orphan"
    )


class Location(Base, TimestampMixin):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    born_here = relationship(
        "BornAt", back_populates="location", cascade="all, delete-orphan"
    )


class Position(Base, TimestampMixin):
    """Position entity for political positions."""

    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    held_by = relationship(
        "HoldsPosition", back_populates="position", cascade="all, delete-orphan"
    )


class HoldsPosition(Base, TimestampMixin):
    """HoldsPosition entity for politician-position relationships."""

    __tablename__ = "holds_position"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    politician_id = Column(
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
    )
    position_id = Column(UUID(as_uuid=True), ForeignKey("positions.id"), nullable=False)
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

    # Relationships
    politician = relationship("Politician", back_populates="positions_held")
    position = relationship("Position", back_populates="held_by")
    archived_page = relationship("ArchivedPage", back_populates="positions_held")
    evaluations = relationship(
        "Evaluation", back_populates="holds_position", cascade="all, delete-orphan"
    )


class BornAt(Base, TimestampMixin):
    """BornAt entity for politician-location birth relationships."""

    __tablename__ = "born_at"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    politician_id = Column(
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
    )
    location_id = Column(UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False)
    archived_page_id = Column(
        UUID(as_uuid=True), ForeignKey("archived_pages.id"), nullable=True
    )  # NULL for Wikidata imports, set for extracted data
    proof_line = Column(
        String, nullable=True
    )  # NULL for Wikidata imports, set for extracted data

    # Relationships
    politician = relationship("Politician", back_populates="birthplaces")
    location = relationship("Location", back_populates="born_here")
    archived_page = relationship("ArchivedPage", back_populates="birthplaces")
    evaluations = relationship(
        "Evaluation", back_populates="born_at", cascade="all, delete-orphan"
    )


class HasCitizenship(Base, TimestampMixin):
    """HasCitizenship entity for politician-country citizenship relationships."""

    __tablename__ = "has_citizenship"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    politician_id = Column(
        UUID(as_uuid=True), ForeignKey("politicians.id"), nullable=False
    )
    country_id = Column(UUID(as_uuid=True), ForeignKey("countries.id"), nullable=False)

    # Relationships
    politician = relationship("Politician", back_populates="citizenships")
    country = relationship("Country", back_populates="citizens")


# Vector columns are now defined directly in the model classes using pgvector.Vector(384)
