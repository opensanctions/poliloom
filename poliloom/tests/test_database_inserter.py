"""Tests for DatabaseInserter."""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import DisconnectionError

from poliloom.services.database_inserter import DatabaseInserter


class TestDatabaseInserter:
    """Test DatabaseInserter functionality."""

    @pytest.fixture
    def inserter(self):
        """Create a DatabaseInserter instance."""
        return DatabaseInserter()

    def test_insert_positions_batch(self, inserter):
        """Test inserting a batch of positions."""
        positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
            {"wikidata_id": "Q2", "name": "Position 2"},
        ]

        # Mock the database session and query
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # No existing positions

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_positions_batch(positions)

            # Should check for existing positions
            mock_session.query.assert_called_once()
            # Should add new positions
            mock_session.add_all.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_insert_positions_batch_with_duplicates(self, inserter):
        """Test inserting positions with some duplicates."""
        positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
            {"wikidata_id": "Q2", "name": "Position 2"},
            {"wikidata_id": "Q3", "name": "Position 3"},
        ]

        # Mock existing positions Q1 and Q2
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [("Q1",), ("Q2",)]

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_positions_batch(positions)

            # Should only add Q3 (the new one)
            mock_session.add_all.assert_called_once()
            added_positions = mock_session.add_all.call_args[0][0]
            assert len(added_positions) == 1
            assert added_positions[0].wikidata_id == "Q3"

    def test_insert_positions_batch_empty(self, inserter):
        """Test inserting empty batch of positions."""
        positions = []

        with patch(
            "poliloom.services.database_inserter.get_worker_session"
        ) as mock_get_session:
            inserter.insert_positions_batch(positions)

            # Should not create session for empty batch
            mock_get_session.assert_not_called()

    def test_insert_positions_batch_with_retry(self, inserter):
        """Test inserting positions with database error and retry."""
        positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
        ]

        # Mock session that fails once then succeeds
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        # First call raises exception, second succeeds
        mock_session.commit.side_effect = [
            DisconnectionError("connection lost", None, None),
            None,
        ]

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            with patch("time.sleep"):  # Mock sleep to speed up test
                inserter.insert_positions_batch(positions)

                # Should be called twice (retry)
                assert mock_session.commit.call_count == 2
                assert mock_session.rollback.call_count == 1

    def test_insert_locations_batch(self, inserter):
        """Test inserting a batch of locations."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
        ]

        # Mock the database session and query
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # No existing locations

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_locations_batch(locations)

            # Should check for existing locations
            mock_session.query.assert_called_once()
            # Should add new locations
            mock_session.add_all.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_insert_locations_batch_with_duplicates(self, inserter):
        """Test inserting locations with some duplicates."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
            {"wikidata_id": "Q3", "name": "Location 3"},
        ]

        # Mock existing locations Q1 and Q2
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [("Q1",), ("Q2",)]

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_locations_batch(locations)

            # Should only add Q3 (the new one)
            mock_session.add_all.assert_called_once()
            added_locations = mock_session.add_all.call_args[0][0]
            assert len(added_locations) == 1
            assert added_locations[0].wikidata_id == "Q3"

    def test_insert_locations_batch_empty(self, inserter):
        """Test inserting empty batch of locations."""
        locations = []

        with patch(
            "poliloom.services.database_inserter.get_worker_session"
        ) as mock_get_session:
            inserter.insert_locations_batch(locations)

            # Should not create session for empty batch
            mock_get_session.assert_not_called()

    def test_insert_countries_batch(self, inserter):
        """Test inserting a batch of countries."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
            {"wikidata_id": "Q2", "name": "Country 2", "iso_code": "C2"},
        ]

        # Mock the database session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_session.execute.return_value = mock_result

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_countries_batch(countries)

            # Should execute insert statement
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_insert_countries_batch_empty(self, inserter):
        """Test inserting empty batch of countries."""
        countries = []

        with patch(
            "poliloom.services.database_inserter.get_worker_session"
        ) as mock_get_session:
            inserter.insert_countries_batch(countries)

            # Should not create session for empty batch
            mock_get_session.assert_not_called()

    def test_insert_countries_batch_with_retry(self, inserter):
        """Test inserting countries with database error and retry."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
        ]

        # Mock session that fails once then succeeds
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1

        # First call raises exception, second succeeds
        mock_session.execute.side_effect = [
            DisconnectionError("connection lost", None, None),
            mock_result,
        ]

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            with patch("time.sleep"):  # Mock sleep to speed up test
                inserter.insert_countries_batch(countries)

                # Should be called twice (retry)
                assert mock_session.execute.call_count == 2
                assert mock_session.rollback.call_count == 1

    def test_insert_countries_batch_with_duplicates_handling(self, inserter):
        """Test that countries batch uses ON CONFLICT DO NOTHING."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
        ]

        # Mock the database session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0  # No rows inserted (conflict)
        mock_session.execute.return_value = mock_result

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_countries_batch(countries)

            # Should still execute and commit (ON CONFLICT handles duplicates)
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()
            # Should not raise exception even with 0 rowcount
