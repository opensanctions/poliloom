"""Tests for the HoldsPosition model."""

from poliloom.models import Politician, Position, HoldsPosition
from ..conftest import assert_model_fields


class TestHoldsPosition:
    """Test cases for the HoldsPosition model."""

    def test_holds_position_creation(
        self,
        db_session,
        sample_politician_data,
        sample_position_data,
    ):
        """Test basic holds position creation."""
        # Create politician
        politician = Politician(**sample_politician_data)
        db_session.add(politician)

        # Create position with wikidata entity
        position = Position.create_with_entity(
            db_session, sample_position_data["wikidata_id"], "Test Position"
        )
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
            position = Position.create_with_entity(
                db_session, position_qid, f"Test Position {position_qid}"
            )
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
    ):
        """Test default values for holds position fields."""
        # Create politician and position
        politician = Politician(**sample_politician_data)
        position = Position.create_with_entity(db_session, "Q30185", "Test Position")
        db_session.add(politician)
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
