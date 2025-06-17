"""Vector similarity search backends for both PostgreSQL and SQLite."""

import os
import json
from abc import ABC, abstractmethod
from typing import List, Tuple, Any, Optional, Type
from sqlalchemy import text
from sqlalchemy.orm import Session


class VectorSearchBackend(ABC):
    """Abstract base class for vector search backends."""
    
    @abstractmethod
    def setup_vector_column(self, table_class: Type, column_name: str, dimensions: int):
        """Setup vector column for the table."""
        pass
    
    @abstractmethod
    def find_similar(self, session: Session, table_class: Type, vector_column: str, 
                    query_vector: List[float], top_k: int = 10, 
                    filters=None) -> List[Tuple[Any, float]]:
        """Find similar vectors and return (entity, similarity_score) pairs."""
        pass
    
    @abstractmethod
    def create_vector_index(self, session: Session, table_class: Type, vector_column: str):
        """Create index for vector similarity search."""
        pass
    
    @abstractmethod
    def supports_dynamic_embedding(self) -> bool:
        """Whether this backend supports dynamic embedding generation."""
        pass


class PostgresVectorBackend(VectorSearchBackend):
    """PostgreSQL backend using pgvector extension."""
    
    def setup_vector_column(self, table_class: Type, column_name: str, dimensions: int):
        """Add pgvector column to the model."""
        try:
            from pgvector.sqlalchemy import Vector
            setattr(table_class, column_name, Vector(dimensions))
        except ImportError:
            raise ImportError("pgvector package is required for PostgreSQL vector search. Install with: pip install pgvector")
    
    def find_similar(self, session: Session, table_class: Type, vector_column: str, 
                    query_vector: List[float], top_k: int = 10, 
                    filters=None) -> List[Tuple[Any, float]]:
        """Find similar entities using pgvector cosine similarity."""
        try:
            from pgvector.sqlalchemy import Vector
        except ImportError:
            raise ImportError("pgvector package is required for PostgreSQL vector search")
        
        # Build base query
        query = session.query(table_class)
        
        # Apply filters if provided
        if filters is not None:
            query = query.filter(filters)
        
        # Get the vector column
        vector_col = getattr(table_class, vector_column)
        
        # Filter out entities without embeddings
        query = query.filter(vector_col.isnot(None))
        
        # Order by cosine similarity (distance)
        query = query.order_by(vector_col.cosine_distance(query_vector))
        
        # Limit results
        results = query.limit(top_k).all()
        
        # Calculate similarity scores (1 - distance)
        similarities = []
        for item in results:
            # Get the distance for this specific item
            distance_query = session.query(
                vector_col.cosine_distance(query_vector)
            ).filter(table_class.id == item.id)
            
            distance = distance_query.scalar()
            similarity = 1 - distance if distance is not None else 0.0
            similarities.append((item, float(similarity)))
        
        return similarities
    
    def create_vector_index(self, session: Session, table_class: Type, vector_column: str):
        """Create IVFFlat index for vector similarity search."""
        table_name = table_class.__tablename__
        index_name = f"idx_{table_name}_{vector_column}_cosine"
        
        # Create index if it doesn't exist
        session.execute(text(f"""
            CREATE INDEX IF NOT EXISTS {index_name} 
            ON {table_name} 
            USING ivfflat ({vector_column} vector_cosine_ops)
            WITH (lists = 100)
        """))
        session.commit()
    
    def supports_dynamic_embedding(self) -> bool:
        """PostgreSQL supports dynamic embedding with proper indexing."""
        return True


class SQLiteVectorBackend(VectorSearchBackend):
    """SQLite backend using in-memory vector search with scikit-learn."""
    
    def __init__(self):
        self._vector_cache = {}
        self._cache_loaded = {}
    
    def setup_vector_column(self, table_class: Type, column_name: str, dimensions: int):
        """Add JSON column for SQLite vector storage."""
        from sqlalchemy import JSON
        setattr(table_class, column_name, JSON)
    
    def find_similar(self, session: Session, table_class: Type, vector_column: str, 
                    query_vector: List[float], top_k: int = 10, 
                    filters=None) -> List[Tuple[Any, float]]:
        """Find similar entities using in-memory cosine similarity."""
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            raise ImportError("numpy and scikit-learn are required for SQLite vector search. Install with: pip install numpy scikit-learn")
        
        cache_key = f"{table_class.__tablename__}_{vector_column}"
        
        # Load vectors into cache if not already loaded
        if cache_key not in self._cache_loaded:
            self._load_vectors_to_cache(session, table_class, vector_column, cache_key)
        
        if cache_key not in self._vector_cache:
            return []
        
        vectors, items = self._vector_cache[cache_key]
        
        if len(vectors) == 0:
            return []
        
        # Calculate similarities
        query_vector_2d = np.array([query_vector])
        similarities = cosine_similarity(query_vector_2d, vectors)[0]
        
        # Apply filters if any
        if filters is not None:
            # Get IDs that match filters
            filtered_query = session.query(table_class.id).filter(filters)
            valid_ids = {row.id for row in filtered_query}
            
            # Filter results
            filtered_results = []
            for item, sim in zip(items, similarities):
                if item.id in valid_ids:
                    filtered_results.append((item, float(sim)))
            
            # Sort by similarity and return top-k
            filtered_results.sort(key=lambda x: x[1], reverse=True)
            return filtered_results[:top_k]
        
        # Get top-k results without filters
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [(items[i], float(similarities[i])) for i in top_indices]
    
    def _load_vectors_to_cache(self, session: Session, table_class: Type, 
                              vector_column: str, cache_key: str):
        """Load all vectors for a table into memory cache."""
        import numpy as np
        
        # Query all entities with vectors
        results = session.query(table_class).filter(
            getattr(table_class, vector_column).isnot(None)
        ).all()
        
        vectors = []
        items = []
        
        for item in results:
            vector_data = getattr(item, vector_column)
            if vector_data:
                # Handle both string and direct JSON data
                if isinstance(vector_data, str):
                    try:
                        vector = json.loads(vector_data)
                    except json.JSONDecodeError:
                        continue
                else:
                    vector = vector_data
                
                # Ensure vector is a list of numbers
                if isinstance(vector, list) and all(isinstance(x, (int, float)) for x in vector):
                    vectors.append(vector)
                    items.append(item)
        
        if vectors:
            self._vector_cache[cache_key] = (
                np.array(vectors, dtype=np.float32), 
                items
            )
        
        self._cache_loaded[cache_key] = True
    
    def create_vector_index(self, session: Session, table_class: Type, vector_column: str):
        """No-op for SQLite as we use in-memory search."""
        pass
    
    def supports_dynamic_embedding(self) -> bool:
        """SQLite requires cache reload for new embeddings."""
        return False
    
    def invalidate_cache(self, table_class: Type, vector_column: str):
        """Invalidate cache to force reload on next search."""
        cache_key = f"{table_class.__tablename__}_{vector_column}"
        if cache_key in self._cache_loaded:
            del self._cache_loaded[cache_key]
        if cache_key in self._vector_cache:
            del self._vector_cache[cache_key]


def get_vector_backend() -> VectorSearchBackend:
    """Factory function to get the appropriate vector backend based on database URL."""
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./poliloom.db')
    
    if db_url.startswith('postgresql'):
        return PostgresVectorBackend()
    else:
        return SQLiteVectorBackend()


def setup_vector_extensions(engine):
    """Setup required database extensions for vector search."""
    db_url = str(engine.url)
    
    if db_url.startswith('postgresql'):
        # Enable pgvector extension for PostgreSQL
        with engine.connect() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            conn.commit()