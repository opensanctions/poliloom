"""Tests for ImportService core functionality."""
import pytest
from unittest.mock import Mock, patch

from poliloom.services.import_service import ImportService
from poliloom.services.wikidata import WikidataClient
from poliloom.models import Politician, Property, Position, HoldsPosition, Source, Country, HasCitizenship
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
        
        # Verify properties were created (excluding citizenships)
        properties = test_session.query(Property).filter_by(politician_id=politician.id).all()
        assert len(properties) == 1  # Only BirthDate (birthplace uses BornAt relationship, citizenship uses HasCitizenship)
        prop_types = {prop.type: prop.value for prop in properties}
        assert prop_types['BirthDate'] == '1970-01-15'
        
        # Verify citizenship was created as HasCitizenship relationship
        citizenships = test_session.query(HasCitizenship).filter_by(politician_id=politician.id).all()
        assert len(citizenships) == 1
        citizenship = citizenships[0]
        assert citizenship.country.iso_code == 'US'
        
        # Verify position was NOT created (new behavior - only link to existing positions)
        position = test_session.query(Position).filter_by(wikidata_id="Q30185").first()
        assert position is None  # Position should not be created
        
        # Verify no holds_position relationship was created since position doesn't exist
        holds_position = test_session.query(HoldsPosition).filter_by(
            politician_id=politician.id
        ).first()
        assert holds_position is None  # No relationship should exist
        
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
            {'type': 'DeathDate', 'value': ''},  # Empty value
            {'type': 'BirthDate', 'value': None}  # None value (duplicate type for testing)
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
        """Test that multiple citizenships are created as separate HasCitizenship relationships."""
        properties = [
            {'type': 'BirthDate', 'value': '1970-01-15'}
        ]
        citizenships = ['US', 'CA']
        
        # Create properties
        import_service._create_properties(test_session, sample_politician, properties)
        # Create citizenship relationships
        import_service._create_citizenships(test_session, sample_politician, citizenships)
        test_session.flush()
        
        # Check that properties were created
        created_props = test_session.query(Property).filter_by(
            politician_id=sample_politician.id
        ).all()
        assert len(created_props) == 1  # Only BirthDate
        assert created_props[0].type == 'BirthDate'
        
        # Check citizenship relationships
        citizenships = test_session.query(HasCitizenship).filter_by(
            politician_id=sample_politician.id
        ).all()
        assert len(citizenships) == 2
        citizenship_countries = {c.country.iso_code for c in citizenships}
        assert 'US' in citizenship_countries
        assert 'CA' in citizenship_countries
    
    def test_link_to_existing_positions_only(self, import_service, test_session, 
                                            sample_politician, sample_position):
        """Test that politicians are only linked to existing positions."""
        positions = [
            {
                'wikidata_id': sample_position.wikidata_id,
                'name': 'Updated Mayor Name',  # Different name, should reuse existing
                'start_date': '2020',
                'end_date': '2024'
            }
        ]
        
        import_service._link_to_existing_positions(test_session, sample_politician, positions)
        test_session.flush()
        
        # Verify only one position exists (the pre-existing one)
        all_positions = test_session.query(Position).all()
        assert len(all_positions) == 1
        assert all_positions[0].id == sample_position.id
        
        # Verify holds_position was created
        holds_position = test_session.query(HoldsPosition).filter_by(
            politician_id=sample_politician.id,
            position_id=sample_position.id
        ).first()
        assert holds_position is not None
    
    def test_holds_position_dates_with_existing_position(self, import_service, test_session, 
                                        sample_politician_data, mock_wikidata_client):
        """Test that HoldsPosition dates are set when linking to existing positions."""
        # First create the position that the politician data references
        position = Position(name="mayor", wikidata_id="Q30185")
        test_session.add(position)
        test_session.flush()
        
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
    
    def test_create_citizenships_with_new_country(self, import_service, test_session, sample_politician):
        """Test that citizenships are created with new countries as needed."""
        citizenships = ['FR']  # France - new country
        
        import_service._create_citizenships(test_session, sample_politician, citizenships)
        test_session.flush()
        
        # Verify country was created
        country = test_session.query(Country).filter_by(iso_code='FR').first()
        assert country is not None
        # Note: Country name depends on whether pycountry is available
        # If not available, it falls back to the country code
        assert country.name in ['France', 'FR']  # pycountry lookup or fallback
        
        # Verify citizenship relationship was created
        citizenship = test_session.query(HasCitizenship).filter_by(
            politician_id=sample_politician.id,
            country_id=country.id
        ).first()
        assert citizenship is not None
    
    def test_create_citizenships_with_existing_country(self, import_service, test_session, sample_politician):
        """Test that citizenships reuse existing countries."""
        # Create existing country
        existing_country = Country(name="United States", iso_code="US")
        test_session.add(existing_country)
        test_session.flush()
        
        citizenships = ['US']
        
        import_service._create_citizenships(test_session, sample_politician, citizenships)
        test_session.flush()
        
        # Verify no new country was created
        countries = test_session.query(Country).filter_by(iso_code='US').all()
        assert len(countries) == 1
        assert countries[0].id == existing_country.id
        
        # Verify citizenship relationship was created
        citizenship = test_session.query(HasCitizenship).filter_by(
            politician_id=sample_politician.id,
            country_id=existing_country.id
        ).first()
        assert citizenship is not None
    
    def test_create_citizenships_prevents_duplicates(self, import_service, test_session, sample_politician):
        """Test that duplicate citizenship relationships are not created."""
        # Create country and existing citizenship
        country = Country(name="Canada", iso_code="CA")
        test_session.add(country)
        test_session.flush()
        
        existing_citizenship = HasCitizenship(
            politician_id=sample_politician.id,
            country_id=country.id
        )
        test_session.add(existing_citizenship)
        test_session.flush()
        
        citizenships = ['CA']  # Same citizenship again
        
        import_service._create_citizenships(test_session, sample_politician, citizenships)
        test_session.flush()
        
        # Verify no duplicate was created
        citizenships = test_session.query(HasCitizenship).filter_by(
            politician_id=sample_politician.id,
            country_id=country.id
        ).all()
        assert len(citizenships) == 1
        assert citizenships[0].id == existing_citizenship.id
    
    def test_get_or_create_country_with_pycountry(self, import_service, test_session):
        """Test country creation with pycountry lookup if available."""
        country = import_service._get_or_create_country(test_session, 'DE')
        test_session.flush()
        
        assert country is not None
        assert country.iso_code == 'DE'
        # Country name depends on whether pycountry is available
        assert country.name in ['Germany', 'DE']  # From pycountry or fallback
        assert country.wikidata_id is None
    
    def test_get_or_create_country_fallback_without_pycountry(self, import_service, test_session):
        """Test country creation fallback when pycountry is not available."""
        # Test with an unknown country code to verify fallback behavior
        country = import_service._get_or_create_country(test_session, 'XX')
        test_session.flush()
        
        assert country is not None
        assert country.iso_code == 'XX'
        assert country.name == 'XX'  # Should fallback to country code when pycountry unavailable
    
    def test_get_or_create_country_returns_existing(self, import_service, test_session):
        """Test that existing countries are returned instead of creating duplicates."""
        # Create existing country
        existing = Country(name="Japan", iso_code="JP")
        test_session.add(existing)
        test_session.flush()
        
        country = import_service._get_or_create_country(test_session, 'jp')  # lowercase
        
        assert country.id == existing.id
        assert country.iso_code == 'JP'
        
        # Verify no duplicate was created
        countries = test_session.query(Country).filter_by(iso_code='JP').all()
        assert len(countries) == 1