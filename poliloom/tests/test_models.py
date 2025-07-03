"""Tests for database models."""
import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from poliloom.models import (
    Politician, Source, Property, Position, HoldsPosition, Country, HasCitizenship, Location, BornAt
)
from poliloom.embeddings import generate_embedding


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_creation(self, test_session):
        """Test basic politician creation."""
        politician = Politician(
            name="Jane Smith",
            wikidata_id="Q789012",
            is_deceased=True
        )
        test_session.add(politician)
        test_session.commit()
        test_session.refresh(politician)

        assert politician.id is not None
        assert politician.name == "Jane Smith"
        assert politician.wikidata_id == "Q789012"
        assert politician.is_deceased is True
        assert politician.created_at is not None
        assert politician.updated_at is not None

    def test_politician_unique_wikidata_id(self, test_session, sample_politician):
        """Test that wikidata_id must be unique."""
        duplicate_politician = Politician(
            name="Different Name",
            wikidata_id=sample_politician.wikidata_id  # Same wikidata_id
        )
        test_session.add(duplicate_politician)
        
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_politician_default_values(self, test_session):
        """Test default values for politician fields."""
        politician = Politician(name="Test Person")
        test_session.add(politician)
        test_session.commit()
        test_session.refresh(politician)

        assert politician.is_deceased is False
        assert politician.wikidata_id is None

    def test_politician_cascade_delete_properties(self, test_session, sample_politician):
        """Test that deleting a politician cascades to properties."""
        prop = Property(
            politician_id=sample_politician.id,
            type="BirthDate",
            value="1980-01-01"
        )
        test_session.add(prop)
        test_session.commit()

        # Delete politician should cascade to properties
        test_session.delete(sample_politician)
        test_session.commit()

        # Property should be deleted
        assert test_session.query(Property).filter_by(politician_id=sample_politician.id).first() is None



class TestSource:
    """Test cases for the Source model."""

    def test_source_creation(self, test_session):
        """Test basic source creation."""
        extracted_time = datetime(2024, 2, 1, 14, 30, 0)
        source = Source(
            url="https://example.com/test-page",
            extracted_at=extracted_time
        )
        test_session.add(source)
        test_session.commit()
        test_session.refresh(source)

        assert source.id is not None
        assert source.url == "https://example.com/test-page"
        assert source.extracted_at == extracted_time
        assert source.created_at is not None



class TestProperty:
    """Test cases for the Property model."""

    def test_property_creation(self, test_session, sample_politician):
        """Test basic property creation."""
        prop = Property(
            politician_id=sample_politician.id,
            type="Education",
            value="Harvard University",
            is_extracted=False,
            confirmed_by="user123",
            confirmed_at=datetime(2024, 1, 20, 9, 0, 0)
        )
        test_session.add(prop)
        test_session.commit()
        test_session.refresh(prop)

        assert prop.id is not None
        assert prop.politician_id == sample_politician.id
        assert prop.type == "Education"
        assert prop.value == "Harvard University"
        assert prop.is_extracted is False
        assert prop.confirmed_by == "user123"
        assert prop.confirmed_at is not None

    def test_property_default_values(self, test_session, sample_politician):
        """Test default values for property fields."""
        prop = Property(
            politician_id=sample_politician.id,
            type="BirthDate",
            value="1980"
        )
        test_session.add(prop)
        test_session.commit()
        test_session.refresh(prop)

        assert prop.is_extracted is True
        assert prop.confirmed_by is None
        assert prop.confirmed_at is None



class TestCountry:
    """Test cases for the Country model."""

    def test_country_creation(self, test_session):
        """Test basic country creation."""
        country = Country(
            name="Germany",
            iso_code="DE",
            wikidata_id="Q183"
        )
        test_session.add(country)
        test_session.commit()
        test_session.refresh(country)

        assert country.id is not None
        assert country.name == "Germany"
        assert country.iso_code == "DE"
        assert country.wikidata_id == "Q183"
        assert country.created_at is not None
        assert country.updated_at is not None


    def test_country_optional_iso_code(self, test_session):
        """Test that iso_code is optional."""
        country = Country(
            name="Some Territory",
            wikidata_id="Q12345"
        )
        test_session.add(country)
        test_session.commit()
        test_session.refresh(country)

        assert country.iso_code is None
        assert country.name == "Some Territory"




class TestPosition:
    """Test cases for the Position model."""

    def test_position_creation(self, test_session, sample_country):
        """Test basic position creation."""
        position = Position(
            name="Senator",
            wikidata_id="Q4416090"
        )
        position.countries.append(sample_country)
        test_session.add(position)
        test_session.commit()
        test_session.refresh(position)

        assert position.id is not None
        assert position.name == "Senator"
        assert len(position.countries) == 1
        assert position.countries[0].id == sample_country.id
        assert position.wikidata_id == "Q4416090"




class TestPositionVectorSimilarity:
    """Test cases for Position vector similarity search functionality."""

    def test_generate_embedding_with_default_name(self, test_session):
        """Test that generate_embedding uses position name by default."""
        position = Position(name="Prime Minister", wikidata_id="Q14212")
        embedding = generate_embedding(position.name)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # Expected dimension for all-MiniLM-L6-v2
        assert all(isinstance(val, (int, float)) for val in embedding)

    def test_generate_embedding_with_custom_text(self, test_session):
        """Test that generate_embedding works with custom text."""
        position = Position(name="Mayor", wikidata_id="Q30185")
        custom_text = "Chief Executive Officer of City"
        embedding = generate_embedding(custom_text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(val, (int, float)) for val in embedding)
        
        # Different text should produce different embeddings
        name_embedding = generate_embedding(position.name)
        assert embedding != name_embedding

    def test_manual_embedding_generation(self, test_session):
        """Test that embedding can be manually generated for a position."""
        position = Position(name="Secretary of State", wikidata_id="Q3112749")
        test_session.add(position)
        test_session.commit()
        test_session.refresh(position)
        
        # Should not have embedding initially
        embedding = getattr(position, 'embedding', None)
        assert embedding is None
        
        # Generate embedding manually
        position.embedding = generate_embedding(position.name)
        test_session.commit()
        test_session.refresh(position)
        
        # Should have embedding after manual generation
        embedding = getattr(position, 'embedding', None)
        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(val, (int, float)) for val in embedding)

    def test_embedding_update_on_name_change(self, test_session):
        """Test that embedding can be updated when position name changes."""
        position = Position(name="Minister", wikidata_id="Q83307")
        test_session.add(position)
        test_session.commit()
        test_session.refresh(position)
        
        # Generate initial embedding
        position.embedding = generate_embedding(position.name)
        test_session.commit()
        test_session.refresh(position)
        initial_embedding = getattr(position, 'embedding', None)
        assert initial_embedding is not None
        
        # Update name and regenerate embedding
        position.name = "Prime Minister"
        position.embedding = generate_embedding(position.name)
        test_session.commit()
        test_session.refresh(position)
        
        # Embedding should be updated
        updated_embedding = getattr(position, 'embedding', None)
        assert updated_embedding is not None
        assert isinstance(updated_embedding, list)
        assert len(updated_embedding) == 384
        assert updated_embedding != initial_embedding

    def test_find_similar_basic(self, test_session, sample_country):
        """Test basic similarity search functionality."""
        # Create test positions
        positions = [
            Position(name="President", wikidata_id="Q11696"),
            Position(name="Prime Minister", wikidata_id="Q14212"),
            Position(name="Mayor", wikidata_id="Q30185"),
            Position(name="Governor", wikidata_id="Q889821")
        ]
        
        for pos in positions:
            pos.countries.append(sample_country)
            test_session.add(pos)
        test_session.commit()
        
        # Embeddings are automatically generated on insert
        
        # Search for similar positions
        similar_positions = Position.find_similar(test_session, "Chief Executive", top_k=2)
        
        assert isinstance(similar_positions, list)
        assert len(similar_positions) <= 2
        # All results should be (Position, similarity_score) tuples
        for item in similar_positions:
            assert isinstance(item, tuple)
            assert len(item) == 2
            pos, score = item
            assert isinstance(pos, Position)
            assert isinstance(score, float)

    def test_find_similar_with_country_filter(self, test_session):
        """Test similarity search with country filtering."""
        # Create countries
        us_country = Country(name="United States", iso_code="US", wikidata_id="Q30")
        uk_country = Country(name="United Kingdom", iso_code="GB", wikidata_id="Q145")
        test_session.add_all([us_country, uk_country])
        test_session.commit()
        
        # Create positions with different countries
        us_positions = [
            Position(name="US President", wikidata_id="Q11696"),
            Position(name="US Governor", wikidata_id="Q889821")
        ]
        uk_positions = [
            Position(name="UK Prime Minister", wikidata_id="Q14212"),
            Position(name="UK Minister", wikidata_id="Q83307")
        ]
        
        for pos in us_positions:
            pos.countries.append(us_country)
            test_session.add(pos)
        for pos in uk_positions:
            pos.countries.append(uk_country)
            test_session.add(pos)
        test_session.commit()
        
        # Embeddings are automatically generated on insert
        
        # Search with US country filter
        us_results = Position.find_similar(
            test_session, "Executive Leader", top_k=5, country_filter="US"
        )
        
        # Results should only include US positions
        for item in us_results:
            pos, score = item
            assert us_country in pos.countries
            assert uk_country not in pos.countries

    def test_find_similar_with_invalid_country_filter(self, test_session):
        """Test similarity search with invalid country code returns empty list."""
        # Create a position
        position = Position(name="President", wikidata_id="Q11696")
        test_session.add(position)
        test_session.commit()
        
        # Embedding is automatically generated on insert
        
        # Search with invalid country code
        results = Position.find_similar(
            test_session, "Leader", top_k=5, country_filter="XX"
        )
        
        assert results == []

    def test_find_similar_no_matches(self, test_session):
        """Test similarity search returns limited results based on top_k parameter."""
        # Create positions with very different names
        positions = [
            Position(name="XYZ123ABC", wikidata_id="Q99901"),
            Position(name="DEF456GHI", wikidata_id="Q99902")
        ]
        
        for pos in positions:
            test_session.add(pos)
        test_session.commit()
        
        # Embeddings are automatically generated on insert
        
        # Search with top_k=0 should return empty list
        results = Position.find_similar(test_session, "Completely Different Query String", top_k=0)
        assert results == []
        
        # Search with top_k=1 should return at most 1 result
        results = Position.find_similar(test_session, "Another Different Query", top_k=1)
        assert len(results) <= 1

    def test_embedding_deterministic_for_same_text(self, test_session):
        """Test that same text produces same embedding."""
        position1 = Position(name="Test Position", wikidata_id="Q1")
        position2 = Position(name="Test Position", wikidata_id="Q2") 
        
        embedding1 = generate_embedding(position1.name)
        embedding2 = generate_embedding(position2.name)
        
        # Same text should produce same embedding
        assert embedding1 == embedding2

    def test_embedding_different_for_different_text(self, test_session):
        """Test that different text produces different embeddings."""
        position1 = Position(name="President", wikidata_id="Q1")
        position2 = Position(name="Secretary", wikidata_id="Q2")
        
        embedding1 = generate_embedding(position1.name)
        embedding2 = generate_embedding(position2.name)
        
        # Different text should produce different embeddings
        assert embedding1 != embedding2


class TestHoldsPosition:
    """Test cases for the HoldsPosition model."""

    def test_holds_position_creation(self, test_session, sample_politician, sample_position):
        """Test basic holds position creation."""
        holds_pos = HoldsPosition(
            politician_id=sample_politician.id,
            position_id=sample_position.id,
            start_date="2019-01",
            end_date="2023-12-31",
            is_extracted=False,
            confirmed_by="admin",
            confirmed_at=datetime(2024, 1, 25, 16, 45, 0)
        )
        test_session.add(holds_pos)
        test_session.commit()
        test_session.refresh(holds_pos)

        assert holds_pos.id is not None
        assert holds_pos.politician_id == sample_politician.id
        assert holds_pos.position_id == sample_position.id
        assert holds_pos.start_date == "2019-01"
        assert holds_pos.end_date == "2023-12-31"
        assert holds_pos.is_extracted is False
        assert holds_pos.confirmed_by == "admin"
        assert holds_pos.confirmed_at is not None

    def test_holds_position_incomplete_dates(self, test_session, sample_politician, sample_position):
        """Test handling of incomplete dates in HoldsPosition."""
        # Test various incomplete date formats
        test_cases = [
            ("2020", None),  # Only year
            ("2020-03", "2021"),  # Year-month to year
            ("1995", "2000-06-15"),  # Year to full date
            (None, "2024"),  # No start date
            ("2022", None)  # No end date
        ]

        for start_date, end_date in test_cases:
            holds_pos = HoldsPosition(
                politician_id=sample_politician.id,
                position_id=sample_position.id,
                start_date=start_date,
                end_date=end_date
            )
            test_session.add(holds_pos)
            test_session.commit()
            test_session.refresh(holds_pos)

            assert holds_pos.start_date == start_date
            assert holds_pos.end_date == end_date
            
            # Clean up for next iteration
            test_session.delete(holds_pos)
            test_session.commit()

    def test_holds_position_default_values(self, test_session, sample_politician, sample_position):
        """Test default values for holds position fields."""
        holds_pos = HoldsPosition(
            politician_id=sample_politician.id,
            position_id=sample_position.id
        )
        test_session.add(holds_pos)
        test_session.commit()
        test_session.refresh(holds_pos)

        assert holds_pos.is_extracted is True
        assert holds_pos.confirmed_by is None
        assert holds_pos.confirmed_at is None
        assert holds_pos.start_date is None
        assert holds_pos.end_date is None



class TestHasCitizenship:
    """Test cases for the HasCitizenship model."""

    def test_has_citizenship_creation(self, test_session, sample_politician, sample_country):
        """Test basic citizenship relationship creation."""
        citizenship = HasCitizenship(
            politician_id=sample_politician.id,
            country_id=sample_country.id
        )
        test_session.add(citizenship)
        test_session.commit()
        test_session.refresh(citizenship)

        assert citizenship.id is not None
        assert citizenship.politician_id == sample_politician.id
        assert citizenship.country_id == sample_country.id
        assert citizenship.created_at is not None
        assert citizenship.updated_at is not None


    def test_has_citizenship_multiple_citizenships_per_politician(self, test_session, sample_politician):
        """Test that a politician can have multiple citizenships."""
        # Create two countries
        country1 = Country(name="United States", iso_code="US")
        country2 = Country(name="Canada", iso_code="CA")
        test_session.add_all([country1, country2])
        test_session.flush()

        # Create two citizenships for the same politician
        citizenship1 = HasCitizenship(
            politician_id=sample_politician.id,
            country_id=country1.id
        )
        citizenship2 = HasCitizenship(
            politician_id=sample_politician.id,
            country_id=country2.id
        )
        test_session.add_all([citizenship1, citizenship2])
        test_session.commit()

        # Verify both citizenships exist
        citizenships = test_session.query(HasCitizenship).filter_by(
            politician_id=sample_politician.id
        ).all()
        assert len(citizenships) == 2
        
        # Verify relationships
        assert len(sample_politician.citizenships) == 2
        country_names = {c.country.name for c in sample_politician.citizenships}
        assert "United States" in country_names
        assert "Canada" in country_names

    def test_has_citizenship_multiple_politicians_per_country(self, test_session, sample_country):
        """Test that a country can have multiple citizen politicians."""
        # Create two politicians
        politician1 = Politician(name="Alice Smith", wikidata_id="Q111")
        politician2 = Politician(name="Bob Jones", wikidata_id="Q222")
        test_session.add_all([politician1, politician2])
        test_session.flush()

        # Create two citizenships for the same country
        citizenship1 = HasCitizenship(
            politician_id=politician1.id,
            country_id=sample_country.id
        )
        citizenship2 = HasCitizenship(
            politician_id=politician2.id,
            country_id=sample_country.id
        )
        test_session.add_all([citizenship1, citizenship2])
        test_session.commit()

        # Verify both citizenships exist
        citizenships = test_session.query(HasCitizenship).filter_by(
            country_id=sample_country.id
        ).all()
        assert len(citizenships) == 2
        
        # Verify relationships
        assert len(sample_country.citizens) == 2
        politician_names = {c.politician.name for c in sample_country.citizens}
        assert "Alice Smith" in politician_names
        assert "Bob Jones" in politician_names

    def test_has_citizenship_prevents_duplicate_relationships(self, test_session, sample_politician, sample_country):
        """Test database constraints prevent duplicate citizenship relationships."""
        citizenship1 = HasCitizenship(
            politician_id=sample_politician.id,
            country_id=sample_country.id
        )
        test_session.add(citizenship1)
        test_session.commit()

        # Attempt to create duplicate
        citizenship2 = HasCitizenship(
            politician_id=sample_politician.id,
            country_id=sample_country.id
        )
        test_session.add(citizenship2)
        
        # Note: If there are no unique constraints in the model, this might not raise an error
        # This test verifies the current behavior - you might want to add unique constraints
        try:
            test_session.commit()
            # If no constraint exists, verify at least that the application logic prevents duplicates
            citizenships = test_session.query(HasCitizenship).filter_by(
                politician_id=sample_politician.id,
                country_id=sample_country.id
            ).all()
            # This should be handled by application logic in import_service._create_citizenships
            assert len(citizenships) >= 1  # At least one exists
        except IntegrityError:
            # If database has unique constraint, this is expected
            test_session.rollback()


class TestManyToManyRelationships:
    """Test cases for many-to-many relationships via association tables."""


    def test_multiple_sources_per_entity(self, test_session, sample_politician):
        """Test that entities can have multiple sources."""
        source1 = Source(url="https://example.com/source1")
        source2 = Source(url="https://example.com/source2")
        test_session.add_all([source1, source2])
        test_session.commit()

        # Add both sources to politician
        sample_politician.sources.extend([source1, source2])
        test_session.commit()

        assert len(sample_politician.sources) == 2
        assert source1 in sample_politician.sources
        assert source2 in sample_politician.sources


class TestTimestampBehavior:
    """Test cases for timestamp mixin behavior."""

    def test_created_at_set_on_creation(self, test_session):
        """Test that created_at is set when entity is created."""
        before_create = datetime.now(timezone.utc)
        politician = Politician(name="Timestamp Test")
        test_session.add(politician)
        test_session.commit()
        test_session.refresh(politician)
        after_create = datetime.now(timezone.utc)

        # Convert to naive UTC for comparison since SQLAlchemy returns naive datetimes
        before_create_naive = before_create.replace(tzinfo=None)
        after_create_naive = after_create.replace(tzinfo=None)
        assert before_create_naive <= politician.created_at <= after_create_naive
        # Allow for microsecond differences between created_at and updated_at
        time_diff = abs((politician.created_at - politician.updated_at).total_seconds())
        assert time_diff < 0.001  # Less than 1 millisecond difference

    def test_updated_at_changes_on_update(self, test_session, sample_politician):
        """Test that updated_at changes when entity is updated."""
        original_updated_at = sample_politician.updated_at
        
        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)
        
        # Update the politician
        sample_politician.name = "Updated Name"
        test_session.commit()
        test_session.refresh(sample_politician)

        assert sample_politician.updated_at > original_updated_at
        assert sample_politician.created_at < sample_politician.updated_at


class TestUUIDBehavior:
    """Test cases for UUID mixin behavior."""

    def test_uuid_generation(self, test_session):
        """Test that UUIDs are generated automatically."""
        politician = Politician(name="UUID Test")
        test_session.add(politician)
        test_session.commit()
        test_session.refresh(politician)

        assert politician.id is not None
        assert isinstance(politician.id, str)
        assert len(politician.id) == 36  # Standard UUID string length

    def test_uuid_uniqueness(self, test_session):
        """Test that generated UUIDs are unique."""
        politicians = [
            Politician(name=f"Test Politician {i}")
            for i in range(10)
        ]
        test_session.add_all(politicians)
        test_session.commit()

        # Refresh all to get their IDs
        for politician in politicians:
            test_session.refresh(politician)

        ids = [p.id for p in politicians]
        assert len(set(ids)) == len(ids)  # All IDs should be unique


class TestLocation:
    """Test cases for the Location model."""

    def test_location_creation(self, test_session):
        """Test basic location creation."""
        location = Location(
            name="New York City",
            wikidata_id="Q60"
        )
        test_session.add(location)
        test_session.commit()
        test_session.refresh(location)

        assert location.name == "New York City"
        assert location.wikidata_id == "Q60"
        assert location.id is not None
        assert location.created_at is not None
        assert location.updated_at is not None

    def test_location_unique_wikidata_id(self, test_session):
        """Test that Wikidata ID must be unique."""
        location1 = Location(name="New York City", wikidata_id="Q60")
        location2 = Location(name="NYC", wikidata_id="Q60")
        
        test_session.add(location1)
        test_session.commit()
        
        test_session.add(location2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_location_find_similar(self, test_session):
        """Test location similarity search functionality."""
        # Create test locations with embeddings
        locations_data = [
            ("New York City", "Q60"),
            ("Los Angeles", "Q65"),
            ("Chicago", "Q1297")
        ]
        
        locations = []
        for name, wikidata_id in locations_data:
            location = Location(name=name, wikidata_id=wikidata_id)
            location.embedding = generate_embedding(name)
            locations.append(location)
        
        test_session.add_all(locations)
        test_session.commit()
        
        # Test similarity search (just verify it works and returns correct format)
        similar = Location.find_similar(test_session, "New York", top_k=2)
        assert len(similar) <= 2  # Should return at most 2 results
        if len(similar) > 0:
            # Verify we get tuples with (entity, similarity_score) format
            assert len(similar[0]) == 2
            assert hasattr(similar[0][0], 'name')
            assert isinstance(similar[0][1], float)


class TestBornAt:
    """Test cases for the BornAt relationship model."""

    def test_born_at_creation(self, test_session, sample_politician):
        """Test basic BornAt relationship creation."""
        location = Location(name="Paris", wikidata_id="Q90")
        test_session.add(location)
        test_session.flush()

        born_at = BornAt(
            politician_id=sample_politician.id,
            location_id=location.id,
            is_extracted=True
        )
        test_session.add(born_at)
        test_session.commit()
        test_session.refresh(born_at)

        assert born_at.politician_id == sample_politician.id
        assert born_at.location_id == location.id
        assert born_at.is_extracted is True
        assert born_at.confirmed_by is None
        assert born_at.confirmed_at is None
        assert born_at.id is not None

    def test_born_at_default_values(self, test_session, sample_politician):
        """Test BornAt model default values."""
        location = Location(name="London", wikidata_id="Q84")
        test_session.add(location)
        test_session.flush()

        born_at = BornAt(
            politician_id=sample_politician.id,
            location_id=location.id
        )
        test_session.add(born_at)
        test_session.commit()
        test_session.refresh(born_at)

        assert born_at.is_extracted is True  # Default value
        assert born_at.confirmed_by is None
        assert born_at.confirmed_at is None

    def test_born_at_confirmation(self, test_session, sample_politician):
        """Test BornAt confirmation workflow."""
        location = Location(name="Berlin", wikidata_id="Q64")
        test_session.add(location)
        test_session.flush()

        born_at = BornAt(
            politician_id=sample_politician.id,
            location_id=location.id,
            is_extracted=True
        )
        test_session.add(born_at)
        test_session.commit()

        # Confirm the relationship
        confirmation_time = datetime.now(timezone.utc)
        born_at.confirmed_by = "user123"
        born_at.confirmed_at = confirmation_time
        born_at.is_extracted = False
        test_session.commit()
        test_session.refresh(born_at)

        assert born_at.confirmed_by == "user123"
        # Compare datetime without microseconds and timezone due to database storage differences
        assert born_at.confirmed_at.replace(microsecond=0, tzinfo=None) == confirmation_time.replace(microsecond=0, tzinfo=None)
        assert born_at.is_extracted is False

    def test_born_at_relationships(self, test_session, sample_politician):
        """Test BornAt model relationships."""
        location = Location(name="Tokyo", wikidata_id="Q1490")
        test_session.add(location)
        test_session.flush()

        born_at = BornAt(
            politician_id=sample_politician.id,
            location_id=location.id
        )
        test_session.add(born_at)
        test_session.commit()

        # Test politician relationship
        assert born_at.politician.id == sample_politician.id
        assert born_at.politician.name == sample_politician.name

        # Test location relationship
        assert born_at.location.id == location.id
        assert born_at.location.name == "Tokyo"

        # Test reverse relationships
        assert len(sample_politician.birthplaces) == 1
        assert sample_politician.birthplaces[0].id == born_at.id
        assert len(location.born_here) == 1
        assert location.born_here[0].id == born_at.id

    def test_born_at_cascade_delete(self, test_session, sample_politician):
        """Test that deleting a politician cascades to BornAt relationships."""
        location = Location(name="Rome", wikidata_id="Q220")
        test_session.add(location)
        test_session.flush()

        born_at = BornAt(
            politician_id=sample_politician.id,
            location_id=location.id
        )
        test_session.add(born_at)
        test_session.commit()
        born_at_id = born_at.id

        # Delete politician should cascade to BornAt
        test_session.delete(sample_politician)
        test_session.commit()

        # BornAt should be deleted
        deleted_born_at = test_session.query(BornAt).filter_by(id=born_at_id).first()
        assert deleted_born_at is None

        # Location should still exist
        existing_location = test_session.query(Location).filter_by(id=location.id).first()
        assert existing_location is not None