"""Web page fetching and archiving using Playwright."""

import logging
from dataclasses import dataclass

from playwright.async_api import async_playwright
from unmhtml import MHTMLConverter

from . import __version__, __repo_url__

logger = logging.getLogger(__name__)

# Page fetch timeout in milliseconds (60 seconds)
PAGE_FETCH_TIMEOUT_MS = 60000

# User agent for web requests
USER_AGENT = f"poliloom/{__version__} ({__repo_url__})"


class PageFetchError(Exception):
    """Error fetching a web page."""

    pass


@dataclass
class FetchedPage:
    """Result of fetching a web page."""

    mhtml: str
    html: str


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
                raise PageFetchError(f"No response received: {url}")

            if not response.ok:
                raise PageFetchError(f"HTTP {response.status} for {url}")

            # Capture MHTML using CDP
            cdp_session = await context.new_cdp_session(page)
            mhtml_result = await cdp_session.send(
                "Page.captureSnapshot", {"format": "mhtml"}
            )
            mhtml_content = mhtml_result.get("data")

            if not mhtml_content:
                raise PageFetchError(f"No MHTML content captured: {url}")

            # Convert MHTML to HTML
            converter = MHTMLConverter()
            html_content = converter.convert(mhtml_content)

            return FetchedPage(mhtml=mhtml_content, html=html_content)

        except PlaywrightTimeoutError:
            raise PageFetchError(f"Timeout after {PAGE_FETCH_TIMEOUT_MS}ms: {url}")
        except PlaywrightError as e:
            raise PageFetchError(f"Browser error for {url}: {e}")
        finally:
            await browser.close()
