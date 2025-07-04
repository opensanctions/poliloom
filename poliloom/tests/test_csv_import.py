"""Tests for CSV import functionality."""

import pytest
import tempfile
import os
from unittest.mock import patch
from pathlib import Path

from poliloom.services.import_service import ImportService
from poliloom.models import Position, Country


class TestCSVImport:
    """Test CSV import functionality."""

    @pytest.fixture
    def test_csv_file(self):
        """Path to test CSV fixture."""
        return Path(__file__).parent / "fixtures" / "test_positions.csv"

    @pytest.fixture
    def sample_countries(self, test_session):
        """Create sample countries for testing."""
        countries = [
            Country(name="Spain", iso_code="ES", wikidata_id="Q29"),
            Country(name="South Korea", iso_code="KR", wikidata_id="Q884"),
            Country(name="United States", iso_code="US", wikidata_id="Q30"),
            Country(name="Canada", iso_code="CA", wikidata_id="Q16"),
        ]
        for country in countries:
            test_session.add(country)
        test_session.commit()
        return countries

    def test_import_positions_from_csv_success(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test successful import of positions from CSV file."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_positions_from_csv(str(test_csv_file))

        # Should import 7 positions (filtering out FALSE is_pep and invalid rows)
        # Valid positions: Q110118256, Q134765401, Q134765105, Q134758719, Q134758625, Q134758519, Q134758330
        assert result == 7

        # Verify positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 7

        # Check specific positions
        mayor_hongseong = (
            test_session.query(Position).filter_by(wikidata_id="Q110118256").first()
        )
        assert mayor_hongseong is not None
        assert mayor_hongseong.name == "Mayor of Hongseong"
        # Should map to South Korea
        kr_country = test_session.query(Country).filter_by(iso_code="KR").first()
        assert len(mayor_hongseong.countries) == 1
        assert mayor_hongseong.countries[0].id == kr_country.id

        mayor_jeongeup = (
            test_session.query(Position).filter_by(wikidata_id="Q134765401").first()
        )
        assert mayor_jeongeup is not None
        assert mayor_jeongeup.name == "Mayor of Jeongeup"
        assert len(mayor_jeongeup.countries) == 1
        assert mayor_jeongeup.countries[0].id == kr_country.id

        mayor_gunsan = (
            test_session.query(Position).filter_by(wikidata_id="Q134765105").first()
        )
        assert mayor_gunsan is not None
        assert mayor_gunsan.name == "Mayor of Gunsan"
        # Should map to United States
        us_country = test_session.query(Country).filter_by(iso_code="US").first()
        assert len(mayor_gunsan.countries) == 1
        assert mayor_gunsan.countries[0].id == us_country.id

    def test_import_positions_filters_false_is_pep(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test that positions with is_pep=FALSE are filtered out."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            import_service.import_positions_from_csv(str(test_csv_file))

        # Should not import positions with is_pep=FALSE
        filtered_positions = ["Q89279295", "Q134765299"]  # These have is_pep=FALSE

        for wikidata_id in filtered_positions:
            position = (
                test_session.query(Position).filter_by(wikidata_id=wikidata_id).first()
            )
            assert position is None, (
                f"Position {wikidata_id} should have been filtered out"
            )

    def test_import_positions_handles_empty_countries(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test handling of positions with empty or missing countries."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            import_service.import_positions_from_csv(str(test_csv_file))

        # Check position with empty countries array
        position_empty_countries = (
            test_session.query(Position).filter_by(wikidata_id="Q134758719").first()
        )
        assert position_empty_countries is not None
        assert len(position_empty_countries.countries) == 0

        # Check position with empty string for countries
        position_empty_string = (
            test_session.query(Position).filter_by(wikidata_id="Q134758519").first()
        )
        assert position_empty_string is not None
        assert len(position_empty_string.countries) == 0

    def test_import_positions_uses_all_countries(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test that all countries from the countries array are linked to the position."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            import_service.import_positions_from_csv(str(test_csv_file))

        # Check position with multiple countries - should link to both (US and CA)
        position_multi_countries = (
            test_session.query(Position).filter_by(wikidata_id="Q134758625").first()
        )
        assert position_multi_countries is not None
        us_country = test_session.query(Country).filter_by(iso_code="US").first()
        ca_country = test_session.query(Country).filter_by(iso_code="CA").first()

        assert len(position_multi_countries.countries) == 2
        country_ids = {country.id for country in position_multi_countries.countries}
        assert us_country.id in country_ids
        assert ca_country.id in country_ids

    def test_import_positions_skips_invalid_rows(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test that rows with missing required fields are skipped."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            import_service.import_positions_from_csv(str(test_csv_file))

        # Should skip row with empty caption only - Q134758330 has valid entity_id and caption
        invalid_positions = ["Q134758429"]  # Empty caption only

        for wikidata_id in invalid_positions:
            position = (
                test_session.query(Position).filter_by(wikidata_id=wikidata_id).first()
            )
            assert position is None, (
                f"Invalid position {wikidata_id} should have been skipped"
            )

        # Q134758330 should be imported as it has valid entity_id and caption
        valid_position = (
            test_session.query(Position).filter_by(wikidata_id="Q134758330").first()
        )
        assert valid_position is not None, (
            "Position Q134758330 should have been imported"
        )

    def test_import_positions_skips_existing(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test that existing positions are skipped."""
        import_service = ImportService()

        # Create existing position
        existing_position = Position(
            name="Existing Mayor",
            wikidata_id="Q110118256",  # Same as one in CSV
        )
        test_session.add(existing_position)
        test_session.commit()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_positions_from_csv(str(test_csv_file))

        # Should import 6 positions (7 total - 1 existing)
        assert result == 6

        # Verify existing position wasn't updated
        existing = (
            test_session.query(Position).filter_by(wikidata_id="Q110118256").first()
        )
        assert existing.name == "Existing Mayor"  # Original name preserved

    def test_import_positions_creates_unknown_countries(
        self, test_session, test_csv_file
    ):
        """Test that positions with unknown country codes create countries on-demand."""
        import_service = ImportService()

        # Don't add any countries to the database initially

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_positions_from_csv(str(test_csv_file))

        # Should import positions and create countries on-demand
        assert result == 7

        # Check that countries were created for positions that reference them
        from poliloom.models import Country

        countries = test_session.query(Country).all()
        assert len(countries) > 0  # Countries should have been created on-demand

        # Check that positions with countries are properly linked
        positions_with_countries = (
            test_session.query(Position).filter(Position.countries.any()).all()
        )
        assert len(positions_with_countries) > 0

    def test_import_positions_file_not_found(self, test_session):
        """Test handling of non-existent CSV file."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_positions_from_csv("/nonexistent/file.csv")

        assert result == 0

        # Verify no positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 0

    def test_import_positions_malformed_csv(self, test_session, sample_countries):
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
                with patch(
                    "poliloom.services.import_service.SessionLocal",
                    return_value=test_session,
                ):
                    result = import_service.import_positions_from_csv(f.name)

                # Should import 2 positions (both have valid entity_id and caption)
                # Q123 has invalid JSON but still gets imported with no countries
                # Q124 has valid JSON and gets imported
                assert result == 2

                # Verify both positions were created
                positions = test_session.query(Position).all()
                assert len(positions) == 2
                wikidata_ids = {pos.wikidata_id for pos in positions}
                assert "Q123" in wikidata_ids
                assert "Q124" in wikidata_ids

            finally:
                os.unlink(f.name)

    def test_import_positions_database_error(
        self, test_session, test_csv_file, sample_countries
    ):
        """Test handling of database errors during import."""
        import_service = ImportService()

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            # Mock a database error during commit
            with patch.object(
                test_session, "commit", side_effect=Exception("Database error")
            ):
                result = import_service.import_positions_from_csv(str(test_csv_file))

        assert result == 0

        # Verify rollback occurred - no positions should exist
        positions = test_session.query(Position).all()
        assert len(positions) == 0

    def test_import_positions_batch_commit(self, test_session, sample_countries):
        """Test that positions are committed in batches of 1000."""
        import_service = ImportService()

        # Create a CSV with 1250 positions to test batching
        csv_content = '"id","entity_id","caption","is_pep","countries","topics","dataset","created_at","modified_at","modified_by","deleted_at"\n'
        for i in range(1, 1251):
            csv_content += f'{i},"Q{i}","Position {i}",TRUE,"[\\"us\\"]","[]","test","2025-01-01 00:00:00",,,\n'

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            f.flush()

            try:
                with patch(
                    "poliloom.services.import_service.SessionLocal",
                    return_value=test_session,
                ):
                    # Track commits
                    original_commit = test_session.commit
                    commit_count = 0

                    def count_commits():
                        nonlocal commit_count
                        commit_count += 1
                        return original_commit()

                    with patch.object(
                        test_session, "commit", side_effect=count_commits
                    ):
                        result = import_service.import_positions_from_csv(f.name)

                assert result == 1250

                # Should commit 2 times: after 1000 and final commit
                assert commit_count >= 2

                # Verify all positions were created
                positions = test_session.query(Position).all()
                assert len(positions) == 1250

            finally:
                os.unlink(f.name)
