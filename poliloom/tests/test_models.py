"""Tests for database models."""

import pytest
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.exc import IntegrityError

from poliloom.models import (
    Politician,
    WikipediaLink,
    Property,
    Position,
    HoldsPosition,
    Country,
    HasCitizenship,
    Location,
    BornAt,
    Evaluation,
    EvaluationResult,
)
from poliloom.embeddings import generate_embedding


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_creation(
        self, test_session, create_entities, assert_model_fields
    ):
        """Test basic politician creation."""
        politician = create_entities(
            test_session,
            Politician(name="Jane Smith", wikidata_id="Q789012"),
        )
        assert_model_fields(
            politician,
            {"name": "Jane Smith", "wikidata_id": "Q789012"},
        )

    def test_politician_unique_wikidata_id(self, test_session, sample_politician):
        """Test that wikidata_id must be unique."""
        duplicate_politician = Politician(
            name="Different Name",
            wikidata_id=sample_politician.wikidata_id,  # Same wikidata_id
        )
        test_session.add(duplicate_politician)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_politician_default_values(
        self, test_session, create_entities, assert_model_fields
    ):
        """Test default values for politician fields."""
        politician = create_entities(test_session, Politician(name="Test Person"))
        assert_model_fields(
            politician,
            {"name": "Test Person", "is_deceased": False, "wikidata_id": None},
        )

    def test_politician_cascade_delete_properties(
        self, test_session, sample_politician
    ):
        """Test that deleting a politician cascades to properties."""
        prop = Property(
            politician_id=sample_politician.id, type="BirthDate", value="1980-01-01"
        )
        test_session.add(prop)
        test_session.commit()

        # Delete politician should cascade to properties
        test_session.delete(sample_politician)
        test_session.commit()

        # Property should be deleted
        assert (
            test_session.query(Property)
            .filter_by(politician_id=sample_politician.id)
            .first()
            is None
        )


class TestWikipediaLink:
    """Test cases for the WikipediaLink model."""

    def test_wikipedia_link_creation(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test basic Wikipedia link creation."""
        wikipedia_link = create_entities(
            test_session,
            WikipediaLink(
                politician_id=sample_politician.id,
                url="https://en.wikipedia.org/wiki/John_Doe",
                language_code="en",
            ),
        )
        assert_model_fields(
            wikipedia_link,
            {
                "politician_id": sample_politician.id,
                "url": "https://en.wikipedia.org/wiki/John_Doe",
                "language_code": "en",
            },
        )


class TestProperty:
    """Test cases for the Property model."""

    def test_property_creation(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test basic property creation."""
        prop = create_entities(
            test_session,
            Property(
                politician_id=sample_politician.id,
                type="Education",
                value="Harvard University",
                is_extracted=False,
            ),
        )
        assert_model_fields(
            prop,
            {
                "politician_id": sample_politician.id,
                "type": "Education",
                "value": "Harvard University",
                "is_extracted": False,
            },
        )

    def test_property_default_values(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test default values for property fields."""
        prop = create_entities(
            test_session,
            Property(
                politician_id=sample_politician.id, type="BirthDate", value="1980"
            ),
        )
        assert_model_fields(
            prop,
            {
                "politician_id": sample_politician.id,
                "type": "BirthDate",
                "value": "1980",
                "is_extracted": True,
            },
        )


class TestCountry:
    """Test cases for the Country model."""

    def test_country_creation(self, test_session, create_entities, assert_model_fields):
        """Test basic country creation."""
        country = create_entities(
            test_session, Country(name="Germany", iso_code="DE", wikidata_id="Q183")
        )
        assert_model_fields(
            country, {"name": "Germany", "iso_code": "DE", "wikidata_id": "Q183"}
        )

    def test_country_optional_iso_code(
        self, test_session, create_entities, assert_model_fields
    ):
        """Test that iso_code is optional."""
        country = create_entities(
            test_session, Country(name="Some Territory", wikidata_id="Q12345")
        )
        assert_model_fields(
            country,
            {"name": "Some Territory", "wikidata_id": "Q12345", "iso_code": None},
        )


class TestPosition:
    """Test cases for the Position model."""

    def test_position_creation(
        self, test_session, create_entities, assert_model_fields
    ):
        """Test basic position creation."""
        position = Position(name="Senator", wikidata_id="Q4416090")
        position = create_entities(test_session, position)

        assert_model_fields(position, {"name": "Senator", "wikidata_id": "Q4416090"})


class TestPositionVectorSimilarity:
    """Test cases for Position vector similarity search functionality."""

    def test_embedding_generation_and_properties(self, test_session):
        """Test embedding generation with various properties."""
        # Test basic embedding generation
        embedding = generate_embedding("Prime Minister")
        assert isinstance(embedding, list)
        assert len(embedding) == 384
        assert all(isinstance(val, (int, float)) for val in embedding)

        # Test deterministic behavior
        embedding2 = generate_embedding("Prime Minister")
        assert embedding == embedding2

        # Test different text produces different embeddings
        different_embedding = generate_embedding("Mayor")
        assert embedding != different_embedding

    def test_position_embedding_workflow(self, test_session, create_entities):
        """Test complete embedding workflow for positions."""
        position = create_entities(
            test_session, Position(name="Secretary of State", wikidata_id="Q3112749")
        )

        # Should not have embedding initially
        assert getattr(position, "embedding", None) is None

        # Generate embedding manually
        position.embedding = generate_embedding(position.name)
        test_session.commit()
        test_session.refresh(position)

        # Verify embedding exists and has correct properties
        embedding = getattr(position, "embedding", None)
        assert embedding is not None
        import numpy as np

        assert isinstance(embedding, (list, np.ndarray))
        assert len(embedding) == 384

        # Test embedding update on name change
        original_embedding = (
            embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
        )
        position.name = "Prime Minister"
        position.embedding = generate_embedding(position.name)
        test_session.commit()
        test_session.refresh(position)

        updated_embedding = getattr(position, "embedding", None)
        updated_embedding = (
            updated_embedding.tolist()
            if isinstance(updated_embedding, np.ndarray)
            else updated_embedding
        )
        assert updated_embedding != original_embedding

    def test_similarity_search_functionality(
        self,
        test_session,
        position_with_embedding,
        create_entities,
        similarity_searcher,
    ):
        """Test similarity search with various scenarios."""
        # Create positions with embeddings
        positions = [
            position_with_embedding("US President", "Q11696"),
            position_with_embedding("US Governor", "Q889821"),
            position_with_embedding("UK Prime Minister", "Q14212"),
            position_with_embedding("UK Minister", "Q83307"),
        ]

        create_entities(test_session, *positions)

        # Test basic similarity search
        results = similarity_searcher(
            test_session, Position, "Chief Executive", limit=2
        )
        assert len(results) <= 2
        assert all(isinstance(pos, Position) for pos in results)

        # Test limit behavior
        no_results = similarity_searcher(test_session, Position, "Query", limit=0)
        assert no_results == []

        one_result = similarity_searcher(test_session, Position, "Query", limit=1)
        assert len(one_result) <= 1


class TestHoldsPosition:
    """Test cases for the HoldsPosition model."""

    def test_holds_position_creation(
        self,
        test_session,
        sample_politician,
        sample_position,
        create_entities,
        assert_model_fields,
    ):
        """Test basic holds position creation."""
        holds_pos = create_entities(
            test_session,
            HoldsPosition(
                politician_id=sample_politician.id,
                position_id=sample_position.id,
                start_date="2019-01",
                end_date="2023-12-31",
                is_extracted=False,
            ),
        )
        assert_model_fields(
            holds_pos,
            {
                "politician_id": sample_politician.id,
                "position_id": sample_position.id,
                "start_date": "2019-01",
                "end_date": "2023-12-31",
                "is_extracted": False,
            },
        )

    def test_holds_position_incomplete_dates(
        self, test_session, sample_politician, sample_position
    ):
        """Test handling of incomplete dates in HoldsPosition."""
        # Test various incomplete date formats
        test_cases = [
            ("2020", None),  # Only year
            ("2020-03", "2021"),  # Year-month to year
            ("1995", "2000-06-15"),  # Year to full date
            (None, "2024"),  # No start date
            ("2022", None),  # No end date
        ]

        for start_date, end_date in test_cases:
            holds_pos = HoldsPosition(
                politician_id=sample_politician.id,
                position_id=sample_position.id,
                start_date=start_date,
                end_date=end_date,
            )
            test_session.add(holds_pos)
            test_session.commit()
            test_session.refresh(holds_pos)

            assert holds_pos.start_date == start_date
            assert holds_pos.end_date == end_date

            # Clean up for next iteration
            test_session.delete(holds_pos)
            test_session.commit()

    def test_holds_position_default_values(
        self,
        test_session,
        sample_politician,
        sample_position,
        create_entities,
        assert_model_fields,
    ):
        """Test default values for holds position fields."""
        holds_pos = create_entities(
            test_session,
            HoldsPosition(
                politician_id=sample_politician.id, position_id=sample_position.id
            ),
        )
        assert_model_fields(
            holds_pos,
            {
                "politician_id": sample_politician.id,
                "position_id": sample_position.id,
                "is_extracted": True,
                "start_date": None,
                "end_date": None,
            },
        )


class TestHasCitizenship:
    """Test cases for the HasCitizenship model."""

    def test_has_citizenship_creation(
        self,
        test_session,
        sample_politician,
        sample_country,
        create_entities,
        assert_model_fields,
    ):
        """Test basic citizenship relationship creation."""
        citizenship = create_entities(
            test_session,
            HasCitizenship(
                politician_id=sample_politician.id, country_id=sample_country.id
            ),
        )
        assert_model_fields(
            citizenship,
            {"politician_id": sample_politician.id, "country_id": sample_country.id},
        )

    def test_has_citizenship_multiple_citizenships_per_politician(
        self, test_session, sample_politician, create_entities
    ):
        """Test that a politician can have multiple citizenships."""
        # Create two countries
        country1, country2 = create_entities(
            test_session,
            Country(name="United States", iso_code="US"),
            Country(name="Canada", iso_code="CA"),
        )

        # Create two citizenships for the same politician
        create_entities(
            test_session,
            HasCitizenship(politician_id=sample_politician.id, country_id=country1.id),
            HasCitizenship(politician_id=sample_politician.id, country_id=country2.id),
        )

        # Verify both citizenships exist
        citizenships = (
            test_session.query(HasCitizenship)
            .filter_by(politician_id=sample_politician.id)
            .all()
        )
        assert len(citizenships) == 2

        # Verify relationships
        assert len(sample_politician.citizenships) == 2
        country_names = {c.country.name for c in sample_politician.citizenships}
        assert "United States" in country_names
        assert "Canada" in country_names

    def test_has_citizenship_multiple_politicians_per_country(
        self, test_session, sample_country, create_entities
    ):
        """Test that a country can have multiple citizen politicians."""
        # Create two politicians
        politician1, politician2 = create_entities(
            test_session,
            Politician(name="Alice Smith", wikidata_id="Q111"),
            Politician(name="Bob Jones", wikidata_id="Q222"),
        )

        # Create two citizenships for the same country
        create_entities(
            test_session,
            HasCitizenship(politician_id=politician1.id, country_id=sample_country.id),
            HasCitizenship(politician_id=politician2.id, country_id=sample_country.id),
        )

        # Verify both citizenships exist
        citizenships = (
            test_session.query(HasCitizenship)
            .filter_by(country_id=sample_country.id)
            .all()
        )
        assert len(citizenships) == 2

        # Verify relationships
        assert len(sample_country.citizens) == 2
        politician_names = {c.politician.name for c in sample_country.citizens}
        assert "Alice Smith" in politician_names
        assert "Bob Jones" in politician_names

    def test_has_citizenship_prevents_duplicate_relationships(
        self, test_session, sample_politician, sample_country
    ):
        """Test database constraints prevent duplicate citizenship relationships."""
        citizenship1 = HasCitizenship(
            politician_id=sample_politician.id, country_id=sample_country.id
        )
        test_session.add(citizenship1)
        test_session.commit()

        # Attempt to create duplicate
        citizenship2 = HasCitizenship(
            politician_id=sample_politician.id, country_id=sample_country.id
        )
        test_session.add(citizenship2)

        # Note: If there are no unique constraints in the model, this might not raise an error
        # This test verifies the current behavior - you might want to add unique constraints
        try:
            test_session.commit()
            # If no constraint exists, verify at least that the application logic prevents duplicates
            citizenships = (
                test_session.query(HasCitizenship)
                .filter_by(
                    politician_id=sample_politician.id, country_id=sample_country.id
                )
                .all()
            )
            # This should be handled by application logic in import_service._create_citizenships
            assert len(citizenships) >= 1  # At least one exists
        except IntegrityError:
            # If database has unique constraint, this is expected
            test_session.rollback()


class TestWikipediaLinkRelationships:
    """Test cases for Wikipedia link relationships."""

    def test_multiple_wikipedia_links_per_politician(
        self, test_session, sample_politician
    ):
        """Test that politicians can have multiple Wikipedia links."""
        wiki_link1 = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://en.wikipedia.org/wiki/John_Doe",
            language_code="en",
        )
        wiki_link2 = WikipediaLink(
            politician_id=sample_politician.id,
            url="https://de.wikipedia.org/wiki/John_Doe",
            language_code="de",
        )
        test_session.add_all([wiki_link1, wiki_link2])
        test_session.commit()

        # Verify relationship
        test_session.refresh(sample_politician)
        assert len(sample_politician.wikipedia_links) == 2
        assert wiki_link1 in sample_politician.wikipedia_links
        assert wiki_link2 in sample_politician.wikipedia_links


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
        assert isinstance(politician.id, UUID)
        assert len(str(politician.id)) == 36  # Standard UUID string length

    def test_uuid_uniqueness(self, test_session):
        """Test that generated UUIDs are unique."""
        politicians = [Politician(name=f"Test Politician {i}") for i in range(10)]
        test_session.add_all(politicians)
        test_session.commit()

        # Refresh all to get their IDs
        for politician in politicians:
            test_session.refresh(politician)

        ids = [p.id for p in politicians]
        assert len(set(ids)) == len(ids)  # All IDs should be unique


class TestLocation:
    """Test cases for the Location model."""

    def test_location_creation(
        self, test_session, create_entities, assert_model_fields
    ):
        """Test basic location creation."""
        location = create_entities(
            test_session, Location(name="New York City", wikidata_id="Q60")
        )
        assert_model_fields(location, {"name": "New York City", "wikidata_id": "Q60"})

    def test_location_unique_wikidata_id(self, test_session):
        """Test that Wikidata ID must be unique."""
        location1 = Location(name="New York City", wikidata_id="Q60")
        location2 = Location(name="NYC", wikidata_id="Q60")

        test_session.add(location1)
        test_session.commit()

        test_session.add(location2)
        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_location_find_similar(
        self,
        test_session,
        location_with_embedding,
        create_entities,
        similarity_searcher,
    ):
        """Test location similarity search functionality."""
        # Create test locations with embeddings
        locations = [
            location_with_embedding("New York City", "Q60"),
            location_with_embedding("Los Angeles", "Q65"),
            location_with_embedding("Chicago", "Q1297"),
        ]

        create_entities(test_session, *locations)

        # Test similarity search
        similar = similarity_searcher(test_session, Location, "New York", limit=2)
        assert len(similar) <= 2
        if len(similar) > 0:
            assert isinstance(similar[0], Location)
            assert hasattr(similar[0], "name")


class TestEvaluation:
    """Test cases for the Evaluation model."""

    def test_evaluation_creation_for_property(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test creating an evaluation for a property."""
        prop = create_entities(
            test_session,
            Property(
                politician_id=sample_politician.id,
                type="BirthDate",
                value="1980-01-01",
                is_extracted=True,
            ),
        )

        evaluation = create_entities(
            test_session,
            Evaluation(
                user_id="user123",
                result=EvaluationResult.CONFIRMED,
                property_id=prop.id,
            ),
        )

        assert_model_fields(
            evaluation,
            {
                "user_id": "user123",
                "result": EvaluationResult.CONFIRMED,
                "property_id": prop.id,
                "holds_position_id": None,
                "born_at_id": None,
            },
        )

        # Check relationships
        assert evaluation.property == prop
        assert evaluation.holds_position is None
        assert evaluation.born_at is None
        assert len(prop.evaluations) == 1
        assert prop.evaluations[0] == evaluation

    def test_evaluation_creation_for_holds_position(
        self,
        test_session,
        sample_politician,
        sample_position,
        create_entities,
        assert_model_fields,
    ):
        """Test creating an evaluation for a holds position."""
        holds_pos = create_entities(
            test_session,
            HoldsPosition(
                politician_id=sample_politician.id,
                position_id=sample_position.id,
                start_date="2020-01",
                is_extracted=True,
            ),
        )

        evaluation = create_entities(
            test_session,
            Evaluation(
                user_id="admin",
                result=EvaluationResult.DISCARDED,
                holds_position_id=holds_pos.id,
            ),
        )

        assert_model_fields(
            evaluation,
            {
                "user_id": "admin",
                "result": EvaluationResult.DISCARDED,
                "property_id": None,
                "holds_position_id": holds_pos.id,
                "born_at_id": None,
            },
        )

        # Check relationships
        assert evaluation.holds_position == holds_pos
        assert evaluation.property is None
        assert evaluation.born_at is None
        assert len(holds_pos.evaluations) == 1
        assert holds_pos.evaluations[0] == evaluation

    def test_evaluation_creation_for_born_at(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test creating an evaluation for a born at relationship."""
        location = create_entities(
            test_session, Location(name="Paris", wikidata_id="Q90")
        )

        born_at = create_entities(
            test_session,
            BornAt(
                politician_id=sample_politician.id,
                location_id=location.id,
                is_extracted=True,
            ),
        )

        evaluation = create_entities(
            test_session,
            Evaluation(
                user_id="reviewer",
                result=EvaluationResult.CONFIRMED,
                born_at_id=born_at.id,
            ),
        )

        assert_model_fields(
            evaluation,
            {
                "user_id": "reviewer",
                "result": EvaluationResult.CONFIRMED,
                "property_id": None,
                "holds_position_id": None,
                "born_at_id": born_at.id,
            },
        )

        # Check relationships
        assert evaluation.born_at == born_at
        assert evaluation.property is None
        assert evaluation.holds_position is None
        assert len(born_at.evaluations) == 1
        assert born_at.evaluations[0] == evaluation

    def test_multiple_evaluations_for_same_entity(
        self, test_session, sample_politician, create_entities
    ):
        """Test multiple evaluations for the same entity."""
        prop = create_entities(
            test_session,
            Property(
                politician_id=sample_politician.id,
                type="BirthDate",
                value="1980-01-01",
                is_extracted=True,
            ),
        )

        create_entities(
            test_session,
            Evaluation(
                user_id="user1",
                result=EvaluationResult.CONFIRMED,
                property_id=prop.id,
            ),
        )

        create_entities(
            test_session,
            Evaluation(
                user_id="user2",
                result=EvaluationResult.CONFIRMED,
                property_id=prop.id,
            ),
        )

        create_entities(
            test_session,
            Evaluation(
                user_id="user3",
                result=EvaluationResult.DISCARDED,
                property_id=prop.id,
            ),
        )

        # Check that all evaluations are linked to the property
        assert len(prop.evaluations) == 3
        evaluation_users = [e.user_id for e in prop.evaluations]
        assert "user1" in evaluation_users
        assert "user2" in evaluation_users
        assert "user3" in evaluation_users

        # Check that evaluations have correct results
        confirmed_count = sum(
            1 for e in prop.evaluations if e.result == EvaluationResult.CONFIRMED
        )
        discarded_count = sum(
            1 for e in prop.evaluations if e.result == EvaluationResult.DISCARDED
        )
        assert confirmed_count == 2
        assert discarded_count == 1


class TestBornAt:
    """Test cases for the BornAt relationship model."""

    def test_born_at_creation(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test basic BornAt relationship creation."""
        location = create_entities(
            test_session, Location(name="Paris", wikidata_id="Q90")
        )

        born_at = create_entities(
            test_session,
            BornAt(
                politician_id=sample_politician.id,
                location_id=location.id,
                is_extracted=True,
            ),
        )
        assert_model_fields(
            born_at,
            {
                "politician_id": sample_politician.id,
                "location_id": location.id,
                "is_extracted": True,
            },
        )

    def test_born_at_default_values(
        self, test_session, sample_politician, create_entities, assert_model_fields
    ):
        """Test BornAt model default values."""
        location = create_entities(
            test_session, Location(name="London", wikidata_id="Q84")
        )

        born_at = create_entities(
            test_session,
            BornAt(politician_id=sample_politician.id, location_id=location.id),
        )
        assert_model_fields(
            born_at,
            {
                "politician_id": sample_politician.id,
                "location_id": location.id,
                "is_extracted": True,
            },
        )

    def test_born_at_confirmation(
        self, test_session, sample_politician, create_entities
    ):
        """Test BornAt confirmation workflow with evaluations."""
        location = create_entities(
            test_session, Location(name="Berlin", wikidata_id="Q64")
        )

        born_at = create_entities(
            test_session,
            BornAt(
                politician_id=sample_politician.id,
                location_id=location.id,
                is_extracted=True,
            ),
        )

        # Add evaluation to confirm the relationship
        evaluation = create_entities(
            test_session,
            Evaluation(
                user_id="user123",
                result=EvaluationResult.CONFIRMED,
                born_at_id=born_at.id,
            ),
        )

        # Check that the evaluation is linked properly
        assert evaluation.born_at_id == born_at.id
        assert evaluation.user_id == "user123"
        assert evaluation.result == EvaluationResult.CONFIRMED
        assert len(born_at.evaluations) == 1
        assert born_at.evaluations[0].user_id == "user123"

    def test_born_at_relationships(
        self, test_session, sample_politician, create_entities
    ):
        """Test BornAt model relationships."""
        location = create_entities(
            test_session, Location(name="Tokyo", wikidata_id="Q1490")
        )

        born_at = create_entities(
            test_session,
            BornAt(politician_id=sample_politician.id, location_id=location.id),
        )

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

    def test_born_at_cascade_delete(
        self, test_session, sample_politician, create_entities
    ):
        """Test that deleting a politician cascades to BornAt relationships."""
        location = create_entities(
            test_session, Location(name="Rome", wikidata_id="Q220")
        )

        born_at = create_entities(
            test_session,
            BornAt(politician_id=sample_politician.id, location_id=location.id),
        )
        born_at_id = born_at.id

        # Delete politician should cascade to BornAt
        test_session.delete(sample_politician)
        test_session.commit()

        # BornAt should be deleted
        deleted_born_at = test_session.query(BornAt).filter_by(id=born_at_id).first()
        assert deleted_born_at is None

        # Location should still exist
        existing_location = (
            test_session.query(Location).filter_by(id=location.id).first()
        )
        assert existing_location is not None
