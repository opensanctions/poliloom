"""Tests for the stats API endpoint."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from poliloom.models import ArchivedPage, Country, Evaluation, Politician, Property
from poliloom.models.base import PropertyType
from poliloom.models.wikidata import WikidataEntity


class TestEvaluationCountEndpoint:
    """Test suite for GET /stats/count endpoint."""

    def test_count_requires_authentication(self, client):
        """Count endpoint should require authentication."""
        response = client.get("/stats/count")
        assert response.status_code == 401

    def test_count_returns_total(self, client, db_session, mock_auth):
        """Count endpoint should return total evaluation count."""
        # Create a politician with a property
        entity = WikidataEntity(wikidata_id="Q123", name="Test Politician")
        db_session.add(entity)

        politician = Politician(wikidata_id="Q123", name="Test Politician")
        db_session.add(politician)
        db_session.flush()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-01-01T00:00:00Z",
            value_precision=11,
        )
        db_session.add(prop)
        db_session.flush()

        # Create evaluations
        eval1 = Evaluation(user_id="user1", is_accepted=True, property_id=prop.id)
        eval2 = Evaluation(user_id="user1", is_accepted=False, property_id=prop.id)
        eval3 = Evaluation(user_id="user2", is_accepted=True, property_id=prop.id)
        db_session.add_all([eval1, eval2, eval3])
        db_session.commit()

        response = client.get("/stats/count", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 3

    def test_count_returns_zero_when_empty(self, client, db_session, mock_auth):
        """Count endpoint should return 0 when no evaluations exist."""
        response = client.get("/stats/count", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0


class TestStatsEndpoint:
    """Test suite for GET /stats endpoint."""

    def test_stats_requires_authentication(self, client):
        """Stats endpoint should require authentication."""
        response = client.get("/stats")
        assert response.status_code == 401

    def test_stats_returns_empty_data(self, client, db_session, mock_auth):
        """Stats endpoint should return empty data when no evaluations exist."""
        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert "evaluations_timeseries" in data
        assert "country_coverage" in data
        assert "stateless_evaluated_count" in data
        assert "stateless_total_count" in data
        assert "cooldown_days" in data
        # Timeseries should have all weeks in cooldown period, even if empty
        assert len(data["evaluations_timeseries"]) == data["cooldown_days"] // 7
        assert data["country_coverage"] == []

    def test_stats_timeseries_returns_weekly_data(self, client, db_session, mock_auth):
        """Stats endpoint should return evaluations grouped by week."""
        # Create a politician with a property
        entity = WikidataEntity(wikidata_id="Q123", name="Test Politician")
        db_session.add(entity)

        politician = Politician(wikidata_id="Q123", name="Test Politician")
        db_session.add(politician)
        db_session.flush()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-01-01T00:00:00Z",
            value_precision=11,
        )
        db_session.add(prop)
        db_session.flush()

        # Create evaluations
        eval1 = Evaluation(
            user_id="user1",
            is_accepted=True,
            property_id=prop.id,
        )
        eval2 = Evaluation(
            user_id="user1",
            is_accepted=False,
            property_id=prop.id,
        )
        db_session.add_all([eval1, eval2])
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        # Find the week with data (current week)
        weeks_with_data = [
            w
            for w in data["evaluations_timeseries"]
            if w["accepted"] > 0 or w["rejected"] > 0
        ]
        assert len(weeks_with_data) == 1
        assert weeks_with_data[0]["accepted"] == 1
        assert weeks_with_data[0]["rejected"] == 1

    def test_stats_country_coverage(self, client, db_session, mock_auth):
        """Stats endpoint should return country coverage based on evaluated extractions."""
        # Create country
        country_entity = WikidataEntity(
            wikidata_id="Q30", name="United States", description="Country"
        )
        db_session.add(country_entity)
        country = Country(wikidata_id="Q30")
        db_session.add(country)

        # Create archived page for extraction
        archived_page = ArchivedPage(
            id=uuid4(),
            url="https://example.com/politician",
            content_hash="test_hash",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)

        # Create politician with citizenship
        politician_entity = WikidataEntity(wikidata_id="Q123", name="Test Politician")
        db_session.add(politician_entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Test Politician",
        )
        db_session.add(politician)
        db_session.flush()

        # Add citizenship property (from Wikidata, has statement_id)
        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
            statement_id="Q123$citizenship-1",
        )
        db_session.add(citizenship)

        # Add extracted birth date property with evaluation
        extracted_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(extracted_prop)
        db_session.flush()

        # Add evaluation for the extracted property
        evaluation = Evaluation(
            user_id="user1",
            is_accepted=True,
            property_id=extracted_prop.id,
        )
        db_session.add(evaluation)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert len(data["country_coverage"]) == 1
        assert data["country_coverage"][0]["wikidata_id"] == "Q30"
        assert data["country_coverage"][0]["name"] == "United States"
        assert data["country_coverage"][0]["total_count"] == 1
        assert data["country_coverage"][0]["evaluated_count"] == 1

    def test_stats_stateless_politicians(self, client, db_session, mock_auth):
        """Stats endpoint should count politicians without Wikidata citizenship."""
        # Create archived page for extraction
        archived_page = ArchivedPage(
            id=uuid4(),
            url="https://example.com/politician",
            content_hash="test_hash",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)

        # Create country for extracted citizenship
        country_entity = WikidataEntity(
            wikidata_id="Q30", name="United States", description="Country"
        )
        db_session.add(country_entity)
        country = Country(wikidata_id="Q30")
        db_session.add(country)

        # Create politician without Wikidata citizenship
        entity = WikidataEntity(wikidata_id="Q123", name="Stateless Politician")
        db_session.add(entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Stateless Politician",
        )
        db_session.add(politician)
        db_session.flush()

        # Add extracted citizenship (no statement_id, has archived_page_id)
        extracted_citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
            archived_page_id=archived_page.id,
        )
        db_session.add(extracted_citizenship)
        db_session.flush()

        # Add evaluation for the extracted citizenship
        evaluation = Evaluation(
            user_id="user1",
            is_accepted=True,
            property_id=extracted_citizenship.id,
        )
        db_session.add(evaluation)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["stateless_total_count"] == 1
        assert data["stateless_evaluated_count"] == 1

    def test_stats_old_evaluation_not_counted(self, client, db_session, mock_auth):
        """Politicians with evaluations outside cooldown period should not be counted."""
        # Create country
        country_entity = WikidataEntity(
            wikidata_id="Q30", name="United States", description="Country"
        )
        db_session.add(country_entity)
        country = Country(wikidata_id="Q30")
        db_session.add(country)

        # Create archived page for extraction
        archived_page = ArchivedPage(
            id=uuid4(),
            url="https://example.com/politician",
            content_hash="test_hash",
            fetch_timestamp=datetime.now(timezone.utc) - timedelta(days=400),
        )
        db_session.add(archived_page)

        # Create politician
        politician_entity = WikidataEntity(wikidata_id="Q123", name="Old Politician")
        db_session.add(politician_entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Old Politician",
        )
        db_session.add(politician)
        db_session.flush()

        # Add citizenship from Wikidata
        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
            statement_id="Q123$citizenship-1",
        )
        db_session.add(citizenship)

        # Add extracted property
        extracted_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(extracted_prop)
        db_session.flush()

        # Add old evaluation (outside cooldown period - default is 365 days)
        evaluation = Evaluation(
            user_id="user1",
            is_accepted=True,
            property_id=extracted_prop.id,
        )
        db_session.add(evaluation)
        db_session.commit()

        # Manually set evaluation created_at to be outside cooldown period (400 days > 365 days default)
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        db_session.execute(
            text("UPDATE evaluations SET created_at = :created_at WHERE id = :eval_id"),
            {"created_at": old_date, "eval_id": str(evaluation.id)},
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert len(data["country_coverage"]) == 1
        assert data["country_coverage"][0]["total_count"] == 1
        assert data["country_coverage"][0]["evaluated_count"] == 0

    def test_stats_unevaluated_politician_not_counted(
        self, client, db_session, mock_auth
    ):
        """Politicians without evaluated extractions should not be counted as evaluated."""
        # Create country
        country_entity = WikidataEntity(
            wikidata_id="Q30", name="United States", description="Country"
        )
        db_session.add(country_entity)
        country = Country(wikidata_id="Q30")
        db_session.add(country)

        # Create archived page for extraction
        archived_page = ArchivedPage(
            id=uuid4(),
            url="https://example.com/politician",
            content_hash="test_hash",
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)

        # Create politician
        politician_entity = WikidataEntity(wikidata_id="Q123", name="Test Politician")
        db_session.add(politician_entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Test Politician",
        )
        db_session.add(politician)
        db_session.flush()

        # Add citizenship from Wikidata
        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
            statement_id="Q123$citizenship-1",
        )
        db_session.add(citizenship)

        # Add extracted property without evaluation
        extracted_prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-01-01T00:00:00Z",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(extracted_prop)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert len(data["country_coverage"]) == 1
        assert data["country_coverage"][0]["total_count"] == 1
        # Not evaluated because no evaluations exist
        assert data["country_coverage"][0]["evaluated_count"] == 0
