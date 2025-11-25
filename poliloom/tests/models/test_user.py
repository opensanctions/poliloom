"""Tests for evaluation models."""

from poliloom.models import Evaluation
from ..conftest import assert_model_fields


class TestEvaluation:
    """Test cases for the Evaluation model."""

    def test_date_property_evaluation_creation(
        self, db_session, sample_politician, create_birth_date
    ):
        """Test creating an evaluation for a date property."""
        # Create date property using fixture
        prop = create_birth_date(sample_politician)
        db_session.flush()
        db_session.refresh(prop)

        # Create evaluation
        evaluation = Evaluation(
            user_id="user123",
            is_accepted=True,
            property_id=prop.id,
        )
        db_session.add(evaluation)
        db_session.flush()
        db_session.refresh(evaluation)

        assert_model_fields(
            evaluation,
            {
                "user_id": "user123",
                "is_accepted": True,
                "property_id": prop.id,
            },
        )

        # Check relationships
        assert evaluation.property == prop
        assert len(prop.evaluations) == 1
        assert prop.evaluations[0] == evaluation


class TestEvaluationMultiple:
    """Test cases for multiple evaluations."""

    def test_multiple_evaluations_for_same_property(
        self, db_session, sample_politician, create_birth_date
    ):
        """Test multiple evaluations for the same property."""
        # Create property using fixture
        prop = create_birth_date(sample_politician)
        db_session.flush()
        db_session.refresh(prop)

        # Create evaluations
        evaluations = [
            Evaluation(
                user_id="user1",
                is_accepted=True,
                property_id=prop.id,
            ),
            Evaluation(
                user_id="user2",
                is_accepted=True,
                property_id=prop.id,
            ),
            Evaluation(
                user_id="user3",
                is_accepted=False,
                property_id=prop.id,
            ),
        ]

        db_session.add_all(evaluations)
        db_session.flush()

        # Check that all evaluations are linked to the property
        assert len(prop.evaluations) == 3
        evaluation_users = [e.user_id for e in prop.evaluations]
        assert "user1" in evaluation_users
        assert "user2" in evaluation_users
        assert "user3" in evaluation_users

        # Check that evaluations have correct results
        confirmed_count = sum(1 for e in prop.evaluations if e.is_accepted)
        discarded_count = sum(1 for e in prop.evaluations if not e.is_accepted)
        assert confirmed_count == 2
        assert discarded_count == 1

    def test_multiple_evaluations_for_different_property_types(
        self,
        db_session,
        sample_politician,
        sample_location,
        sample_position,
        create_birth_date,
        create_birthplace,
        create_position,
    ):
        """Test evaluations for different property types."""
        # Create different types of properties using fixtures
        date_prop = create_birth_date(sample_politician)
        birthplace_prop = create_birthplace(sample_politician, sample_location)
        position_prop = create_position(sample_politician, sample_position)

        db_session.flush()
        db_session.refresh(date_prop)
        db_session.refresh(birthplace_prop)
        db_session.refresh(position_prop)

        # Create evaluations for each property
        evaluations = [
            Evaluation(
                user_id="user1",
                is_accepted=True,
                property_id=date_prop.id,
            ),
            Evaluation(
                user_id="user1",
                is_accepted=False,
                property_id=birthplace_prop.id,
            ),
            Evaluation(
                user_id="user1",
                is_accepted=True,
                property_id=position_prop.id,
            ),
        ]

        db_session.add_all(evaluations)
        db_session.flush()

        # Check that each property has one evaluation
        assert len(date_prop.evaluations) == 1
        assert len(birthplace_prop.evaluations) == 1
        assert len(position_prop.evaluations) == 1

        # Check evaluation results
        assert date_prop.evaluations[0].is_accepted is True
        assert birthplace_prop.evaluations[0].is_accepted is False
        assert position_prop.evaluations[0].is_accepted is True
