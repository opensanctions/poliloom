"""Tests for POST /politicians/{qid}/sources endpoint."""

from unittest.mock import patch, AsyncMock

from poliloom.models import Source, SourceStatus


class TestCreateSource:
    """Test the POST /politicians/{qid}/sources endpoint."""

    def test_requires_authentication(self, client, sample_politician):
        response = client.post(
            f"/politicians/{sample_politician.wikidata_id}/sources",
            json={"url": "https://example.com"},
        )
        assert response.status_code in [401, 403]

    def test_not_found_for_unknown_qid(self, client, mock_auth):
        response = client.post(
            "/politicians/Q999999999/sources",
            json={"url": "https://example.com"},
            headers=mock_auth,
        )
        assert response.status_code == 404

    @patch("poliloom.api.politicians.process_source_task", new_callable=AsyncMock)
    def test_creates_source(
        self, mock_process, client, mock_auth, db_session, sample_politician
    ):
        """Test that a source is created and linked to the politician."""
        response = client.post(
            f"/politicians/{sample_politician.wikidata_id}/sources",
            json={"url": "https://example.com/article"},
            headers=mock_auth,
        )
        assert response.status_code == 202
        data = response.json()
        assert data["url"] == "https://example.com/article"
        assert data["status"] == "processing"

        # Verify the page exists in DB with correct attributes
        page = db_session.get(Source, data["id"])
        assert page is not None
        assert page.status == SourceStatus.PROCESSING
        assert page.user_id == "12345"  # from mock_auth fixture

    @patch("poliloom.api.politicians.process_source_task", new_callable=AsyncMock)
    def test_links_page_to_politician(
        self, mock_process, client, mock_auth, db_session, sample_politician
    ):
        """Test that the source is linked to the politician."""
        response = client.post(
            f"/politicians/{sample_politician.wikidata_id}/sources",
            json={"url": "https://example.com/article"},
            headers=mock_auth,
        )
        assert response.status_code == 202

        db_session.refresh(sample_politician)
        page_urls = [p.url for p in sample_politician.sources]
        assert "https://example.com/article" in page_urls

    @patch("poliloom.api.politicians.process_source_task", new_callable=AsyncMock)
    def test_fires_background_task(
        self, mock_process, client, mock_auth, db_session, sample_politician
    ):
        """Test that process_source_task is launched as a background task."""
        response = client.post(
            f"/politicians/{sample_politician.wikidata_id}/sources",
            json={"url": "https://example.com/article"},
            headers=mock_auth,
        )
        assert response.status_code == 202

        # asyncio.create_task calls process_source_task with source_id and politician_id
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        # First arg is source_id (UUID), second is politician_id
        assert call_args[0][1] == sample_politician.id
