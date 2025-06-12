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
    
    def test_get_politician_by_id_success(self, wikidata_client, mock_politician_sparql_response):
        """Test successful politician data retrieval."""
        with patch.object(wikidata_client.session, 'get') as mock_get:
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
            assert result['wikidata_id'] == 'Q123456'
            assert result['name'] == 'John Doe'
            assert result['is_deceased'] is False
            
            # Check properties structure
            prop_dict = {prop['type']: prop['value'] for prop in result['properties']}
            assert prop_dict.get('BirthDate') == '1970-01-15'
            assert prop_dict.get('BirthPlace') == 'New York City'
            assert prop_dict.get('Citizenship') == 'US'
            assert len(result['positions']) == 1
            assert result['positions'][0]['name'] == 'mayor'
            assert result['positions'][0]['start_date'] == '2020-01-01'
            assert result['positions'][0]['end_date'] == '2024-01-01'
            assert len(result['wikipedia_links']) == 2
    
    def test_get_politician_by_id_not_found(self, wikidata_client):
        """Test handling of non-existent politician ID."""
        with patch.object(wikidata_client.session, 'get') as mock_get:
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
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_get.side_effect = httpx.RequestError("Network error")
            
            result = wikidata_client.get_politician_by_id("Q123456")
            
            assert result is None
    
    def test_extract_incomplete_dates(self, wikidata_client):
        """Test extraction of incomplete dates with different precisions."""
        # Test year precision
        year_claim = [{
            "mainsnak": {
                "datavalue": {
                    "type": "time",
                    "value": {
                        "time": "+1970-00-00T00:00:00Z",
                        "precision": 9  # year precision
                    }
                }
            }
        }]
        
        result = wikidata_client._extract_date_claim(year_claim)
        assert result == "1970"
        
        # Test month precision
        month_claim = [{
            "mainsnak": {
                "datavalue": {
                    "type": "time",
                    "value": {
                        "time": "+1970-06-00T00:00:00Z",
                        "precision": 10  # month precision
                    }
                }
            }
        }]
        
        result = wikidata_client._extract_date_claim(month_claim)
        assert result == "1970-06"
        
        # Test day precision
        day_claim = [{
            "mainsnak": {
                "datavalue": {
                    "type": "time",
                    "value": {
                        "time": "+1970-06-15T00:00:00Z",
                        "precision": 11  # day precision
                    }
                }
            }
        }]
        
        result = wikidata_client._extract_date_claim(day_claim)
        assert result == "1970-06-15"