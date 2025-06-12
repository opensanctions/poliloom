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
    
    def test_get_politician_by_id_success(self, wikidata_client, mock_politician_response, 
                                         mock_place_response, mock_position_response, 
                                         mock_country_response):
        """Test successful politician data retrieval."""
        with patch.object(wikidata_client.session, 'get') as mock_get:
            # Create a function that returns appropriate responses based on the request
            def mock_api_call(*args, **kwargs):
                params = kwargs.get('params', {})
                entity_ids = params.get('ids', '')
                
                mock_response = Mock()
                mock_response.raise_for_status = Mock()
                
                if entity_ids == "Q123456":
                    mock_response.json.return_value = mock_politician_response
                elif entity_ids == "Q60":
                    mock_response.json.return_value = mock_place_response
                elif entity_ids == "Q30":
                    mock_response.json.return_value = mock_country_response
                elif entity_ids == "Q30185":
                    mock_response.json.return_value = mock_position_response
                else:
                    # Default response for any other entities
                    mock_response.json.return_value = {"entities": {}}
                
                return mock_response
            
            mock_get.side_effect = mock_api_call
            
            result = wikidata_client.get_politician_by_id("Q123456")
            
            assert result is not None
            assert result['wikidata_id'] == 'Q123456'
            assert result['name'] == 'John Doe'
            assert result['is_deceased'] is False
            
            # Check properties structure
            prop_dict = {prop['type']: prop['value'] for prop in result['properties']}
            assert prop_dict.get('BirthDate') == '1970-01-15'
            assert prop_dict.get('BirthPlace') == 'New York City'
            assert 'Citizenship' in prop_dict
            assert len(result['positions']) == 1
            assert result['positions'][0]['name'] == 'mayor'
            assert result['positions'][0]['start_date'] == '2020'
            assert result['positions'][0]['end_date'] == '2024'
            assert len(result['wikipedia_links']) == 2
    
    def test_get_politician_by_id_not_found(self, wikidata_client):
        """Test handling of non-existent politician ID."""
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"entities": {}}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = wikidata_client.get_politician_by_id("Q999999")
            
            assert result is None
    
    def test_get_politician_by_id_not_human(self, wikidata_client):
        """Test rejection of non-human entities."""
        non_human_response = load_json_fixture("wikidata_non_human_response.json")
        
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = non_human_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = wikidata_client.get_politician_by_id("Q123456")
            
            assert result is None
    
    def test_get_politician_by_id_not_politician(self, wikidata_client):
        """Test rejection of non-politician humans."""
        non_politician_response = load_json_fixture("wikidata_non_politician_response.json")
        
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = non_politician_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = wikidata_client.get_politician_by_id("Q123456")
            
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