"""Tests for the stats API endpoint."""

from datetime import datetime, timedelta, timezone


from poliloom.models import Country, Evaluation, Politician, Property
from poliloom.models.base import PropertyType
from poliloom.models.wikidata import WikidataEntity


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
        assert "stateless_enriched_count" in data
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
        """Stats endpoint should return country coverage data."""
        # Create country
        country_entity = WikidataEntity(
            wikidata_id="Q30", name="United States", description="Country"
        )
        db_session.add(country_entity)
        country = Country(wikidata_id="Q30")
        db_session.add(country)

        # Create politician with citizenship
        politician_entity = WikidataEntity(wikidata_id="Q123", name="Test Politician")
        db_session.add(politician_entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Test Politician",
            enriched_at=datetime.now(timezone.utc),  # Recently enriched
        )
        db_session.add(politician)
        db_session.flush()

        # Add citizenship property
        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
        )
        db_session.add(citizenship)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert len(data["country_coverage"]) == 1
        assert data["country_coverage"][0]["wikidata_id"] == "Q30"
        assert data["country_coverage"][0]["name"] == "United States"
        assert data["country_coverage"][0]["total_count"] == 1
        assert data["country_coverage"][0]["enriched_count"] == 1

    def test_stats_stateless_politicians(self, client, db_session, mock_auth):
        """Stats endpoint should count politicians without citizenship."""
        # Create politician without citizenship
        entity = WikidataEntity(wikidata_id="Q123", name="Stateless Politician")
        db_session.add(entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Stateless Politician",
            enriched_at=datetime.now(timezone.utc),
        )
        db_session.add(politician)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["stateless_total_count"] == 1
        assert data["stateless_enriched_count"] == 1

    def test_stats_old_enrichment_not_counted(self, client, db_session, mock_auth):
        """Politicians enriched outside cooldown period should not be counted as enriched."""
        # Create country
        country_entity = WikidataEntity(
            wikidata_id="Q30", name="United States", description="Country"
        )
        db_session.add(country_entity)
        country = Country(wikidata_id="Q30")
        db_session.add(country)

        # Create politician enriched 7 months ago (outside 6-month cooldown)
        politician_entity = WikidataEntity(wikidata_id="Q123", name="Old Politician")
        db_session.add(politician_entity)
        politician = Politician(
            wikidata_id="Q123",
            name="Old Politician",
            enriched_at=datetime.now(timezone.utc) - timedelta(days=210),
        )
        db_session.add(politician)
        db_session.flush()

        citizenship = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id="Q30",
        )
        db_session.add(citizenship)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert len(data["country_coverage"]) == 1
        assert data["country_coverage"][0]["total_count"] == 1
        assert data["country_coverage"][0]["enriched_count"] == 0
