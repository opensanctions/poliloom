"""Tests for CSV import functionality."""

import pytest
import tempfile
import os
from pathlib import Path

from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import Country, Position
from poliloom.services.import_service import ImportService
from .conftest import load_json_fixture


class TestCSVImport:
    """Test CSV import functionality."""

    @pytest.fixture
    def test_csv_file(self):
        """Path to test CSV fixture."""
        return Path(__file__).parent / "fixtures" / "test_positions.csv"

    @pytest.fixture
    def sample_countries(self):
        """Create sample countries for testing."""

        # Load test data from fixture
        position_data = load_json_fixture("position_test_data.json")
        country_data = position_data["sample_countries"]

        countries = [
            Country(
                name=c["name"], iso_code=c["iso_code"], wikidata_id=c["wikidata_id"]
            )
            for c in country_data
        ]

        with Session(get_engine()) as session:
            for country in countries:
                session.add(country)
            session.commit()
            for country in countries:
                session.refresh(country)

        return countries

    def test_import_positions_from_csv_success(self, test_csv_file, sample_countries):
        """Test successful import of positions from CSV file."""
        import_service = ImportService()

        result = import_service.import_positions_from_csv(str(test_csv_file))

        # Should import 7 positions (filtering out FALSE is_pep and invalid rows)
        # Valid positions: Q110118256, Q134765401, Q134765105, Q134758719, Q134758625, Q134758519, Q134758330
        assert result == 7

        # Verify positions were created

        with Session(get_engine()) as session:
            positions = session.query(Position).all()
            assert len(positions) == 7

            # Check specific positions
            mayor_hongseong = (
                session.query(Position).filter_by(wikidata_id="Q110118256").first()
            )
            assert mayor_hongseong is not None
            assert mayor_hongseong.name == "Mayor of Hongseong"

            mayor_jeongeup = (
                session.query(Position).filter_by(wikidata_id="Q134765401").first()
            )
            assert mayor_jeongeup is not None
            assert mayor_jeongeup.name == "Mayor of Jeongeup"

            mayor_gunsan = (
                session.query(Position).filter_by(wikidata_id="Q134765105").first()
            )
            assert mayor_gunsan is not None
            assert mayor_gunsan.name == "Mayor of Gunsan"

    def test_import_positions_filters_false_is_pep(
        self, test_csv_file, sample_countries
    ):
        """Test that positions with is_pep=FALSE are filtered out."""
        import_service = ImportService()

        import_service.import_positions_from_csv(str(test_csv_file))

        # Should not import positions with is_pep=FALSE

        filtered_positions = ["Q89279295", "Q134765299"]  # These have is_pep=FALSE

        with Session(get_engine()) as session:
            for wikidata_id in filtered_positions:
                position = (
                    session.query(Position).filter_by(wikidata_id=wikidata_id).first()
                )
                assert position is None, (
                    f"Position {wikidata_id} should have been filtered out"
                )

    def test_import_positions_handles_empty_countries(
        self, test_csv_file, sample_countries
    ):
        """Test handling of positions with empty or missing countries."""
        import_service = ImportService()

        import_service.import_positions_from_csv(str(test_csv_file))

        # Check position with empty countries array

        with Session(get_engine()) as session:
            position_empty_countries = (
                session.query(Position).filter_by(wikidata_id="Q134758719").first()
            )
            assert position_empty_countries is not None

            # Check position with empty string for countries
            position_empty_string = (
                session.query(Position).filter_by(wikidata_id="Q134758519").first()
            )
            assert position_empty_string is not None

    def test_import_positions_uses_all_countries(self, test_csv_file, sample_countries):
        """Test that all countries from the countries array are linked to the position."""
        import_service = ImportService()

        import_service.import_positions_from_csv(str(test_csv_file))

        # Check position with multiple countries - should exist

        with Session(get_engine()) as session:
            position_multi_countries = (
                session.query(Position).filter_by(wikidata_id="Q134758625").first()
            )
            assert position_multi_countries is not None

    def test_import_positions_skips_invalid_rows(self, test_csv_file, sample_countries):
        """Test that rows with missing required fields are skipped."""
        import_service = ImportService()

        import_service.import_positions_from_csv(str(test_csv_file))

        # Should skip row with empty caption only - Q134758330 has valid entity_id and caption

        invalid_positions = ["Q134758429"]  # Empty caption only

        with Session(get_engine()) as session:
            for wikidata_id in invalid_positions:
                position = (
                    session.query(Position).filter_by(wikidata_id=wikidata_id).first()
                )
                assert position is None, (
                    f"Invalid position {wikidata_id} should have been skipped"
                )

            # Q134758330 should be imported as it has valid entity_id and caption
            valid_position = (
                session.query(Position).filter_by(wikidata_id="Q134758330").first()
            )
            assert valid_position is not None, (
                "Position Q134758330 should have been imported"
            )

    def test_import_positions_skips_existing(self, test_csv_file, sample_countries):
        """Test that existing positions are skipped."""
        import_service = ImportService()

        # Create existing position

        with Session(get_engine()) as session:
            existing_position = Position(
                name="Existing Mayor",
                wikidata_id="Q110118256",  # Same as one in CSV
            )
            session.add(existing_position)
            session.commit()

        result = import_service.import_positions_from_csv(str(test_csv_file))

        # Should import 6 positions (7 total - 1 existing)
        assert result == 6

        # Verify existing position wasn't updated
        with Session(get_engine()) as session:
            existing = (
                session.query(Position).filter_by(wikidata_id="Q110118256").first()
            )
            assert existing.name == "Existing Mayor"  # Original name preserved

    def test_import_positions_creates_unknown_countries(self, test_csv_file):
        """Test that positions with unknown country codes create countries on-demand."""
        import_service = ImportService()

        # Don't add any countries to the database initially

        result = import_service.import_positions_from_csv(str(test_csv_file))

        # Should import positions and create countries on-demand
        assert result == 7

        # Check that positions were created

        with Session(get_engine()) as session:
            positions = session.query(Position).all()
            assert len(positions) == 7

    def test_import_positions_file_not_found(self):
        """Test handling of non-existent CSV file."""
        import_service = ImportService()

        result = import_service.import_positions_from_csv("/nonexistent/file.csv")

        assert result == 0

        # Verify no positions were created

        with Session(get_engine()) as session:
            positions = session.query(Position).all()
            assert len(positions) == 0

    def test_import_positions_malformed_csv(self, sample_countries, db_session):
        """Test handling of malformed CSV data."""
        import_service = ImportService()

        # Create a malformed CSV file
        malformed_csv_content = '''id,entity_id,caption,is_pep,countries
"123","Q123","Position 1",TRUE,"invalid_json"
"124","Q124","Position 2",,"[""us""]"'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(malformed_csv_content)
            f.flush()

            try:
                result = import_service.import_positions_from_csv(f.name)

                # Should import 2 positions (both have valid entity_id and caption)
                # Q123 has invalid JSON but still gets imported with no countries
                # Q124 has valid JSON and gets imported
                assert result == 2

                # Verify both positions were created
                positions = db_session.query(Position).all()
                assert len(positions) == 2
                wikidata_ids = {pos.wikidata_id for pos in positions}
                assert "Q123" in wikidata_ids
                assert "Q124" in wikidata_ids

            finally:
                os.unlink(f.name)
