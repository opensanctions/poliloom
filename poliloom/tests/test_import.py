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
from poliloom.models import Politician, Property, Position, HoldsPosition, Source, Country


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
            # Create a function that returns appropriate responses based on the request
            def mock_api_call(*args, **kwargs):
                url = args[0] if args else ""
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
        assert politician.is_deceased is False
        
        # Verify properties were created (including citizenships)
        properties = test_session.query(Property).filter_by(politician_id=politician.id).all()
        assert len(properties) == 3  # BirthDate, BirthPlace, Citizenship
        prop_types = {prop.type: prop.value for prop in properties}
        assert prop_types['BirthDate'] == '1970-01-15'
        assert prop_types['BirthPlace'] == 'New York City'
        assert prop_types['Citizenship'] == 'US'
        
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
        assert politician.is_deceased is False
    
    def test_create_properties_skips_empty_values(self, import_service, test_session, 
                                                sample_politician):
        """Test that empty property values are skipped."""
        properties = [
            {'type': 'BirthDate', 'value': '1970-01-15'},
            {'type': 'BirthPlace', 'value': ''},  # Empty value
            {'type': 'DeathDate', 'value': None}  # None value
        ]
        
        import_service._create_properties(test_session, sample_politician, properties)
        test_session.flush()
        
        created_props = test_session.query(Property).filter_by(
            politician_id=sample_politician.id
        ).all()
        
        assert len(created_props) == 1
        assert created_props[0].type == 'BirthDate'
        assert created_props[0].value == '1970-01-15'
    
    def test_create_multiple_citizenships(self, import_service, test_session, sample_politician):
        """Test that multiple citizenships are created as separate properties."""
        properties = [
            {'type': 'Citizenship', 'value': 'US'},
            {'type': 'Citizenship', 'value': 'CA'},
            {'type': 'BirthDate', 'value': '1970-01-15'}
        ]
        
        import_service._create_properties(test_session, sample_politician, properties)
        test_session.flush()
        
        created_props = test_session.query(Property).filter_by(
            politician_id=sample_politician.id
        ).all()
        
        assert len(created_props) == 3
        
        # Check citizenship properties
        citizenship_props = [prop for prop in created_props if prop.type == 'Citizenship']
        assert len(citizenship_props) == 2
        citizenship_values = {prop.value for prop in citizenship_props}
        assert 'US' in citizenship_values
        assert 'CA' in citizenship_values
    
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


class TestCountryImport:
    """Test country import functionality."""
    
    @pytest.fixture
    def mock_countries_sparql_response(self):
        """Mock SPARQL response for countries."""
        return load_json_fixture("wikidata_countries_sparql_response.json")
    
    def test_get_all_countries_success(self, mock_countries_sparql_response):
        """Test successful countries retrieval from Wikidata."""
        wikidata_client = WikidataClient()
        
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_countries_sparql_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = wikidata_client.get_all_countries()
            
            assert result is not None
            assert len(result) == 3
            
            # Check first country (USA)
            usa = result[0]
            assert usa['wikidata_id'] == 'Q30'
            assert usa['name'] == 'United States of America'
            assert usa['iso_code'] == 'US'
            
            # Check second country (Canada)
            canada = result[1]
            assert canada['wikidata_id'] == 'Q16'
            assert canada['name'] == 'Canada'
            assert canada['iso_code'] == 'CA'
            
            # Check third country (France - no ISO code in response)
            france = result[2]
            assert france['wikidata_id'] == 'Q142'
            assert france['name'] == 'France'
            assert france['iso_code'] is None
    
    def test_get_all_countries_network_error(self):
        """Test handling of network errors when fetching countries."""
        wikidata_client = WikidataClient()
        
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_get.side_effect = httpx.RequestError("Network error")
            
            result = wikidata_client.get_all_countries()
            
            assert result == []
    
    def test_import_all_countries_success(self, test_session, mock_countries_sparql_response):
        """Test successful import of all countries."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        # Mock the SPARQL response data
        countries_data = [
            {'wikidata_id': 'Q30', 'name': 'United States of America', 'iso_code': 'US'},
            {'wikidata_id': 'Q16', 'name': 'Canada', 'iso_code': 'CA'},
            {'wikidata_id': 'Q142', 'name': 'France', 'iso_code': None}
        ]
        mock_wikidata_client.get_all_countries.return_value = countries_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_all_countries()
        
        assert result == 3
        mock_wikidata_client.get_all_countries.assert_called_once()
        
        # Verify countries were created
        countries = test_session.query(Country).all()
        assert len(countries) == 3
        
        # Check USA
        usa = test_session.query(Country).filter_by(wikidata_id='Q30').first()
        assert usa is not None
        assert usa.name == 'United States of America'
        assert usa.iso_code == 'US'
        
        # Check Canada
        canada = test_session.query(Country).filter_by(wikidata_id='Q16').first()
        assert canada is not None
        assert canada.name == 'Canada'
        assert canada.iso_code == 'CA'
        
        # Check France (no ISO code)
        france = test_session.query(Country).filter_by(wikidata_id='Q142').first()
        assert france is not None
        assert france.name == 'France'
        assert france.iso_code is None
    
    def test_import_all_countries_skip_existing(self, test_session, sample_country):
        """Test that existing countries are skipped during import."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        # Store the wikidata_id and name before the session is mocked
        existing_wikidata_id = sample_country.wikidata_id
        existing_name = sample_country.name
        
        # Mock data that includes existing country
        countries_data = [
            {'wikidata_id': existing_wikidata_id, 'name': 'Updated Name', 'iso_code': 'US'},
            {'wikidata_id': 'Q16', 'name': 'Canada', 'iso_code': 'CA'}
        ]
        mock_wikidata_client.get_all_countries.return_value = countries_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_all_countries()
        
        # Should only import 1 new country (Canada), skip existing one
        assert result == 1
        
        # Verify only 2 countries total exist
        countries = test_session.query(Country).all()
        assert len(countries) == 2
        
        # Verify existing country wasn't updated
        existing = test_session.query(Country).filter_by(wikidata_id=existing_wikidata_id).first()
        assert existing.name == existing_name  # Original name, not "Updated Name"
    
    def test_import_all_countries_wikidata_error(self, test_session):
        """Test handling of Wikidata client errors."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        mock_wikidata_client.get_all_countries.return_value = None
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_all_countries()
        
        assert result == 0
        
        # Verify no countries were created
        countries = test_session.query(Country).all()
        assert len(countries) == 0
    
    def test_import_all_countries_database_error(self, test_session):
        """Test handling of database errors during country import."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        countries_data = [
            {'wikidata_id': 'Q30', 'name': 'United States', 'iso_code': 'US'}
        ]
        mock_wikidata_client.get_all_countries.return_value = countries_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            # Mock a database error during commit
            with patch.object(test_session, 'commit', side_effect=Exception("Database error")):
                result = import_service.import_all_countries()
        
        assert result == 0
        
        # Verify rollback occurred - no countries should exist
        countries = test_session.query(Country).all()
        assert len(countries) == 0
    
    def test_import_all_countries_batch_commit(self, test_session):
        """Test that countries are committed in batches."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        # Create 250 countries to test batch committing (batch size is 100)
        countries_data = [
            {'wikidata_id': f'Q{i}', 'name': f'Country {i}', 'iso_code': f'C{i:02d}'}
            for i in range(1, 251)
        ]
        mock_wikidata_client.get_all_countries.return_value = countries_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            # Track commits
            original_commit = test_session.commit
            commit_count = 0
            
            def count_commits():
                nonlocal commit_count
                commit_count += 1
                return original_commit()
            
            with patch.object(test_session, 'commit', side_effect=count_commits):
                result = import_service.import_all_countries()
        
        assert result == 250
        
        # Should commit 3 times: after 100, after 200, and final commit
        assert commit_count >= 3
        
        # Verify all countries were created
        countries = test_session.query(Country).all()
        assert len(countries) == 250


class TestPositionImport:
    """Test position import functionality."""
    
    @pytest.fixture
    def mock_positions_sparql_response(self):
        """Mock SPARQL response for positions."""
        return load_json_fixture("wikidata_positions_sparql_response.json")
    
    def test_get_all_positions_success(self, mock_positions_sparql_response):
        """Test successful positions retrieval from Wikidata."""
        wikidata_client = WikidataClient()
        
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_positions_sparql_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = wikidata_client.get_all_positions()
            
            assert result is not None
            assert len(result) == 4
            
            # Check first position (President)
            president = result[0]
            assert president['wikidata_id'] == 'Q11696'
            assert president['name'] == 'President of the United States'
            
            # Check second position (Representative)
            rep = result[1]
            assert rep['wikidata_id'] == 'Q13218630'
            assert rep['name'] == 'United States representative'
            
            # Check third position (Senator)
            senator = result[2]
            assert senator['wikidata_id'] == 'Q4416090'
            assert senator['name'] == 'United States senator'
            
            # Check fourth position (Minister)
            minister = result[3]
            assert minister['wikidata_id'] == 'Q83307'
            assert minister['name'] == 'minister'
    
    def test_get_all_positions_network_error(self):
        """Test handling of network errors when fetching positions."""
        wikidata_client = WikidataClient()
        
        with patch.object(wikidata_client.session, 'get') as mock_get:
            mock_get.side_effect = httpx.RequestError("Network error")
            
            result = wikidata_client.get_all_positions()
            
            assert result == []
    
    def test_import_all_positions_success(self, test_session, mock_positions_sparql_response):
        """Test successful import of all positions."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        # Mock the SPARQL response data
        positions_data = [
            {'wikidata_id': 'Q11696', 'name': 'President of the United States'},
            {'wikidata_id': 'Q13218630', 'name': 'United States representative'},
            {'wikidata_id': 'Q4416090', 'name': 'United States senator'},
            {'wikidata_id': 'Q83307', 'name': 'minister'}
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_all_positions()
        
        assert result == 4
        mock_wikidata_client.get_all_positions.assert_called_once()
        
        # Verify positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 4
        
        # Check President position
        president = test_session.query(Position).filter_by(wikidata_id='Q11696').first()
        assert president is not None
        assert president.name == 'President of the United States'
        assert president.country_id is None  # Should be None initially
        
        # Check Representative position
        rep = test_session.query(Position).filter_by(wikidata_id='Q13218630').first()
        assert rep is not None
        assert rep.name == 'United States representative'
        assert rep.country_id is None
        
        # Check Senator position
        senator = test_session.query(Position).filter_by(wikidata_id='Q4416090').first()
        assert senator is not None
        assert senator.name == 'United States senator'
        assert senator.country_id is None
        
        # Check Minister position
        minister = test_session.query(Position).filter_by(wikidata_id='Q83307').first()
        assert minister is not None
        assert minister.name == 'minister'
        assert minister.country_id is None
    
    def test_import_all_positions_skip_existing(self, test_session, sample_position):
        """Test that existing positions are skipped during import."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        # Store the wikidata_id and name before the session is mocked
        existing_wikidata_id = sample_position.wikidata_id
        existing_name = sample_position.name
        
        # Mock data that includes existing position
        positions_data = [
            {'wikidata_id': existing_wikidata_id, 'name': 'Updated Position Name'},
            {'wikidata_id': 'Q11696', 'name': 'President of the United States'}
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_all_positions()
        
        # Should only import 1 new position, skip existing one
        assert result == 1
        
        # Verify only 2 positions total exist
        positions = test_session.query(Position).all()
        assert len(positions) == 2
        
        # Verify existing position wasn't updated
        existing = test_session.query(Position).filter_by(wikidata_id=existing_wikidata_id).first()
        assert existing.name == existing_name  # Original name, not "Updated Position Name"
    
    def test_import_all_positions_wikidata_error(self, test_session):
        """Test handling of Wikidata client errors."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        mock_wikidata_client.get_all_positions.return_value = None
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            result = import_service.import_all_positions()
        
        assert result == 0
        
        # Verify no positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 0
    
    def test_import_all_positions_database_error(self, test_session):
        """Test handling of database errors during position import."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        positions_data = [
            {'wikidata_id': 'Q11696', 'name': 'President of the United States'}
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            # Mock a database error during commit
            with patch.object(test_session, 'commit', side_effect=Exception("Database error")):
                result = import_service.import_all_positions()
        
        assert result == 0
        
        # Verify rollback occurred - no positions should exist
        positions = test_session.query(Position).all()
        assert len(positions) == 0
    
    def test_import_all_positions_batch_commit(self, test_session):
        """Test that positions are committed in batches."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        
        # Create 250 positions to test batch committing (batch size is 100)
        positions_data = [
            {'wikidata_id': f'Q{i}', 'name': f'Position {i}'}
            for i in range(1, 251)
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client
        
        with patch('poliloom.services.import_service.SessionLocal', return_value=test_session):
            # Track commits
            original_commit = test_session.commit
            commit_count = 0
            
            def count_commits():
                nonlocal commit_count
                commit_count += 1
                return original_commit()
            
            with patch.object(test_session, 'commit', side_effect=count_commits):
                result = import_service.import_all_positions()
        
        assert result == 250
        
        # Should commit 3 times: after 100, after 200, and final commit
        assert commit_count >= 3
        
        # Verify all positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 250