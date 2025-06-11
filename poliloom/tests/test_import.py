"""Tests for Wikidata import functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
import json
import os
from datetime import datetime
from pathlib import Path

from poliloom.services.import_service import ImportService
from poliloom.services.wikidata import WikidataClient
from poliloom.models import Politician, Property, Position, HoldsPosition, Source


def load_json_fixture(filename):
    """Load a JSON fixture file."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / filename, 'r') as f:
        return json.load(f)


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
            # Configure mock responses for different API calls in correct order:
            # 1. Main entity, 2. Birth place, 3. Country, 4. Position
            mock_responses = [
                Mock(json=lambda: mock_politician_response),  # Main entity
                Mock(json=lambda: mock_place_response),       # Birth place (Q60)
                Mock(json=lambda: mock_country_response),     # Country (Q30)
                Mock(json=lambda: mock_position_response),    # Position (Q30185)
            ]
            
            for response in mock_responses:
                response.raise_for_status = Mock()
            
            mock_get.side_effect = mock_responses
            
            result = wikidata_client.get_politician_by_id("Q123456")
            
            assert result is not None
            assert result['wikidata_id'] == 'Q123456'
            assert result['name'] == 'John Doe'
            assert result['country'] == 'US'
            assert result['is_deceased'] is False
            assert result['properties']['BirthDate'] == '1970-01-15'
            assert result['properties']['BirthPlace'] == 'New York City'
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


class TestImportService:
    """Test ImportService functionality."""
    
    @pytest.fixture
    def mock_wikidata_client(self):
        """Create a mock WikidataClient."""
        return Mock(spec=WikidataClient)
    
    @pytest.fixture
    def import_service(self, mock_wikidata_client):
        """Create ImportService with mocked WikidataClient."""
        service = ImportService()
        service.wikidata_client = mock_wikidata_client
        return service
    
    @pytest.fixture
    def sample_politician_data(self):
        """Sample politician data as returned by WikidataClient."""
        return load_json_fixture("sample_politician_data.json")
    
    def test_import_politician_by_id_success(self, import_service, test_session, 
                                           sample_politician_data, mock_wikidata_client):
        """Test successful politician import."""
        mock_wikidata_client.get_politician_by_id.return_value = sample_politician_data
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_politician_by_id("Q123456")
        
        assert result is not None
        mock_wikidata_client.get_politician_by_id.assert_called_once_with("Q123456")
        
        # Verify politician was created
        politician = test_session.query(Politician).filter_by(wikidata_id="Q123456").first()
        assert politician is not None
        assert politician.name == "John Doe"
        assert politician.country == "US"
        assert politician.is_deceased is False
        
        # Verify properties were created
        properties = test_session.query(Property).filter_by(politician_id=politician.id).all()
        assert len(properties) == 2
        prop_types = {prop.type: prop.value for prop in properties}
        assert prop_types['BirthDate'] == '1970-01-15'
        assert prop_types['BirthPlace'] == 'New York City'
        
        # Verify position was created
        position = test_session.query(Position).filter_by(wikidata_id="Q30185").first()
        assert position is not None
        assert position.name == "mayor"
        
        # Verify holds_position relationship was created
        holds_position = test_session.query(HoldsPosition).filter_by(
            politician_id=politician.id,
            position_id=position.id
        ).first()
        assert holds_position is not None
        assert holds_position.start_date == "2020"
        assert holds_position.end_date == "2024"
        assert holds_position.is_extracted is False  # From Wikidata, so confirmed
        
        # Verify source was created
        source = test_session.query(Source).filter_by(
            url="https://en.wikipedia.org/wiki/John_Doe"
        ).first()
        assert source is not None
        assert source in politician.sources
    
    def test_import_politician_already_exists(self, import_service, test_session, 
                                            sample_politician_data, mock_wikidata_client,
                                            sample_politician):
        """Test importing a politician that already exists."""
        # Set up existing politician with same wikidata_id
        sample_politician.wikidata_id = "Q123456"
        test_session.commit()
        
        mock_wikidata_client.get_politician_by_id.return_value = sample_politician_data
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_politician_by_id("Q123456")
        
        assert result == sample_politician.id
        mock_wikidata_client.get_politician_by_id.assert_called_once_with("Q123456")
        
        # Verify no duplicate was created
        politicians = test_session.query(Politician).filter_by(wikidata_id="Q123456").all()
        assert len(politicians) == 1
    
    def test_import_politician_wikidata_error(self, import_service, test_session, 
                                            mock_wikidata_client):
        """Test handling of Wikidata client errors."""
        mock_wikidata_client.get_politician_by_id.return_value = None
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_politician_by_id("Q999999")
        
        assert result is None
        mock_wikidata_client.get_politician_by_id.assert_called_once_with("Q999999")
        
        # Verify no politician was created
        politicians = test_session.query(Politician).all()
        assert len(politicians) == 0
    
    def test_import_politician_database_error(self, import_service, test_session, 
                                            sample_politician_data, mock_wikidata_client):
        """Test handling of database errors during import."""
        mock_wikidata_client.get_politician_by_id.return_value = sample_politician_data
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            # Mock a database error during commit
            with patch.object(test_session, 'commit', side_effect=Exception("Database error")):
                result = import_service.import_politician_by_id("Q123456")
        
        assert result is None
        
        # Verify rollback occurred - no politician should exist
        politicians = test_session.query(Politician).all()
        assert len(politicians) == 0
    
    def test_create_politician_with_minimal_data(self, import_service, test_session):
        """Test creating politician with minimal required data."""
        minimal_data = {
            'wikidata_id': 'Q123456',
            'name': 'John Doe'
        }
        
        politician = import_service._create_politician(test_session, minimal_data)
        test_session.flush()
        
        assert politician.name == "John Doe"
        assert politician.wikidata_id == "Q123456"
        assert politician.country is None
        assert politician.is_deceased is False
    
    def test_create_properties_skips_empty_values(self, import_service, test_session, 
                                                sample_politician):
        """Test that empty property values are skipped."""
        properties = {
            'BirthDate': '1970-01-15',
            'BirthPlace': '',  # Empty value
            'DeathDate': None  # None value
        }
        
        import_service._create_properties(test_session, sample_politician, properties)
        test_session.flush()
        
        created_props = test_session.query(Property).filter_by(
            politician_id=sample_politician.id
        ).all()
        
        assert len(created_props) == 1
        assert created_props[0].type == 'BirthDate'
        assert created_props[0].value == '1970-01-15'
    
    def test_create_positions_reuses_existing(self, import_service, test_session, 
                                            sample_politician, sample_position):
        """Test that existing positions are reused."""
        positions = [
            {
                'wikidata_id': sample_position.wikidata_id,
                'name': 'Updated Mayor Name',  # Different name, should reuse existing
                'start_date': '2020',
                'end_date': '2024'
            }
        ]
        
        import_service._create_positions(test_session, sample_politician, positions)
        test_session.flush()
        
        # Verify only one position exists
        all_positions = test_session.query(Position).all()
        assert len(all_positions) == 1
        assert all_positions[0].id == sample_position.id
        
        # Verify holds_position was created
        holds_position = test_session.query(HoldsPosition).filter_by(
            politician_id=sample_politician.id,
            position_id=sample_position.id
        ).first()
        assert holds_position is not None
    
    def test_holds_position_dates_are_set(self, import_service, test_session, 
                                        sample_politician_data, mock_wikidata_client):
        """Test that HoldsPosition start_date and end_date are properly set from Wikidata."""
        mock_wikidata_client.get_politician_by_id.return_value = sample_politician_data
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            politician_id = import_service.import_politician_by_id("Q123456")
        
        assert politician_id is not None
        
        # Get the politician
        politician = test_session.query(Politician).filter_by(id=politician_id).first()
        assert politician is not None
        
        # Get the position relationship
        holds_position = test_session.query(HoldsPosition).filter_by(
            politician_id=politician.id
        ).first()
        assert holds_position is not None
        
        # Verify dates are set correctly
        assert holds_position.start_date == "2020", f"Expected '2020', got '{holds_position.start_date}'"
        assert holds_position.end_date == "2024", f"Expected '2024', got '{holds_position.end_date}'"
        assert holds_position.start_date is not None, "start_date should not be NULL"
        assert holds_position.end_date is not None, "end_date should not be NULL"