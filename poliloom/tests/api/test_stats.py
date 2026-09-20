"""Tests for the stats API endpoint."""

from datetime import UTC, datetime, timedelta

from poliloom.models import (
    Action,
    ActionKind,
    Country,
    Politician,
    Source,
    Statement,
)


def birth_date_create_payload(statement_id="Q123456$birth-new"):
    """Build a CREATE_STATEMENT payload for a birth-date statement."""
    return {
        "statement": {
            "id": statement_id,
            "rank": "normal",
            "property": {"id": "P569", "data_type": "time"},
            "value": {
                "type": "value",
                "content": {"time": "+1970-01-15T00:00:00Z", "precision": 11},
            },
        }
    }


def create_action(db_session, politician, *, is_accepted=None, decided_at=None):
    """Create an action with an optional decision."""
    action = Action(
        politician_id=politician.id,
        kind=ActionKind.CREATE_STATEMENT,
        payload=birth_date_create_payload(),
        is_accepted=is_accepted,
        decided_at=decided_at,
    )
    db_session.add(action)
    return action


def citizenship_document(statement_id, country_qid):
    """Build a canonical P27 citizenship statement document."""
    return {
        "id": statement_id,
        "rank": "normal",
        "property": {"id": "P27", "data_type": "wikibase-item"},
        "value": {"type": "value", "content": country_qid},
    }


def set_terms(entity, *, labels=None, descriptions=None, aliases=None):
    """Set language-keyed term maps on an entity's WikidataEntity."""
    entity.wikidata_entity.labels = labels or {}
    entity.wikidata_entity.descriptions = descriptions or {}
    entity.wikidata_entity.aliases = aliases or {}


def create_citizenship(db_session, politician, country_qid, statement_id):
    """Create a live P27 citizenship statement for a politician."""
    statement = Statement(
        politician_id=politician.id,
        document=citizenship_document(statement_id, country_qid),
    )
    db_session.add(statement)
    return statement


def create_enrichment_source(db_session, politician, *, fetch_timestamp):
    """Link a fetched source snapshot to a politician."""
    source = Source(
        url=f"https://example.com/{politician.wikidata_id}",
        url_hash=f"hash-{politician.wikidata_id}-{fetch_timestamp.date()}",
        fetch_timestamp=fetch_timestamp,
    )
    db_session.add(source)
    db_session.flush()
    source.politicians.append(politician)
    return source


class TestDecisionCountEndpoint:
    """Test suite for GET /stats/count endpoint."""

    def test_count_requires_authentication(self, client):
        """Count endpoint should require authentication."""
        response = client.get("/stats/count")
        assert response.status_code == 401

    def test_count_returns_decided_actions_only(self, client, db_session, mock_auth):
        """Count endpoint should count decided actions, not pending ones."""
        politician = Politician.create_with_entity(
            db_session, "Q123", "Test Politician"
        )
        db_session.flush()

        create_action(
            db_session, politician, is_accepted=True, decided_at=datetime.now(UTC)
        )
        create_action(
            db_session, politician, is_accepted=False, decided_at=datetime.now(UTC)
        )
        create_action(db_session, politician)  # still pending
        db_session.commit()

        response = client.get("/stats/count", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2

    def test_count_returns_zero_when_empty(self, client, db_session, mock_auth):
        """Count endpoint should return 0 when no actions exist."""
        response = client.get("/stats/count", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0


class TestStatsTimeseries:
    """Test suite for the decisions timeseries of GET /stats."""

    def test_stats_requires_authentication(self, client):
        """Stats endpoint should require authentication."""
        response = client.get("/stats")
        assert response.status_code == 401

    def test_stats_returns_empty_data(self, client, db_session, mock_auth):
        """Stats endpoint should return zeroed weeks when no actions exist."""
        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert "decisions_timeseries" in data
        assert "country_coverage" in data
        assert "cooldown_days" in data
        # Timeseries should have all weeks in cooldown period, even if empty
        assert len(data["decisions_timeseries"]) == data["cooldown_days"] // 7
        assert all(
            point["accepted"] == 0 and point["discarded"] == 0
            for point in data["decisions_timeseries"]
        )
        assert data["country_coverage"] == []

    def test_timeseries_counts_decisions_by_week(self, client, db_session, mock_auth):
        """Accepted and discarded actions in the current week are counted."""
        politician = Politician.create_with_entity(
            db_session, "Q123", "Test Politician"
        )
        db_session.flush()

        create_action(
            db_session, politician, is_accepted=True, decided_at=datetime.now(UTC)
        )
        create_action(
            db_session, politician, is_accepted=False, decided_at=datetime.now(UTC)
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        weeks_with_data = [
            w
            for w in data["decisions_timeseries"]
            if w["accepted"] > 0 or w["discarded"] > 0
        ]
        assert len(weeks_with_data) == 1
        assert weeks_with_data[0]["accepted"] == 1
        assert weeks_with_data[0]["discarded"] == 1

    def test_timeseries_separates_weeks(self, client, db_session, mock_auth):
        """Decisions from different weeks land in different buckets."""
        politician = Politician.create_with_entity(
            db_session, "Q123", "Test Politician"
        )
        db_session.flush()

        create_action(
            db_session, politician, is_accepted=True, decided_at=datetime.now(UTC)
        )
        create_action(
            db_session,
            politician,
            is_accepted=False,
            decided_at=datetime.now(UTC) - timedelta(weeks=2),
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        weeks_with_data = [
            w
            for w in data["decisions_timeseries"]
            if w["accepted"] > 0 or w["discarded"] > 0
        ]
        assert len(weeks_with_data) == 2
        by_date = {w["date"]: w for w in weeks_with_data}
        earlier, current = sorted(by_date)
        assert by_date[current]["accepted"] == 1
        assert by_date[current]["discarded"] == 0
        assert by_date[earlier]["accepted"] == 0
        assert by_date[earlier]["discarded"] == 1

    def test_timeseries_ignores_pending_actions(self, client, db_session, mock_auth):
        """Pending actions are not decisions and must not appear."""
        politician = Politician.create_with_entity(
            db_session, "Q123", "Test Politician"
        )
        db_session.flush()

        create_action(db_session, politician)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert all(
            w["accepted"] == 0 and w["discarded"] == 0
            for w in data["decisions_timeseries"]
        )

    def test_timeseries_ignores_decisions_outside_cooldown(
        self, client, db_session, mock_auth
    ):
        """Decisions older than the cooldown period are not counted."""
        politician = Politician.create_with_entity(
            db_session, "Q123", "Test Politician"
        )
        db_session.flush()

        create_action(
            db_session,
            politician,
            is_accepted=True,
            decided_at=datetime.now(UTC) - timedelta(days=400),
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert all(
            w["accepted"] == 0 and w["discarded"] == 0
            for w in data["decisions_timeseries"]
        )


class TestStatsCountryCoverage:
    """Test suite for the country coverage of GET /stats."""

    def test_coverage_groups_by_p27_statements(self, client, db_session, mock_auth):
        """Politicians are grouped by their live P27 citizenship statements."""
        us = Country.create_with_entity(db_session, "Q30", "United States")
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        db_session.flush()
        set_terms(
            us,
            labels={"en": "United States"},
            descriptions={"en": "country in North America"},
        )
        set_terms(germany, labels={"en": "Germany", "de": "Deutschland"})
        db_session.flush()

        politician1 = Politician.create_with_entity(db_session, "Q1", "Dual Citizen")
        politician2 = Politician.create_with_entity(db_session, "Q2", "American")
        db_session.flush()

        # politician1 is a citizen of both countries, politician2 only of the US
        create_citizenship(db_session, politician1, "Q30", "Q1$P27-1")
        create_citizenship(db_session, politician1, "Q183", "Q1$P27-2")
        create_citizenship(db_session, politician2, "Q30", "Q2$P27-1")

        # politician1 also decided an action within the cooldown
        create_action(
            db_session, politician1, is_accepted=True, decided_at=datetime.now(UTC)
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = {
            entry["wikidata_id"]: entry for entry in response.json()["country_coverage"]
        }
        assert set(coverage) == {"Q30", "Q183"}

        us_entry = coverage["Q30"]
        assert us_entry["terms"] == {
            "labels": {"en": "United States"},
            "descriptions": {"en": "country in North America"},
            "aliases": {},
        }
        assert us_entry["total_count"] == 2
        assert us_entry["decided_count"] == 1

        germany_entry = coverage["Q183"]
        assert germany_entry["terms"]["labels"] == {
            "en": "Germany",
            "de": "Deutschland",
        }
        assert germany_entry["total_count"] == 1
        assert germany_entry["decided_count"] == 1

        # Resolved names are gone; only term maps are exposed
        assert "name" not in us_entry

    def test_coverage_without_citizenship_bucket(self, client, db_session, mock_auth):
        """Politicians without citizenship statements get a null-terms group."""
        Country.create_with_entity(db_session, "Q30", "United States")
        politician = Politician.create_with_entity(db_session, "Q1", "No Country")
        db_session.flush()

        create_action(
            db_session, politician, is_accepted=False, decided_at=datetime.now(UTC)
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = response.json()["country_coverage"]
        assert len(coverage) == 1
        entry = coverage[0]
        assert entry["wikidata_id"] is None
        assert entry["terms"] is None
        assert entry["total_count"] == 1
        assert entry["decided_count"] == 1

    def test_coverage_ignores_deleted_statements(self, client, db_session, mock_auth):
        """Soft-deleted citizenship statements count as no citizenship."""
        Country.create_with_entity(db_session, "Q30", "United States")
        politician = Politician.create_with_entity(db_session, "Q1", "Ex Citizen")
        db_session.flush()

        statement = create_citizenship(db_session, politician, "Q30", "Q1$P27-1")
        db_session.flush()
        statement.deleted_at = datetime.now(UTC)
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = response.json()["country_coverage"]
        assert len(coverage) == 1
        assert coverage[0]["wikidata_id"] is None
        assert coverage[0]["terms"] is None
        assert coverage[0]["total_count"] == 1

    def test_coverage_ignores_non_citizenship_statements(
        self, client, db_session, mock_auth
    ):
        """Only P27 statements group politicians; P39 statements do not."""
        Country.create_with_entity(db_session, "Q30", "United States")
        politician = Politician.create_with_entity(db_session, "Q1", "Official")
        db_session.flush()

        db_session.add(
            Statement(
                politician_id=politician.id,
                document={
                    "id": "Q1$P39-1",
                    "rank": "normal",
                    "property": {"id": "P39", "data_type": "wikibase-item"},
                    "value": {"type": "value", "content": "Q30"},
                },
            )
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = response.json()["country_coverage"]
        assert len(coverage) == 1
        assert coverage[0]["wikidata_id"] is None
        assert coverage[0]["terms"] is None

    def test_coverage_decided_within_cooldown(self, client, db_session, mock_auth):
        """Politicians whose decisions predate the cooldown are not decided."""
        Country.create_with_entity(db_session, "Q30", "United States")
        politician = Politician.create_with_entity(db_session, "Q1", "Old Decision")
        db_session.flush()

        create_citizenship(db_session, politician, "Q30", "Q1$P27-1")
        create_action(
            db_session,
            politician,
            is_accepted=True,
            decided_at=datetime.now(UTC) - timedelta(days=400),
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = response.json()["country_coverage"]
        assert len(coverage) == 1
        assert coverage[0]["wikidata_id"] == "Q30"
        assert coverage[0]["total_count"] == 1
        assert coverage[0]["decided_count"] == 0

    def test_coverage_enriched_within_cooldown(self, client, db_session, mock_auth):
        """Only sources fetched within the cooldown count as enriched."""
        Country.create_with_entity(db_session, "Q30", "United States")
        politician = Politician.create_with_entity(db_session, "Q1", "Enriched")
        db_session.flush()

        create_citizenship(db_session, politician, "Q30", "Q1$P27-1")
        create_enrichment_source(
            db_session,
            politician,
            fetch_timestamp=datetime.now(UTC) - timedelta(days=400),
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = response.json()["country_coverage"]
        assert len(coverage) == 1
        assert coverage[0]["total_count"] == 1
        assert coverage[0]["enriched_count"] == 0

    def test_coverage_enriched_recent_source(self, client, db_session, mock_auth):
        """A source fetched within the cooldown counts as enriched."""
        Country.create_with_entity(db_session, "Q30", "United States")
        politician = Politician.create_with_entity(db_session, "Q1", "Enriched")
        db_session.flush()

        create_citizenship(db_session, politician, "Q30", "Q1$P27-1")
        create_enrichment_source(
            db_session, politician, fetch_timestamp=datetime.now(UTC)
        )
        db_session.commit()

        response = client.get("/stats", headers=mock_auth)
        assert response.status_code == 200

        coverage = response.json()["country_coverage"]
        assert len(coverage) == 1
        assert coverage[0]["enriched_count"] == 1
