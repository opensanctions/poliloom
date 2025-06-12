"""Tests for country import functionality."""
import pytest
from unittest.mock import Mock, patch
import httpx

from poliloom.services.import_service import ImportService
from poliloom.services.wikidata import WikidataClient
from poliloom.models import Country
from .conftest import load_json_fixture


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