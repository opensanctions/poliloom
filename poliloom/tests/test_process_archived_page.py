"""Tests for process_archived_page pipeline function."""

import pytest
from unittest.mock import AsyncMock, patch

from poliloom.enrichment import process_archived_page
from poliloom.models import (
    ArchivedPage,
    ArchivedPageError,
    ArchivedPageStatus,
)
from poliloom.page_fetcher import FetchedPage, PageFetchError


@pytest.fixture
def pending_archived_page(db_session, sample_politician):
    """Create a PENDING archived page linked to sample_politician."""
    page = ArchivedPage(
        url="https://en.wikipedia.org/wiki/Test_Politician",
        status=ArchivedPageStatus.PENDING,
    )
    db_session.add(page)
    db_session.flush()
    sample_politician.archived_pages.append(page)
    db_session.flush()
    return page


def _patch_happy_path(**overrides):
    """Return a tuple of patches for the happy path through the pipeline."""
    defaults = dict(
        fetch_return=FetchedPage(
            mhtml="<mhtml>", html="<html><body>text</body></html>"
        ),
        permanent_url=None,
        html_content="<html><body>Some real text content</body></html>",
        date_properties=None,
        two_stage_return=None,
    )
    defaults.update(overrides)

    return (
        patch(
            "poliloom.enrichment.fetch_page",
            AsyncMock(return_value=defaults["fetch_return"]),
        ),
        patch(
            "poliloom.enrichment.extract_permanent_url",
            return_value=defaults["permanent_url"],
        ),
        patch.object(ArchivedPage, "save_archived_files"),
        patch(
            "poliloom.enrichment.archive.read_archived_content",
            return_value=defaults["html_content"],
        ),
        patch(
            "poliloom.enrichment.extract_properties_generic",
            new_callable=AsyncMock,
            return_value=defaults["date_properties"],
        ),
        patch(
            "poliloom.enrichment.extract_two_stage_generic",
            new_callable=AsyncMock,
            return_value=defaults["two_stage_return"],
        ),
        patch("poliloom.enrichment.store_extracted_data", return_value=True),
        patch("poliloom.enrichment.AsyncOpenAI", return_value=AsyncMock()),
    )


class TestProcessArchivedPage:
    """Test process_archived_page pipeline."""

    @pytest.mark.asyncio
    async def test_happy_path_sets_done(
        self, db_session, sample_politician, pending_archived_page
    ):
        patches = _patch_happy_path()
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7],
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error is None

    @pytest.mark.asyncio
    async def test_fetch_error_sets_error_type(
        self, db_session, sample_politician, pending_archived_page
    ):
        with patch(
            "poliloom.enrichment.fetch_page",
            AsyncMock(
                side_effect=PageFetchError(
                    "HTTP 404", http_status_code=404, error_type="FETCH_ERROR"
                )
            ),
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error == ArchivedPageError.FETCH_ERROR
        assert pending_archived_page.http_status_code == 404

    @pytest.mark.asyncio
    async def test_timeout_error(
        self, db_session, sample_politician, pending_archived_page
    ):
        with patch(
            "poliloom.enrichment.fetch_page",
            AsyncMock(side_effect=PageFetchError("Timeout", error_type="TIMEOUT")),
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error == ArchivedPageError.TIMEOUT

    @pytest.mark.asyncio
    async def test_no_response_error(
        self, db_session, sample_politician, pending_archived_page
    ):
        with patch(
            "poliloom.enrichment.fetch_page",
            AsyncMock(
                side_effect=PageFetchError("No response", error_type="NO_RESPONSE")
            ),
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error == ArchivedPageError.NO_RESPONSE

    @pytest.mark.asyncio
    async def test_generic_exception_sets_pipeline_error(
        self, db_session, sample_politician, pending_archived_page
    ):
        with patch(
            "poliloom.enrichment.fetch_page",
            AsyncMock(side_effect=RuntimeError("unexpected crash")),
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error == ArchivedPageError.PIPELINE_ERROR

    @pytest.mark.asyncio
    async def test_no_html_content_sets_invalid_content(
        self, db_session, sample_politician, pending_archived_page
    ):
        patches = _patch_happy_path(html_content=None)
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7],
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error == ArchivedPageError.INVALID_CONTENT

    @pytest.mark.asyncio
    async def test_empty_text_sets_invalid_content(
        self, db_session, sample_politician, pending_archived_page
    ):
        patches = _patch_happy_path(html_content="<html><body>   </body></html>")
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7],
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.status == ArchivedPageStatus.DONE
        assert pending_archived_page.error == ArchivedPageError.INVALID_CONTENT

    @pytest.mark.asyncio
    async def test_permanent_url_extracted_for_wikipedia(
        self,
        db_session,
        sample_politician,
        pending_archived_page,
        sample_wikipedia_project,
    ):
        pending_archived_page.wikipedia_project_id = (
            sample_wikipedia_project.wikidata_id
        )
        db_session.flush()

        permanent_url = "https://en.wikipedia.org/w/index.php?title=Test&oldid=123"
        patches = _patch_happy_path(permanent_url=permanent_url)
        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7],
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert pending_archived_page.permanent_url == permanent_url
        assert pending_archived_page.status == ArchivedPageStatus.DONE

    @pytest.mark.asyncio
    async def test_status_transitions_to_processing(
        self, db_session, sample_politician, pending_archived_page
    ):
        """Status should be PROCESSING when fetch is called."""
        observed_status = None

        async def capture_status(url):
            nonlocal observed_status
            observed_status = pending_archived_page.status
            return FetchedPage(mhtml="<mhtml>", html="<html><body>text</body></html>")

        patches = _patch_happy_path()
        with (
            patch("poliloom.enrichment.fetch_page", side_effect=capture_status),
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patches[7],
        ):
            await process_archived_page(
                db_session, pending_archived_page, sample_politician
            )

        assert observed_status == ArchivedPageStatus.PROCESSING
