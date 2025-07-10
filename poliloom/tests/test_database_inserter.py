"""Tests for DatabaseInserter."""

import pytest
from unittest.mock import patch, MagicMock

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
                "is_deceased": False,
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

        # Mock the database session and all queries
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = None  # No existing entities
        mock_query.all.return_value = []  # No existing politicians

        # Mock existing position, country, and location
        mock_position = MagicMock()
        mock_position.id = 1
        mock_country = MagicMock()
        mock_country.id = 1
        mock_location = MagicMock()
        mock_location.id = 1

        # Set up query returns for different entity types
        def mock_query_side_effect(*args, **kwargs):
            if hasattr(args[0], "__name__"):
                if args[0].__name__ == "Position":
                    mock_query.first.return_value = mock_position
                elif args[0].__name__ == "Country":
                    mock_query.first.return_value = mock_country
                elif args[0].__name__ == "Location":
                    mock_query.first.return_value = mock_location
                else:
                    mock_query.first.return_value = None
            return mock_query

        mock_session.query.side_effect = mock_query_side_effect

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should check for existing politicians
            assert mock_session.query.call_count >= 1
            # Should add politician and related entities
            assert mock_session.add_all.call_count >= 1
            assert mock_session.add.call_count >= 1  # For related entities
            mock_session.commit.assert_called_once()

    def test_insert_politicians_batch_with_duplicates(self, inserter):
        """Test inserting politicians with some duplicates."""
        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "is_deceased": False,
                "properties": [],
                "citizenships": [],
                "positions": [],
                "birthplace": None,
                "wikipedia_links": [],
            },
            {
                "wikidata_id": "Q2",
                "name": "Jane Smith",
                "is_deceased": False,
                "properties": [],
                "citizenships": [],
                "positions": [],
                "birthplace": None,
                "wikipedia_links": [],
            },
        ]

        # Mock existing politician Q1
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [("Q1",)]  # Q1 already exists

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should only add Q2 (the new one)
            mock_session.add_all.assert_called_once()
            added_politicians = mock_session.add_all.call_args[0][0]
            assert len(added_politicians) == 1
            assert added_politicians[0].wikidata_id == "Q2"

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

        # Mock the database session and existing entities
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.all.return_value = []

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

        # Set up query returns
        def mock_first_side_effect():
            # Return different entities based on filter_by calls
            return mock_position1

        mock_query.first.side_effect = [
            mock_position1,  # First position
            mock_position2,  # Second position
            mock_country1,  # First country
            mock_country2,  # Second country
            mock_location,  # Location
        ]

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should create all relationships
            mock_session.add_all.assert_called_once()  # Politicians
            # Should add properties, positions, citizenships, birthplace, sources, and wikipedia links
            add_calls = mock_session.add.call_args_list
            assert (
                len(add_calls) >= 7
            )  # At least 2 properties + 2 positions + 2 citizenships + 1 birthplace + 2 sources + 2 wikipedia links

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
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_query.first.return_value = None  # No existing entities

        with patch(
            "poliloom.services.database_inserter.get_worker_session",
            return_value=mock_session,
        ):
            inserter.insert_politicians_batch(politicians)

            # Should still insert the politician
            mock_session.add_all.assert_called_once()
            added_politicians = mock_session.add_all.call_args[0][0]
            assert len(added_politicians) == 1
            assert added_politicians[0].wikidata_id == "Q1"

            # Should not create relationships for missing entities
            # Only politician should be added, no related entities
            mock_session.commit.assert_called_once()
