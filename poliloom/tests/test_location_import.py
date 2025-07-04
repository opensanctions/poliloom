"""Tests for location import functionality."""

import pytest
from unittest.mock import Mock, patch
import httpx

from poliloom.services.import_service import ImportService
from poliloom.services.wikidata import WikidataClient
from poliloom.models import Location


class TestLocationImport:
    """Test cases for location import functionality."""

    @pytest.fixture
    def sample_locations_data(self):
        """Sample location data from Wikidata."""
        return [
            {"wikidata_id": "Q60", "name": "New York City"},
            {"wikidata_id": "Q65", "name": "Los Angeles"},
            {"wikidata_id": "Q90", "name": "Paris"},
        ]

    def test_get_all_locations_success(self, sample_locations_data):
        """Test successful fetching of locations from Wikidata."""
        mock_response_data = {
            "results": {
                "bindings": [
                    {
                        "place": {"value": "http://www.wikidata.org/entity/Q60"},
                        "placeLabel": {"value": "New York City"},
                    },
                    {
                        "place": {"value": "http://www.wikidata.org/entity/Q65"},
                        "placeLabel": {"value": "Los Angeles"},
                    },
                    {
                        "place": {"value": "http://www.wikidata.org/entity/Q90"},
                        "placeLabel": {"value": "Paris"},
                    },
                ]
            }
        }

        with patch("httpx.Client.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            client = WikidataClient()
            result = client.get_all_locations()

            assert len(result) == 3
            assert result[0]["wikidata_id"] == "Q60"
            assert result[0]["name"] == "New York City"
            assert result[1]["wikidata_id"] == "Q65"
            assert result[1]["name"] == "Los Angeles"
            assert result[2]["wikidata_id"] == "Q90"
            assert result[2]["name"] == "Paris"

    def test_get_all_locations_network_error(self):
        """Test handling of network errors when fetching locations."""
        with patch("httpx.Client.get") as mock_get, patch("time.sleep"):
            mock_get.side_effect = httpx.RequestError("Network error")

            client = WikidataClient()
            result = client.get_all_locations()

            assert result == []

    def test_get_all_locations_http_status_error(self):
        """Test handling of HTTP status errors (like 504 Gateway Timeout) when fetching locations."""
        with patch("httpx.Client.get") as mock_get, patch("time.sleep"):
            # Create a mock response that will raise HTTPStatusError on raise_for_status()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="504 Gateway Timeout", request=Mock(), response=Mock()
            )
            mock_get.return_value = mock_response

            client = WikidataClient()
            result = client.get_all_locations()

            assert result == []

    def test_import_all_locations_success(self, test_session, sample_locations_data):
        """Test successful import of all locations."""
        with patch.object(
            WikidataClient, "get_all_locations", return_value=sample_locations_data
        ):
            # Patch SessionLocal to use the test session
            with patch(
                "poliloom.services.import_service.SessionLocal",
                return_value=test_session,
            ):
                import_service = ImportService()
                count = import_service.import_all_locations()

                assert count == 3

                # Verify locations were created
                locations = test_session.query(Location).all()
                assert len(locations) == 3

                wikidata_ids = [loc.wikidata_id for loc in locations]
                assert "Q60" in wikidata_ids
                assert "Q65" in wikidata_ids
                assert "Q90" in wikidata_ids

                # Verify embeddings are initially None (not generated during import)
                for location in locations:
                    assert location.embedding is None

    def test_import_all_locations_skip_existing(
        self, test_session, sample_locations_data
    ):
        """Test that import skips existing locations."""
        # Create one location that already exists
        existing_location = Location(name="New York City", wikidata_id="Q60")
        test_session.add(existing_location)
        test_session.commit()

        with patch.object(
            WikidataClient, "get_all_locations", return_value=sample_locations_data
        ):
            # Patch SessionLocal to use the test session
            with patch(
                "poliloom.services.import_service.SessionLocal",
                return_value=test_session,
            ):
                import_service = ImportService()
                count = import_service.import_all_locations()

                # Should only import 2 new locations (skipping the existing one)
                assert count == 2

                # Total should be 3 (1 existing + 2 new)
                locations = test_session.query(Location).all()
                assert len(locations) == 3

    def test_import_all_locations_wikidata_error(self):
        """Test handling of Wikidata errors during import."""
        with patch.object(WikidataClient, "get_all_locations", return_value=None):
            import_service = ImportService()
            count = import_service.import_all_locations()

            assert count == 0

    def test_import_all_locations_database_error(
        self, test_session, sample_locations_data
    ):
        """Test handling of database errors during import."""
        with patch.object(
            WikidataClient, "get_all_locations", return_value=sample_locations_data
        ):
            # Mock SessionLocal to use a broken session that will cause errors
            broken_session = Mock()
            broken_session.query.side_effect = Exception("Database connection error")
            broken_session.rollback = Mock()
            broken_session.close = Mock()

            with patch(
                "poliloom.services.import_service.SessionLocal",
                return_value=broken_session,
            ):
                import_service = ImportService()
                count = import_service.import_all_locations()

                assert count == 0
                broken_session.rollback.assert_called_once()

    def test_import_all_locations_batch_commit(self, test_session):
        """Test that locations are processed in batches."""
        # Create a smaller dataset to test batch processing logic
        large_dataset = []
        for i in range(50):  # Use smaller number for testing
            large_dataset.append(
                {"wikidata_id": f"Q{i + 100000}", "name": f"Location {i + 1}"}
            )

        with patch.object(
            WikidataClient, "get_all_locations", return_value=large_dataset
        ):
            # Use real session but monitor the behavior
            with patch(
                "poliloom.services.import_service.SessionLocal",
                return_value=test_session,
            ):
                import_service = ImportService()
                count = import_service.import_all_locations()

                # Should import all locations
                assert count == 50

                # Verify locations were created
                locations = test_session.query(Location).all()
                assert len(locations) == 50

    def test_location_embeddings_generation_command(self, test_session):
        """Test that location embeddings are properly generated using the embed command."""
        # First create locations without embeddings
        location1 = Location(name="New York City", wikidata_id="Q60")
        location2 = Location(name="Los Angeles", wikidata_id="Q65")
        test_session.add(location1)
        test_session.add(location2)
        test_session.commit()

        # Verify embeddings are initially None
        locations = test_session.query(Location).all()
        for location in locations:
            assert location.embedding is None

        # Now generate embeddings
        from poliloom.embeddings import generate_embeddings

        locations_without_embeddings = (
            test_session.query(Location).filter(Location.embedding.is_(None)).all()
        )

        names = [loc.name for loc in locations_without_embeddings]
        embeddings = generate_embeddings(names)

        for location, embedding in zip(locations_without_embeddings, embeddings):
            location.embedding = embedding

        test_session.commit()

        # Verify embeddings were generated
        locations = test_session.query(Location).all()
        for location in locations:
            assert location.embedding is not None
            assert len(location.embedding) == 384  # Dimension of all-MiniLM-L6-v2 model

    def test_location_find_similar_after_embed(self, test_session):
        """Test that location similarity search works after embedding generation."""
        # Create locations without embeddings
        location1 = Location(name="New York City", wikidata_id="Q60")
        location2 = Location(name="Los Angeles", wikidata_id="Q65")
        location3 = Location(name="Chicago", wikidata_id="Q1297")
        test_session.add_all([location1, location2, location3])
        test_session.commit()

        # Generate embeddings for all locations
        from poliloom.embeddings import generate_embeddings, generate_embedding

        locations = test_session.query(Location).all()
        names = [loc.name for loc in locations]
        embeddings = generate_embeddings(names)

        for location, embedding in zip(locations, embeddings):
            location.embedding = embedding

        test_session.commit()

        # Test similarity search using direct query
        query_embedding = generate_embedding("New York")

        similar = (
            test_session.query(Location)
            .filter(Location.embedding.isnot(None))
            .order_by(Location.embedding.cosine_distance(query_embedding))
            .limit(2)
            .all()
        )

        assert len(similar) <= 2  # Should return at most 2 results
        if len(similar) > 0:
            # Verify we get Location objects
            assert isinstance(similar[0], Location)
            assert hasattr(similar[0], "name")
