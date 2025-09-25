"""Embedding generation utilities for PoliLoom.

This module provides centralized embedding functionality using SentenceTransformers
for semantic similarity search and entity matching.
"""

import logging
from typing import List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from poliloom.database import get_engine
from poliloom.models import Location, Position, Country

logger = logging.getLogger(__name__)

# Global cached embedding model
_embedding_model = None

T = TypeVar("T", Position, Location, Country)


def get_embedding_model():
    """Get or create the cached SentenceTransformer model."""
    import torch
    from sentence_transformers import SentenceTransformer

    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading SentenceTransformer model...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        _embedding_model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2", device=device
        )
        logger.info("SentenceTransformer model loaded and cached successfully")
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text string."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist()


def generate_embeddings_for_entities(
    model_class: Type[T],
    entity_name: str,
    batch_size: int = 1000,
    encode_batch_size: int = 2048,
    session: Optional[Session] = None,
) -> int:
    """Generate embeddings for all entities of a given type that are missing embeddings.

    Args:
        model_class: The SQLAlchemy model class (Position or Location)
        entity_name: Human-readable name for logging (e.g., "positions", "locations")
        batch_size: Number of entities to process in each database batch
        encode_batch_size: Number of texts to encode at once
        session: Optional database session (will create if not provided)

    Returns:
        Number of entities processed
    """
    model = get_embedding_model()
    should_close_session = session is None

    if session is None:
        session = Session(get_engine())

    try:
        # Get total count
        total_count = (
            session.query(model_class).filter(model_class.embedding.is_(None)).count()
        )

        if total_count == 0:
            logger.info(f"All {entity_name} already have embeddings")
            return 0

        logger.info(f"Found {total_count} {entity_name} without embeddings")
        processed = 0

        # Process entities in batches
        while True:
            # Query full ORM objects to use the name property
            batch = (
                session.query(model_class)
                .filter(model_class.embedding.is_(None))
                .limit(batch_size)
                .all()
            )

            if not batch:
                break

            # Use the name property from ORM objects
            names = [entity.name for entity in batch]

            # Generate embeddings (typed lists). Use encode_batch_size for both CPU/GPU
            embeddings = model.encode(
                names, convert_to_tensor=False, batch_size=encode_batch_size
            )

            # Update embeddings on the ORM objects
            for entity, embedding in zip(batch, embeddings):
                entity.embedding = embedding

            session.commit()

            processed += len(batch)
            logger.info(f"Processed {processed}/{total_count} {entity_name}")

        logger.info(f"Generated embeddings for {processed} {entity_name}")
        return processed

    finally:
        if should_close_session:
            session.close()


def generate_all_embeddings(
    batch_size: int = 1000, encode_batch_size: int = 2048
) -> None:
    """Generate embeddings for all positions and locations missing embeddings."""
    import torch

    # Use GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device for encoding: {device}")

    try:
        with Session(get_engine()) as session:
            for model_class, entity_name in [
                (Position, "positions"),
                (Location, "locations"),
                (Country, "countries"),
            ]:
                logger.info(f"Processing {entity_name}...")
                generate_embeddings_for_entities(
                    model_class=model_class,
                    entity_name=entity_name,
                    batch_size=batch_size,
                    encode_batch_size=encode_batch_size,
                    session=session,
                )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise
