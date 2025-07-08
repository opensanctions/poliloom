"""Database models for the PoliLoom project."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base
from uuid import uuid4
from pgvector.sqlalchemy import Vector

Base = declarative_base()


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


class UUIDMixin:
    """Mixin for adding UUID primary key."""

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))


# Association tables for many-to-many relationships
politician_source_table = Table(
    "politician_source",
    Base.metadata,
    Column("politician_id", String, ForeignKey("politicians.id"), primary_key=True),
    Column("source_id", String, ForeignKey("sources.id"), primary_key=True),
)

property_source_table = Table(
    "property_source",
    Base.metadata,
    Column("property_id", String, ForeignKey("properties.id"), primary_key=True),
    Column("source_id", String, ForeignKey("sources.id"), primary_key=True),
)

holdsposition_source_table = Table(
    "holdsposition_source",
    Base.metadata,
    Column(
        "holdsposition_id", String, ForeignKey("holds_position.id"), primary_key=True
    ),
    Column("source_id", String, ForeignKey("sources.id"), primary_key=True),
)

bornat_source_table = Table(
    "bornat_source",
    Base.metadata,
    Column("bornat_id", String, ForeignKey("born_at.id"), primary_key=True),
    Column("source_id", String, ForeignKey("sources.id"), primary_key=True),
)



class Politician(Base, UUIDMixin, TimestampMixin):
    """Politician entity."""

    __tablename__ = "politicians"

    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)
    is_deceased = Column(Boolean, default=False)

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
    sources = relationship(
        "Source", secondary=politician_source_table, back_populates="politicians"
    )


class Source(Base, UUIDMixin, TimestampMixin):
    """Source entity for tracking where data was extracted from."""

    __tablename__ = "sources"

    url = Column(String, nullable=False, unique=True)
    extracted_at = Column(DateTime)

    # Relationships
    politicians = relationship(
        "Politician", secondary=politician_source_table, back_populates="sources"
    )
    properties = relationship(
        "Property", secondary=property_source_table, back_populates="sources"
    )
    birthplaces = relationship(
        "BornAt", secondary=bornat_source_table, back_populates="sources"
    )
    positions_held = relationship(
        "HoldsPosition", secondary=holdsposition_source_table, back_populates="sources"
    )


class Property(Base, UUIDMixin, TimestampMixin):
    """Property entity for storing extracted politician properties."""

    __tablename__ = "properties"

    politician_id = Column(String, ForeignKey("politicians.id"), nullable=False)
    type = Column(String, nullable=False)  # e.g., 'BirthDate'
    value = Column(String, nullable=False)
    is_extracted = Column(
        Boolean, default=True
    )  # True if newly extracted and unconfirmed
    confirmed_by = Column(String, nullable=True)  # ID of user who confirmed
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    politician = relationship("Politician", back_populates="properties")
    sources = relationship(
        "Source", secondary=property_source_table, back_populates="properties"
    )


class Country(Base, UUIDMixin, TimestampMixin):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    name = Column(String, nullable=False)  # Country name in English
    iso_code = Column(String, unique=True, index=True)  # ISO 3166-1 alpha-2 code
    wikidata_id = Column(String, unique=True, index=True)

    # Relationships
    citizens = relationship(
        "HasCitizenship", back_populates="country", cascade="all, delete-orphan"
    )


class Location(Base, UUIDMixin, TimestampMixin):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    born_here = relationship(
        "BornAt", back_populates="location", cascade="all, delete-orphan"
    )


class Position(Base, UUIDMixin, TimestampMixin):
    """Position entity for political positions."""

    __tablename__ = "positions"

    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)
    embedding = Column(Vector(384), nullable=True)

    # Relationships
    held_by = relationship(
        "HoldsPosition", back_populates="position", cascade="all, delete-orphan"
    )


class HoldsPosition(Base, UUIDMixin, TimestampMixin):
    """HoldsPosition entity for politician-position relationships."""

    __tablename__ = "holds_position"

    politician_id = Column(String, ForeignKey("politicians.id"), nullable=False)
    position_id = Column(String, ForeignKey("positions.id"), nullable=False)
    start_date = Column(String)  # Allowing incomplete dates as strings
    end_date = Column(String)  # Allowing incomplete dates as strings
    is_extracted = Column(
        Boolean, default=True
    )  # True if newly extracted and unconfirmed
    confirmed_by = Column(String, nullable=True)  # ID of user who confirmed
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    politician = relationship("Politician", back_populates="positions_held")
    position = relationship("Position", back_populates="held_by")
    sources = relationship(
        "Source", secondary=holdsposition_source_table, back_populates="positions_held"
    )


class BornAt(Base, UUIDMixin, TimestampMixin):
    """BornAt entity for politician-location birth relationships."""

    __tablename__ = "born_at"

    politician_id = Column(String, ForeignKey("politicians.id"), nullable=False)
    location_id = Column(String, ForeignKey("locations.id"), nullable=False)
    is_extracted = Column(
        Boolean, default=True
    )  # True if newly extracted and unconfirmed
    confirmed_by = Column(String, nullable=True)  # ID of user who confirmed
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    politician = relationship("Politician", back_populates="birthplaces")
    location = relationship("Location", back_populates="born_here")
    sources = relationship(
        "Source", secondary=bornat_source_table, back_populates="birthplaces"
    )


class HasCitizenship(Base, UUIDMixin, TimestampMixin):
    """HasCitizenship entity for politician-country citizenship relationships."""

    __tablename__ = "has_citizenship"

    politician_id = Column(String, ForeignKey("politicians.id"), nullable=False)
    country_id = Column(String, ForeignKey("countries.id"), nullable=False)

    # Relationships
    politician = relationship("Politician", back_populates="citizenships")
    country = relationship("Country", back_populates="citizens")


# Vector columns are now defined directly in the model classes using pgvector.Vector(384)
