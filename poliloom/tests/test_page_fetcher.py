"""Tests for page_fetcher module."""

import pytest
from unittest.mock import Mock, patch


class TestFetchPage:
    """Test fetch_page function."""

    def _create_playwright_mocks(
        self, response_ok=True, response_status=200, mhtml_data="MHTML content"
    ):
        """Create mock objects for playwright."""
        mock_response = Mock()
        mock_response.ok = response_ok
        mock_response.status = response_status

        mock_cdp_session = Mock()

        async def mock_cdp_send(*args, **kwargs):
            return {"data": mhtml_data}

        mock_cdp_session.send = mock_cdp_send

        mock_page = Mock()

        async def mock_goto(*args, **kwargs):
            return mock_response

        mock_page.goto = mock_goto

        mock_context = Mock()

        async def mock_new_page():
            return mock_page

        async def mock_new_cdp_session(page):
            return mock_cdp_session

        mock_context.new_page = mock_new_page
        mock_context.new_cdp_session = mock_new_cdp_session

        mock_browser = Mock()

        async def mock_new_context(**kwargs):
            return mock_context

        async def mock_close():
            pass

        mock_browser.new_context = mock_new_context
        mock_browser.close = mock_close

        mock_chromium = Mock()

        async def mock_launch():
            return mock_browser

        mock_chromium.launch = mock_launch

        mock_playwright = Mock()
        mock_playwright.chromium = mock_chromium

        return mock_playwright

    @pytest.mark.asyncio
    async def test_fetch_page_success(self):
        """Test successful page fetch."""
        from poliloom.page_fetcher import fetch_page, FetchedPage

        url = "https://example.com/page"
        mock_playwright = self._create_playwright_mocks(
            mhtml_data="<mhtml>content</mhtml>"
        )

        async def mock_aenter(*args):
            return mock_playwright

        async def mock_aexit(*args):
            return None

        mock_playwright_cm = Mock()
        mock_playwright_cm.__aenter__ = mock_aenter
        mock_playwright_cm.__aexit__ = mock_aexit

        with patch(
            "poliloom.page_fetcher.async_playwright", return_value=mock_playwright_cm
        ):
            with patch("poliloom.page_fetcher.convert_mhtml_to_html") as mock_convert:
                mock_convert.return_value = "<html>converted</html>"

                result = await fetch_page(url)

                assert isinstance(result, FetchedPage)
                assert result.mhtml == "<mhtml>content</mhtml>"
                assert result.html == "<html>converted</html>"

    @pytest.mark.asyncio
    async def test_fetch_page_http_error(self):
        """Test HTTP error handling."""
        from poliloom.page_fetcher import fetch_page, PageFetchError

        url = "https://example.com/not-found"
        mock_playwright = self._create_playwright_mocks(
            response_ok=False, response_status=404
        )

        async def mock_aenter(*args):
            return mock_playwright

        async def mock_aexit(*args):
            return None

        mock_playwright_cm = Mock()
        mock_playwright_cm.__aenter__ = mock_aenter
        mock_playwright_cm.__aexit__ = mock_aexit

        with patch(
            "poliloom.page_fetcher.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="HTTP 404"):
                await fetch_page(url)

    @pytest.mark.asyncio
    async def test_fetch_page_no_response(self):
        """Test handling when no response is received."""
        from poliloom.page_fetcher import fetch_page, PageFetchError

        url = "https://example.com/no-response"
        mock_playwright = self._create_playwright_mocks()

        # Override goto to return None
        mock_page = Mock()

        async def mock_goto_none(*args, **kwargs):
            return None

        mock_page.goto = mock_goto_none

        mock_context = Mock()

        async def mock_new_page():
            return mock_page

        mock_context.new_page = mock_new_page

        mock_browser = Mock()

        async def mock_new_context(**kwargs):
            return mock_context

        async def mock_close():
            pass

        mock_browser.new_context = mock_new_context
        mock_browser.close = mock_close

        mock_chromium = Mock()

        async def mock_launch():
            return mock_browser

        mock_chromium.launch = mock_launch

        mock_playwright.chromium = mock_chromium

        async def mock_aenter(*args):
            return mock_playwright

        async def mock_aexit(*args):
            return None

        mock_playwright_cm = Mock()
        mock_playwright_cm.__aenter__ = mock_aenter
        mock_playwright_cm.__aexit__ = mock_aexit

        with patch(
            "poliloom.page_fetcher.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="No response"):
                await fetch_page(url)

    @pytest.mark.asyncio
    async def test_fetch_page_timeout(self):
        """Test timeout handling."""
        from poliloom.page_fetcher import fetch_page, PageFetchError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        url = "https://example.com/slow"
        mock_playwright = self._create_playwright_mocks()

        # Override goto to raise timeout
        mock_page = Mock()

        async def mock_goto_timeout(*args, **kwargs):
            raise PlaywrightTimeoutError("Timeout 60000ms exceeded")

        mock_page.goto = mock_goto_timeout

        mock_context = Mock()

        async def mock_new_page():
            return mock_page

        mock_context.new_page = mock_new_page

        mock_browser = Mock()

        async def mock_new_context(**kwargs):
            return mock_context

        async def mock_close():
            pass

        mock_browser.new_context = mock_new_context
        mock_browser.close = mock_close

        mock_chromium = Mock()

        async def mock_launch():
            return mock_browser

        mock_chromium.launch = mock_launch

        mock_playwright.chromium = mock_chromium

        async def mock_aenter(*args):
            return mock_playwright

        async def mock_aexit(*args):
            return None

        mock_playwright_cm = Mock()
        mock_playwright_cm.__aenter__ = mock_aenter
        mock_playwright_cm.__aexit__ = mock_aexit

        with patch(
            "poliloom.page_fetcher.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="Timeout"):
                await fetch_page(url)

    @pytest.mark.asyncio
    async def test_fetch_page_browser_error(self):
        """Test browser error handling."""
        from poliloom.page_fetcher import fetch_page, PageFetchError
        from playwright.async_api import Error as PlaywrightError

        url = "https://example.com/error"
        mock_playwright = self._create_playwright_mocks()

        # Override goto to raise browser error
        mock_page = Mock()

        async def mock_goto_error(*args, **kwargs):
            raise PlaywrightError("Browser crashed")

        mock_page.goto = mock_goto_error

        mock_context = Mock()

        async def mock_new_page():
            return mock_page

        mock_context.new_page = mock_new_page

        mock_browser = Mock()

        async def mock_new_context(**kwargs):
            return mock_context

        async def mock_close():
            pass

        mock_browser.new_context = mock_new_context
        mock_browser.close = mock_close

        mock_chromium = Mock()

        async def mock_launch():
            return mock_browser

        mock_chromium.launch = mock_launch

        mock_playwright.chromium = mock_chromium

        async def mock_aenter(*args):
            return mock_playwright

        async def mock_aexit(*args):
            return None

        mock_playwright_cm = Mock()
        mock_playwright_cm.__aenter__ = mock_aenter
        mock_playwright_cm.__aexit__ = mock_aexit

        with patch(
            "poliloom.page_fetcher.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="Browser error"):
                await fetch_page(url)
