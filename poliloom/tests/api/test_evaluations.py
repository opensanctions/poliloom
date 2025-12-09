"""Tests for the evaluations API endpoint."""

from datetime import datetime, timezone
from unittest.mock import patch

from poliloom.models import (
    ArchivedPage,
    Language,
    Politician,
    Position,
    Property,
    PropertyType,
    WikidataRelation,
    WikipediaProject,
    WikipediaSource,
    RelationType,
)
from poliloom.wikidata_date import WikidataDate


class TestEvaluationsEndpoint:
    """Test the evaluations API endpoint."""

    def test_evaluate_single_list(self, client, mock_auth, db_session):
        """Test evaluation accepts single list format."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        wikipedia_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Create extracted properties (with archived_page, no statement_id)
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
            supporting_quotes=["Born on January 15, 1970"],
        )
        db_session.add(birth_prop)

        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
            },
            supporting_quotes=["Served as Mayor from 2020"],
        )
        db_session.add(position_prop)
        db_session.flush()

        test_properties = [birth_prop, position_prop]

        # Old format should NOT work
        old_format = {
            "property_evaluations": [
                {"id": str(test_properties[0].id), "is_accepted": True}
            ],
            "position_evaluations": [],
            "birthplace_evaluations": [],
        }
        response = client.post("/evaluations/", json=old_format, headers=mock_auth)
        assert response.status_code == 422  # Validation error

        # New format should work
        new_format = {
            "evaluations": [
                {"id": str(test_properties[0].id), "is_accepted": True},
                {"id": str(test_properties[1].id), "is_accepted": False},
            ]
        }
        response = client.post("/evaluations/", json=new_format, headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["evaluations"]) == 2

        # Verify evaluation objects are returned
        eval_ids = {e["id"] for e in data["evaluations"]}
        assert len(eval_ids) == 2  # Two unique evaluation IDs

        # Verify each evaluation has required fields
        for evaluation in data["evaluations"]:
            assert "id" in evaluation
            assert "user_id" in evaluation
            assert "is_accepted" in evaluation
            assert "property_id" in evaluation
            assert "created_at" in evaluation

    def test_evaluate_nonexistent_property(self, client, mock_auth):
        """Test evaluation with nonexistent property ID."""
        fake_uuid = "99999999-9999-9999-9999-999999999999"
        evaluation_data = {
            "evaluations": [
                {"id": fake_uuid, "is_accepted": True}  # Nonexistent ID
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200  # Should succeed but with errors
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert len(result["errors"]) > 0
        assert f"Property {fake_uuid} not found" in result["errors"]

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_mixed_valid_invalid_properties(
        self, mock_push_evaluation, client, mock_auth, db_session
    ):
        """Test evaluation with mix of valid and invalid property IDs."""
        mock_push_evaluation.return_value = True

        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Mayor")
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        wikipedia_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        # Create extracted properties
        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(birth_prop)

        position_prop = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            archived_page_id=archived_page.id,
        )
        db_session.add(position_prop)
        db_session.flush()

        test_properties = [birth_prop, position_prop]

        fake_uuid = "99999999-9999-9999-9999-999999999999"
        evaluation_data = {
            "evaluations": [
                {"id": str(test_properties[0].id), "is_accepted": True},  # Valid
                {"id": fake_uuid, "is_accepted": False},  # Invalid
                {"id": str(test_properties[1].id), "is_accepted": True},  # Valid
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 2  # Only valid properties evaluated
        assert len(result["errors"]) == 1
        assert f"Property {fake_uuid} not found" in result["errors"][0]

    def test_evaluate_requires_authentication(self, client):
        """Test that evaluation endpoint requires authentication."""
        evaluation_data = {
            "evaluations": [
                {"id": "11111111-1111-1111-1111-111111111111", "is_accepted": True}
            ]
        }
        response = client.post("/evaluations/", json=evaluation_data)
        assert response.status_code in [401, 403]  # Unauthorized

    def test_evaluate_empty_list(self, client, mock_auth):
        """Test evaluation with empty evaluations list."""
        evaluation_data = {"evaluations": []}
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 0
        assert result["success"] is True

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push(
        self, mock_push_evaluation, client, mock_auth, db_session
    ):
        """Test that evaluations are pushed to Wikidata when accepted."""
        mock_push_evaluation.return_value = True

        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        wikipedia_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(birth_prop)
        db_session.flush()

        evaluation_data = {
            "evaluations": [{"id": str(birth_prop.id), "is_accepted": True}]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200
        result = response.json()
        assert len(result["evaluations"]) == 1

        # Verify push_evaluation was called
        mock_push_evaluation.assert_called_once()

    @patch("poliloom.api.evaluations.push_evaluation")
    def test_evaluate_with_wikidata_push_failure(
        self, mock_push_evaluation, client, mock_auth, db_session
    ):
        """Test handling of Wikidata push failures."""
        mock_push_evaluation.side_effect = Exception("Wikidata API error")

        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        language.iso_639_2 = "eng"
        wikipedia_project = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wikipedia_project.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id=language.wikidata_id,
                child_entity_id=wikipedia_project.wikidata_id,
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="Q328$test-statement",
            )
        )
        db_session.flush()

        wikipedia_source = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wikipedia_project.wikidata_id,
        )
        db_session.add(wikipedia_source)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/w/index.php?title=Test&oldid=123",
            content_hash="test123",
            fetch_timestamp=datetime.now(timezone.utc),
            wikipedia_source_id=wikipedia_source.id,
        )
        db_session.add(archived_page)
        db_session.flush()

        birth_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1970-01-15T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(birth_prop)
        db_session.flush()

        evaluation_data = {
            "evaluations": [{"id": str(birth_prop.id), "is_accepted": True}]
        }
        response = client.post("/evaluations/", json=evaluation_data, headers=mock_auth)
        assert response.status_code == 200  # Should still succeed locally
        result = response.json()
        assert len(result["evaluations"]) == 1
        assert len(result["errors"]) > 0
        assert any("Wikidata API error" in error for error in result["errors"])
