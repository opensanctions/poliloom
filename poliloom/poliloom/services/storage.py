"""Storage abstraction layer for handling both local and Google Cloud Storage."""

import io
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator, Optional, Tuple
from urllib.parse import urlparse

from tqdm import tqdm

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
    def download(
        self, source: str, destination: str, show_progress: bool = True
    ) -> None:
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

    def download(
        self, source: str, destination: str, show_progress: bool = True
    ) -> None:
        """Copy a local file to another location."""
        import shutil

        if show_progress:
            file_size = self.get_size(source)
            with tqdm(
                total=file_size, unit="B", unit_scale=True, desc="Copying"
            ) as pbar:
                with open(source, "rb") as src, open(destination, "wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        dst.write(chunk)
                        pbar.update(len(chunk))
        else:
            shutil.copy2(source, destination)

    def stream_lines(self, path: str) -> Iterator[str]:
        """Stream lines from a local file."""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize GCS storage backend.

        Args:
            credentials_path: Optional path to service account credentials JSON.
                            If not provided, uses Application Default Credentials.
        """
        try:
            from google.cloud import storage
            from google.auth import default

            if credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

            # Use Application Default Credentials
            credentials, project = default()
            self.client = storage.Client(credentials=credentials, project=project)
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS support. "
                "Install with: pip install google-cloud-storage"
            )
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            raise

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
            # For writing, we need to handle this differently
            # GCS doesn't support true streaming writes
            class GCSWriteStream:
                def __init__(self, blob):
                    self.blob = blob
                    self.buffer = io.BytesIO()

                def write(self, data):
                    return self.buffer.write(data)

                def close(self):
                    self.buffer.seek(0)
                    self.blob.upload_from_file(self.buffer)
                    self.buffer.close()

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

    def download(
        self, source: str, destination: str, show_progress: bool = True
    ) -> None:
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

            if show_progress:
                # Get file size for progress bar
                blob.reload()
                file_size = blob.size or 0

                with tqdm(
                    total=file_size, unit="B", unit_scale=True, desc="Downloading"
                ) as pbar:

                    def _download_callback(bytes_downloaded):
                        pbar.update(bytes_downloaded - pbar.n)

                    blob.download_to_filename(destination, raw_download=True)
            else:
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
    def get_backend(
        cls, path: str, credentials_path: Optional[str] = None
    ) -> StorageBackend:
        """Get the appropriate storage backend for a given path.

        Args:
            path: File path (local or gs://)
            credentials_path: Optional GCS credentials path

        Returns:
            StorageBackend instance
        """
        if path.startswith("gs://"):
            if cls._gcs_storage is None:
                cls._gcs_storage = GCSStorage(credentials_path)
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
    def download_from_url(
        cls, url: str, destination: str, show_progress: bool = True
    ) -> None:
        """Download a file from a URL (HTTP/HTTPS) to a destination.

        Args:
            url: Source URL
            destination: Destination path (local or gs://)
            show_progress: Whether to show progress bar
        """

        # First download to a temporary local file if destination is GCS
        if cls.is_gcs_path(destination):
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = tmp_file.name

            # Download to temp file first
            cls._download_http_to_file(url, tmp_path, show_progress)

            # Then upload to GCS
            backend = cls.get_backend(destination)
            backend.download(tmp_path, destination, show_progress)

            # Clean up temp file
            os.unlink(tmp_path)
        else:
            # Direct download to local file
            cls._download_http_to_file(url, destination, show_progress)

    @staticmethod
    def _download_http_to_file(url: str, destination: str, show_progress: bool) -> None:
        """Download from HTTP/HTTPS to a local file."""
        import httpx

        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()

            # Get total size if available
            total_size = int(response.headers.get("content-length", 0))

            if show_progress and total_size:
                pbar = tqdm(
                    total=total_size, unit="B", unit_scale=True, desc="Downloading"
                )
            else:
                pbar = None

            with open(destination, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)
                    if pbar:
                        pbar.update(len(chunk))

            if pbar:
                pbar.close()

    @classmethod
    def extract_bz2(
        cls,
        source: str,
        destination: str,
        show_progress: bool = True,
        use_parallel: bool = True,
    ) -> None:
        """Extract a bz2 file to a destination.

        Args:
            source: Source bz2 file path (local or gs://)
            destination: Destination path (local or gs://)
            show_progress: Whether to show progress bar
            use_parallel: Whether to use parallel decompression (lbzip2)
        """
        # For now, we need to handle this with local files
        # GCS streaming decompression would require more complex implementation

        source_backend = cls.get_backend(source)
        dest_backend = cls.get_backend(destination)

        # Check if we need temporary files
        needs_temp_source = cls.is_gcs_path(source)
        needs_temp_dest = cls.is_gcs_path(destination)

        import tempfile

        # Download source if needed
        if needs_temp_source:
            with tempfile.NamedTemporaryFile(suffix=".bz2", delete=False) as tmp:
                tmp_source = tmp.name
            logger.info(f"Downloading {source} to temporary file for extraction...")
            source_backend.download(source, tmp_source, show_progress)
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

        # Perform extraction using lbzip2 (required)
        if use_parallel:
            # Check for lbzip2 (required)
            if subprocess.run(["which", "lbzip2"], capture_output=True).returncode != 0:
                raise RuntimeError(
                    "lbzip2 not found. Please install lbzip2 for parallel extraction."
                )

        # Use lbzip2 for decompression
        logger.info("Using lbzip2 for parallel decompression...")
        cmd = ["lbzip2", "-d", "-c", actual_source]
        with open(actual_dest, "wb") as out_file:
            if show_progress:
                # Get source file size for progress estimation
                source_size = (
                    source_backend.get_size(source)
                    if not needs_temp_source
                    else os.path.getsize(actual_source)
                )
                pbar = tqdm(
                    total=source_size, unit="B", unit_scale=True, desc="Extracting"
                )

                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                while True:
                    chunk = process.stdout.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    out_file.write(chunk)
                    # Rough progress based on compressed size
                    pbar.update(len(chunk) // 10)  # Assume 10:1 compression ratio
                pbar.close()
            else:
                subprocess.run(cmd, stdout=out_file, check=True)

        # Upload to GCS if needed
        if needs_temp_dest:
            logger.info(f"Uploading extracted file to {destination}...")
            # For large files, we should stream upload
            # but for simplicity, we'll upload the whole file
            with open(actual_dest, "rb") as f:
                with dest_backend.open(destination, "wb") as dest_f:
                    if show_progress:
                        file_size = os.path.getsize(actual_dest)
                        pbar = tqdm(
                            total=file_size, unit="B", unit_scale=True, desc="Uploading"
                        )

                        while True:
                            chunk = f.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            dest_f.write(chunk)
                            pbar.update(len(chunk))
                        pbar.close()
                    else:
                        dest_f.write(f.read())

        # Clean up temporary files
        if needs_temp_source:
            os.unlink(tmp_source)
        if needs_temp_dest:
            os.unlink(tmp_dest)
