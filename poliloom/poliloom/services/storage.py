"""Storage abstraction layer for handling both local and Google Cloud Storage."""

import io
import logging
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator, Tuple
from urllib.parse import urlparse

import httpx

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


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self):
        """Initialize GCS storage backend.

        Uses environment variables for authentication:
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON file
        """
        try:
            from google.cloud import storage
            from google.auth import default

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
        """Open a GCS file for streaming.

        Note: Write mode creates a temporary file that uploads on close.
        """
        bucket_name, blob_name = self._parse_gcs_path(path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if "r" in mode:
            # For reading, return a file-like object
            return blob.open(mode)
        elif "w" in mode:
            # For writing, use streaming uploads via resumable upload
            class GCSWriteStream:
                def __init__(self, blob):
                    self.blob = blob
                    self._buffer = io.BytesIO()
                    self._chunk_size = 100 * 1024 * 1024  # 100MB chunks
                    self._closed = False

                def write(self, data):
                    if self._closed:
                        raise ValueError("I/O operation on closed file")
                    return self._buffer.write(data)

                def close(self):
                    if not self._closed:
                        self._buffer.seek(0)
                        # Use resumable upload for efficient streaming
                        self.blob.chunk_size = self._chunk_size
                        self.blob.upload_from_file(self._buffer, rewind=True)
                        self._buffer.close()
                        self._closed = True

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.close()

            return GCSWriteStream(blob)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

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
        # First download to a temporary local file if destination is GCS
        if cls.is_gcs_path(destination):
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name

            # Download to temp file first
            cls._download_http_to_file(url, tmp_path)

            # Then upload to GCS
            backend = cls.get_backend(destination)
            backend.download(tmp_path, destination)

            # Clean up temp file
            os.unlink(tmp_path)
        else:
            # Direct download to local file
            cls._download_http_to_file(url, destination)

    @staticmethod
    def _download_http_to_file(url: str, destination: str) -> None:
        """Download from HTTP/HTTPS to a local file."""
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()

            with open(destination, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)

    @classmethod
    def extract_bz2(
        cls,
        source: str,
        destination: str,
        use_parallel: bool = True,
    ) -> None:
        """Extract a bz2 file to a destination.

        Args:
            source: Source bz2 file path (local or gs://)
            destination: Destination path (local or gs://)
            use_parallel: Whether to use parallel decompression (lbzip2)
        """
        source_backend = cls.get_backend(source)
        dest_backend = cls.get_backend(destination)

        # Check if we need temporary files
        needs_temp_source = cls.is_gcs_path(source)
        needs_temp_dest = cls.is_gcs_path(destination)

        # Download source if needed
        if needs_temp_source:
            with tempfile.NamedTemporaryFile(suffix=".bz2", delete=False) as tmp:
                tmp_source = tmp.name
            logger.info(f"Downloading {source} to temporary file for extraction...")
            source_backend.download(source, tmp_source)
            actual_source = tmp_source
        else:
            actual_source = source

        # Determine actual destination
        if needs_temp_dest:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                tmp_dest = tmp.name
            actual_dest = tmp_dest
        else:
            actual_dest = destination

        # Check for lbzip2 if parallel extraction requested
        if use_parallel:
            if subprocess.run(["which", "lbzip2"], capture_output=True).returncode != 0:
                raise RuntimeError(
                    "lbzip2 not found. Please install lbzip2 for parallel extraction."
                )
            cmd = ["lbzip2", "-d", "-c", actual_source]
        else:
            cmd = ["bunzip2", "-c", actual_source]

        # Perform extraction
        logger.info(f"Extracting {source} to {destination}...")
        with open(actual_dest, "wb") as out_file:
            subprocess.run(cmd, stdout=out_file, check=True)

        # Upload to GCS if needed
        if needs_temp_dest:
            logger.info(f"Uploading extracted file to {destination}...")
            with open(actual_dest, "rb") as f:
                with dest_backend.open(destination, "wb") as dest_f:
                    # Stream file in chunks to avoid loading entire file into memory
                    chunk_size = 64 * 1024 * 1024  # 64MB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        dest_f.write(chunk)

        # Clean up temporary files
        if needs_temp_source:
            os.unlink(tmp_source)
        if needs_temp_dest:
            os.unlink(tmp_dest)
