"""Database models for the PoliLoom project."""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid4

Base = declarative_base()


class TimestampMixin:
    """Mixin for adding timestamp fields."""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UUIDMixin:
    """Mixin for adding UUID primary key."""
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))


# Association tables for many-to-many relationships
politician_source_table = Table(
    'politician_source',
    Base.metadata,
    Column('politician_id', String, ForeignKey('politicians.id'), primary_key=True),
    Column('source_id', String, ForeignKey('sources.id'), primary_key=True)
)

property_source_table = Table(
    'property_source',
    Base.metadata,
    Column('property_id', String, ForeignKey('properties.id'), primary_key=True),
    Column('source_id', String, ForeignKey('sources.id'), primary_key=True)
)

holdsposition_source_table = Table(
    'holdsposition_source',
    Base.metadata,
    Column('holdsposition_id', String, ForeignKey('holds_position.id'), primary_key=True),
    Column('source_id', String, ForeignKey('sources.id'), primary_key=True)
)

position_country_table = Table(
    'position_country',
    Base.metadata,
    Column('position_id', String, ForeignKey('positions.id'), primary_key=True),
    Column('country_id', String, ForeignKey('countries.id'), primary_key=True)
)


class Politician(Base, UUIDMixin, TimestampMixin):
    """Politician entity."""
    __tablename__ = "politicians"

    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)
    is_deceased = Column(Boolean, default=False)

    # Relationships
    properties = relationship("Property", back_populates="politician", cascade="all, delete-orphan")
    positions_held = relationship("HoldsPosition", back_populates="politician", cascade="all, delete-orphan")
    sources = relationship("Source", secondary=politician_source_table, back_populates="politicians")


class Source(Base, UUIDMixin, TimestampMixin):
    """Source entity for tracking where data was extracted from."""
    __tablename__ = "sources"

    url = Column(String, nullable=False, unique=True)
    extracted_at = Column(DateTime)

    # Relationships
    politicians = relationship("Politician", secondary=politician_source_table, back_populates="sources")
    properties = relationship("Property", secondary=property_source_table, back_populates="sources")
    positions_held = relationship("HoldsPosition", secondary=holdsposition_source_table, back_populates="sources")


class Property(Base, UUIDMixin, TimestampMixin):
    """Property entity for storing extracted politician properties."""
    __tablename__ = "properties"

    politician_id = Column(String, ForeignKey('politicians.id'), nullable=False)
    type = Column(String, nullable=False)  # e.g., 'BirthDate', 'BirthPlace'
    value = Column(String, nullable=False)
    is_extracted = Column(Boolean, default=True)  # True if newly extracted and unconfirmed
    confirmed_by = Column(String, nullable=True)  # ID of user who confirmed
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    politician = relationship("Politician", back_populates="properties")
    sources = relationship("Source", secondary=property_source_table, back_populates="properties")


class Country(Base, UUIDMixin, TimestampMixin):
    """Country entity for storing country information."""
    __tablename__ = "countries"

    name = Column(String, nullable=False)  # Country name in English
    iso_code = Column(String, unique=True, index=True)  # ISO 3166-1 alpha-2 code
    wikidata_id = Column(String, unique=True, index=True)

    # Relationships
    positions = relationship("Position", secondary=position_country_table, back_populates="countries")


class Position(Base, UUIDMixin, TimestampMixin):
    """Position entity for political positions."""
    __tablename__ = "positions"

    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)

    # Relationships
    countries = relationship("Country", secondary=position_country_table, back_populates="positions")
    held_by = relationship("HoldsPosition", back_populates="position", cascade="all, delete-orphan")


class HoldsPosition(Base, UUIDMixin, TimestampMixin):
    """HoldsPosition entity for politician-position relationships."""
    __tablename__ = "holds_position"

    politician_id = Column(String, ForeignKey('politicians.id'), nullable=False)
    position_id = Column(String, ForeignKey('positions.id'), nullable=False)
    start_date = Column(String)  # Allowing incomplete dates as strings
    end_date = Column(String)    # Allowing incomplete dates as strings
    is_extracted = Column(Boolean, default=True)  # True if newly extracted and unconfirmed
    confirmed_by = Column(String, nullable=True)  # ID of user who confirmed
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    politician = relationship("Politician", back_populates="positions_held")
    position = relationship("Position", back_populates="held_by")
    sources = relationship("Source", secondary=holdsposition_source_table, back_populates="positions_held")