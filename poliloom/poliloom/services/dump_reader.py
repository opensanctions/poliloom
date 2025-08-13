"""File reading utilities for Wikidata dump processing."""

import json
import logging
from typing import Dict, Any, Iterator, List, Tuple

from .storage import StorageFactory

logger = logging.getLogger(__name__)


class DumpReader:
    """Handles reading and chunking of Wikidata dump files from local or GCS."""

    def __init__(self):
        """Initialize DumpReader.

        GCS authentication uses environment variables:
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
        - GOOGLE_CLOUD_PROJECT: GCS project ID (optional)
        """
        pass

    def calculate_file_chunks(
        self, dump_file_path: str, num_workers: int
    ) -> List[Tuple[int, int]]:
        """
        Calculate byte ranges for each worker to process independently.

        Splits the file into roughly equal chunks while respecting JSON line boundaries.
        For very large files (1TB), this ensures each worker gets a substantial chunk.

        Args:
            dump_file_path: Path to dump file (local or gs://)
            num_workers: Number of parallel workers

        Returns:
            List of (start_byte, end_byte) tuples
        """
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

    def stream_dump_entities(self, dump_file_path: str) -> Iterator[Dict[str, Any]]:
        """
        Stream entities from a Wikidata JSON dump file.

        The dump format has one JSON object per line, with a trailing comma.
        First line is '[', last line is ']'.

        Args:
            dump_file_path: Path to the JSON dump file (local or gs://)

        Yields:
            Parsed entity dictionaries
        """
        # Get the appropriate storage backend
        backend = StorageFactory.get_backend(dump_file_path)

        for line in backend.stream_lines(dump_file_path):
            line = line.strip()

            # Skip array brackets
            if line in ["[", "]"]:
                continue

            # Remove trailing comma if present
            if line.endswith(","):
                line = line[:-1]

            # Skip empty lines
            if not line:
                continue

            try:
                entity = json.loads(line)
                yield entity
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON line: {e}")
                continue

    def read_chunk_entities(
        self, dump_file_path: str, start_byte: int, end_byte: int
    ) -> Iterator[Dict[str, Any]]:
        """
        Read entities from a specific byte range of the dump file.

        Args:
            dump_file_path: Path to the JSON dump file (local or gs://)
            start_byte: Starting byte position
            end_byte: Ending byte position

        Yields:
            Parsed entity dictionaries
        """
        # Get the appropriate storage backend
        backend = StorageFactory.get_backend(dump_file_path)

        # For GCS, we need to handle this differently
        if StorageFactory.is_gcs_path(dump_file_path):
            # Read the entire chunk at once for GCS
            # This is more efficient than many small reads
            chunk_data = backend.read_range(dump_file_path, start_byte, end_byte)

            # Process lines from the chunk
            lines = chunk_data.split(b"\n")
            for line in lines:
                line = line.strip()

                # Skip array brackets and empty lines
                if line in [b"[", b"]"] or not line:
                    continue

                # Remove trailing comma if present
                if line.endswith(b","):
                    line = line[:-1]

                try:
                    entity = json.loads(line.decode("utf-8"))
                    yield entity
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Skip malformed lines
                    continue
        else:
            # For local files, use the existing approach
            with open(dump_file_path, "rb") as f:
                f.seek(start_byte)
                current_pos = start_byte

                while current_pos < end_byte:
                    line = f.readline()
                    if not line:
                        break

                    current_pos = f.tell()

                    # Skip array brackets and empty lines
                    line = line.strip()
                    if line in [b"[", b"]"] or not line:
                        continue

                    # Remove trailing comma if present
                    if line.endswith(b","):
                        line = line[:-1]

                    try:
                        entity = json.loads(line.decode("utf-8"))
                        yield entity
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Skip malformed lines
                        continue
