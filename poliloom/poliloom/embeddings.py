"""Embedding generation utilities for PoliLoom.

This module provides centralized embedding functionality using SentenceTransformers
for semantic similarity search and entity matching.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from poliloom.database import get_engine
from poliloom.models import Position

logger = logging.getLogger(__name__)


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


def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple text strings in a batch.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embeddings (each embedding is a list of floats)
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_tensor=False)
    return [embedding.tolist() for embedding in embeddings]


def generate_embeddings_for_positions(
    batch_size: int = 1000,
    encode_batch_size: int = 2048,
    session: Optional[Session] = None,
) -> int:
    """Generate embeddings for all positions that are missing embeddings.

    Args:
        batch_size: Number of positions to process in each database batch
        encode_batch_size: Number of texts to encode at once
        session: Optional database session (will create if not provided)

    Returns:
        Number of positions processed
    """
    model = get_embedding_model()
    should_close_session = session is None

    if session is None:
        session = Session(get_engine())

    try:
        # Get total count
        total_count = (
            session.query(Position).filter(Position.embedding.is_(None)).count()
        )

        if total_count == 0:
            logger.info("All positions already have embeddings")
            return 0

        logger.info(f"Found {total_count} positions without embeddings")
        processed = 0

        # Process positions in batches
        while True:
            # Query full ORM objects to use the name property
            batch = (
                session.query(Position)
                .filter(Position.embedding.is_(None))
                .limit(batch_size)
                .all()
            )

            if not batch:
                break

            # Use the name property from ORM objects
            names = [position.name for position in batch]

            # Generate embeddings (typed lists). Use encode_batch_size for both CPU/GPU
            embeddings = model.encode(
                names, convert_to_tensor=False, batch_size=encode_batch_size
            )

            # Update embeddings on the ORM objects
            for position, embedding in zip(batch, embeddings):
                position.embedding = embedding

            session.commit()

            processed += len(batch)
            logger.info(f"Processed {processed}/{total_count} positions")

        logger.info(f"Generated embeddings for {processed} positions")
        return processed

    finally:
        if should_close_session:
            session.close()


def generate_all_embeddings(
    batch_size: int = 1000, encode_batch_size: int = 2048
) -> None:
    """Generate embeddings for all positions missing embeddings."""
    import torch

    # Use GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device for encoding: {device}")

    try:
        with Session(get_engine()) as session:
            logger.info("Processing positions...")
            generate_embeddings_for_positions(
                batch_size=batch_size,
                encode_batch_size=encode_batch_size,
                session=session,
            )

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise
