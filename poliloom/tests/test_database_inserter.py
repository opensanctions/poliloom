"""Tests for DatabaseInserter."""

import pytest
from unittest.mock import patch, MagicMock

from poliloom.services.database_inserter import DatabaseInserter
from poliloom.models import Position, Location


class TestDatabaseInserter:
    """Test DatabaseInserter functionality."""

    @pytest.fixture
    def inserter(self):
        """Create a DatabaseInserter instance."""
        return DatabaseInserter()

    def test_insert_positions_batch(self, inserter, test_session):
        """Test inserting a batch of positions."""
        positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
            {"wikidata_id": "Q2", "name": "Position 2"},
        ]

        inserter.insert_positions_batch(positions)

        # Verify positions were inserted
        inserted_positions = test_session.query(Position).all()
        assert len(inserted_positions) == 2
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_positions_batch_with_duplicates(self, inserter, test_session):
        """Test inserting positions with some duplicates."""
        # Insert initial batch
        initial_positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
            {"wikidata_id": "Q2", "name": "Position 2"},
        ]
        inserter.insert_positions_batch(initial_positions)

        # Insert batch with some duplicates and new items
        positions_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "name": "Position 1 Updated",
            },  # Duplicate (should update)
            {"wikidata_id": "Q2", "name": "Position 2"},  # Duplicate (no change)
            {"wikidata_id": "Q3", "name": "Position 3"},  # New
        ]
        inserter.insert_positions_batch(positions_with_duplicates)

        # Verify all positions exist with correct data
        inserted_positions = test_session.query(Position).all()
        assert len(inserted_positions) == 3
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2", "Q3"}

        # Verify Q1 was updated
        q1_position = (
            test_session.query(Position).filter(Position.wikidata_id == "Q1").first()
        )
        assert q1_position.name == "Position 1 Updated"

    def test_insert_positions_batch_empty(self, inserter, test_session):
        """Test inserting empty batch of positions."""
        positions = []

        # Should handle empty batch gracefully without errors
        inserter.insert_positions_batch(positions)

        # Verify no positions were inserted
        inserted_positions = test_session.query(Position).all()
        assert len(inserted_positions) == 0

    def test_insert_locations_batch(self, inserter, test_session):
        """Test inserting a batch of locations."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
        ]

        inserter.insert_locations_batch(locations)

        # Verify locations were inserted
        inserted_locations = test_session.query(Location).all()
        assert len(inserted_locations) == 2
        wikidata_ids = {loc.wikidata_id for loc in inserted_locations}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_locations_batch_with_duplicates(self, inserter):
        """Test inserting locations with some duplicates."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
            {"wikidata_id": "Q3", "name": "Location 3"},
        ]

        # Mock the database session for UPSERT (handles duplicates automatically)
        mock_session = MagicMock()

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_locations_batch(locations)

            # Should execute UPSERT statement (duplicates handled by PostgreSQL)
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

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

    def test_insert_politicians_batch(self, inserter):
        """Test inserting a batch of politicians."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [{"type": "BirthDate", "value": "1970-01-01"}],
                "citizenships": ["Q30"],  # US
                "positions": [
                    {
                        "wikidata_id": "Q30185",
                        "start_date": "2020-01-01",
                        "end_date": "2024-01-01",
                    }
                ],
                "birthplace": "Q60",  # NYC
                "wikipedia_links": [
                    {
                        "language": "en",
                        "title": "John Doe",
                        "url": "https://en.wikipedia.org/wiki/John_Doe",
                    }
                ],
            }
        ]

        # Mock the database session for complex politician operations
        mock_session = MagicMock()

        # Mock politician object returned after insert
        mock_politician = MagicMock()
        mock_politician.id = 1
        mock_politician.wikidata_id = "Q1"

        # Mock related entities
        mock_position = MagicMock()
        mock_position.id = 1
        mock_country = MagicMock()
        mock_country.id = 1
        mock_location = MagicMock()
        mock_location.id = 1

        # Set up query behavior for different calls
        def mock_query_filter_behavior(*args, **kwargs):
            # First call is for politicians after insert
            if (
                args
                and hasattr(args[0], "__name__")
                and args[0].__name__ == "Politician"
            ):
                mock_query = MagicMock()
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = [mock_politician]
                return mock_query
            # Other calls are for checking existing entities
            else:
                mock_query = MagicMock()
                mock_query.filter_by.return_value = mock_query
                mock_query.first.return_value = None  # No existing relationships
                return mock_query

        mock_session.query.side_effect = mock_query_filter_behavior

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should execute politician UPSERT
            mock_session.execute.assert_called()
            # Should flush and commit
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_insert_politicians_batch_with_duplicates(self, inserter):
        """Test inserting politicians with some duplicates."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "properties": [],
                "citizenships": [],
                "positions": [],
                "birthplace": None,
                "wikipedia_links": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "properties": [],
                "citizenships": [],
                "positions": [],
                "birthplace": None,
                "wikipedia_links": [],
            },
        ]

        # Mock the database session for UPSERT (handles duplicates automatically)
        mock_session = MagicMock()

        # Mock politician objects returned after insert
        mock_politician1 = MagicMock()
        mock_politician1.id = 1
        mock_politician1.wikidata_id = "Q1"
        mock_politician2 = MagicMock()
        mock_politician2.id = 2
        mock_politician2.wikidata_id = "Q2"

        # Mock query for retrieving inserted politicians
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_politician1, mock_politician2]
        mock_session.query.return_value = mock_query

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should execute UPSERT statement (duplicates handled by PostgreSQL)
            mock_session.execute.assert_called()
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_insert_politicians_batch_empty(self, inserter):
        """Test inserting empty batch of politicians."""
        politicians = []

        with patch(
            "poliloom.services.database_inserter.get_worker_session"
        ) as mock_get_session:
            inserter.insert_politicians_batch(politicians)

            # Should not create session for empty batch
            mock_get_session.assert_not_called()

    def test_insert_politicians_batch_with_relationships(self, inserter):
        """Test inserting politicians with full relationship data."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "is_deceased": False,
                "properties": [
                    {"type": "BirthDate", "value": "1970-01-01"},
                    {"type": "DeathDate", "value": "2024-01-01"},
                ],
                "citizenships": ["Q30", "Q16"],  # US and Canada
                "positions": [
                    {
                        "wikidata_id": "Q30185",
                        "start_date": "2020-01-01",
                        "end_date": "2024-01-01",
                    },
                    {
                        "wikidata_id": "Q11696",
                        "start_date": "2018-01-01",
                        "end_date": "2020-01-01",
                    },
                ],
                "birthplace": "Q60",
                "wikipedia_links": [
                    {
                        "language": "en",
                        "title": "John Doe",
                        "url": "https://en.wikipedia.org/wiki/John_Doe",
                    },
                    {
                        "language": "fr",
                        "title": "John Doe",
                        "url": "https://fr.wikipedia.org/wiki/John_Doe",
                    },
                ],
            }
        ]

        # Mock the database session
        mock_session = MagicMock()

        # Mock politician object returned after UPSERT
        mock_politician = MagicMock()
        mock_politician.id = 1
        mock_politician.wikidata_id = "Q1"

        # Mock existing entities
        mock_position1 = MagicMock()
        mock_position1.id = 1
        mock_position2 = MagicMock()
        mock_position2.id = 2
        mock_country1 = MagicMock()
        mock_country1.id = 1
        mock_country2 = MagicMock()
        mock_country2.id = 2
        mock_location = MagicMock()
        mock_location.id = 1

        # Set up query behavior for different calls
        def mock_query_side_effect(model):
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.filter_by.return_value = mock_query

            # For politician query after UPSERT
            if hasattr(model, "__name__") and model.__name__ == "Politician":
                mock_query.all.return_value = [mock_politician]
            else:
                mock_query.all.return_value = []

            # For individual entity lookups
            mock_query.first.side_effect = [
                mock_position1,  # First position
                mock_position2,  # Second position
                mock_country1,  # First country
                mock_country2,  # Second country
                mock_location,  # Location
            ]
            return mock_query

        mock_session.query.side_effect = mock_query_side_effect

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should execute and commit
            mock_session.execute.assert_called()
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_insert_politicians_batch_missing_relationships(self, inserter):
        """Test inserting politicians when some related entities don't exist."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "is_deceased": False,
                "properties": [],
                "citizenships": ["Q999"],  # Non-existent country
                "positions": [
                    {
                        "wikidata_id": "Q999",  # Non-existent position
                        "start_date": "2020-01-01",
                        "end_date": "2024-01-01",
                    }
                ],
                "birthplace": "Q999",  # Non-existent location
                "wikipedia_links": [],
            }
        ]

        # Mock the database session
        mock_session = MagicMock()

        # Mock politician object returned after UPSERT
        mock_politician = MagicMock()
        mock_politician.id = 1
        mock_politician.wikidata_id = "Q1"

        # Set up query behavior for different calls
        def mock_query_side_effect(model):
            mock_query = MagicMock()
            mock_query.filter.return_value = mock_query
            mock_query.filter_by.return_value = mock_query

            # For politician query after UPSERT
            if hasattr(model, "__name__") and model.__name__ == "Politician":
                mock_query.all.return_value = [mock_politician]
            else:
                mock_query.all.return_value = []

            # For individual entity lookups - all return None (missing entities)
            mock_query.first.return_value = None
            return mock_query

        mock_session.query.side_effect = mock_query_side_effect

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should execute and commit
            mock_session.execute.assert_called()
            mock_session.flush.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
