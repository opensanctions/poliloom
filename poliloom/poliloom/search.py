"""Meilisearch client for entity search.

Provides a thin wrapper around Meilisearch for indexing and searching entities.
Uses a single 'entities' index with a 'type' field for filtering.
Supports hybrid search (keyword + semantic) using OpenAI embeddings.
"""

import logging
import os
from typing import Optional, TypedDict

import meilisearch
from dotenv import load_dotenv


# Single index for all searchable entities
INDEX_NAME = "entities"

# Embedder name for hybrid search
EMBEDDER_NAME = "openai"

# OpenAI embedding model configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class SearchDocument(TypedDict):
    """Document format for Meilisearch indexing."""

    id: str
    types: list[str]  # Entity types (e.g., ['Location', 'Country'])
    labels: list[str]


load_dotenv()

logger = logging.getLogger(__name__)


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
        """Create the entities index with proper settings and OpenAI embedder."""
        logger.info(f"Creating index '{INDEX_NAME}'")
        task = self.client.create_index(INDEX_NAME, {"primaryKey": "id"})
        self.client.wait_for_task(task.task_uid)

        # Configure index settings
        index = self.client.index(INDEX_NAME)
        task = index.update_settings(
            {
                "searchableAttributes": ["labels"],
                "filterableAttributes": ["types"],
                "displayedAttributes": ["id", "types", "labels"],
            }
        )
        self.client.wait_for_task(task.task_uid)

        # Configure OpenAI embedder for hybrid search
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        logger.info(f"Configuring OpenAI embedder '{EMBEDDER_NAME}'")
        task = index.update_embedders(
            {
                EMBEDDER_NAME: {
                    "source": "openAi",
                    "apiKey": openai_api_key,
                    "model": EMBEDDING_MODEL,
                    "dimensions": EMBEDDING_DIMENSIONS,
                    "documentTemplate": "{{doc.labels | join: ', '}}",
                }
            }
        )
        self.client.wait_for_task(task.task_uid)
        logger.info("OpenAI embedder configured successfully")

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

    def ensure_index(self) -> bool:
        """Create the index if it doesn't exist.

        Returns:
            True if index was created, False if it already existed.
        """
        try:
            self.client.get_index(INDEX_NAME)
            logger.debug(f"Index '{INDEX_NAME}' already exists")
            return False
        except meilisearch.errors.MeilisearchApiError as e:
            if "index_not_found" not in str(e):
                raise
            self.create_index()
            return True

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
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 100,
        semantic_ratio: float = 0.0,
    ) -> list[str]:
        """Search Meilisearch for entities by label.

        Supports hybrid search combining keyword matching and semantic similarity.

        Args:
            query: Search query text
            entity_type: Optional type filter (e.g., 'Location', 'Politician')
            limit: Maximum number of results
            semantic_ratio: Balance between keyword (0.0) and semantic (1.0) search.
                           Default 0.0 uses pure keyword search for backward compatibility.
                           Use 0.5 for balanced hybrid search.

        Returns:
            List of document IDs (wikidata_ids) ordered by relevance
        """
        index = self.client.index(INDEX_NAME)
        search_params: dict = {"limit": limit}
        if entity_type:
            search_params["filter"] = f"types = '{entity_type}'"

        # Use hybrid search when semantic_ratio > 0
        if semantic_ratio > 0:
            search_params["hybrid"] = {
                "semanticRatio": semantic_ratio,
                "embedder": EMBEDDER_NAME,
            }

        results = index.search(query, search_params)
        return [hit["id"] for hit in results["hits"]]
