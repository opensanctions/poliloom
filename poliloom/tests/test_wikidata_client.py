"""Tests for WikidataClient functionality."""

import pytest
from unittest.mock import Mock, patch
import httpx

from poliloom.services.wikidata import WikidataClient
from .conftest import load_json_fixture


class TestWikidataClient:
    """Test WikidataClient functionality."""

    @pytest.fixture
    def wikidata_client(self):
        """Create a WikidataClient instance for testing."""
        return WikidataClient()

    @pytest.fixture
    def mock_politician_response(self):
        """Mock Wikidata API response for a politician."""
        return load_json_fixture("wikidata_politician_response.json")

    @pytest.fixture
    def mock_politician_sparql_response(self):
        """Mock SPARQL response for a politician."""
        return load_json_fixture("wikidata_politician_sparql_response.json")

    @pytest.fixture
    def mock_place_response(self):
        """Mock response for place entity."""
        return load_json_fixture("wikidata_place_response.json")

    @pytest.fixture
    def mock_position_response(self):
        """Mock response for position entity."""
        return load_json_fixture("wikidata_position_response.json")

    @pytest.fixture
    def mock_country_response(self):
        """Mock response for country entity with ISO code."""
        return load_json_fixture("wikidata_country_response.json")

    def test_get_politician_by_id_success(
        self, wikidata_client, mock_politician_sparql_response
    ):
        """Test successful politician data retrieval."""
        with patch.object(wikidata_client.session, "get") as mock_get:
            # Mock SPARQL endpoint response
            def mock_sparql_call(*args, **kwargs):
                # Check if this is a SPARQL query
                if args[0] == wikidata_client.SPARQL_ENDPOINT:
                    mock_response = Mock()
                    mock_response.raise_for_status = Mock()
                    mock_response.json.return_value = mock_politician_sparql_response
                    return mock_response
                else:
                    # Fallback for any other calls
                    mock_response = Mock()
                    mock_response.raise_for_status = Mock()
                    mock_response.json.return_value = {"entities": {}}
                    return mock_response

            mock_get.side_effect = mock_sparql_call

            result = wikidata_client.get_politician_by_id("Q123456")

            assert result is not None
            assert result["wikidata_id"] == "Q123456"
            assert result["name"] == "John Doe"
            assert result["is_deceased"] is False

            # Check properties structure
            prop_dict = {prop["type"]: prop["value"] for prop in result["properties"]}
            assert prop_dict.get("BirthDate") == "1970-01-15"

            # Check citizenships are returned separately
            assert "citizenships" in result
            assert "US" in result["citizenships"]
            assert len(result["positions"]) == 1
            assert result["positions"][0]["name"] == "mayor"
            assert result["positions"][0]["start_date"] == "2020-01-01"
            assert result["positions"][0]["end_date"] == "2024-01-01"
            assert len(result["wikipedia_links"]) == 2

    def test_get_politician_by_id_not_found(self, wikidata_client):
        """Test handling of non-existent politician ID."""
        with patch.object(wikidata_client.session, "get") as mock_get:
            # Mock empty SPARQL response (no results)
            empty_sparql_response = {"results": {"bindings": []}}
            mock_response = Mock()
            mock_response.json.return_value = empty_sparql_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = wikidata_client.get_politician_by_id("Q999999")

            assert result is None

    def test_get_politician_by_id_network_error(self, wikidata_client):
        """Test handling of network errors."""
        with patch.object(wikidata_client.session, "get") as mock_get:
            mock_get.side_effect = httpx.RequestError("Network error")

            result = wikidata_client.get_politician_by_id("Q123456")

            assert result is None

    def test_get_politician_by_id_http_status_error(self, wikidata_client):
        """Test handling of HTTP status errors like 504 Gateway Timeout."""
        with patch.object(wikidata_client.session, "get") as mock_get:
            # Create a mock response that will raise HTTPStatusError on raise_for_status()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="504 Gateway Timeout", request=Mock(), response=Mock()
            )
            mock_get.return_value = mock_response

            result = wikidata_client.get_politician_by_id("Q123456")

            assert result is None

    def test_extract_incomplete_dates(self, wikidata_client):
        """Test extraction of incomplete dates with different precisions."""
        # Load test data from fixture
        date_claims = load_json_fixture("wikidata_date_claims.json")
        expected_results = date_claims["expected_results"]
        
        # Test year precision
        result = wikidata_client._extract_date_claim(date_claims["year_precision_claim"])
        assert result == expected_results["year_precision"]

        # Test month precision
        result = wikidata_client._extract_date_claim(date_claims["month_precision_claim"])
        assert result == expected_results["month_precision"]

        # Test day precision
        result = wikidata_client._extract_date_claim(date_claims["day_precision_claim"])
        assert result == expected_results["day_precision"]
        
        # Test empty claim
        result = wikidata_client._extract_date_claim(date_claims["empty_claim"])
        assert result == expected_results["empty_claim"]
        
        # Test malformed claims
        result = wikidata_client._extract_date_claim(date_claims["malformed_claim_missing_datavalue"])
        assert result == expected_results["malformed_claims"]
        
        # Test multiple claims (should return first valid one)
        result = wikidata_client._extract_date_claim(date_claims["multiple_claims"])
        assert result == expected_results["multiple_claims"]
