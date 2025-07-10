"""Embedding functionality for the PoliLoom project."""

import logging
import os
from typing import List, Type, TypeVar, Any
import torch
from sqlalchemy.orm import Session

# Global cached embedding model
_embedding_model = None

# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType")


def get_embedding_model():
    """Get or create the cached SentenceTransformer model."""
    global _embedding_model
    if _embedding_model is None:
        logger = logging.getLogger(__name__)
        pid = os.getpid()
        logger.info(
            f"Loading SentenceTransformer model in process {pid} (should only happen once per process)..."
        )

        # Suppress sentence-transformers logging during model loading
        st_logger = logging.getLogger("sentence_transformers")
        original_level = st_logger.level
        st_logger.setLevel(logging.WARNING)

        try:
            from sentence_transformers import SentenceTransformer

            # Use GPU if available
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device}")

            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        finally:
            # Restore original logging level
            st_logger.setLevel(original_level)

        logger.info(
            f"SentenceTransformer model loaded and cached successfully in process {pid}"
        )
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text string."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)


def generate_embeddings(texts: List[str], batch_size: int = 2048) -> List[List[float]]:
    """Generate embeddings for multiple texts with configurable batch size."""
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_tensor=False, batch_size=batch_size)

    # Convert to list format
    return [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings]


def _noop_callback(msg: str) -> None:
    """No-op callback function when no progress callback is provided."""
    pass


def generate_embeddings_for_entities(
    session: Session,
    model_class: Type[ModelType],
    entity_name: str,
    batch_size: int = 100000,
    progress_callback: Any = None,
) -> int:
    """
    Generic function to generate embeddings for entities that don't have embeddings yet.

    Args:
        session: SQLAlchemy session
        model_class: The SQLAlchemy model class (Position, Location, etc.)
        entity_name: Name of the entity type for progress messages (e.g., "positions", "locations")
        batch_size: Number of entities to process in each batch
        progress_callback: Optional callback function for progress updates (e.g., click.echo)

    Returns:
        Number of entities processed
    """
    if progress_callback is None:
        progress_callback = _noop_callback

    # Get total count of entities without embeddings
    total_count = (
        session.query(model_class).filter(model_class.embedding.is_(None)).count()
    )

    if total_count == 0:
        progress_callback(f"✅ All {entity_name} already have embeddings")
        return 0

    progress_callback(f"Found {total_count} {entity_name} without embeddings")
    progress_callback(f"Processing in batches of {batch_size}")

    processed_count = 0

    while processed_count < total_count:
        # Load batch of entities - always get the first batch of entities without embeddings
        # since we're updating them as we go
        batch_entities = (
            session.query(model_class)
            .filter(model_class.embedding.is_(None))
            .limit(batch_size)
            .all()
        )

        if not batch_entities:
            break

        # Extract names for this batch
        names = [entity.name for entity in batch_entities]

        # Generate embeddings for this batch
        embeddings = generate_embeddings(names)

        # Update entities with embeddings
        for entity, embedding in zip(batch_entities, embeddings):
            entity.embedding = embedding

        # Commit this batch
        session.commit()

        # Update progress
        batch_size_actual = len(batch_entities)
        processed_count += batch_size_actual
        progress_callback(f"Processed {processed_count}/{total_count} {entity_name}")

    progress_callback(
        f"✅ Successfully generated embeddings for {processed_count} {entity_name}"
    )

    return processed_count
