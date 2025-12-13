"""Meilisearch client for entity search.

Provides a thin wrapper around Meilisearch for indexing and searching entities.
Uses a single 'entities' index with a 'type' field for filtering.
"""

import logging
import os
from typing import Optional, TypedDict

import meilisearch
from dotenv import load_dotenv


# Single index for all searchable entities
INDEX_NAME = "entities"


class SearchDocument(TypedDict):
    """Document format for Meilisearch indexing."""

    id: str
    type: str  # Entity type (e.g., 'locations', 'politicians')
    labels: list[str]


load_dotenv()

logger = logging.getLogger(__name__)

# Global instance for lazy initialization
_search_service: Optional["SearchService"] = None


class SearchService:
    """Meilisearch client for entity search.

    Uses a single 'entities' index with type-based filtering.
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

    def create_index(self) -> None:
        """Create the entities index with proper settings."""
        logger.info(f"Creating index '{INDEX_NAME}'")
        task = self.client.create_index(INDEX_NAME, {"primaryKey": "id"})
        self.client.wait_for_task(task.task_uid)

        # Configure index settings
        index = self.client.index(INDEX_NAME)
        task = index.update_settings(
            {
                "searchableAttributes": ["labels"],
                "filterableAttributes": ["type"],
                "displayedAttributes": ["id", "type", "labels"],
            }
        )
        self.client.wait_for_task(task.task_uid)

    def delete_index(self) -> None:
        """Delete the entities index if it exists."""
        try:
            logger.info(f"Deleting index '{INDEX_NAME}'")
            task = self.client.delete_index(INDEX_NAME)
            self.client.wait_for_task(task.task_uid)
        except meilisearch.errors.MeilisearchApiError as e:
            if "index_not_found" not in str(e):
                raise
            logger.debug(f"Index '{INDEX_NAME}' does not exist, nothing to delete")

    def index_documents(self, documents: list[SearchDocument]) -> Optional[int]:
        """Index documents to Meilisearch.

        Returns immediately without waiting, allowing Meilisearch's
        auto-batching to combine consecutive requests for faster indexing.

        Args:
            documents: List of SearchDocument dicts with 'id', 'type', and 'labels'

        Returns:
            Task UID for tracking, or None if no documents
        """
        if not documents:
            return None

        index = self.client.index(INDEX_NAME)
        task = index.add_documents(documents)
        return task.task_uid

    def wait_for_tasks(self, task_uids: list[int], timeout_in_ms: int = 300000) -> None:
        """Wait for multiple tasks to complete.

        Args:
            task_uids: List of task UIDs to wait for
            timeout_in_ms: Timeout for each task (default 5 minutes)
        """
        for task_uid in task_uids:
            self.client.wait_for_task(task_uid, timeout_in_ms=timeout_in_ms)

    def delete_documents(self, document_ids: list[str]) -> int:
        """Delete documents from Meilisearch by ID.

        Args:
            document_ids: List of document IDs (wikidata_ids) to delete

        Returns:
            Number of documents requested for deletion
        """
        if not document_ids:
            return 0

        index = self.client.index(INDEX_NAME)
        task = index.delete_documents(document_ids)
        self.client.wait_for_task(task.task_uid, timeout_in_ms=60000)

        return len(document_ids)

    def search(
        self, query: str, entity_type: Optional[str] = None, limit: int = 100
    ) -> list[str]:
        """Search Meilisearch for entities by label.

        Args:
            query: Search query text
            entity_type: Optional type filter (e.g., 'locations', 'politicians')
            limit: Maximum number of results

        Returns:
            List of document IDs (wikidata_ids) ordered by relevance
        """
        index = self.client.index(INDEX_NAME)
        search_params = {"limit": limit}
        if entity_type:
            search_params["filter"] = f"type = '{entity_type}'"
        results = index.search(query, search_params)
        return [hit["id"] for hit in results["hits"]]


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
