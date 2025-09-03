"""Archive utilities for managing archived page files."""

import os

from .storage import StorageFactory


def read_archived_content(path_root: str, extension: str) -> str:
    """Read content for an archived page.

    Args:
        path_root: The path root (timestamp/content_hash) from ArchivedPage.path_root
        extension: File extension (e.g., 'md', 'html', 'mhtml')

    Returns:
        The file content as a string

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    archive_root = os.getenv("POLILOOM_ARCHIVE_ROOT", "./archives")

    file_path = os.path.join(archive_root, f"{path_root}.{extension}")

    backend = StorageFactory.get_backend(file_path)
    if not backend.exists(file_path):
        raise FileNotFoundError(f"Archived file not found: {file_path}")

    with backend.open(file_path, "r") as f:
        return f.read()


def save_archived_content(
    path_root: str,
    extension: str,
    content: str,
) -> str:
    """Save content for an archived page.

    Args:
        path_root: The path root (timestamp/content_hash) from ArchivedPage.path_root
        extension: File extension (e.g., 'md', 'html', 'mhtml')
        content: The content to save

    Returns:
        The path where the file was saved
    """
    archive_root = os.getenv("POLILOOM_ARCHIVE_ROOT", "./archives")

    file_path = os.path.join(archive_root, f"{path_root}.{extension}")

    backend = StorageFactory.get_backend(file_path)
    with backend.open(file_path, "w") as f:
        f.write(content)

    return file_path
