"""File reading utilities for Wikidata dump processing."""

import orjson
import logging
import multiprocessing as mp
from typing import Dict, Any, Iterator, List, Tuple, Optional

from .storage import StorageFactory
from .wikidata_entity import WikidataEntity

logger = logging.getLogger(__name__)


def calculate_file_chunks(
    dump_file_path: str, num_workers: Optional[int] = None
) -> List[Tuple[int, int]]:
    """
    Calculate byte ranges for each worker to process independently.

    Splits the file into roughly equal chunks while respecting JSON line boundaries.
    For very large files (1TB), this ensures each worker gets a substantial chunk.

    Args:
        dump_file_path: Path to dump file (local or gs://)
        num_workers: Number of parallel workers (default: CPU count)

    Returns:
        List of (start_byte, end_byte) tuples
    """
    if num_workers is None:
        num_workers = mp.cpu_count()

    # Get the appropriate storage backend
    backend = StorageFactory.get_backend(dump_file_path)
    file_size = backend.get_size(dump_file_path)

    # For small files, don't create more chunks than needed
    if file_size < num_workers * 1024 * 1024:  # Less than 1MB per worker
        num_workers = max(1, file_size // (1024 * 1024))

    chunk_size = file_size // num_workers
    chunks = []

    current_pos = 0

    for i in range(num_workers):
        start_pos = current_pos

        if i == num_workers - 1:
            # Last chunk gets everything remaining
            end_pos = file_size
        else:
            # Move to approximate chunk boundary
            target_pos = start_pos + chunk_size

            # Find next newline to respect line boundaries
            # For GCS, we read a small buffer to find the newline
            if target_pos < file_size:
                # Read up to 1KB to find the next newline
                buffer_size = min(1024, file_size - target_pos)
                buffer = backend.read_range(
                    dump_file_path, target_pos, target_pos + buffer_size
                )

                # Find newline in buffer
                newline_pos = buffer.find(b"\n")
                if newline_pos != -1:
                    target_pos += newline_pos + 1
                else:
                    # If no newline in buffer, just use the target position
                    # This is rare for JSON lines format
                    pass

            end_pos = target_pos

        if start_pos < end_pos:
            chunks.append((start_pos, end_pos))

        current_pos = end_pos

        if current_pos >= file_size:
            break

    return chunks


def _process_dump_line(line: bytes) -> Optional[Dict[str, Any]]:
    """
    Process a single line from the dump file.

    Args:
        line: Raw line bytes from the dump file

    Returns:
        Parsed entity dictionary or None if line should be skipped
    """
    line = line.strip()

    # Skip array brackets and empty lines
    if line in [b"[", b"]"] or not line:
        return None

    # Remove trailing comma if present
    if line.endswith(b","):
        line = line[:-1]

    try:
        return orjson.loads(line)
    except (orjson.JSONDecodeError, UnicodeDecodeError):
        # Skip malformed lines
        return None


def read_chunk_entities(
    dump_file_path: str, start_byte: int, end_byte: int
) -> Iterator[WikidataEntity]:
    """
    Read entities from a specific byte range of the dump file.

    Args:
        dump_file_path: Path to the JSON dump file (local or gs://)
        start_byte: Starting byte position
        end_byte: Ending byte position

    Yields:
        WikidataEntity instances
    """
    # Get the appropriate storage backend
    backend = StorageFactory.get_backend(dump_file_path)

    # Stream lines from the byte range
    for line in backend.stream_lines_range(dump_file_path, start_byte, end_byte):
        entity_dict = _process_dump_line(line)
        if entity_dict is not None:
            yield WikidataEntity.from_raw(entity_dict)
