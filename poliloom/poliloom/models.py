"""Database models for the PoliLoom project."""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, event
from sqlalchemy.orm import relationship, declarative_base
from uuid import uuid4
from .vector_search import get_vector_backend

Base = declarative_base()

# Initialize vector backend
vector_backend = get_vector_backend()

# Global cached embedding model
_embedding_model = None


def _get_embedding_model():
    """Get or create the cached SentenceTransformer model."""
    global _embedding_model
    if _embedding_model is None:
        import logging
        import os
        logger = logging.getLogger(__name__)
        pid = os.getpid()
        logger.info(f"Loading SentenceTransformer model in process {pid} (should only happen once per process)...")
        
        # Suppress sentence-transformers logging during model loading
        st_logger = logging.getLogger('sentence_transformers')
        original_level = st_logger.level
        st_logger.setLevel(logging.WARNING)
        
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        finally:
            # Restore original logging level
            st_logger.setLevel(original_level)
        
        logger.info(f"SentenceTransformer model loaded and cached successfully in process {pid}")
    return _embedding_model


class TimestampMixin:
    """Mixin for adding timestamp fields."""
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


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
    citizenships = relationship("HasCitizenship", back_populates="politician", cascade="all, delete-orphan")
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
    citizens = relationship("HasCitizenship", back_populates="country", cascade="all, delete-orphan")


class Position(Base, UUIDMixin, TimestampMixin):
    """Position entity for political positions."""
    __tablename__ = "positions"

    name = Column(String, nullable=False)
    wikidata_id = Column(String, unique=True, index=True)

    # Relationships
    countries = relationship("Country", secondary=position_country_table, back_populates="positions")
    held_by = relationship("HoldsPosition", back_populates="position", cascade="all, delete-orphan")

    def generate_embedding(self, text=None):
        """Generate embedding for this position."""
        if text is None:
            text = self.name
        
        model = _get_embedding_model()
        embedding = model.encode(text, convert_to_tensor=False)
        return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

    @classmethod
    def find_similar(cls, session, query_text, top_k=10, country_filter=None):
        """Find positions similar to the query text."""
        # Generate embedding for query
        dummy_position = cls(name=query_text)
        query_embedding = dummy_position.generate_embedding()
        
        # Build filters
        filters = None
        if country_filter:
            country = session.query(Country).filter(
                Country.iso_code == country_filter.upper()
            ).first()
            if country:
                filters = cls.countries.contains(country)
            else:
                return []
        
        # Use vector backend to find similar positions
        return vector_backend.find_similar(
            session, cls, 'embedding', query_embedding, top_k, filters
        )




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


class HasCitizenship(Base, UUIDMixin, TimestampMixin):
    """HasCitizenship entity for politician-country citizenship relationships."""
    __tablename__ = "has_citizenship"

    politician_id = Column(String, ForeignKey('politicians.id'), nullable=False)
    country_id = Column(String, ForeignKey('countries.id'), nullable=False)

    # Relationships
    politician = relationship("Politician", back_populates="citizenships")
    country = relationship("Country", back_populates="citizens")


# Setup vector columns for similarity search
# Using 384 dimensions for sentence-transformers/all-MiniLM-L6-v2 embeddings
vector_backend.setup_vector_column(Position, 'embedding', dimensions=384)