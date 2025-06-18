"""Embedding functionality for the PoliLoom project."""
import logging
import os
from typing import List

# Global cached embedding model
_embedding_model = None


def get_embedding_model():
    """Get or create the cached SentenceTransformer model."""
    global _embedding_model
    if _embedding_model is None:
        logger = logging.getLogger(__name__)
        pid = os.getpid()
        logger.info(f"Loading SentenceTransformer model in process {pid} (should only happen once per process)...")
        
        # Suppress sentence-transformers logging during model loading
        st_logger = logging.getLogger('sentence_transformers')
        original_level = st_logger.level
        st_logger.setLevel(logging.WARNING)
        
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        finally:
            # Restore original logging level
            st_logger.setLevel(original_level)
        
        logger.info(f"SentenceTransformer model loaded and cached successfully in process {pid}")
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text string."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)


def generate_batch_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    if not texts:
        return []
    
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_tensor=False)
    
    # Convert to list format
    return [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]