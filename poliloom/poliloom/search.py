"""Meilisearch functions for entity search.

Thin wrappers around Meilisearch for indexing and searching entities.
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
    types: list[str]  # Entity types (e.g., ['Location', 'Country'])
    labels: list[str]


load_dotenv()

logger = logging.getLogger(__name__)

_client: Optional[meilisearch.Client] = None


def get_client() -> meilisearch.Client:
    """Get the shared Meilisearch client, creating it on first use."""
    global _client
    if _client is None:
        url = os.getenv("MEILI_URL", "http://localhost:7700")
        _client = meilisearch.Client(url, os.getenv("MEILI_MASTER_KEY"))
    return _client


def create_index() -> None:
    """Create the entities index with proper settings."""
    logger.info(f"Creating index '{INDEX_NAME}'")
    client = get_client()
    task = client.create_index(INDEX_NAME, {"primaryKey": "id"})
    client.wait_for_task(task.task_uid)

    # Configure index settings
    index = client.index(INDEX_NAME)
    task = index.update_settings(
        {
            "searchableAttributes": ["labels"],
            "filterableAttributes": ["types"],
            "displayedAttributes": ["id", "types", "labels"],
        }
    )
    client.wait_for_task(task.task_uid)


def delete_index() -> None:
    """Delete the entities index if it exists."""
    try:
        logger.info(f"Deleting index '{INDEX_NAME}'")
        client = get_client()
        task = client.delete_index(INDEX_NAME)
        client.wait_for_task(task.task_uid)
    except meilisearch.errors.MeilisearchApiError as e:
        if "index_not_found" not in str(e):
            raise
        logger.debug(f"Index '{INDEX_NAME}' does not exist, nothing to delete")


def ensure_index() -> bool:
    """Create the index if it doesn't exist.

    Returns:
        True if index was created, False if it already existed.
    """
    try:
        get_client().get_index(INDEX_NAME)
        logger.debug(f"Index '{INDEX_NAME}' already exists")
        return False
    except meilisearch.errors.MeilisearchApiError as e:
        if "index_not_found" not in str(e):
            raise
        create_index()
        return True


def index_documents(documents: list[SearchDocument]) -> Optional[int]:
    """Index documents to Meilisearch.

    Returns immediately without waiting, allowing Meilisearch's
    auto-batching to combine consecutive requests for faster indexing.

    Args:
        documents: List of SearchDocument dicts with 'id', 'types', and 'labels'

    Returns:
        Task UID for tracking, or None if no documents
    """
    if not documents:
        return None

    index = get_client().index(INDEX_NAME)
    task = index.add_documents(documents)
    return task.task_uid


def delete_documents(document_ids: list[str], batch_size: int = 10000) -> int:
    """Delete documents from Meilisearch by ID.

    Sends deletes in batches without waiting, matching the fire-and-forget
    pattern used by index_documents and letting Meilisearch auto-batch.

    Args:
        document_ids: List of document IDs (wikidata_ids) to delete
        batch_size: Number of IDs per batch (default 10000)

    Returns:
        Number of documents requested for deletion
    """
    if not document_ids:
        return 0

    index = get_client().index(INDEX_NAME)
    for i in range(0, len(document_ids), batch_size):
        batch = document_ids[i : i + batch_size]
        index.delete_documents(batch)

    return len(document_ids)


def search(
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 100,
) -> list[str]:
    """Search Meilisearch for entities by label.

    Args:
        query: Search query text
        entity_type: Optional type filter (e.g., 'Location', 'Politician')
        limit: Maximum number of results

    Returns:
        List of document IDs (wikidata_ids) ordered by relevance
    """
    index = get_client().index(INDEX_NAME)
    search_params: dict = {"limit": limit}
    if entity_type:
        search_params["filter"] = f"types = '{entity_type}'"

    results = index.search(query, search_params)
    return [hit["id"] for hit in results["hits"]]
