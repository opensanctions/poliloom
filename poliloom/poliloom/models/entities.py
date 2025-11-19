"""Supporting entity models: Country, Language, Location, Position."""

from typing import List

from sqlalchemy import Column, String
from pgvector.sqlalchemy import Vector

from .base import (
    Base,
    EntityCreationMixin,
    LanguageCodeMixin,
    TimestampMixin,
    UpsertMixin,
)
from .wikidata import WikidataEntityMixin


class Country(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    # UpsertMixin configuration
    _upsert_update_columns = ["iso_code"]

    iso_code = Column(String, index=True)  # ISO 3166-1 alpha-2 code

    # Mapping configuration for two-stage extraction
    MAPPING_ENTITY_NAME = "country"


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

    # UpsertMixin configuration
    _upsert_update_columns = ["iso1_code", "iso3_code", "wikimedia_code"]


class WikipediaProject(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Wikipedia project entity for storing Wikipedia language editions."""

    __tablename__ = "wikipedia_projects"

    # UpsertMixin configuration
    _upsert_update_columns = ["official_website"]

    official_website = Column(String, nullable=True)  # P856 official website URL


class Location(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    # Mapping configuration for two-stage extraction
    MAPPING_ENTITY_NAME = "location"


class Position(
    Base, TimestampMixin, UpsertMixin, WikidataEntityMixin, EntityCreationMixin
):
    """Position entity for political positions."""

    __tablename__ = "positions"

    embedding = Column(Vector(384), nullable=True)

    # Mapping configuration for two-stage extraction
    MAPPING_ENTITY_NAME = "position"

    @classmethod
    def search_by_embedding(cls, query, query_embedding: List[float]):
        """Apply embedding similarity filter to a position query using vector search.

        Filters positions with embeddings and orders by cosine similarity.

        Args:
            query: Existing select statement for Position entities
            query_embedding: Pre-generated embedding vector to search for

        Returns:
            Modified query filtered and ordered by embedding similarity
        """
        query = query.filter(cls.embedding.isnot(None)).order_by(
            cls.embedding.cosine_distance(query_embedding)
        )

        return query
