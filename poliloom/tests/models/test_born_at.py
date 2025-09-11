"""Tests for the BornAt relationship model."""

from sqlalchemy.orm import selectinload

from poliloom.models import Politician, Location, BornAt, BirthplaceEvaluation
from ..conftest import assert_model_fields


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
        location = Location.create_with_entity(db_session, "Q90", "Paris")
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
        location = Location.create_with_entity(db_session, "Q84", "London")
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
        location = Location.create_with_entity(db_session, "Q64", "Berlin")
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

        # Create location with entity
        location = Location.create_with_entity(db_session, "Q1490", "Tokyo")
        db_session.commit()
        db_session.refresh(location)

        # Create born at
        born_at = BornAt(politician_id=politician.id, location_id=location.wikidata_id)
        db_session.add(born_at)
        db_session.commit()
        # Refresh born_at with location and wikidata_entity loaded
        born_at = (
            db_session.query(BornAt)
            .options(selectinload(BornAt.location))
            .filter_by(id=born_at.id)
            .first()
        )

        # Test politician relationship
        assert born_at.politician.id == politician.id
        assert born_at.politician.name == politician.name

        # Test location relationship
        assert born_at.location.wikidata_id == location.wikidata_id
        assert born_at.location.wikidata_entity.name == "Tokyo"

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
        location = Location.create_with_entity(db_session, "Q220", "Rome")
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
