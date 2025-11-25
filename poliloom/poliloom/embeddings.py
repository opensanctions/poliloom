"""Embedding generation utilities for PoliLoom.

This module provides centralized embedding functionality using SentenceTransformers
for semantic similarity search and entity matching.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Global cache for the embedding model
_embedding_model = None


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
