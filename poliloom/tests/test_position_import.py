"""Tests for position import functionality."""

import pytest
from unittest.mock import Mock, patch
import httpx

from poliloom.services.import_service import ImportService
from poliloom.services.wikidata import WikidataClient
from poliloom.models import Position
from .conftest import load_json_fixture


class TestPositionImport:
    """Test position import functionality."""

    @pytest.fixture
    def mock_positions_sparql_response(self):
        """Mock SPARQL response for positions."""
        return load_json_fixture("wikidata_positions_sparql_response.json")

    def test_get_all_positions_success(self, mock_positions_sparql_response):
        """Test successful positions retrieval from Wikidata."""
        wikidata_client = WikidataClient()

        with patch.object(wikidata_client.session, "get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_positions_sparql_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = wikidata_client.get_all_positions()

            assert result is not None
            assert len(result) == 4

            # Check first position (President)
            president = result[0]
            assert president["wikidata_id"] == "Q11696"
            assert president["name"] == "President of the United States"

            # Check second position (Representative)
            rep = result[1]
            assert rep["wikidata_id"] == "Q13218630"
            assert rep["name"] == "United States representative"

            # Check third position (Senator)
            senator = result[2]
            assert senator["wikidata_id"] == "Q4416090"
            assert senator["name"] == "United States senator"

            # Check fourth position (Minister)
            minister = result[3]
            assert minister["wikidata_id"] == "Q83307"
            assert minister["name"] == "minister"

    def test_get_all_positions_network_error(self):
        """Test handling of network errors when fetching positions."""
        wikidata_client = WikidataClient()

        with (
            patch.object(wikidata_client.session, "get") as mock_get,
            patch("time.sleep"),
        ):
            mock_get.side_effect = httpx.RequestError("Network error")

            result = wikidata_client.get_all_positions()

            assert result == []

    def test_import_all_positions_success(
        self, test_session, mock_positions_sparql_response
    ):
        """Test successful import of all positions."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)

        # Mock the SPARQL response data
        positions_data = [
            {"wikidata_id": "Q11696", "name": "President of the United States"},
            {"wikidata_id": "Q13218630", "name": "United States representative"},
            {"wikidata_id": "Q4416090", "name": "United States senator"},
            {"wikidata_id": "Q83307", "name": "minister"},
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_all_positions()

        assert result == 4
        mock_wikidata_client.get_all_positions.assert_called_once()

        # Verify positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 4

        # Check President position
        president = test_session.query(Position).filter_by(wikidata_id="Q11696").first()
        assert president is not None
        assert president.name == "President of the United States"

        # Check Representative position
        rep = test_session.query(Position).filter_by(wikidata_id="Q13218630").first()
        assert rep is not None
        assert rep.name == "United States representative"

        # Check Senator position
        senator = test_session.query(Position).filter_by(wikidata_id="Q4416090").first()
        assert senator is not None
        assert senator.name == "United States senator"

        # Check Minister position
        minister = test_session.query(Position).filter_by(wikidata_id="Q83307").first()
        assert minister is not None
        assert minister.name == "minister"

    def test_import_all_positions_skip_existing(self, test_session, sample_position):
        """Test that existing positions are skipped during import."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)

        # Store the wikidata_id and name before the session is mocked
        existing_wikidata_id = sample_position.wikidata_id
        existing_name = sample_position.name

        # Mock data that includes existing position
        positions_data = [
            {"wikidata_id": existing_wikidata_id, "name": "Updated Position Name"},
            {"wikidata_id": "Q11696", "name": "President of the United States"},
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_all_positions()

        # Should only import 1 new position, skip existing one
        assert result == 1

        # Verify only 2 positions total exist
        positions = test_session.query(Position).all()
        assert len(positions) == 2

        # Verify existing position wasn't updated
        existing = (
            test_session.query(Position)
            .filter_by(wikidata_id=existing_wikidata_id)
            .first()
        )
        assert (
            existing.name == existing_name
        )  # Original name, not "Updated Position Name"

    def test_import_all_positions_wikidata_error(self, test_session):
        """Test handling of Wikidata client errors."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)
        mock_wikidata_client.get_all_positions.return_value = None
        import_service.wikidata_client = mock_wikidata_client

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            result = import_service.import_all_positions()

        assert result == 0

        # Verify no positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 0

    def test_import_all_positions_database_error(self, test_session):
        """Test handling of database errors during position import."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)

        positions_data = [
            {"wikidata_id": "Q11696", "name": "President of the United States"}
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            # Mock a database error during commit
            with patch.object(
                test_session, "commit", side_effect=Exception("Database error")
            ):
                result = import_service.import_all_positions()

        assert result == 0

        # Verify rollback occurred - no positions should exist
        positions = test_session.query(Position).all()
        assert len(positions) == 0

    def test_import_all_positions_batch_commit(self, test_session):
        """Test that positions are committed in batches."""
        import_service = ImportService()
        mock_wikidata_client = Mock(spec=WikidataClient)

        # Create 2500 positions to test batch committing (batch size is 1000)
        positions_data = [
            {"wikidata_id": f"Q{i}", "name": f"Position {i}"} for i in range(1, 2501)
        ]
        mock_wikidata_client.get_all_positions.return_value = positions_data
        import_service.wikidata_client = mock_wikidata_client

        with patch(
            "poliloom.services.import_service.SessionLocal", return_value=test_session
        ):
            # Track commits
            original_commit = test_session.commit
            commit_count = 0

            def count_commits():
                nonlocal commit_count
                commit_count += 1
                return original_commit()

            with patch.object(test_session, "commit", side_effect=count_commits):
                result = import_service.import_all_positions()

        assert result == 2500

        # Should commit 3 times: after 1000, after 2000, and final commit
        assert commit_count >= 3

        # Verify all positions were created
        positions = test_session.query(Position).all()
        assert len(positions) == 2500
