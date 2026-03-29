"""Archiving: page fetching, storage, and source processing pipeline."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from unmhtml import MHTMLConverter

from . import __version__, __repo_url__
from .enrichment import extract_and_store
from .models import (
    Source,
    SourceError,
    SourceStatus,
    Politician,
)
from .storage import StorageFactory

logger = logging.getLogger(__name__)

# Page fetch timeout in milliseconds (60 seconds)
PAGE_FETCH_TIMEOUT_MS = 60000

# User agent for web requests
USER_AGENT = f"poliloom/{__version__} ({__repo_url__})"


class PageFetchError(Exception):
    """Error fetching a web page."""

    def __init__(
        self,
        message: str,
        http_status_code: Optional[int] = None,
        error_type: Optional[str] = None,
    ):
        super().__init__(message)
        self.http_status_code = http_status_code
        self.error_type = error_type


@dataclass
class FetchedPage:
    """Result of fetching a web page."""

    mhtml: str
    html: Optional[str]


def convert_mhtml_to_html(mhtml_content: Optional[str]) -> Optional[str]:
    """Convert MHTML content to HTML, returning None on failure."""
    if not mhtml_content:
        return None

    try:
        converter = MHTMLConverter()
        return converter.convert(mhtml_content)
    except Exception as e:
        logger.warning(f"Failed to convert MHTML to HTML: {e}")
        return None


async def fetch_page(url: str) -> FetchedPage:
    """Fetch a web page and return its content as MHTML and HTML.

    Uses Playwright to render the page fully (including JavaScript) and
    captures a complete MHTML snapshot.

    Args:
        url: The URL to fetch

    Returns:
        FetchedPage with mhtml and html content

    Raises:
        PageFetchError: If the page cannot be fetched (timeout, network error, HTTP error)
    """
    from playwright.async_api import (
        TimeoutError as PlaywrightTimeoutError,
        Error as PlaywrightError,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        try:
            response = await page.goto(
                url,
                wait_until="load",
                timeout=PAGE_FETCH_TIMEOUT_MS,
            )

            if not response:
                raise PageFetchError(
                    f"No response received: {url}",
                    error_type="NO_RESPONSE",
                )

            if not response.ok:
                raise PageFetchError(
                    f"HTTP {response.status} for {url}",
                    http_status_code=response.status,
                    error_type="FETCH_ERROR",
                )

            # Capture MHTML using CDP
            cdp_session = await context.new_cdp_session(page)
            mhtml_result = await cdp_session.send(
                "Page.captureSnapshot", {"format": "mhtml"}
            )
            mhtml_content = mhtml_result.get("data")

            # Convert MHTML to HTML
            html_content = convert_mhtml_to_html(mhtml_content)

            return FetchedPage(mhtml=mhtml_content, html=html_content)

        except PlaywrightTimeoutError:
            raise PageFetchError(
                f"Timeout after {PAGE_FETCH_TIMEOUT_MS}ms: {url}",
                error_type="TIMEOUT",
            )
        except PlaywrightError as e:
            raise PageFetchError(
                f"Browser error for {url}: {e}",
                error_type="BROWSER_ERROR",
            )
        finally:
            await browser.close()


# --- Archived content storage ---


def read_archived_content(path_root: str, extension: str) -> str:
    """Read content for a source.

    Args:
        path_root: The path root (timestamp/url_hash) from Source.path_root
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
    """Save content for a source.

    Args:
        path_root: The path root (timestamp/url_hash) from Source.path_root
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


# --- Source processing ---


def extract_permanent_url(html_content: str) -> Optional[str]:
    """Extract Wikipedia permanent URL with oldid from HTML content.

    Uses the Wikipedia sidebar's permanent link element (id="t-permalink") to extract
    the canonical permanent URL. This handles redirects correctly since the permanent
    link always points to the actual page revision being viewed.

    Args:
        html_content: The HTML content to search

    Returns:
        The permanent URL with oldid (e.g., "https://en.wikipedia.org/w/index.php?title=Page&oldid=123456789"),
        or None if not found
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        permalink_element = soup.find(id="t-permalink")

        if not permalink_element:
            logger.debug("No t-permalink element found in HTML")
            return None

        anchor = permalink_element.find("a")
        if not anchor or not anchor.get("href"):
            logger.debug("No anchor with href found in t-permalink element")
            return None

        permanent_url = anchor["href"]
        logger.debug(f"Found permanent URL via t-permalink: {permanent_url}")
        return permanent_url

    except Exception as e:
        logger.warning(f"Error extracting permanent URL: {e}")
        return None


async def process_source(db: Session, source: Source, politician: Politician) -> int:
    """Fetch, archive, and extract properties from a source.

    Handles status transitions and error recording on the source.
    Caller is responsible for providing the session and loading entities.

    Returns:
        Number of properties extracted (0 on error or empty content).
    """
    try:
        # Fetch & archive
        fetched = await fetch_page(source.url)
        now = datetime.now(timezone.utc)

        if source.wikipedia_project_id and fetched.html:
            permanent_url = extract_permanent_url(fetched.html)
            if permanent_url:
                logger.info(f"Extracted permanent URL: {permanent_url}")
                source.permanent_url = permanent_url

        source.url_hash = Source._generate_url_hash(source.url)
        source.fetch_timestamp = now
        db.flush()

        source.link_languages_from_project(db)
        db.flush()

        if fetched.mhtml:
            path = save_archived_content(source.path_root, "mhtml", fetched.mhtml)
            logger.info(f"Saved MHTML archive: {path}")
        if fetched.html:
            path = save_archived_content(source.path_root, "html", fetched.html)
            logger.info(f"Saved HTML: {path}")
        db.commit()

        # Read content and extract text
        html_content = read_archived_content(source.path_root, "html")
        if not html_content:
            source.status = SourceStatus.DONE
            source.error = SourceError.INVALID_CONTENT
            db.commit()
            return 0
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text()
        content = " ".join(text.split())
        if not content.strip():
            source.status = SourceStatus.DONE
            source.error = SourceError.INVALID_CONTENT
            db.commit()
            return 0

        # Extract and store properties
        count = await extract_and_store(db, content, politician, source)

        source.status = SourceStatus.DONE
        db.commit()

        return count

    except PageFetchError as e:
        logger.error(f"Fetch error for source {source.id}: {e}")
        source.status = SourceStatus.DONE
        source.error = SourceError(e.error_type)
        if e.http_status_code is not None:
            source.http_status_code = e.http_status_code
        db.commit()
        return 0
    except Exception as e:
        logger.error(f"Pipeline error for source {source.id}: {e}")
        source.status = SourceStatus.DONE
        source.error = SourceError.PIPELINE_ERROR
        db.commit()
        return 0
