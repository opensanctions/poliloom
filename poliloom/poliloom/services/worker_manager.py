"""Worker process management for multiprocessing dump operations."""

import logging
import os
from typing import Set, Tuple, Dict

logger = logging.getLogger(__name__)

# Global variable to store worker-specific database session
_worker_session = None

# Global variables for hierarchy data in worker processes
_shared_position_descendants = None
_shared_location_descendants = None
_shared_class_lookup = None


def _init_worker_db():
    """Initialize database session for worker process using centralized database logic."""
    global _worker_session
    from sqlalchemy.orm import sessionmaker
    from ..database import get_engine

    # Use the centralized engine from database.py but create a separate sessionmaker for workers
    # This ensures consistent connection logic across the application
    worker_engine = get_engine()

    # Create sessionmaker for this worker with appropriate settings for multiprocessing
    WorkerSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=worker_engine
    )
    _worker_session = WorkerSessionLocal

    logger.info(f"Initialized database session for worker process {os.getpid()}")


def _load_class_lookup() -> Dict[str, str]:
    """Load WikidataClass lookup mapping from database.

    Returns:
        Dictionary mapping wikidata_id to UUID for class lookups
    """
    session = get_worker_session()
    try:
        from ..models import WikidataClass

        class_lookup = {}
        classes = session.query(WikidataClass).all()
        for cls in classes:
            if cls.wikidata_id:
                class_lookup[cls.wikidata_id] = str(cls.id)

        return class_lookup
    except Exception as e:
        logger.error(f"Failed to load class lookup: {e}")
        return {}
    finally:
        session.close()


def get_worker_session():
    """Get the worker-specific database session."""
    global _worker_session
    if _worker_session is None:
        _init_worker_db()
    return _worker_session()


def init_worker_hierarchy(
    position_descendants: Set[str], location_descendants: Set[str]
):
    """Initialize hierarchy data in worker process."""
    global \
        _shared_position_descendants, \
        _shared_location_descendants, \
        _shared_class_lookup

    try:
        _shared_position_descendants = position_descendants or set()
        _shared_location_descendants = location_descendants or set()

        # Load class lookup mapping from database
        _shared_class_lookup = _load_class_lookup()

        logger.info(
            f"Worker {os.getpid()}: Loaded {len(_shared_position_descendants)} position descendants and {len(_shared_location_descendants)} location descendants"
        )
        logger.info(
            f"Worker {os.getpid()}: Loaded {len(_shared_class_lookup)} class mappings"
        )

    except Exception as e:
        logger.error(f"Worker {os.getpid()}: Failed to initialize hierarchy data: {e}")
        raise


def get_hierarchy_sets() -> Tuple[Set[str], Set[str]]:
    """Get hierarchy sets for current worker."""
    global _shared_position_descendants, _shared_location_descendants

    if _shared_position_descendants is None or _shared_location_descendants is None:
        # Return empty sets if not initialized
        return set(), set()

    return _shared_position_descendants, _shared_location_descendants


def get_class_lookup():
    """Get class lookup mapping for current worker."""
    global _shared_class_lookup
    return _shared_class_lookup or {}


def init_worker_with_db():
    """Initialize worker process with database session only."""
    _init_worker_db()


def init_worker_with_hierarchy(
    position_descendants: Set[str], location_descendants: Set[str]
):
    """Initialize worker process with both database and hierarchy data."""
    _init_worker_db()
    init_worker_hierarchy(position_descendants, location_descendants)
