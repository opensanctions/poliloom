"""Worker process management for multiprocessing dump operations."""

import json
import logging
import mmap
import os
import tempfile
from typing import Set, Tuple

logger = logging.getLogger(__name__)

# Global variable to store worker-specific database session
_worker_session = None

# Global variables for memory-mapped files in worker processes
_shared_position_descendants = None
_shared_location_descendants = None


def _init_worker_db():
    """Initialize database session for worker process."""
    global _worker_session
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from dotenv import load_dotenv

    load_dotenv()
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/poliloom"
    )

    # Create a separate engine for this worker process
    worker_engine = create_engine(
        DATABASE_URL,
        pool_size=5,  # Smaller pool per worker
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

    # Create sessionmaker for this worker
    WorkerSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=worker_engine
    )
    _worker_session = WorkerSessionLocal

    logger.info(f"Initialized database session for worker process {os.getpid()}")


def get_worker_session():
    """Get the worker-specific database session."""
    global _worker_session
    if _worker_session is None:
        _init_worker_db()
    return _worker_session()


def create_shared_memory_from_set(data_set: Set[str], name: str) -> str:
    """Create memory-mapped file from a set of strings."""
    # Convert set to JSON string
    json_data = json.dumps(sorted(list(data_set)))
    json_bytes = json_data.encode("utf-8")

    # Create temporary file for memory mapping
    temp_dir = tempfile.gettempdir()
    filename = os.path.join(temp_dir, f"{name}.json")

    with open(filename, "wb") as f:
        f.write(json_bytes)

    return filename


def load_set_from_shared_memory(filename: str) -> Set[str]:
    """Load a set from memory-mapped file."""
    with open(filename, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
            # Read and decode JSON data
            json_data = mmapped_file[:].decode("utf-8")
            data_list = json.loads(json_data)

            # Convert back to set
            return set(data_list)


def init_worker_hierarchy(position_filename: str, location_filename: str):
    """Initialize hierarchy data in worker process from memory-mapped files."""
    global _shared_position_descendants, _shared_location_descendants

    try:
        _shared_position_descendants = load_set_from_shared_memory(position_filename)
        _shared_location_descendants = load_set_from_shared_memory(location_filename)

        logger.info(
            f"Worker {os.getpid()}: Loaded {len(_shared_position_descendants)} position descendants and {len(_shared_location_descendants)} location descendants from memory-mapped files"
        )

    except Exception as e:
        logger.error(
            f"Worker {os.getpid()}: Failed to load hierarchy from memory-mapped files: {e}"
        )
        raise


def get_hierarchy_sets() -> Tuple[Set[str], Set[str]]:
    """Get hierarchy sets for current worker."""
    global _shared_position_descendants, _shared_location_descendants

    if _shared_position_descendants is None or _shared_location_descendants is None:
        raise RuntimeError("Hierarchy data not initialized in worker process")

    return _shared_position_descendants, _shared_location_descendants


def init_worker_with_db():
    """Initialize worker process with database session only."""
    _init_worker_db()


def init_worker_with_hierarchy(position_filename: str, location_filename: str):
    """Initialize worker process with both database and hierarchy data."""
    _init_worker_db()
    init_worker_hierarchy(position_filename, location_filename)
