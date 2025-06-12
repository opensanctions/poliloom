"""Tests for ImportService core functionality."""
import pytest
from unittest.mock import Mock, patch

from poliloom.services.import_service import ImportService
from poliloom.services.wikidata import WikidataClient
from poliloom.models import Politician, Property, Position, HoldsPosition, Source
from .conftest import load_json_fixture


class TestImportService:
    """Test ImportService core functionality."""
    
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