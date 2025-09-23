"""Tests for the HoldsPosition model."""

from poliloom.models import HoldsPosition
from poliloom.enrichment import create_qualifiers_json_for_position
from ..conftest import assert_model_fields


class TestHoldsPosition:
    """Test cases for the HoldsPosition model."""

    def test_holds_position_creation(self, sample_holds_position):
        """Test basic holds position creation using fixture."""
        holds_pos = sample_holds_position

        # Verify basic fields
        assert holds_pos.politician_id is not None
        assert holds_pos.position_id is not None
        assert holds_pos.qualifiers_json is not None

        # Verify qualifiers_json structure has expected date qualifiers
        assert "P580" in holds_pos.qualifiers_json  # start time
        assert "P582" in holds_pos.qualifiers_json  # end time

    def test_holds_position_with_qualifiers_json(
        self, db_session, sample_politician, sample_position
    ):
        """Test creating HoldsPosition with custom qualifiers_json."""
        qualifiers_json = create_qualifiers_json_for_position("2020", "2023-06")

        holds_pos = HoldsPosition(
            politician_id=sample_politician.id,
            position_id=sample_position.wikidata_id,
            qualifiers_json=qualifiers_json,
        )
        db_session.add(holds_pos)
        db_session.commit()
        db_session.refresh(holds_pos)

        assert holds_pos.qualifiers_json is not None
        assert "P580" in holds_pos.qualifiers_json
        assert "P582" in holds_pos.qualifiers_json

    def test_holds_position_default_values(
        self, db_session, sample_politician, sample_position
    ):
        """Test default values for holds position fields."""
        # Create holds position with minimal data
        holds_pos = HoldsPosition(
            politician_id=sample_politician.id, position_id=sample_position.wikidata_id
        )
        db_session.add(holds_pos)
        db_session.commit()
        db_session.refresh(holds_pos)

        assert_model_fields(
            holds_pos,
            {
                "politician_id": sample_politician.id,
                "position_id": sample_position.wikidata_id,
                "archived_page_id": None,
                "qualifiers_json": None,
            },
        )

    def test_create_qualifiers_json_for_position(self):
        """Test the helper function for creating qualifiers_json."""
        # Test with both dates
        qualifiers = create_qualifiers_json_for_position("2020-01", "2023-12-31")
        assert qualifiers is not None
        assert "P580" in qualifiers
        assert "P582" in qualifiers

        # Test with only start date
        qualifiers = create_qualifiers_json_for_position("2020", None)
        assert qualifiers is not None
        assert "P580" in qualifiers
        assert "P582" not in qualifiers

        # Test with only end date
        qualifiers = create_qualifiers_json_for_position(None, "2023")
        assert qualifiers is not None
        assert "P580" not in qualifiers
        assert "P582" in qualifiers

        # Test with no dates
        qualifiers = create_qualifiers_json_for_position(None, None)
        assert qualifiers is None
