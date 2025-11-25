"""Tests for enrichment module functionality."""

import pytest
from unittest.mock import Mock, patch

from poliloom.enrichment import (
    enrich_politician_from_wikipedia,
    extract_properties_generic,
    extract_two_stage_generic,
    store_extracted_data,
    count_politicians_with_unevaluated,
    enrich_batch,
    extract_permanent_url,
    _convert_mhtml_to_html,
    fetch_and_archive_page,
    ExtractedProperty,
    ExtractedPosition,
    ExtractedBirthplace,
    PropertyType,
    DATES_CONFIG,
    POSITIONS_CONFIG,
    BIRTHPLACES_CONFIG,
    FreeFormPosition,
    FreeFormPositionResult,
    FreeFormBirthplace,
    FreeFormBirthplaceResult,
)
from poliloom.models import (
    Location,
    Position,
    Property,
)


class TestEnrichment:
    """Test enrichment module functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        return Mock()

    @pytest.mark.asyncio
    async def test_extract_dates_success(self, mock_openai_client, sample_politician):
        """Test successful date extraction."""
        # Mock OpenAI response
        mock_parsed = Mock()
        mock_parsed.properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            ),
            ExtractedProperty(
                type=PropertyType.DEATH_DATE,
                value="2020-05-20",
                supporting_quotes=["died May 20, 2020"],
            ),
        ]
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed

        # Make the mock async
        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is not None
        assert len(properties) == 2
        assert properties[0].type == PropertyType.BIRTH_DATE
        assert properties[0].value == "1970-01-15"
        assert properties[1].type == PropertyType.DEATH_DATE

    @pytest.mark.asyncio
    async def test_extract_dates_none_parsed(
        self, mock_openai_client, sample_politician
    ):
        """Test date extraction when LLM returns None."""
        mock_response = Mock()
        mock_response.output_parsed = None

        # Make the mock async
        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_dates_exception(self, mock_openai_client, sample_politician):
        """Test date extraction handles exceptions."""

        # Make the mock async and raise exception
        async def mock_parse(*args, **kwargs):
            raise Exception("API Error")

        mock_openai_client.responses.parse = mock_parse

        properties = await extract_properties_generic(
            mock_openai_client, "test content", sample_politician, DATES_CONFIG
        )

        assert properties is None

    @pytest.mark.asyncio
    async def test_extract_positions_success(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test successful position extraction and mapping."""
        # Create position in database
        position = Position.create_with_entity(db_session, "Q30185", "Test Position")
        position.embedding = [0.1] * 384
        db_session.flush()

        # Mock Stage 1: Free-form extraction (using actual model from enrichment)
        mock_parsed1 = FreeFormPositionResult(
            positions=[
                FreeFormPosition(
                    name="Mayor of Springfield",
                    start_date="2020",
                    end_date="2024",
                    supporting_quotes=["served as Mayor from 2020 to 2024"],
                )
            ]
        )
        # Mock Stage 2: Mapping
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_position_qid = "Q30185"

        mock_response1 = Mock()
        mock_response1.output_parsed = mock_parsed1
        mock_response2 = Mock()
        mock_response2.output_parsed = mock_parsed2

        # Make the mock async with side_effect
        call_count = [0]

        async def mock_parse(*args, **kwargs):
            result = [mock_response1, mock_response2][call_count[0]]
            call_count[0] += 1
            return result

        mock_openai_client.responses.parse = mock_parse

        positions = await extract_two_stage_generic(
            mock_openai_client,
            db_session,
            "test content",
            sample_politician,
            POSITIONS_CONFIG,
        )

        assert positions is not None
        assert len(positions) == 1
        assert positions[0].wikidata_id == "Q30185"
        assert positions[0].start_date == "2020"
        assert positions[0].end_date == "2024"

    @pytest.mark.asyncio
    async def test_extract_positions_no_results(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test position extraction with no results."""
        mock_parsed = Mock()
        mock_parsed.positions = []
        mock_response = Mock()
        mock_response.output_parsed = mock_parsed

        # Make the mock async
        async def mock_parse(*args, **kwargs):
            return mock_response

        mock_openai_client.responses.parse = mock_parse

        positions = await extract_two_stage_generic(
            mock_openai_client,
            db_session,
            "test content",
            sample_politician,
            POSITIONS_CONFIG,
        )

        assert positions == []

    @pytest.mark.asyncio
    async def test_extract_birthplaces_success(
        self, mock_openai_client, db_session, sample_politician
    ):
        """Test successful birthplace extraction and mapping."""
        # Create location in database with labels for fuzzy search
        Location.create_with_entity(
            db_session,
            "Q28513",
            "Springfield, Illinois",
            labels=["Springfield, Illinois", "Springfield"],
        )
        db_session.flush()

        # Mock Stage 1: Free-form extraction (using actual model from enrichment)
        mock_parsed1 = FreeFormBirthplaceResult(
            birthplaces=[
                FreeFormBirthplace(
                    name="Springfield, Illinois",
                    supporting_quotes=["born in Springfield, Illinois"],
                )
            ]
        )
        # Mock Stage 2: Mapping
        mock_parsed2 = Mock()
        mock_parsed2.wikidata_location_qid = "Q28513"

        mock_response1 = Mock()
        mock_response1.output_parsed = mock_parsed1
        mock_response2 = Mock()
        mock_response2.output_parsed = mock_parsed2

        # Make the mock async with side_effect
        call_count = [0]

        async def mock_parse(*args, **kwargs):
            result = [mock_response1, mock_response2][call_count[0]]
            call_count[0] += 1
            return result

        mock_openai_client.responses.parse = mock_parse

        # No embedding mock needed - locations use pg_trgm fuzzy search
        birthplaces = await extract_two_stage_generic(
            mock_openai_client,
            db_session,
            "test content",
            sample_politician,
            BIRTHPLACES_CONFIG,
        )

        assert birthplaces is not None
        assert len(birthplaces) == 1
        assert birthplaces[0].wikidata_id == "Q28513"

    def test_store_extracted_data_properties(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
        sample_wikipedia_link,
        create_citizenship,
    ):
        """Test storing extracted properties."""
        # Add citizenship as Property (Wikipedia link already created by fixture)
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            properties,
            None,  # positions
            None,  # birthplaces
            None,  # citizenships
        )

        assert success is True

        # Verify property was stored
        property_obj = (
            db_session.query(Property)
            .filter_by(politician_id=sample_politician.id, type=PropertyType.BIRTH_DATE)
            .first()
        )
        assert property_obj is not None
        assert property_obj.value == "+1970-01-15T00:00:00Z"
        assert property_obj.value_precision == 11  # Day precision
        assert property_obj.archived_page_id == sample_archived_page.id

    def test_store_extracted_data_positions(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
        sample_position,
        sample_wikipedia_link,
        create_citizenship,
    ):
        """Test storing extracted positions."""
        # Add citizenship as Property (Wikipedia link created by sample_wikipedia_link fixture)
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        positions = [
            ExtractedPosition(
                wikidata_id="Q30185",
                start_date="2020",
                end_date="2024",
                supporting_quotes=["served as Mayor"],
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            None,  # properties
            positions,
            None,  # birthplaces
            None,  # citizenships
        )

        assert success is True

        # Verify position was stored as Property
        position_property = (
            db_session.query(Property)
            .filter_by(
                politician_id=sample_politician.id,
                type=PropertyType.POSITION,
                entity_id=sample_position.wikidata_id,
            )
            .first()
        )
        assert position_property is not None
        assert position_property.qualifiers_json is not None
        assert "P580" in position_property.qualifiers_json  # start time
        assert "P582" in position_property.qualifiers_json  # end time

    def test_store_extracted_data_birthplaces(
        self,
        db_session,
        sample_location,
        sample_archived_page,
        sample_country,
        sample_politician,
        create_citizenship,
    ):
        """Test storing extracted birthplaces."""
        # Add citizenship as Property
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        birthplaces = [
            ExtractedBirthplace(
                wikidata_id="Q28513", supporting_quotes=["born in Springfield"]
            )
        ]

        success = store_extracted_data(
            db_session,
            sample_politician,
            sample_archived_page,
            None,  # properties
            None,  # positions
            birthplaces,
            None,  # citizenships
        )

        assert success is True

        # Verify birthplace was stored as Property
        birthplace_property = (
            db_session.query(Property)
            .filter_by(
                politician_id=sample_politician.id,
                type=PropertyType.BIRTHPLACE,
                entity_id=sample_location.wikidata_id,
            )
            .first()
        )
        assert birthplace_property is not None
        assert birthplace_property.archived_page_id == sample_archived_page.id

    def test_store_extracted_data_error_handling(
        self,
        db_session,
        sample_archived_page,
        sample_country,
        sample_politician,
    ):
        """Test error handling in store_extracted_data."""

        properties = [
            ExtractedProperty(
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                supporting_quotes=["born January 15, 1970"],
            )
        ]

        # Mock the session to raise an exception during add
        with patch.object(db_session, "add", side_effect=Exception("Database error")):
            success = store_extracted_data(
                db_session,
                sample_politician,
                sample_archived_page,
                properties,
                None,
                None,
                None,  # citizenships
            )

        assert success is False

    @pytest.mark.asyncio
    async def test_enrich_politician_no_wikipedia_links(
        self, db_session, sample_politician
    ):
        """Test enrichment when no politicians have Wikipedia links."""
        # The sample_politician fixture by default has no Wikipedia links
        # The function should filter these out and return False

        with patch("poliloom.enrichment.AsyncOpenAI"):
            politician_found = await enrich_politician_from_wikipedia()

        # Should find no politicians to enrich since they're filtered out by the query
        assert politician_found is False

        # The enriched_at timestamp should remain None since the politician was never processed
        db_session.refresh(sample_politician)
        assert sample_politician.enriched_at is None


class TestCountPoliticiansWithUnevaluated:
    """Test count_politicians_with_unevaluated function."""

    def test_count_with_unevaluated_properties(
        self, db_session, sample_politician, sample_archived_page, create_birth_date
    ):
        """Test counting politicians with unevaluated properties."""
        # Add unevaluated property
        create_birth_date(sample_politician, archived_page=sample_archived_page)
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session)
        assert count == 1

    def test_count_excludes_evaluated_properties(
        self, db_session, sample_politician, sample_archived_page, create_birth_date
    ):
        """Test that count excludes properties with statement_id."""
        # Add property with statement_id
        create_birth_date(
            sample_politician,
            archived_page=sample_archived_page,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.flush()

        count = count_politicians_with_unevaluated(db_session)
        assert count == 0

    def test_count_with_language_filter(
        self,
        db_session,
        sample_politician,
        sample_language,
        create_archived_page,
        create_birth_date,
    ):
        """Test counting with language filter."""
        # Create English archived page
        en_page = create_archived_page(
            url="https://en.example.com/test",
            content_hash="en123",
            languages=[sample_language],
        )

        # Add English property
        create_birth_date(sample_politician, archived_page=en_page)
        db_session.flush()

        # Count with English filter
        count = count_politicians_with_unevaluated(db_session, languages=["Q1860"])
        assert count == 1

        # Count with different language filter
        count = count_politicians_with_unevaluated(db_session, languages=["Q188"])
        assert count == 0

    def test_count_with_country_filter(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_archived_page,
        create_citizenship,
        create_birth_date,
    ):
        """Test counting with country filter."""
        # Add citizenship and unevaluated property
        create_citizenship(sample_politician, sample_country, sample_archived_page)
        create_birth_date(sample_politician, archived_page=sample_archived_page)
        db_session.flush()

        # Count with USA filter
        count = count_politicians_with_unevaluated(db_session, countries=["Q30"])
        assert count == 1

        # Count with different country filter
        count = count_politicians_with_unevaluated(db_session, countries=["Q183"])
        assert count == 0


class TestEnrichBatch:
    """Test enrich_batch function."""

    def test_enrich_batch_enriches_n_politicians(
        self, db_session, sample_politician, sample_wikipedia_link, sample_archived_page
    ):
        """Test enriching a batch of politicians."""
        # Mock the enrichment process
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                return True  # politician_found

            mock_enrich.side_effect = mock_enrich_func

            # Mock env var for batch size
            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "3"}):
                enriched_count = enrich_batch()

        assert enriched_count == 3
        assert mock_enrich.call_count == 3

    def test_enrich_batch_no_more_politicians(self, db_session):
        """Test when no more politicians available to enrich."""
        # No politicians in database
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:
            # Mock returns False indicating no politicians to enrich
            async def mock_enrich_func(languages=None, countries=None):
                return False

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "5"}):
                enriched_count = enrich_batch()

        assert enriched_count == 0
        # Should only call once, then break
        assert mock_enrich.call_count == 1

    def test_enrich_batch_with_filters(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_language,
        sample_wikipedia_link,
        sample_archived_page,
        create_citizenship,
    ):
        """Test enrich_batch with language and country filters."""
        # Add citizenship
        create_citizenship(sample_politician, sample_country)
        db_session.flush()

        # Mock enrichment
        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                return True

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "2"}):
                enriched_count = enrich_batch(languages=["Q1860"], countries=["Q30"])

        assert enriched_count == 2
        # Verify mock was called with correct filters
        mock_enrich.assert_called_with(languages=["Q1860"], countries=["Q30"])

    def test_enrich_batch_stops_early_when_no_politicians(self, db_session):
        """Test that batch stops early if politicians run out."""
        # Mock to return True twice, then False
        call_count = [0]

        with patch(
            "poliloom.enrichment.enrich_politician_from_wikipedia"
        ) as mock_enrich:

            async def mock_enrich_func(languages=None, countries=None):
                call_count[0] += 1
                return call_count[0] <= 2  # True for first 2, False after

            mock_enrich.side_effect = mock_enrich_func

            with patch.dict("os.environ", {"ENRICHMENT_BATCH_SIZE": "5"}):
                enriched_count = enrich_batch()

        assert enriched_count == 2
        assert mock_enrich.call_count == 3  # Called 3 times, but only 2 successful


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
    """Test _convert_mhtml_to_html private function."""

    def test_convert_mhtml_to_html_success(self):
        """Test successful MHTML to HTML conversion."""
        mhtml_content = "MHTML content here"
        expected_html = "<html>Converted content</html>"

        with patch("poliloom.enrichment.MHTMLConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.return_value = expected_html
            mock_converter_class.return_value = mock_converter

            result = _convert_mhtml_to_html(mhtml_content)

            assert result == expected_html
            mock_converter.convert.assert_called_once_with(mhtml_content)

    def test_convert_mhtml_to_html_none_input(self):
        """Test that None input returns None."""
        result = _convert_mhtml_to_html(None)
        assert result is None

    def test_convert_mhtml_to_html_conversion_error(self):
        """Test that conversion errors return None."""
        mhtml_content = "MHTML content"

        with patch("poliloom.enrichment.MHTMLConverter") as mock_converter_class:
            mock_converter = Mock()
            mock_converter.convert.side_effect = Exception("Conversion failed")
            mock_converter_class.return_value = mock_converter

            result = _convert_mhtml_to_html(mhtml_content)
            assert result is None


class TestFetchAndArchivePage:
    """Test fetch_and_archive_page function."""

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_success(
        self, db_session, sample_wikipedia_project
    ):
        """Test successful page fetch and archive with permanent URL extraction."""
        url = "https://en.wikipedia.org/wiki/Test_Page"
        permanent_url = "https://en.wikipedia.org/w/index.php?title=Test_Page&oldid=123"

        # Mock crawl4ai result
        mock_result = Mock()
        mock_result.success = True
        mock_result.mhtml = "MHTML content"
        mock_result.markdown = "# Markdown content"

        # Create async mock for crawler
        mock_crawler = Mock()

        # Mock arun as an async function
        async def mock_arun(*args, **kwargs):
            return mock_result

        mock_crawler.arun = mock_arun

        # Mock async context manager
        async def mock_aenter(*args):
            return mock_crawler

        async def mock_aexit(*args):
            return None

        mock_crawler.__aenter__ = mock_aenter
        mock_crawler.__aexit__ = mock_aexit

        with patch("poliloom.enrichment.AsyncWebCrawler", return_value=mock_crawler):
            with patch("poliloom.enrichment._convert_mhtml_to_html") as mock_convert:
                mock_convert.return_value = "<html>Converted</html>"

                with patch("poliloom.enrichment.extract_permanent_url") as mock_extract:
                    mock_extract.return_value = permanent_url

                    archived_page = await fetch_and_archive_page(
                        url,
                        db_session,
                        wikipedia_project_id=sample_wikipedia_project.wikidata_id,
                    )

                    # Original URL is preserved for display
                    assert archived_page.url == url
                    # Permanent URL is stored separately for references
                    assert archived_page.permanent_url == permanent_url
                    assert (
                        archived_page.wikipedia_project_id
                        == sample_wikipedia_project.wikidata_id
                    )
                    mock_extract.assert_called_once_with("<html>Converted</html>")

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_without_wikipedia_project(self, db_session):
        """Test fetch and archive without Wikipedia project."""
        url = "https://example.com/article"

        mock_result = Mock()
        mock_result.success = True
        mock_result.mhtml = "MHTML content"
        mock_result.markdown = "# Markdown content"

        # Create async mock for crawler
        mock_crawler = Mock()

        async def mock_arun(*args, **kwargs):
            return mock_result

        mock_crawler.arun = mock_arun

        async def mock_aenter(*args):
            return mock_crawler

        async def mock_aexit(*args):
            return None

        mock_crawler.__aenter__ = mock_aenter
        mock_crawler.__aexit__ = mock_aexit

        with patch("poliloom.enrichment.AsyncWebCrawler", return_value=mock_crawler):
            with patch("poliloom.enrichment._convert_mhtml_to_html") as mock_convert:
                mock_convert.return_value = "<html>Converted</html>"

                archived_page = await fetch_and_archive_page(url, db_session)

                assert archived_page.url == url
                assert archived_page.permanent_url is None
                assert archived_page.wikipedia_project_id is None

    @pytest.mark.asyncio
    async def test_fetch_and_archive_page_crawl_failure(self, db_session):
        """Test handling of crawl failure."""
        url = "https://example.com/article"

        mock_result = Mock()
        mock_result.success = False

        # Create async mock for crawler
        mock_crawler = Mock()

        async def mock_arun(*args, **kwargs):
            return mock_result

        mock_crawler.arun = mock_arun

        async def mock_aenter(*args):
            return mock_crawler

        async def mock_aexit(*args):
            return None

        mock_crawler.__aenter__ = mock_aenter
        mock_crawler.__aexit__ = mock_aexit

        with patch("poliloom.enrichment.AsyncWebCrawler", return_value=mock_crawler):
            with pytest.raises(RuntimeError, match="Failed to crawl page"):
                await fetch_and_archive_page(url, db_session)
