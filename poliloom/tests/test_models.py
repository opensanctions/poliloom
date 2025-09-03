"""Tests for database models."""

import pytest
import time
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from poliloom.models import (
    Politician,
    WikipediaLink,
    Property,
    PropertyType,
    Position,
    HoldsPosition,
    Country,
    HasCitizenship,
    Location,
    BornAt,
    PropertyEvaluation,
    PositionEvaluation,
    BirthplaceEvaluation,
)
from poliloom.enrichment import generate_embedding
from .conftest import assert_model_fields


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_creation(self, db_session):
        """Test basic politician creation."""
        politician = Politician(name="Jane Smith", wikidata_id="Q789012")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Jane Smith", "wikidata_id": "Q789012"},
        )

    def test_politician_unique_wikidata_id(self, db_session, sample_politician_data):
        """Test that wikidata_id must be unique."""
        # Create first politician
        politician1 = Politician(**sample_politician_data)
        db_session.add(politician1)
        db_session.commit()

        # Try to create duplicate
        duplicate_politician = Politician(
            name="Different Name",
            wikidata_id=sample_politician_data["wikidata_id"],  # Same wikidata_id
        )
        db_session.add(duplicate_politician)

        with pytest.raises(IntegrityError):
            db_session.commit()

        # Roll back the failed transaction to clean up the session
        db_session.rollback()

    def test_politician_default_values(self, db_session):
        """Test default values for politician fields."""
        politician = Politician(name="Test Person")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert_model_fields(
            politician,
            {"name": "Test Person", "is_deceased": False, "wikidata_id": None},
        )

    def test_politician_cascade_delete_properties(
        self, db_session, sample_politician_data
    ):
        """Test that deleting a politician cascades to properties."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
        )
        db_session.add(prop)
        db_session.commit()

        # Delete politician should cascade to properties
        db_session.delete(politician)
        db_session.commit()

        # Property should be deleted
        assert (
            db_session.query(Property).filter_by(politician_id=politician.id).first()
            is None
        )


class TestWikipediaLink:
    """Test cases for the WikipediaLink model."""

    def test_wikipedia_link_creation(self, db_session, sample_politician_data):
        """Test basic Wikipedia link creation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create wikipedia link
        wikipedia_link = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/John_Doe",
            language_code="en",
        )
        db_session.add(wikipedia_link)
        db_session.commit()
        db_session.refresh(wikipedia_link)

        assert_model_fields(
            wikipedia_link,
            {
                "politician_id": politician.id,
                "url": "https://en.wikipedia.org/wiki/John_Doe",
                "language_code": "en",
            },
        )


class TestProperty:
    """Test cases for the Property model."""

    def test_property_creation(self, db_session, sample_politician_data):
        """Test basic property creation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1990-01-01",
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.BIRTH_DATE,
                "value": "1990-01-01",
                "archived_page_id": None,
            },
        )

    def test_property_default_values(self, db_session, sample_politician_data):
        """Test default values for property fields."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id, type=PropertyType.BIRTH_DATE, value="1980"
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        assert_model_fields(
            prop,
            {
                "politician_id": politician.id,
                "type": PropertyType.BIRTH_DATE,
                "value": "1980",
                "archived_page_id": None,
            },
        )


class TestCountry:
    """Test cases for the Country model."""

    def test_country_creation(self, db_session):
        """Test basic country creation."""
        country = Country(name="Germany", iso_code="DE", wikidata_id="Q183")
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)

        assert_model_fields(
            country, {"name": "Germany", "iso_code": "DE", "wikidata_id": "Q183"}
        )

    def test_country_optional_iso_code(self, db_session):
        """Test that iso_code is optional."""
        country = Country(name="Some Territory", wikidata_id="Q12345")
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)

        assert_model_fields(
            country,
            {"name": "Some Territory", "wikidata_id": "Q12345", "iso_code": None},
        )


class TestPosition:
    """Test cases for the Position model."""

    def test_position_creation(self, db_session):
        """Test basic position creation."""
        position = Position(name="Senator", wikidata_id="Q4416090")
        db_session.add(position)
        db_session.commit()
        db_session.refresh(position)

        assert_model_fields(position, {"name": "Senator", "wikidata_id": "Q4416090"})


class TestPositionVectorSimilarity:
    """Test cases for Position vector similarity search functionality."""

    def test_embedding_deterministic_for_same_text(self):
        """Test that embedding generation is deterministic."""
        # Test deterministic behavior
        embedding1 = generate_embedding("Prime Minister")
        embedding2 = generate_embedding("Prime Minister")
        assert embedding1 == embedding2
        assert len(embedding1) == 384

    def test_similarity_search_functionality(
        self,
        db_session,
    ):
        """Test similarity search functionality."""
        # Create positions with embeddings
        positions = [
            Position(name="US President", wikidata_id="Q11696"),
            Position(name="US Governor", wikidata_id="Q889821"),
            Position(name="UK Prime Minister", wikidata_id="Q14212"),
        ]

        for position in positions:
            position.embedding = generate_embedding(position.name)
            db_session.add(position)

        db_session.commit()

        # Test basic similarity search - using same session
        query_embedding = generate_embedding("Chief Executive")
        results = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(query_embedding))
            .limit(2)
            .all()
        )
        assert len(results) <= 2
        assert all(isinstance(pos, Position) for pos in results)

        # Test limit behavior
        no_query_embedding = generate_embedding("Query")
        no_results = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(no_query_embedding))
            .limit(0)
            .all()
        )
        assert no_results == []

        one_result = (
            db_session.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(no_query_embedding))
            .limit(1)
            .all()
        )
        assert len(one_result) <= 1


class TestHoldsPosition:
    """Test cases for the HoldsPosition model."""

    def test_holds_position_creation(
        self,
        db_session,
        sample_politician_data,
        sample_position_data,
    ):
        """Test basic holds position creation."""
        # Create politician and position
        politician = Politician(**sample_politician_data)
        position = Position(**sample_position_data)
        db_session.add_all([politician, position])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(position)

        # Create holds position
        holds_pos = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2019-01",
            end_date="2023-12-31",
            archived_page_id=None,
        )
        db_session.add(holds_pos)
        db_session.commit()
        db_session.refresh(holds_pos)

        assert_model_fields(
            holds_pos,
            {
                "politician_id": politician.id,
                "position_id": position.wikidata_id,
                "start_date": "2019-01",
                "end_date": "2023-12-31",
                "archived_page_id": None,
            },
        )

    def test_holds_position_incomplete_dates(self, db_session, sample_politician_data):
        """Test handling of incomplete dates in HoldsPosition."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Test various incomplete date formats - each with a different position or archived_page_id
        # to avoid unique constraint violations
        test_cases = [
            ("2020", None, "Q1001"),  # Only year
            ("2020-03", "2021", "Q1002"),  # Year-month to year
            ("1995", "2000-06-15", "Q1003"),  # Year to full date
            (None, "2024", "Q1004"),  # No start date
            ("2022", None, "Q1005"),  # No end date
        ]

        for start_date, end_date, position_qid in test_cases:
            # Create a unique position for each test case
            position = Position(
                name=f"Test Position {position_qid}", wikidata_id=position_qid
            )
            db_session.add(position)
            db_session.commit()
            db_session.refresh(position)

            holds_pos = HoldsPosition(
                politician_id=politician.id,
                position_id=position.wikidata_id,
                start_date=start_date,
                end_date=end_date,
            )
            db_session.add(holds_pos)
            db_session.commit()
            db_session.refresh(holds_pos)

            assert holds_pos.start_date == start_date
            assert holds_pos.end_date == end_date

    def test_holds_position_default_values(
        self,
        db_session,
        sample_politician_data,
        sample_position_data,
    ):
        """Test default values for holds position fields."""
        # Create politician and position
        politician = Politician(**sample_politician_data)
        position = Position(**sample_position_data)
        db_session.add_all([politician, position])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(position)

        # Create holds position with minimal data
        holds_pos = HoldsPosition(
            politician_id=politician.id, position_id=position.wikidata_id
        )
        db_session.add(holds_pos)
        db_session.commit()
        db_session.refresh(holds_pos)

        assert_model_fields(
            holds_pos,
            {
                "politician_id": politician.id,
                "position_id": position.wikidata_id,
                "archived_page_id": None,
                "start_date": None,
                "end_date": None,
            },
        )


class TestHasCitizenship:
    """Test cases for the HasCitizenship model."""

    def test_has_citizenship_creation(
        self,
        db_session,
        sample_politician_data,
        sample_country_data,
    ):
        """Test basic citizenship relationship creation."""
        # Create politician and country
        politician = Politician(**sample_politician_data)
        country = Country(**sample_country_data)
        db_session.add_all([politician, country])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(country)

        # Create citizenship
        citizenship = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        db_session.add(citizenship)
        db_session.commit()
        db_session.refresh(citizenship)

        assert_model_fields(
            citizenship,
            {"politician_id": politician.id, "country_id": country.wikidata_id},
        )

    def test_has_citizenship_multiple_citizenships_per_politician(
        self, db_session, sample_politician_data
    ):
        """Test that a politician can have multiple citizenships."""
        # Create politician and two countries
        politician = Politician(**sample_politician_data)
        country1 = Country(name="United States", iso_code="US", wikidata_id="Q30")
        country2 = Country(name="Canada", iso_code="CA", wikidata_id="Q16")

        db_session.add_all([politician, country1, country2])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(country1)
        db_session.refresh(country2)

        # Create two citizenships for the same politician
        citizenship1 = HasCitizenship(
            politician_id=politician.id, country_id=country1.wikidata_id
        )
        citizenship2 = HasCitizenship(
            politician_id=politician.id, country_id=country2.wikidata_id
        )

        db_session.add_all([citizenship1, citizenship2])
        db_session.commit()

        # Verify both citizenships exist
        citizenships = (
            db_session.query(HasCitizenship)
            .filter_by(politician_id=politician.id)
            .all()
        )
        assert len(citizenships) == 2

        # Verify relationships
        politician_refreshed = (
            db_session.query(Politician).filter_by(id=politician.id).first()
        )
        assert len(politician_refreshed.citizenships) == 2
        country_names = {c.country.name for c in politician_refreshed.citizenships}
        assert "United States" in country_names
        assert "Canada" in country_names

    def test_has_citizenship_multiple_politicians_per_country(
        self, db_session, sample_country_data
    ):
        """Test that a country can have multiple citizen politicians."""
        # Create country and two politicians
        country = Country(**sample_country_data)
        politician1 = Politician(name="Alice Smith", wikidata_id="Q111")
        politician2 = Politician(name="Bob Jones", wikidata_id="Q222")

        db_session.add_all([country, politician1, politician2])
        db_session.commit()
        db_session.refresh(country)
        db_session.refresh(politician1)
        db_session.refresh(politician2)

        # Create two citizenships for the same country
        citizenship1 = HasCitizenship(
            politician_id=politician1.id, country_id=country.wikidata_id
        )
        citizenship2 = HasCitizenship(
            politician_id=politician2.id, country_id=country.wikidata_id
        )

        db_session.add_all([citizenship1, citizenship2])
        db_session.commit()

        # Verify both citizenships exist
        citizenships = (
            db_session.query(HasCitizenship)
            .filter_by(country_id=country.wikidata_id)
            .all()
        )
        assert len(citizenships) == 2

        # Verify relationships
        country_refreshed = (
            db_session.query(Country).filter_by(wikidata_id=country.wikidata_id).first()
        )
        assert len(country_refreshed.citizens) == 2
        politician_names = {c.politician.name for c in country_refreshed.citizens}
        assert "Alice Smith" in politician_names
        assert "Bob Jones" in politician_names

    def test_has_citizenship_prevents_duplicate_relationships(
        self, db_session, sample_politician_data, sample_country_data
    ):
        """Test database constraints prevent duplicate citizenship relationships."""
        # Create politician and country
        politician = Politician(**sample_politician_data)
        country = Country(**sample_country_data)
        db_session.add_all([politician, country])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(country)

        # Create first citizenship
        citizenship1 = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        db_session.add(citizenship1)
        db_session.commit()

        # Attempt to create duplicate
        citizenship2 = HasCitizenship(
            politician_id=politician.id, country_id=country.wikidata_id
        )
        db_session.add(citizenship2)

        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db_session.commit()

        # Clean up failed transaction
        db_session.rollback()


class TestWikipediaLinkRelationships:
    """Test cases for Wikipedia link relationships."""

    def test_multiple_wikipedia_links_per_politician(
        self, db_session, sample_politician_data
    ):
        """Test that politicians can have multiple Wikipedia links."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create wikipedia links
        wiki_link1 = WikipediaLink(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/John_Doe",
            language_code="en",
        )
        wiki_link2 = WikipediaLink(
            politician_id=politician.id,
            url="https://de.wikipedia.org/wiki/John_Doe",
            language_code="de",
        )
        db_session.add_all([wiki_link1, wiki_link2])
        db_session.commit()

        # Verify relationship
        politician_refreshed = (
            db_session.query(Politician).filter_by(id=politician.id).first()
        )
        assert len(politician_refreshed.wikipedia_links) == 2


class TestTimestampBehavior:
    """Test cases for timestamp mixin behavior."""

    def test_created_at_set_on_creation(self, db_session):
        """Test that created_at is set when entity is created."""
        before_create = datetime.now(timezone.utc)

        politician = Politician(name="Timestamp Test")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)
        after_create = datetime.now(timezone.utc)

        # Convert to naive UTC for comparison since SQLAlchemy returns naive datetimes
        before_create_naive = before_create.replace(tzinfo=None)
        after_create_naive = after_create.replace(tzinfo=None)
        assert before_create_naive <= politician.created_at <= after_create_naive
        # Allow for microsecond differences between created_at and updated_at
        time_diff = abs((politician.created_at - politician.updated_at).total_seconds())
        assert time_diff < 0.001  # Less than 1 millisecond difference

    def test_updated_at_changes_on_update(self, db_session, sample_politician_data):
        """Test that updated_at changes when entity is updated."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        original_updated_at = politician.updated_at

        # Small delay to ensure timestamp difference

        time.sleep(0.01)

        # Update the politician
        politician.name = "Updated Name"
        db_session.commit()
        db_session.refresh(politician)

        assert politician.updated_at > original_updated_at
        assert politician.created_at < politician.updated_at


class TestUUIDBehavior:
    """Test cases for UUID mixin behavior."""

    def test_uuid_generation(self, db_session):
        """Test that UUIDs are generated automatically."""
        politician = Politician(name="UUID Test")
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        assert politician.id is not None
        assert isinstance(politician.id, UUID)
        assert len(str(politician.id)) == 36  # Standard UUID string length

    def test_uuid_uniqueness(self, db_session):
        """Test that generated UUIDs are unique."""
        politicians = [Politician(name=f"Test Politician {i}") for i in range(10)]
        db_session.add_all(politicians)
        db_session.commit()

        # Refresh all to get their IDs
        for politician in politicians:
            db_session.refresh(politician)

        ids = [p.id for p in politicians]
        assert len(set(ids)) == len(ids)  # All IDs should be unique


class TestLocation:
    """Test cases for the Location model."""

    def test_location_creation(self, db_session):
        """Test basic location creation."""
        location = Location(name="New York City", wikidata_id="Q60")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        assert_model_fields(location, {"name": "New York City", "wikidata_id": "Q60"})

    def test_location_unique_wikidata_id(self, db_session):
        """Test that Wikidata ID must be unique."""
        location1 = Location(
            name="New York City", wikidata_id="Q60001"
        )  # Use unique ID
        location2 = Location(name="NYC", wikidata_id="Q60001")  # Same unique ID

        db_session.add(location1)
        db_session.commit()

        db_session.add(location2)
        with pytest.raises(IntegrityError):
            db_session.commit()

        # Clean up the session
        db_session.rollback()

    def test_location_find_similar(
        self,
        db_session,
    ):
        """Test location similarity search functionality."""
        # Create test locations with embeddings
        locations = [
            Location(name="New York City", wikidata_id="Q60"),
            Location(name="Los Angeles", wikidata_id="Q65"),
            Location(name="Chicago", wikidata_id="Q1297"),
        ]

        for location in locations:
            location.embedding = generate_embedding(location.name)
            db_session.add(location)

        db_session.commit()

        # Test similarity search - using same session
        query_embedding = generate_embedding("New York")
        similar = (
            db_session.query(Location)
            .filter(Location.embedding.isnot(None))
            .order_by(Location.embedding.cosine_distance(query_embedding))
            .limit(2)
            .all()
        )

        assert len(similar) <= 2
        if len(similar) > 0:
            assert isinstance(similar[0], Location)
            assert hasattr(similar[0], "name")


class TestPropertyEvaluation:
    """Test cases for the PropertyEvaluation model."""

    def test_property_evaluation_creation(self, db_session, sample_politician_data):
        """Test creating a property evaluation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        # Create evaluation
        evaluation = PropertyEvaluation(
            user_id="user123",
            is_confirmed=True,
            property_id=prop.id,
        )
        db_session.add(evaluation)
        db_session.commit()
        db_session.refresh(evaluation)

        assert_model_fields(
            evaluation,
            {
                "user_id": "user123",
                "is_confirmed": True,
                "property_id": prop.id,
            },
        )

        # Check relationships
        assert evaluation.property == prop
        assert len(prop.evaluations) == 1
        assert prop.evaluations[0] == evaluation

    def test_property_evaluation_discarded(self, db_session, sample_politician_data):
        """Test creating a discarded property evaluation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        # Create evaluation
        evaluation = PropertyEvaluation(
            user_id="user123",
            is_confirmed=False,
            property_id=prop.id,
        )
        db_session.add(evaluation)
        db_session.commit()
        db_session.refresh(evaluation)

        assert_model_fields(
            evaluation,
            {
                "user_id": "user123",
                "is_confirmed": False,
                "property_id": prop.id,
            },
        )

        # Check relationships
        assert evaluation.property == prop
        assert len(prop.evaluations) == 1
        assert prop.evaluations[0] == evaluation


class TestPositionEvaluation:
    """Test cases for the PositionEvaluation model."""

    def test_position_evaluation_creation(
        self,
        db_session,
        sample_politician_data,
        sample_position_data,
    ):
        """Test creating a position evaluation."""
        # Create politician and position
        politician = Politician(**sample_politician_data)
        position = Position(**sample_position_data)
        db_session.add_all([politician, position])
        db_session.commit()
        db_session.refresh(politician)
        db_session.refresh(position)

        # Create holds position
        holds_pos = HoldsPosition(
            politician_id=politician.id,
            position_id=position.wikidata_id,
            start_date="2020-01",
            archived_page_id=None,
        )
        db_session.add(holds_pos)
        db_session.commit()
        db_session.refresh(holds_pos)

        # Create evaluation
        evaluation = PositionEvaluation(
            user_id="admin",
            is_confirmed=True,
            holds_position_id=holds_pos.id,
        )
        db_session.add(evaluation)
        db_session.commit()
        db_session.refresh(evaluation)

        assert_model_fields(
            evaluation,
            {
                "user_id": "admin",
                "is_confirmed": True,
                "holds_position_id": holds_pos.id,
            },
        )

        # Check relationships
        assert evaluation.holds_position == holds_pos
        assert len(holds_pos.evaluations) == 1
        assert holds_pos.evaluations[0] == evaluation


class TestBirthplaceEvaluation:
    """Test cases for the BirthplaceEvaluation model."""

    def test_birthplace_evaluation_creation(self, db_session, sample_politician_data):
        """Test creating a birthplace evaluation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create location
        location = Location(name="Paris", wikidata_id="Q90")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(
            politician_id=politician.id,
            location_id=location.wikidata_id,
            archived_page_id=None,
        )
        db_session.add(born_at)
        db_session.commit()
        db_session.refresh(born_at)

        # Create evaluation
        evaluation = BirthplaceEvaluation(
            user_id="reviewer",
            is_confirmed=True,
            born_at_id=born_at.id,
        )
        db_session.add(evaluation)
        db_session.commit()
        db_session.refresh(evaluation)

        assert_model_fields(
            evaluation,
            {
                "user_id": "reviewer",
                "is_confirmed": True,
                "born_at_id": born_at.id,
            },
        )

        # Check relationships
        assert evaluation.born_at == born_at
        assert len(born_at.evaluations) == 1
        assert born_at.evaluations[0] == evaluation


class TestEvaluationMultiple:
    """Test cases for multiple evaluations."""

    def test_multiple_evaluations_for_same_property(
        self, db_session, sample_politician_data
    ):
        """Test multiple evaluations for the same property."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create property
        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            archived_page_id=None,
        )
        db_session.add(prop)
        db_session.commit()
        db_session.refresh(prop)

        # Create evaluations
        evaluations = [
            PropertyEvaluation(
                user_id="user1",
                is_confirmed=True,
                property_id=prop.id,
            ),
            PropertyEvaluation(
                user_id="user2",
                is_confirmed=True,
                property_id=prop.id,
            ),
            PropertyEvaluation(
                user_id="user3",
                is_confirmed=False,
                property_id=prop.id,
            ),
        ]

        db_session.add_all(evaluations)
        db_session.commit()

        # Check that all evaluations are linked to the property
        assert len(prop.evaluations) == 3
        evaluation_users = [e.user_id for e in prop.evaluations]
        assert "user1" in evaluation_users
        assert "user2" in evaluation_users
        assert "user3" in evaluation_users

        # Check that evaluations have correct results
        confirmed_count = sum(1 for e in prop.evaluations if e.is_confirmed)
        discarded_count = sum(1 for e in prop.evaluations if not e.is_confirmed)
        assert confirmed_count == 2
        assert discarded_count == 1


class TestBornAt:
    """Test cases for the BornAt relationship model."""

    def test_born_at_creation(self, db_session, sample_politician_data):
        """Test basic BornAt relationship creation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create location
        location = Location(name="Paris", wikidata_id="Q90")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(
            politician_id=politician.id,
            location_id=location.wikidata_id,
            archived_page_id=None,
        )
        db_session.add(born_at)
        db_session.commit()
        db_session.refresh(born_at)

        assert_model_fields(
            born_at,
            {
                "politician_id": politician.id,
                "location_id": location.wikidata_id,
                "archived_page_id": None,
            },
        )

    def test_born_at_default_values(self, db_session, sample_politician_data):
        """Test BornAt model default values."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create location
        location = Location(name="London", wikidata_id="Q84")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(politician_id=politician.id, location_id=location.wikidata_id)
        db_session.add(born_at)
        db_session.commit()
        db_session.refresh(born_at)

        assert_model_fields(
            born_at,
            {
                "politician_id": politician.id,
                "location_id": location.wikidata_id,
                "archived_page_id": None,
            },
        )

    def test_born_at_confirmation(self, db_session, sample_politician_data):
        """Test BornAt confirmation workflow with evaluations."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create location
        location = Location(name="Berlin", wikidata_id="Q64")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(
            politician_id=politician.id,
            location_id=location.wikidata_id,
            archived_page_id=None,
        )
        db_session.add(born_at)
        db_session.commit()
        db_session.refresh(born_at)

        # Add evaluation to confirm the relationship
        evaluation = BirthplaceEvaluation(
            user_id="user123",
            is_confirmed=True,
            born_at_id=born_at.id,
        )
        db_session.add(evaluation)
        db_session.commit()
        db_session.refresh(evaluation)

        # Check that the evaluation is linked properly
        assert evaluation.born_at_id == born_at.id
        assert evaluation.user_id == "user123"
        assert evaluation.is_confirmed
        assert len(born_at.evaluations) == 1
        assert born_at.evaluations[0].user_id == "user123"

    def test_born_at_relationships(self, db_session, sample_politician_data):
        """Test BornAt model relationships."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create location
        location = Location(name="Tokyo", wikidata_id="Q1490")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(politician_id=politician.id, location_id=location.wikidata_id)
        db_session.add(born_at)
        db_session.commit()
        db_session.refresh(born_at)

        # Test politician relationship
        assert born_at.politician.id == politician.id
        assert born_at.politician.name == politician.name

        # Test location relationship
        assert born_at.location.wikidata_id == location.wikidata_id
        assert born_at.location.name == "Tokyo"

        # Test reverse relationships
        assert len(politician.birthplaces) == 1
        assert politician.birthplaces[0].id == born_at.id
        assert len(location.born_here) == 1
        assert location.born_here[0].id == born_at.id

    def test_born_at_cascade_delete(self, db_session, sample_politician_data):
        """Test that deleting a politician cascades to BornAt relationships."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)
        db_session.commit()
        db_session.refresh(politician)

        # Create location
        location = Location(name="Rome", wikidata_id="Q220")
        db_session.add(location)
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(politician_id=politician.id, location_id=location.wikidata_id)
        db_session.add(born_at)
        db_session.commit()
        born_at_id = born_at.id
        location_id = location.wikidata_id

        # Delete politician should cascade to BornAt
        db_session.delete(politician)
        db_session.commit()

        # BornAt should be deleted
        deleted_born_at = db_session.query(BornAt).filter_by(id=born_at_id).first()
        assert deleted_born_at is None

        # Location should still exist
        existing_location = (
            db_session.query(Location).filter_by(wikidata_id=location_id).first()
        )
        assert existing_location is not None
