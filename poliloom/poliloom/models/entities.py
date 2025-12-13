"""Supporting entity models: Country, Language, Location, Position."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Column, String
from sqlalchemy.orm import Session, relationship
from pgvector.sqlalchemy import Vector

from .base import (
    Base,
    EntityCreationMixin,
    LanguageCodeMixin,
    SearchIndexedMixin,
    TimestampMixin,
    UpsertMixin,
)
from .wikidata import WikidataEntityMixin

if TYPE_CHECKING:
    from poliloom.search import SearchService


class Country(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
    SearchIndexedMixin,
):
    """Country entity for storing country information."""

    __tablename__ = "countries"

    # UpsertMixin configuration
    _upsert_update_columns = ["iso_code"]

    # Hierarchy configuration for import filtering and cleanup
    _hierarchy_roots = [
        "Q6256",  # country
        "Q3624078",  # sovereign state
        "Q20181813",  # disputed territory
        "Q1520223",  # constituent country
        "Q1489259",  # dependent territory
        "Q1048835",  # political territorial entity
    ]
    _hierarchy_ignore = []

    # Cleanup configuration: property type to soft-delete when cleaning hierarchy
    _cleanup_property_type = "CITIZENSHIP"

    iso_code = Column(String, index=True)  # ISO 3166-1 alpha-2 code

    # Mapping configuration for two-stage extraction
    MAPPING_ENTITY_NAME = "country"

    @classmethod
    def should_import(
        cls, entity, instance_ids: set, subclass_ids: set
    ) -> Optional[Dict[str, Any]]:
        """Determine if this country entity should be imported.

        Args:
            entity: WikidataEntityProcessor instance
            instance_ids: Set of P31 (instance of) QIDs
            subclass_ids: Set of P279 (subclass of) QIDs

        Returns:
            Dict with additional fields to add, or None if should not import
        """
        # Extract ISO 3166-1 alpha-2 code for countries (P297)
        iso_claims = entity.get_truthy_claims("P297")
        for claim in iso_claims:
            try:
                iso_code = claim["mainsnak"]["datavalue"]["value"]
                return {"iso_code": iso_code}
            except (KeyError, TypeError):
                continue

        # Only import countries that have an ISO code
        return None


class Language(
    Base,
    TimestampMixin,
    LanguageCodeMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
    SearchIndexedMixin,
):
    """Language entity for storing language information."""

    __tablename__ = "languages"

    # UpsertMixin configuration
    _upsert_update_columns = ["iso_639_1", "iso_639_2", "iso_639_3", "wikimedia_code"]

    # Hierarchy configuration for import filtering and cleanup
    _hierarchy_roots = ["Q34770"]  # language
    _hierarchy_ignore = []

    # Cleanup configuration: no properties reference languages
    _cleanup_property_type = None

    @classmethod
    def should_import(
        cls, entity, instance_ids: set, subclass_ids: set
    ) -> Optional[Dict[str, Any]]:
        """Determine if this language entity should be imported.

        Args:
            entity: WikidataEntityProcessor instance
            instance_ids: Set of P31 (instance of) QIDs
            subclass_ids: Set of P279 (subclass of) QIDs

        Returns:
            Dict with additional fields to add, or None if should not import
        """
        # Extract ISO 639-1 code (P218)
        iso_639_1 = None
        iso_639_1_claims = entity.get_truthy_claims("P218")
        for claim in iso_639_1_claims:
            try:
                iso_639_1 = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        # Extract ISO 639-2 code (P219)
        iso_639_2 = None
        iso_639_2_claims = entity.get_truthy_claims("P219")
        for claim in iso_639_2_claims:
            try:
                iso_639_2 = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        # Extract ISO 639-3 code (P220)
        iso_639_3 = None
        iso_639_3_claims = entity.get_truthy_claims("P220")
        for claim in iso_639_3_claims:
            try:
                iso_639_3 = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        # Extract Wikimedia language code (P424)
        wikimedia_code = None
        wikimedia_claims = entity.get_truthy_claims("P424")
        for claim in wikimedia_claims:
            try:
                wikimedia_code = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        # Import all languages (ISO codes optional)
        return {
            "iso_639_1": iso_639_1,
            "iso_639_2": iso_639_2,
            "iso_639_3": iso_639_3,
            "wikimedia_code": wikimedia_code,
        }


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

    # Relationships
    wikipedia_links = relationship("WikipediaLink", back_populates="wikipedia_project")

    @classmethod
    def should_import(
        cls, entity, instance_ids: set, subclass_ids: set
    ) -> Optional[Dict[str, Any]]:
        """Determine if this Wikipedia project entity should be imported.

        Filtering criteria:
        - Must have P856 (official website)
        - P856 must contain 'wikipedia.org'
        - Must not be umbrella entity (P31 = Q210588)
        - When multiple P856 values exist, use preferred rank

        Args:
            entity: WikidataEntityProcessor instance
            instance_ids: Set of P31 (instance of) QIDs
            subclass_ids: Set of P279 (subclass of) QIDs

        Returns:
            Dict with additional fields to add, or None if should not import
        """
        # Filter out umbrella entities (Q210588)
        if "Q210588" in instance_ids:
            return None

        # Extract P856 (official website) using truthy filtering
        # This automatically handles preferred rank selection when multiple P856 exist
        official_website = None
        p856_claims = entity.get_truthy_claims("P856")

        # Get the first P856 value (truthy filtering already selected preferred if exists)
        if p856_claims:
            try:
                official_website = p856_claims[0]["mainsnak"]["datavalue"]["value"]
            except (KeyError, TypeError):
                pass

        # Only import Wikipedia projects that have a wikipedia.org URL
        if official_website and "wikipedia.org" in official_website:
            return {"official_website": official_website}

        return None


class Location(
    Base,
    TimestampMixin,
    UpsertMixin,
    WikidataEntityMixin,
    EntityCreationMixin,
    SearchIndexedMixin,
):
    """Location entity for geographic locations."""

    __tablename__ = "locations"

    # Hierarchy configuration for import filtering and cleanup
    _hierarchy_roots = [
        "Q486972",  # human settlement
        "Q82794",  # region
        "Q1306755",  # administrative centre
        "Q3257686",  # locality
        "Q48907157",  # section of populated place
    ]
    _hierarchy_ignore = []

    # Cleanup configuration: property type to soft-delete when cleaning hierarchy
    _cleanup_property_type = "BIRTHPLACE"

    # Mapping configuration for two-stage extraction
    MAPPING_ENTITY_NAME = "location"

    @classmethod
    def should_import(
        cls, entity, instance_ids: set, subclass_ids: set
    ) -> Optional[Dict[str, Any]]:
        """Determine if this location entity should be imported.

        Args:
            entity: WikidataEntityProcessor instance
            instance_ids: Set of P31 (instance of) QIDs
            subclass_ids: Set of P279 (subclass of) QIDs

        Returns:
            Empty dict (no additional fields), or None if should not import
        """
        # Locations have no special filtering - import all that match hierarchy
        return {}


class Position(
    Base, TimestampMixin, UpsertMixin, WikidataEntityMixin, EntityCreationMixin
):
    """Position entity for political positions."""

    __tablename__ = "positions"

    embedding = Column(Vector(384), nullable=True)

    # Hierarchy configuration for import filtering and cleanup
    _hierarchy_roots = [
        "Q4164871",  # position
        "Q29645880",  # ambassador of a country
        "Q29645886",  # ambassador to a country
        "Q707492",  # military chief of staff
    ]
    _hierarchy_ignore = [
        "Q114962596",  # historical position
        "Q193622",  # order
        "Q60754876",  # grade of an order
        "Q618779",  # award
        "Q4240305",  # cross
        "Q120560",  # minor basilica
        "Q2977",  # cathedral
        "Q63187345",  # religious occupation
        "Q29982545",  # function in the Evangelical Church of Czech Brethren
        "Q12737077",  # occupation
    ]

    # Cleanup configuration: property type to soft-delete when cleaning hierarchy
    _cleanup_property_type = "POSITION"

    # Mapping configuration for two-stage extraction
    MAPPING_ENTITY_NAME = "position"

    @classmethod
    def should_import(
        cls, entity, instance_ids: set, subclass_ids: set
    ) -> Optional[Dict[str, Any]]:
        """Determine if this position entity should be imported.

        Args:
            entity: WikidataEntityProcessor instance
            instance_ids: Set of P31 (instance of) QIDs
            subclass_ids: Set of P279 (subclass of) QIDs

        Returns:
            Empty dict (no additional fields), or None if should not import
        """
        # Positions have no special filtering - import all that match hierarchy
        return {}

    @classmethod
    def find_similar(
        cls,
        query: str,
        session: Session,
        search_service: "SearchService",
        limit: int = 100,
    ) -> list[str]:
        """Find similar positions using embedding similarity search.

        Implements the Searchable protocol using pgvector embeddings.

        Args:
            query: Search query text to embed
            session: SQLAlchemy session
            search_service: SearchService instance (unused, for protocol compatibility)
            limit: Maximum number of results

        Returns:
            List of wikidata_ids ordered by similarity
        """
        from poliloom.embeddings import get_embedding_model

        model = get_embedding_model()
        query_embedding = model.encode(query, convert_to_tensor=False)

        results = (
            session.query(cls.wikidata_id)
            .filter(cls.embedding.isnot(None))
            .order_by(cls.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .all()
        )

        return [r[0] for r in results]
