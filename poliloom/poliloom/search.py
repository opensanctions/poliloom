"""Unified search service for entity lookup.

Provides a single interface for searching entities:
- positions: pgvector embedding similarity search
- locations, countries, languages, politicians: Meilisearch text search
"""

import logging
import os
from typing import Optional, Type

import meilisearch
from dotenv import load_dotenv
from sqlalchemy.orm import DeclarativeBase

from poliloom.models import Country, Language, Location, Position
from poliloom.models.politician import Politician

load_dotenv()

logger = logging.getLogger(__name__)

# Entity models that use Meilisearch for label search
MEILISEARCH_MODELS: list[Type[DeclarativeBase]] = [
    Location,
    Country,
    Language,
    Politician,
]

# Entity models that use embedding search
EMBEDDING_MODELS: list[Type[DeclarativeBase]] = [Position]

# All searchable entity models
ALL_MODELS = MEILISEARCH_MODELS + EMBEDDING_MODELS

# Global instance for lazy initialization
_search_service: Optional["SearchService"] = None


class SearchService:
    """Unified search service for entity lookup.

    Routes search requests to the appropriate backend:
    - Meilisearch for text-based label search (locations, countries, languages, politicians)
    - pgvector for embedding similarity search (positions)
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize SearchService with Meilisearch connection.

        Args:
            url: Meilisearch server URL. Defaults to MEILI_URL env var
                 or http://localhost:7700.
            api_key: Meilisearch API key. Defaults to MEILI_MASTER_KEY env var.
        """
        self.url = url or os.getenv("MEILI_URL", "http://localhost:7700")
        self.api_key = api_key or os.getenv("MEILI_MASTER_KEY")
        self.client = meilisearch.Client(self.url, self.api_key)

    def create_index(self, index_name: str) -> None:
        """Create an index with proper settings.

        Args:
            index_name: Name of the index to create
        """
        logger.info(f"Creating index '{index_name}'")
        task = self.client.create_index(index_name, {"primaryKey": "id"})
        self.client.wait_for_task(task.task_uid)

        # Configure index settings
        index = self.client.index(index_name)
        task = index.update_settings(
            {
                "searchableAttributes": ["labels"],
                "displayedAttributes": ["id", "labels"],
            }
        )
        self.client.wait_for_task(task.task_uid)

    def delete_index(self, index_name: str) -> None:
        """Delete an index if it exists.

        Args:
            index_name: Name of the index to delete
        """
        try:
            logger.info(f"Deleting index '{index_name}'")
            task = self.client.delete_index(index_name)
            self.client.wait_for_task(task.task_uid)
        except meilisearch.errors.MeilisearchApiError as e:
            if "index_not_found" not in str(e):
                raise
            logger.debug(f"Index '{index_name}' does not exist, nothing to delete")

    def index_entities(self, index_name: str, entities: list) -> int:
        """Index entities with their labels.

        Args:
            index_name: Name of the index (e.g., 'locations', 'politicians')
            entities: List of entity model instances with wikidata_entity.labels loaded

        Returns:
            Number of entities indexed
        """
        index = self.client.index(index_name)

        # Transform entities to documents
        documents = [
            {
                "id": entity.wikidata_id,
                "labels": [label.label for label in entity.wikidata_entity.labels],
            }
            for entity in entities
        ]

        # Add documents and wait for completion
        task = index.add_documents(documents)
        self.client.wait_for_task(task.task_uid, timeout_in_ms=60000)

        return len(documents)

    def search_entities(
        self,
        model_class: Type[DeclarativeBase],
        query: str,
        session,
        limit: int = 100,
    ) -> list[str]:
        """Search for entities by query text.

        Routes to the appropriate search backend based on model class:
        - Position: pgvector embedding similarity search
        - others: Meilisearch text search

        Args:
            model_class: Model class to search (e.g., Location, Position)
            query: Search query text
            session: SQLAlchemy session
            limit: Maximum number of results

        Returns:
            List of entity_ids (wikidata_ids) ordered by relevance
        """
        if model_class not in ALL_MODELS:
            raise ValueError(
                f"Unknown model_class: {model_class}. Must be one of: {ALL_MODELS}"
            )

        if model_class in MEILISEARCH_MODELS:
            results = self._search_meilisearch(model_class.__tablename__, query, limit)
            return [r["id"] for r in results]
        else:
            return self._search_embeddings(model_class, query, session, limit)

    def _search_meilisearch(
        self, index_name: str, query: str, limit: int = 100
    ) -> list[dict]:
        """Search Meilisearch for entities by label.

        Args:
            index_name: Name of the index to search
            query: Search query text
            limit: Maximum number of results

        Returns:
            List of dicts with 'id' and 'labels' keys, ordered by relevance
        """
        try:
            index = self.client.index(index_name)
            results = index.search(query, {"limit": limit})
            return results["hits"]
        except meilisearch.errors.MeilisearchApiError as e:
            if "index_not_found" in str(e):
                logger.warning(
                    f"Index '{index_name}' not found, returning empty results"
                )
                return []
            raise

    def _search_embeddings(
        self,
        model_class: Type[DeclarativeBase],
        query: str,
        session,
        limit: int = 100,
    ) -> list[str]:
        """Search using pgvector embedding similarity.

        Args:
            model_class: Model class with embedding column (currently only Position)
            query: Search query text to embed
            session: SQLAlchemy session
            limit: Maximum number of results

        Returns:
            List of entity_ids ordered by similarity
        """
        from poliloom.embeddings import get_embedding_model

        if model_class != Position:
            raise ValueError(
                f"Embedding search not supported for {model_class.__tablename__}"
            )

        # Generate query embedding
        model = get_embedding_model()
        query_embedding = model.encode(query, convert_to_tensor=False)

        # Search using pgvector
        results = (
            session.query(Position.wikidata_id)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .all()
        )

        return [r[0] for r in results]

    def health_check(self) -> bool:
        """Check if Meilisearch is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            health = self.client.health()
            return health.get("status") == "available"
        except Exception:
            return False

    def build_index(
        self,
        session,
        model_class: Type[DeclarativeBase],
        batch_size: int = 10000,
    ) -> int:
        """Build Meilisearch index for an entity type from database.

        Deletes and recreates the index, then populates it from the database.

        Args:
            session: SQLAlchemy database session
            model_class: Model class to build index for
            batch_size: Number of entities to index per batch

        Returns:
            Number of entities indexed

        Raises:
            ValueError: If model_class is not a Meilisearch model
        """
        from sqlalchemy.orm import selectinload

        from poliloom.models import WikidataEntity

        if model_class not in MEILISEARCH_MODELS:
            raise ValueError(
                f"Invalid model_class: {model_class.__tablename__}. "
                f"Must be one of: {[m.__tablename__ for m in MEILISEARCH_MODELS]}"
            )

        index_name = model_class.__tablename__

        # Delete and recreate index
        self.delete_index(index_name)
        self.create_index(index_name)

        # Query entities with labels eagerly loaded
        query = session.query(model_class).options(
            selectinload(model_class.wikidata_entity).selectinload(
                WikidataEntity.labels
            )
        )

        # Index entities in batches
        indexed_count = 0
        entities_batch = []

        for entity in query.yield_per(batch_size):
            entities_batch.append(entity)

            if len(entities_batch) >= batch_size:
                self.index_entities(index_name, entities_batch)
                indexed_count += len(entities_batch)
                logger.info(f"Indexed {indexed_count} {index_name} entities")
                entities_batch = []

        # Index remaining entities
        if entities_batch:
            self.index_entities(index_name, entities_batch)
            indexed_count += len(entities_batch)

        return indexed_count

    def build_all_indexes(
        self,
        session,
        batch_size: int = 10000,
    ) -> dict[str, int]:
        """Build all Meilisearch indexes from database.

        Args:
            session: SQLAlchemy database session
            batch_size: Number of entities to index per batch

        Returns:
            Dict mapping table name to number of entities indexed
        """
        results = {}
        for model_class in MEILISEARCH_MODELS:
            count = self.build_index(session, model_class, batch_size)
            results[model_class.__tablename__] = count
            logger.info(f"Indexed {count} entities for {model_class.__tablename__}")
        return results


def get_search_service() -> SearchService:
    """Get or create the global SearchService instance.

    This is used as a FastAPI dependency.

    Returns:
        SearchService instance
    """
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


def reset_search_service() -> None:
    """Reset the global SearchService instance.

    Used for testing to allow injecting mock services.
    """
    global _search_service
    _search_service = None
