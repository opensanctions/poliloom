"""Tests for DatabaseInserter."""

import pytest

from poliloom.services.database_inserter import DatabaseInserter
from poliloom.models import Position, Location, Country, Politician


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

        inserter.insert_positions_batch(positions)

        # Verify positions were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_positions = session.query(Position).all()
            assert len(inserted_positions) == 2
            wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
            assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_positions_batch_with_duplicates(self, inserter):
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
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_positions = session.query(Position).all()
            assert len(inserted_positions) == 3
            wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
            assert wikidata_ids == {"Q1", "Q2", "Q3"}

            # Verify Q1 was updated
            q1_position = (
                session.query(Position).filter(Position.wikidata_id == "Q1").first()
            )
            assert q1_position.name == "Position 1 Updated"

    def test_insert_positions_batch_empty(self, inserter):
        """Test inserting empty batch of positions."""
        positions = []

        # Should handle empty batch gracefully without errors
        inserter.insert_positions_batch(positions)

        # Verify no positions were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_positions = session.query(Position).all()
            assert len(inserted_positions) == 0

    def test_insert_locations_batch(self, inserter):
        """Test inserting a batch of locations."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
        ]

        inserter.insert_locations_batch(locations)

        # Verify locations were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_locations = session.query(Location).all()
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

        inserter.insert_locations_batch(locations)

        # Verify locations were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_locations = session.query(Location).all()
            assert len(inserted_locations) == 3
            wikidata_ids = {loc.wikidata_id for loc in inserted_locations}
            assert wikidata_ids == {"Q1", "Q2", "Q3"}

        # Insert again with some duplicates - should handle gracefully
        locations_with_duplicates = [
            {"wikidata_id": "Q1", "name": "Location 1 Updated"},  # Duplicate
            {"wikidata_id": "Q4", "name": "Location 4"},  # New
        ]
        inserter.insert_locations_batch(locations_with_duplicates)

        # Should now have 4 total locations
        with get_db_session() as session:
            all_locations = session.query(Location).all()
            assert len(all_locations) == 4
            wikidata_ids = {loc.wikidata_id for loc in all_locations}
            assert wikidata_ids == {"Q1", "Q2", "Q3", "Q4"}

    def test_insert_locations_batch_empty(self, inserter):
        """Test inserting empty batch of locations."""
        locations = []

        # Should handle empty batch gracefully without errors
        inserter.insert_locations_batch(locations)

        # Verify no locations were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_locations = session.query(Location).all()
            assert len(inserted_locations) == 0

    def test_insert_countries_batch(self, inserter):
        """Test inserting a batch of countries."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
            {"wikidata_id": "Q2", "name": "Country 2", "iso_code": "C2"},
        ]

        inserter.insert_countries_batch(countries)

        # Verify countries were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_countries = session.query(Country).all()
            assert len(inserted_countries) == 2
            wikidata_ids = {country.wikidata_id for country in inserted_countries}
            assert wikidata_ids == {"Q1", "Q2"}

            # Verify specific country data
            country1 = (
                session.query(Country).filter(Country.wikidata_id == "Q1").first()
            )
            assert country1.name == "Country 1"
            assert country1.iso_code == "C1"

    def test_insert_countries_batch_empty(self, inserter):
        """Test inserting empty batch of countries."""
        countries = []

        # Should handle empty batch gracefully without errors
        inserter.insert_countries_batch(countries)

        # Verify no countries were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_countries = session.query(Country).all()
            assert len(inserted_countries) == 0

    def test_insert_countries_batch_with_duplicates_handling(self, inserter):
        """Test that countries batch uses ON CONFLICT DO NOTHING."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
        ]

        # Insert first time
        inserter.insert_countries_batch(countries)

        # Verify first insertion
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_countries = session.query(Country).all()
            assert len(inserted_countries) == 1

        # Insert again - should handle duplicates gracefully
        inserter.insert_countries_batch(countries)

        # Should still have only one country (ON CONFLICT DO NOTHING)
        with get_db_session() as session:
            final_countries = session.query(Country).all()
            assert len(final_countries) == 1
            assert final_countries[0].wikidata_id == "Q1"

    def test_insert_politicians_batch(self, inserter):
        """Test inserting a batch of politicians."""
        # First create the required related entities
        from poliloom.database import get_db_session

        with get_db_session() as session:
            position = Position(name="Mayor", wikidata_id="Q30185")
            country = Country(name="United States", wikidata_id="Q30", iso_code="US")
            location = Location(name="New York City", wikidata_id="Q60")

            session.add_all([position, country, location])
            session.commit()
            session.refresh(position)
            session.refresh(country)
            session.refresh(location)

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

        inserter.insert_politicians_batch(politicians)

        # Verify politician was created
        with get_db_session() as session:
            inserted_politician = (
                session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
            )
            assert inserted_politician is not None
            assert inserted_politician.name == "John Doe"

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

        # Insert first batch
        inserter.insert_politicians_batch(politicians)

        # Verify politicians were created
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_politicians = session.query(Politician).all()
            assert len(inserted_politicians) == 2
            wikidata_ids = {pol.wikidata_id for pol in inserted_politicians}
            assert wikidata_ids == {"Q1", "Q2"}

        # Insert again with duplicates - should handle gracefully
        inserter.insert_politicians_batch(politicians)

        # Should still have only 2 politicians (UPSERT behavior)
        with get_db_session() as session:
            final_politicians = session.query(Politician).all()
            assert len(final_politicians) == 2

    def test_insert_politicians_batch_empty(self, inserter):
        """Test inserting empty batch of politicians."""
        politicians = []

        # Should handle empty batch gracefully without errors
        inserter.insert_politicians_batch(politicians)

        # Verify no politicians were inserted
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_politicians = session.query(Politician).all()
            assert len(inserted_politicians) == 0

    def test_insert_politicians_batch_with_relationships(self, inserter):
        """Test inserting politicians with full relationship data."""
        # First create the required related entities
        from poliloom.database import get_db_session

        with get_db_session() as session:
            position1 = Position(name="Mayor", wikidata_id="Q30185")
            position2 = Position(name="President", wikidata_id="Q11696")
            country1 = Country(name="United States", wikidata_id="Q30", iso_code="US")
            country2 = Country(name="Canada", wikidata_id="Q16", iso_code="CA")
            location = Location(name="New York City", wikidata_id="Q60")

            session.add_all([position1, position2, country1, country2, location])
            session.commit()

        politicians = [
            {
                "wikidata_id": "Q1",
                "name": "John Doe",
                "is_deceased": False,
                "properties": [
                    {"type": "BirthDate", "value": "1970-01-01"},
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

        inserter.insert_politicians_batch(politicians)

        # Verify politician was created with relationships
        with get_db_session() as session:
            inserted_politician = (
                session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
            )
            assert inserted_politician is not None
            assert inserted_politician.name == "John Doe"
            assert not inserted_politician.is_deceased

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

        # Should handle missing relationships gracefully
        inserter.insert_politicians_batch(politicians)

        # Verify politician was still created (relationships are optional)
        from poliloom.database import get_db_session

        with get_db_session() as session:
            inserted_politician = (
                session.query(Politician).filter(Politician.wikidata_id == "Q1").first()
            )
            assert inserted_politician is not None
            assert inserted_politician.name == "John Doe"
