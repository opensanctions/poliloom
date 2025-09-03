"""Service for managing archived page file operations."""

import os
from typing import Optional

from ..storage import StorageFactory


class ArchivalService:
    """Service for handling archived page file storage operations."""

    def __init__(self, archive_root: Optional[str] = None):
        """Initialize the archival service.

        Args:
            archive_root: Root directory for archives. If None, uses POLILOOM_ARCHIVE_ROOT env var
                         or defaults to "./archives"
        """
        self.archive_root = archive_root or os.getenv(
            "POLILOOM_ARCHIVE_ROOT", "./archives"
        )

    def read_content(self, path_root: str, extension: str) -> str:
        """Read content for an archived page.

        Args:
            path_root: The path root (timestamp/content_hash) from ArchivedPage.path_root
            extension: File extension (e.g., 'md', 'html', 'mhtml')

        Returns:
            The file content as a string

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        file_path = os.path.join(self.archive_root, f"{path_root}.{extension}")

        backend = StorageFactory.get_backend(file_path)
        if not backend.exists(file_path):
            raise FileNotFoundError(f"Archived file not found: {file_path}")

        with backend.open(file_path, "r") as f:
            return f.read()

    def save_content(self, path_root: str, extension: str, content: str) -> str:
        """Save content for an archived page.

        Args:
            path_root: The path root (timestamp/content_hash) from ArchivedPage.path_root
            extension: File extension (e.g., 'md', 'html', 'mhtml')
            content: The content to save

        Returns:
            The path where the file was saved
        """
        file_path = os.path.join(self.archive_root, f"{path_root}.{extension}")

        backend = StorageFactory.get_backend(file_path)
        with backend.open(file_path, "w") as f:
            f.write(content)

        return file_path
