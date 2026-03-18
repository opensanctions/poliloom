"""Tests for the archiving module: page fetching, MHTML conversion, and source processing."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from poliloom.archiving import (
    FetchedPage,
    PageFetchError,
    convert_mhtml_to_html,
    extract_permanent_url,
    fetch_page,
    process_source,
)
from poliloom.models import (
    Source,
    SourceError,
    SourceStatus,
)


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
            "poliloom.archiving.async_playwright", return_value=mock_playwright_cm
        ):
            with patch("poliloom.archiving.convert_mhtml_to_html") as mock_convert:
                mock_convert.return_value = "<html>converted</html>"

                result = await fetch_page(url)

                assert isinstance(result, FetchedPage)
                assert result.mhtml == "<mhtml>content</mhtml>"
                assert result.html == "<html>converted</html>"

    @pytest.mark.asyncio
    async def test_fetch_page_http_error(self):
        """Test HTTP error handling."""
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
            "poliloom.archiving.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="HTTP 404"):
                await fetch_page(url)

    @pytest.mark.asyncio
    async def test_fetch_page_no_response(self):
        """Test handling when no response is received."""
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
            "poliloom.archiving.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="No response"):
                await fetch_page(url)

    @pytest.mark.asyncio
    async def test_fetch_page_timeout(self):
        """Test timeout handling."""
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
            "poliloom.archiving.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="Timeout"):
                await fetch_page(url)

    @pytest.mark.asyncio
    async def test_fetch_page_browser_error(self):
        """Test browser error handling."""
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
            "poliloom.archiving.async_playwright", return_value=mock_playwright_cm
        ):
            with pytest.raises(PageFetchError, match="Browser error"):
                await fetch_page(url)


class TestExtractPermanentUrl:
    """Test extract_permanent_url function using t-permalink element."""

    def test_extract_permanent_url_basic(self):
        """Test extracting permanent URL from t-permalink element."""
        html_snippet = """
        <li id="t-permalink" class="mw-list-item">
            <a href="https://en.wikipedia.org/w/index.php?title=Mirjam_Blaak&oldid=1314222018"
               title="Permanent link to this revision of this page">
                <span>Permanent link</span>
            </a>
        </li>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert (
            permanent_url
            == "https://en.wikipedia.org/w/index.php?title=Mirjam_Blaak&oldid=1314222018"
        )

    def test_extract_permanent_url_uses_t_permalink_not_other_links(self):
        """Test that only the t-permalink element is used, not other oldid links."""
        html_snippet = """
        <a href="https://en.wikipedia.org/w/index.php?title=Other_Page&oldid=9999999">Other</a>
        <li id="t-permalink" class="mw-list-item">
            <a href="https://en.wikipedia.org/w/index.php?title=Petra_Butler&oldid=1292404970">Correct</a>
        </li>
        <a href="https://en.wikipedia.org/w/index.php?title=Another_Page&oldid=8888888">Another</a>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert (
            permanent_url
            == "https://en.wikipedia.org/w/index.php?title=Petra_Butler&oldid=1292404970"
        )

    def test_extract_permanent_url_no_t_permalink_returns_none(self):
        """Test that None is returned when no t-permalink element exists."""
        html_snippet = """
        <a href="https://en.wikipedia.org/w/index.php?title=Mirjam_Blaak&oldid=1234567890">Link</a>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert permanent_url is None

    def test_extract_permanent_url_no_anchor_in_t_permalink(self):
        """Test when t-permalink exists but has no anchor tag."""
        html_snippet = """
        <li id="t-permalink" class="mw-list-item">
            <span>Permanent link</span>
        </li>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert permanent_url is None

    def test_extract_permanent_url_with_fragment(self):
        """Test that URL fragments are preserved in permanent URL."""
        html_snippet = """
        <li id="t-permalink" class="mw-list-item">
            <a href="https://en.wikipedia.org/w/index.php?title=2025_shootings&oldid=1321768448#Accused">Link</a>
        </li>
        """

        permanent_url = extract_permanent_url(html_snippet)
        assert (
            permanent_url
            == "https://en.wikipedia.org/w/index.php?title=2025_shootings&oldid=1321768448#Accused"
        )


class TestConvertMhtmlToHtml:
    """Test convert_mhtml_to_html function."""

    def test_convert_mhtml_to_html_success(self):
        """Test successful MHTML to HTML conversion."""
        mhtml_content = "MHTML content here"
        expected_html = "<html>Converted content</html>"

        with patch("poliloom.archiving.MHTMLConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.return_value = expected_html
            mock_converter_class.return_value = mock_converter

            result = convert_mhtml_to_html(mhtml_content)

            assert result == expected_html
            mock_converter.convert.assert_called_once_with(mhtml_content)

    def test_convert_mhtml_to_html_none_input(self):
        """Test that None input returns None."""
        result = convert_mhtml_to_html(None)
        assert result is None

    def test_convert_mhtml_to_html_conversion_error(self):
        """Test that conversion errors return None."""
        mhtml_content = "MHTML content"

        with patch("poliloom.archiving.MHTMLConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.side_effect = Exception("Conversion failed")
            mock_converter_class.return_value = mock_converter

            result = convert_mhtml_to_html(mhtml_content)
            assert result is None


@pytest.fixture
def pending_source(db_session, sample_politician):
    """Create a PENDING source linked to sample_politician."""
    page = Source(
        url="https://en.wikipedia.org/wiki/Test_Politician",
        status=SourceStatus.PENDING,
    )
    db_session.add(page)
    db_session.flush()
    sample_politician.sources.append(page)
    db_session.flush()
    return page


FETCHED_PAGE = FetchedPage(mhtml="<mhtml>", html="<html><body>text</body></html>")
VALID_HTML = "<html><body>Some real text content</body></html>"


class TestProcessSource:
    """Test process_source pipeline."""

    @pytest.mark.asyncio
    @patch(
        "poliloom.archiving.extract_and_store", new_callable=AsyncMock, return_value=3
    )
    @patch("poliloom.archiving.read_archived_content", return_value=VALID_HTML)
    @patch("poliloom.archiving.save_archived_content")
    @patch(
        "poliloom.archiving.fetch_page",
        new_callable=AsyncMock,
        return_value=FETCHED_PAGE,
    )
    async def test_happy_path_sets_done(
        self,
        mock_fetch,
        mock_save,
        mock_read,
        mock_extract,
        db_session,
        sample_politician,
        pending_source,
    ):
        await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error is None

    @pytest.mark.asyncio
    async def test_fetch_error_sets_error_type(
        self, db_session, sample_politician, pending_source
    ):
        with patch(
            "poliloom.archiving.fetch_page",
            AsyncMock(
                side_effect=PageFetchError(
                    "HTTP 404", http_status_code=404, error_type="FETCH_ERROR"
                )
            ),
        ):
            await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error == SourceError.FETCH_ERROR
        assert pending_source.http_status_code == 404

    @pytest.mark.asyncio
    async def test_timeout_error(self, db_session, sample_politician, pending_source):
        with patch(
            "poliloom.archiving.fetch_page",
            AsyncMock(side_effect=PageFetchError("Timeout", error_type="TIMEOUT")),
        ):
            await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error == SourceError.TIMEOUT

    @pytest.mark.asyncio
    async def test_no_response_error(
        self, db_session, sample_politician, pending_source
    ):
        with patch(
            "poliloom.archiving.fetch_page",
            AsyncMock(
                side_effect=PageFetchError("No response", error_type="NO_RESPONSE")
            ),
        ):
            await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error == SourceError.NO_RESPONSE

    @pytest.mark.asyncio
    async def test_generic_exception_sets_pipeline_error(
        self, db_session, sample_politician, pending_source
    ):
        with patch(
            "poliloom.archiving.fetch_page",
            AsyncMock(side_effect=RuntimeError("unexpected crash")),
        ):
            await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error == SourceError.PIPELINE_ERROR

    @pytest.mark.asyncio
    @patch(
        "poliloom.archiving.extract_and_store", new_callable=AsyncMock, return_value=0
    )
    @patch("poliloom.archiving.read_archived_content", return_value=None)
    @patch("poliloom.archiving.save_archived_content")
    @patch(
        "poliloom.archiving.fetch_page",
        new_callable=AsyncMock,
        return_value=FETCHED_PAGE,
    )
    async def test_no_html_content_sets_invalid_content(
        self,
        mock_fetch,
        mock_save,
        mock_read,
        mock_extract,
        db_session,
        sample_politician,
        pending_source,
    ):
        await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error == SourceError.INVALID_CONTENT

    @pytest.mark.asyncio
    @patch(
        "poliloom.archiving.extract_and_store", new_callable=AsyncMock, return_value=0
    )
    @patch(
        "poliloom.archiving.read_archived_content",
        return_value="<html><body>   </body></html>",
    )
    @patch("poliloom.archiving.save_archived_content")
    @patch(
        "poliloom.archiving.fetch_page",
        new_callable=AsyncMock,
        return_value=FETCHED_PAGE,
    )
    async def test_empty_text_sets_invalid_content(
        self,
        mock_fetch,
        mock_save,
        mock_read,
        mock_extract,
        db_session,
        sample_politician,
        pending_source,
    ):
        await process_source(db_session, pending_source, sample_politician)

        assert pending_source.status == SourceStatus.DONE
        assert pending_source.error == SourceError.INVALID_CONTENT

    @pytest.mark.asyncio
    @patch(
        "poliloom.archiving.extract_and_store", new_callable=AsyncMock, return_value=3
    )
    @patch("poliloom.archiving.read_archived_content", return_value=VALID_HTML)
    @patch("poliloom.archiving.save_archived_content")
    @patch(
        "poliloom.archiving.extract_permanent_url",
        return_value="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
    )
    @patch(
        "poliloom.archiving.fetch_page",
        new_callable=AsyncMock,
        return_value=FETCHED_PAGE,
    )
    async def test_permanent_url_extracted_for_wikipedia(
        self,
        mock_fetch,
        mock_perm,
        mock_save,
        mock_read,
        mock_extract,
        db_session,
        sample_politician,
        pending_source,
        sample_wikipedia_project,
    ):
        pending_source.wikipedia_project_id = sample_wikipedia_project.wikidata_id
        db_session.flush()

        await process_source(db_session, pending_source, sample_politician)

        assert (
            pending_source.permanent_url
            == "https://en.wikipedia.org/w/index.php?title=Test&oldid=123"
        )
        assert pending_source.status == SourceStatus.DONE

    @pytest.mark.asyncio
    @patch(
        "poliloom.archiving.extract_and_store", new_callable=AsyncMock, return_value=3
    )
    @patch("poliloom.archiving.read_archived_content", return_value=VALID_HTML)
    @patch("poliloom.archiving.save_archived_content")
    async def test_status_transitions_to_processing(
        self,
        mock_save,
        mock_read,
        mock_extract,
        db_session,
        sample_politician,
        pending_source,
    ):
        """Status should be PROCESSING when fetch is called."""
        observed_status = None

        async def capture_status(url):
            nonlocal observed_status
            observed_status = pending_source.status
            return FetchedPage(mhtml="<mhtml>", html="<html><body>text</body></html>")

        with patch("poliloom.archiving.fetch_page", side_effect=capture_status):
            await process_source(db_session, pending_source, sample_politician)

        assert observed_status == SourceStatus.PROCESSING
