"""Tests for evaluation models."""

from poliloom.models import (
    Location,
    Property,
    PropertyType,
    PropertyEvaluation,
    HoldsPosition,
    PositionEvaluation,
    BornAt,
    BirthplaceEvaluation,
)
from ..conftest import assert_model_fields


class TestPropertyEvaluation:
    """Test cases for the PropertyEvaluation model."""

    def test_property_evaluation_creation(self, db_session, sample_politician):
        """Test creating a property evaluation."""
        # Use fixture politician
        politician = sample_politician

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

    def test_property_evaluation_discarded(self, db_session, sample_politician):
        """Test creating a discarded property evaluation."""
        # Use fixture politician
        politician = sample_politician

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
        sample_politician,
        sample_position,
    ):
        """Test creating a position evaluation."""
        # Use fixture entities
        politician = sample_politician
        position = sample_position

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

    def test_birthplace_evaluation_creation(self, db_session, sample_politician):
        """Test creating a birthplace evaluation."""
        # Use fixture politician
        politician = sample_politician

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
        self, db_session, sample_politician
    ):
        """Test multiple evaluations for the same property."""
        # Use fixture politician
        politician = sample_politician

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
