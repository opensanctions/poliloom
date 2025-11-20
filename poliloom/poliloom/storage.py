"""Storage abstraction layer for handling both local and Google Cloud Storage."""

import logging
import os
import shutil
import tempfile
import httpx
import indexed_bzip2 as ibz2
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator, Tuple
from urllib.parse import urlparse
from google.cloud import storage
from google.auth import default

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists."""
        pass

    @abstractmethod
    def get_size(self, path: str) -> int:
        """Get the size of a file in bytes."""
        pass

    @abstractmethod
    def open(self, path: str, mode: str = "rb") -> BinaryIO:
        """Open a file for reading or writing."""
        pass

    @abstractmethod
    def read_range(self, path: str, start: int, end: int) -> bytes:
        """Read a specific byte range from a file."""
        pass

    @abstractmethod
    def download(self, source: str, destination: str) -> None:
        """Download a file from source to destination."""
        pass

    @abstractmethod
    def stream_lines(self, path: str) -> Iterator[str]:
        """Stream lines from a file."""
        pass

    @abstractmethod
    def stream_lines_range(self, path: str, start: int, end: int) -> Iterator[bytes]:
        """Stream lines from a specific byte range of a file."""
        pass

    @abstractmethod
    def extract_bz2_to(
        self, source_path: str, dest_backend: "StorageBackend", dest_path: str
    ) -> None:
        """Extract a bz2 file from this backend to another backend."""
        pass


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""

    def exists(self, path: str) -> bool:
        """Check if a file exists locally."""
        return os.path.exists(path)

    def get_size(self, path: str) -> int:
        """Get the size of a local file in bytes."""
        return os.path.getsize(path)

    def open(self, path: str, mode: str = "rb") -> BinaryIO:
        """Open a local file."""
        # Create parent directories if writing
        if "w" in mode or "a" in mode:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        return open(path, mode)

    def read_range(self, path: str, start: int, end: int) -> bytes:
        """Read a specific byte range from a local file."""
        with open(path, "rb") as f:
            f.seek(start)
            return f.read(end - start)

    def download(self, source: str, destination: str) -> None:
        """Copy a local file to another location."""
        shutil.copy2(source, destination)

    def stream_lines(self, path: str) -> Iterator[str]:
        """Stream lines from a local file."""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line

    def stream_lines_range(self, path: str, start: int, end: int) -> Iterator[bytes]:
        """Stream lines from a specific byte range of a local file."""
        with open(path, "rb") as f:
            f.seek(start)
            current_pos = start

            while current_pos < end:
                line = f.readline()
                if not line:
                    break

                current_pos = f.tell()
                yield line

    def extract_bz2_to(
        self, source_path: str, dest_backend: "StorageBackend", dest_path: str
    ) -> None:
        """Extract a local bz2 file to another backend using indexed_bzip2 for parallel processing."""
        logger.info(f"Parallel extraction from {source_path} to {dest_path}...")

        # Ensure destination directory exists for local paths
        if not dest_path.startswith("gs://"):
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        with ibz2.open(source_path, parallelization=os.cpu_count()) as source_file:
            with dest_backend.open(dest_path, "wb") as dest_file:
                # Stream in larger chunks for better performance
                chunk_size = 256 * 1024 * 1024  # 256MB chunks
                while True:
                    chunk = source_file.read(chunk_size)
                    if not chunk:
                        break
                    dest_file.write(chunk)

        logger.info(f"✅ Successfully extracted {source_path} to {dest_path}")


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self):
        """Initialize GCS storage backend."""
        try:
            # Use Application Default Credentials from environment
            credentials, project = default()

            self.client = storage.Client(credentials=credentials, project=project)
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS support. "
                "Install with: pip install google-cloud-storage"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GCS client: {e}")

    def _parse_gcs_path(self, path: str) -> Tuple[str, str]:
        """Parse a GCS path into bucket and blob name.

        Args:
            path: GCS path in format gs://bucket/path/to/file

        Returns:
            Tuple of (bucket_name, blob_name)
        """
        if not path.startswith("gs://"):
            raise ValueError(f"Invalid GCS path: {path}. Must start with gs://")

        parsed = urlparse(path)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")

        return bucket_name, blob_name

    def exists(self, path: str) -> bool:
        """Check if a file exists in GCS."""
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.exists()

    def get_size(self, path: str) -> int:
        """Get the size of a GCS file in bytes."""
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.reload()
        return blob.size or 0

    def open(self, path: str, mode: str = "rb") -> BinaryIO:
        """Open a GCS file for streaming."""
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Use native blob.open() which handles streaming uploads natively
        return blob.open(mode)

    def read_range(self, path: str, start: int, end: int) -> bytes:
        """Read a specific byte range from a GCS file."""
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Download the specific byte range
        return blob.download_as_bytes(start=start, end=end)

    def download(self, source: str, destination: str) -> None:
        """Download a file from GCS to local or another GCS location."""
        if destination.startswith("gs://"):
            # GCS to GCS copy
            source_bucket, source_blob = self._parse_gcs_path(source)
            dest_bucket, dest_blob = self._parse_gcs_path(destination)

            source_bucket_obj = self.client.bucket(source_bucket)
            source_blob_obj = source_bucket_obj.blob(source_blob)

            dest_bucket_obj = self.client.bucket(dest_bucket)
            dest_blob_obj = dest_bucket_obj.blob(dest_blob)

            # Copy blob
            dest_blob_obj.upload_from_string(
                source_blob_obj.download_as_bytes(),
                content_type=source_blob_obj.content_type,
            )
        else:
            # GCS to local
            bucket_name, blob_name = self._parse_gcs_path(source)
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.download_to_filename(destination)

    def stream_lines(self, path: str) -> Iterator[str]:
        """Stream lines from a GCS file."""
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Stream the file content
        with blob.open("r") as f:
            for line in f:
                yield line

    def stream_lines_range(self, path: str, start: int, end: int) -> Iterator[bytes]:
        """Stream lines from a specific byte range of a GCS file."""
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        with blob.open("rb") as f:
            f.seek(start)
            current_pos = start

            while current_pos < end:
                line = f.readline()
                if not line:
                    break

                current_pos = f.tell()
                yield line

    def extract_bz2_to(
        self, source_path: str, dest_backend: "StorageBackend", dest_path: str
    ) -> None:
        """Extract a GCS bz2 file to another backend using indexed_bzip2 for parallel processing.

        Streams compressed file to local disk first to enable seekable access for parallel decompression.
        """
        logger.info(f"Parallel extraction from {source_path} to {dest_path}...")

        # Ensure destination directory exists for local paths
        if not dest_path.startswith("gs://"):
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Stream GCS file to local temporary file for seekable access
        with tempfile.NamedTemporaryFile(delete=True) as temp_file:
            logger.info(
                f"Streaming {source_path} to local temp file for parallel processing..."
            )

            # Download compressed file to local disk
            with self.open(source_path, "rb") as source_file:
                shutil.copyfileobj(
                    source_file, temp_file, length=64 * 1024 * 1024
                )  # 64MB chunks

            temp_file.flush()
            logger.info("Local temp file ready, starting parallel decompression...")

            # Now use indexed_bzip2 on seekable local file for parallel processing
            with ibz2.open(temp_file.name, parallelization=os.cpu_count()) as bz2_file:
                with dest_backend.open(dest_path, "wb") as dest_file:
                    # Stream decompressed data in large chunks
                    chunk_size = 256 * 1024 * 1024  # 256MB chunks
                    while True:
                        chunk = bz2_file.read(chunk_size)
                        if not chunk:
                            break
                        dest_file.write(chunk)

        logger.info(f"✅ Successfully extracted {source_path} to {dest_path}")


class StorageFactory:
    """Factory for creating storage backends based on path format."""

    _local_storage = None
    _gcs_storage = None

    @classmethod
    def get_backend(cls, path: str) -> StorageBackend:
        """Get the appropriate storage backend for a given path.

        Args:
            path: File path (local or gs://)

        Returns:
            StorageBackend instance
        """
        if path.startswith("gs://"):
            if cls._gcs_storage is None:
                cls._gcs_storage = GCSStorage()
            return cls._gcs_storage
        else:
            if cls._local_storage is None:
                cls._local_storage = LocalStorage()
            return cls._local_storage

    @classmethod
    def is_gcs_path(cls, path: str) -> bool:
        """Check if a path is a GCS path."""
        return path.startswith("gs://")

    @classmethod
    def download_from_url(cls, url: str, destination: str) -> None:
        """Download a file from a URL (HTTP/HTTPS) to a destination.

        Args:
            url: Source URL
            destination: Destination path (local or gs://)
        """
        backend = cls.get_backend(destination)

        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()

            with backend.open(destination, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)
