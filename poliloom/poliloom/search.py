"""Unified search service for entity lookup.

Provides a single interface for searching entities:
- positions: pgvector embedding similarity search
- locations, countries, languages, politicians: Meilisearch text search
"""

import hashlib
import logging
import os
from typing import Optional

import meilisearch
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Entity types that use Meilisearch for label search
MEILISEARCH_ENTITY_TYPES = ["locations", "countries", "languages", "politicians"]

# Entity types that use embedding search
EMBEDDING_ENTITY_TYPES = ["positions"]

# All searchable entity types
ALL_ENTITY_TYPES = MEILISEARCH_ENTITY_TYPES + EMBEDDING_ENTITY_TYPES

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
            url: Meilisearch server URL. Defaults to MEILISEARCH_URL env var
                 or http://localhost:7700.
            api_key: Meilisearch API key. Defaults to MEILISEARCH_MASTER_KEY env var.
        """
        self.url = url or os.getenv("MEILISEARCH_URL", "http://localhost:7700")
        self.api_key = api_key or os.getenv("MEILISEARCH_MASTER_KEY")
        self.client = meilisearch.Client(self.url, self.api_key)

    def ensure_indexes(self) -> None:
        """Create all indexes with proper settings if they don't exist."""
        for index_name in MEILISEARCH_ENTITY_TYPES:
            self._ensure_index(index_name)

    def _ensure_index(self, index_name: str) -> None:
        """Create a single index with proper settings if it doesn't exist."""
        try:
            self.client.get_index(index_name)
            logger.debug(f"Index '{index_name}' already exists")
        except meilisearch.errors.MeilisearchApiError as e:
            if "index_not_found" in str(e):
                logger.info(f"Creating index '{index_name}'")
                task = self.client.create_index(index_name, {"primaryKey": "id"})
                self.client.wait_for_task(task.task_uid)
            else:
                raise

        # Configure index settings
        index = self.client.index(index_name)
        task = index.update_settings(
            {
                "searchableAttributes": ["label"],
                "displayedAttributes": ["entity_id", "label"],
                "distinctAttribute": "entity_id",
                # Typo tolerance enabled by default in Meilisearch
            }
        )
        self.client.wait_for_task(task.task_uid)

    def index_labels(
        self, index_name: str, labels: list[dict], batch_size: int = 1000
    ) -> int:
        """Index labels for an entity type.

        Args:
            index_name: Name of the index (e.g., 'locations', 'politicians')
            labels: List of dicts with 'entity_id' and 'label' keys
            batch_size: Number of documents per batch

        Returns:
            Number of documents indexed
        """
        self._ensure_index(index_name)
        index = self.client.index(index_name)

        # Transform labels to documents with unique IDs
        documents = []
        for label_data in labels:
            entity_id = label_data["entity_id"]
            label = label_data["label"]
            # Create unique ID from entity_id + label hash
            label_hash = hashlib.md5(label.encode()).hexdigest()[:8]
            doc_id = f"{entity_id}_{label_hash}"
            documents.append(
                {
                    "id": doc_id,
                    "entity_id": entity_id,
                    "label": label,
                }
            )

        # Batch insert
        total_indexed = 0
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            task = index.add_documents(batch)
            self.client.wait_for_task(task.task_uid)
            total_indexed += len(batch)
            logger.debug(f"Indexed {total_indexed}/{len(documents)} documents")

        return total_indexed

    def clear_index(self, index_name: str) -> None:
        """Delete all documents from an index.

        Args:
            index_name: Name of the index to clear
        """
        try:
            index = self.client.index(index_name)
            task = index.delete_all_documents()
            self.client.wait_for_task(task.task_uid)
            logger.info(f"Cleared index '{index_name}'")
        except meilisearch.errors.MeilisearchApiError as e:
            if "index_not_found" not in str(e):
                raise

    def search_entities(
        self,
        entity_type: str,
        query: str,
        session,
        limit: int = 100,
    ) -> list[str]:
        """Search for entities by query text.

        Routes to the appropriate search backend based on entity type:
        - positions: pgvector embedding similarity search
        - others: Meilisearch text search

        Args:
            entity_type: One of 'locations', 'countries', 'languages', 'politicians', 'positions'
            query: Search query text
            session: SQLAlchemy session
            limit: Maximum number of results

        Returns:
            List of entity_ids (wikidata_ids) ordered by relevance
        """
        if entity_type in MEILISEARCH_ENTITY_TYPES:
            results = self._search_meilisearch(entity_type, query, limit)
            return [r["entity_id"] for r in results]
        elif entity_type in EMBEDDING_ENTITY_TYPES:
            return self._search_embeddings(entity_type, query, session, limit)
        else:
            raise ValueError(
                f"Unknown entity_type: {entity_type}. "
                f"Must be one of: {ALL_ENTITY_TYPES}"
            )

    def _search_meilisearch(
        self, index_name: str, query: str, limit: int = 100
    ) -> list[dict]:
        """Search Meilisearch for entities by label.

        Args:
            index_name: Name of the index to search
            query: Search query text
            limit: Maximum number of results

        Returns:
            List of dicts with 'entity_id' and 'label' keys, ordered by relevance
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
        entity_type: str,
        query: str,
        session,
        limit: int = 100,
    ) -> list[str]:
        """Search using pgvector embedding similarity.

        Args:
            entity_type: Entity type (currently only 'positions')
            query: Search query text to embed
            session: SQLAlchemy session
            limit: Maximum number of results

        Returns:
            List of entity_ids ordered by similarity
        """
        from poliloom.embeddings import get_embedding_model
        from poliloom.models import Position

        if entity_type != "positions":
            raise ValueError(f"Embedding search not supported for {entity_type}")

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
        entity_type: str,
        clear: bool = False,
        batch_size: int = 1000,
    ) -> int:
        """Build Meilisearch index for an entity type from database.

        Args:
            session: SQLAlchemy database session
            entity_type: One of 'locations', 'countries', 'languages', 'politicians'
            clear: If True, clear existing index before building
            batch_size: Number of labels to index per batch

        Returns:
            Number of labels indexed

        Raises:
            ValueError: If entity_type is not valid
        """
        from poliloom.models import (
            Location,
            Country,
            Language,
            WikidataEntityLabel,
        )
        from poliloom.models.politician import Politician

        # Map entity types to their model classes
        entity_models = {
            "locations": Location,
            "countries": Country,
            "languages": Language,
            "politicians": Politician,
        }

        if entity_type not in entity_models:
            raise ValueError(
                f"Invalid entity_type: {entity_type}. "
                f"Must be one of: {list(entity_models.keys())}"
            )

        model_class = entity_models[entity_type]
        index_name = model_class.__tablename__

        if clear:
            self.clear_index(index_name)

        # Query labels for this entity type
        query = session.query(
            WikidataEntityLabel.entity_id,
            WikidataEntityLabel.label,
        ).join(
            model_class,
            WikidataEntityLabel.entity_id == model_class.wikidata_id,
        )

        # Collect and index labels in batches
        labels = []
        indexed_count = 0

        for entity_id, label in query.yield_per(batch_size):
            labels.append({"entity_id": entity_id, "label": label})

            if len(labels) >= batch_size:
                self.index_labels(index_name, labels, batch_size)
                indexed_count += len(labels)
                logger.info(f"Indexed {indexed_count} {entity_type} labels")
                labels = []

        # Index remaining labels
        if labels:
            self.index_labels(index_name, labels, batch_size)
            indexed_count += len(labels)

        return indexed_count

    def build_all_indexes(
        self,
        session,
        clear: bool = False,
        batch_size: int = 1000,
    ) -> dict[str, int]:
        """Build all Meilisearch indexes from database.

        Args:
            session: SQLAlchemy database session
            clear: If True, clear existing indexes before building
            batch_size: Number of labels to index per batch

        Returns:
            Dict mapping entity_type to number of labels indexed
        """
        results = {}
        for entity_type in MEILISEARCH_ENTITY_TYPES:
            count = self.build_index(session, entity_type, clear, batch_size)
            results[entity_type] = count
            logger.info(f"Indexed {count} labels for {entity_type}")
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
