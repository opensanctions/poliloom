"""Tests for the /politicians endpoints for evaluation workflow."""

import pytest
from datetime import datetime, timezone

from poliloom.models import (
    Politician,
    ArchivedPage,
    Evaluation,
)
from poliloom.wikidata_date import WikidataDate


@pytest.fixture
def politician_with_evaluated_data(db_session, create_birth_date):
    """Create a politician with only evaluated extracted data (should be excluded)."""
    archived_page = ArchivedPage(
        url="https://example.com/test2",
        content_hash="test456",
    )
    db_session.add(archived_page)

    # Create politician
    politician = Politician.create_with_entity(
        db_session, "Q789012", "Evaluated Politician"
    )
    db_session.add(politician)
    db_session.flush()  # Need IDs for relationships

    # Add extracted property with evaluation
    extracted_property = create_birth_date(
        politician,
        value="1980-05-20",
        archived_page=archived_page,
        supporting_quotes=["Born on May 20, 1980"],
    )
    db_session.flush()  # Need ID for evaluation

    # Add evaluation (this makes the data "evaluated")
    evaluation = Evaluation(
        user_id="testuser",
        is_accepted=True,
        property_id=extracted_property.id,
    )
    db_session.add(evaluation)
    db_session.flush()

    return politician


@pytest.fixture
def politician_with_only_wikidata(
    db_session, sample_position, create_birth_date, create_position
):
    """Create a politician with only Wikidata (non-extracted) data."""
    politician = Politician.create_with_entity(
        db_session, "Q345678", "Wikidata Only Politician"
    )
    db_session.add(politician)
    db_session.flush()  # Need ID for properties

    # Add only Wikidata (non-extracted) data
    create_birth_date(
        politician,
        value="1965-12-10",
        statement_id="Q345678$12345678-1234-1234-1234-123456789012",
    )

    create_position(
        politician,
        sample_position,
        qualifiers_json={
            "P580": [WikidataDate.from_date_string("2016").to_wikidata_qualifier()]
        },
        statement_id="Q345678$87654321-4321-4321-4321-210987654321",
    )
    db_session.flush()

    return politician


class TestNextEndpointFiltering:
    """Test the GET /politicians/next endpoint filtering behavior."""

    def test_returns_politician_with_unevaluated_data(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that politicians with unevaluated extracted data are found."""
        response = client.get("/politicians/next", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] == "Q123456"

    def test_includes_politician_with_evaluated_but_no_statement_id(
        self, client, mock_auth, politician_with_evaluated_data
    ):
        """Test that politicians with evaluated data but no statement_id are included."""
        response = client.get("/politicians/next", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] == "Q789012"

    def test_excludes_politician_with_only_wikidata(
        self, client, mock_auth, politician_with_only_wikidata
    ):
        """Test that politicians with only Wikidata data are excluded."""
        response = client.get("/politicians/next", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] is None

    def test_returns_null_when_no_qualifying_politicians(self, client, mock_auth):
        """Test that endpoint returns null when no politicians have unevaluated data."""
        response = client.get("/politicians/next", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] is None


class TestGetPoliticianEndpointProperties:
    """Test the GET /politicians/{qid} endpoint property details."""

    def test_returns_all_property_types(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that all property types are returned in the response."""
        response = client.get("/politicians/Q123456", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Test Politician"
        assert data["wikidata_id"] == "Q123456"

        assert "properties" in data
        assert isinstance(data["properties"], list)
        assert len(data["properties"]) == 6

        property_types = [prop["type"] for prop in data["properties"]]
        assert "P569" in property_types
        assert "P570" in property_types
        assert "P39" in property_types
        assert "P19" in property_types

    def test_extracted_data_contains_supporting_quotes_and_archive_info(
        self, client, mock_auth, db_session, politician_with_unevaluated_data
    ):
        """Test that extracted data includes supporting_quotes and archived_page info."""
        from poliloom.models import ArchivedPage, PropertyReference

        extracted_properties = [
            p
            for p in politician_with_unevaluated_data.properties
            if p.statement_id is None
        ]
        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
        )
        db_session.add(archived_page)
        db_session.flush()

        quotes = {
            0: ["Born on January 15, 1970"],
            1: ["Served as Mayor from 2020 to 2024"],
            2: ["Born in Springfield"],
        }
        for i, prop in enumerate(extracted_properties):
            db_session.add(
                PropertyReference(
                    property_id=prop.id,
                    archived_page_id=archived_page.id,
                    supporting_quotes=quotes[i],
                )
            )
        db_session.flush()

        response = client.get("/politicians/Q123456", headers=mock_auth)

        data = response.json()
        props = data["properties"]
        extracted = [p for p in props if p["statement_id"] is None]

        birth_dates = [p for p in extracted if p["type"] == "P569"]
        assert len(birth_dates) == 1
        assert len(birth_dates[0]["sources"]) == 1
        assert birth_dates[0]["sources"][0]["supporting_quotes"] == [
            "Born on January 15, 1970"
        ]
        assert birth_dates[0]["sources"][0]["archived_page"] is not None
        assert "url" in birth_dates[0]["sources"][0]["archived_page"]

        positions = [p for p in extracted if p["type"] == "P39"]
        assert len(positions) == 1
        assert len(positions[0]["sources"]) == 1
        assert positions[0]["sources"][0]["supporting_quotes"] == [
            "Served as Mayor from 2020 to 2024"
        ]

        birthplaces = [p for p in extracted if p["type"] == "P19"]
        assert len(birthplaces) == 1
        assert len(birthplaces[0]["sources"]) == 1
        assert birthplaces[0]["sources"][0]["supporting_quotes"] == [
            "Born in Springfield"
        ]

    def test_wikidata_data_excludes_extraction_fields(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that Wikidata entries don't include extraction-specific fields."""
        response = client.get("/politicians/Q123456", headers=mock_auth)

        data = response.json()
        wikidata = [p for p in data["properties"] if p["statement_id"] is not None]
        death_dates = [p for p in wikidata if p["type"] == "P570"]
        assert len(death_dates) >= 1
        assert death_dates[0].get("sources") == []
        assert "value_precision" in death_dates[0]

    def test_property_response_structure(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test property response has correct fields."""
        response = client.get("/politicians/Q123456", headers=mock_auth)
        data = response.json()

        for prop in data["properties"]:
            assert "id" in prop
            assert "type" in prop

            if prop["type"] in ["P569", "P570"]:
                assert prop["value"] is not None
                assert prop["entity_id"] is None
            elif prop["type"] in ["P19", "P39", "P27"]:
                assert prop["entity_id"] is not None
                assert prop["value"] is None
                assert "entity_name" in prop

    def test_mixed_evaluation_states(
        self,
        client,
        mock_auth,
        db_session,
        sample_position,
        create_birth_date,
        create_position,
    ):
        """Test politician with mix of evaluated and unevaluated data."""
        archived_page = ArchivedPage(
            url="https://example.com/mixed",
            content_hash="mixed123",
        )
        db_session.add(archived_page)

        politician = Politician.create_with_entity(
            db_session, "Q999999", "Mixed Evaluation"
        )
        db_session.add(politician)
        db_session.flush()

        evaluated_prop = create_birth_date(
            politician, value="1975-03-15", archived_page=archived_page
        )
        db_session.flush()

        evaluation = Evaluation(
            user_id="testuser",
            is_accepted=True,
            property_id=evaluated_prop.id,
        )

        create_position(
            politician,
            sample_position,
            archived_page=archived_page,
            qualifiers_json={
                "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()]
            },
        )

        db_session.add(evaluation)
        db_session.flush()

        response = client.get("/politicians/Q999999", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        extracted = [p for p in data["properties"] if p["statement_id"] is None]
        assert len([p for p in extracted if p["type"] == "P569"]) == 1
        assert len([p for p in extracted if p["type"] == "P39"]) == 1

    def test_language_filtering(
        self,
        client,
        mock_auth,
        db_session,
        sample_language,
        sample_german_language,
        create_archived_page,
        create_birth_date,
        create_death_date,
    ):
        """Test that when filtering by language, only properties from that language's archived pages are returned."""
        english_page = create_archived_page(
            url="https://en.wikipedia.org/test",
            content_hash="en123",
            languages=[sample_language],
        )
        german_page = create_archived_page(
            url="https://de.wikipedia.org/test",
            content_hash="de123",
            languages=[sample_german_language],
        )

        politician = Politician.create_with_entity(
            db_session, "Q4001", "Multilingual Politician"
        )
        db_session.add(politician)
        db_session.flush()

        create_birth_date(
            politician,
            value="1970-01-01",
            archived_page=english_page,
            supporting_quotes=["Born on January 1, 1970"],
        )
        create_birth_date(
            politician,
            value="1970-01-02",
            archived_page=german_page,
            supporting_quotes=["Geboren am 2. Januar 1970"],
        )
        create_death_date(
            politician,
            value="2024-01-01",
            statement_id="Q4001$12345678-1234-1234-1234-123456789012",
        )
        db_session.flush()

        # English filter
        response = client.get("/politicians/Q4001?languages=Q1860", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        extracted_props = [
            p for p in data["properties"] if len(p.get("sources", [])) > 0
        ]
        assert len(extracted_props) == 1
        assert extracted_props[0]["value"] == "1970-01-01"

        # German filter
        response = client.get("/politicians/Q4001?languages=Q188", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        extracted_props = [
            p for p in data["properties"] if len(p.get("sources", [])) > 0
        ]
        assert len(extracted_props) == 1
        assert extracted_props[0]["value"] == "1970-01-02"

    def test_excludes_soft_deleted_properties(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_position,
        sample_archived_page,
        create_birth_date,
        create_position,
    ):
        """Test that soft-deleted properties are excluded from results."""
        create_birth_date(
            sample_politician,
            value="1980-01-01",
            archived_page=sample_archived_page,
            supporting_quotes=["Born on January 1, 1980"],
        )

        deleted_property = create_position(
            sample_politician,
            sample_position,
            archived_page=sample_archived_page,
            supporting_quotes=["Served as Mayor"],
        )
        deleted_property.deleted_at = datetime.now(timezone.utc)
        db_session.flush()

        response = client.get("/politicians/Q123456", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        props = data["properties"]
        birth_dates = [p for p in props if p["type"] == "P569"]
        assert len(birth_dates) == 1
        assert len([p for p in props if p["type"] == "P39"]) == 0
        assert birth_dates[0]["value"] == "1980-01-01"

    def test_excludes_politicians_with_soft_deleted_wikidata_entity(
        self, client, mock_auth, db_session, sample_archived_page, create_birth_date
    ):
        """Test that politicians whose WikidataEntity has been soft-deleted are excluded."""
        politician = Politician.create_with_entity(
            db_session, "Q997766", "Soft Deleted Entity Politician"
        )
        db_session.add(politician)
        db_session.flush()

        create_birth_date(
            politician,
            value="1985-07-20",
            archived_page=sample_archived_page,
            supporting_quotes=["Born on July 20, 1985"],
        )
        db_session.flush()

        # Verify politician appears before soft-delete
        response = client.get("/politicians/Q997766", headers=mock_auth)
        assert response.status_code == 200

        # Soft-delete the WikidataEntity
        politician.wikidata_entity.soft_delete()
        db_session.flush()

        # Should get 404 now
        response = client.get("/politicians/Q997766", headers=mock_auth)
        assert response.status_code == 404


class TestNextEndpointLanguageFiltering:
    """Test language filtering on the /politicians/next endpoint."""

    def test_language_filtering(
        self,
        client,
        mock_auth,
        db_session,
        sample_language,
        sample_german_language,
        create_archived_page,
        create_birth_date,
    ):
        """Test filtering politicians by language QIDs."""
        english_page = create_archived_page(
            url="https://en.example.com/test",
            content_hash="en123",
            languages=[sample_language],
        )
        german_page = create_archived_page(
            url="https://de.example.com/test",
            content_hash="de123",
            languages=[sample_german_language],
        )

        english_politician = Politician.create_with_entity(
            db_session, "Q1001", "English Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q1002", "German Politician"
        )

        db_session.add_all([english_politician, german_politician])
        db_session.flush()

        create_birth_date(
            english_politician, value="1970-01-01", archived_page=english_page
        )
        create_birth_date(
            german_politician, value="1971-01-01", archived_page=german_page
        )
        db_session.flush()

        # English filter should find English politician
        response = client.get("/politicians/next?languages=Q1860", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] == "Q1001"

        # German filter should find German politician
        response = client.get("/politicians/next?languages=Q188", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] == "Q1002"

        # Non-existent language
        response = client.get("/politicians/next?languages=Q999999", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] is None

    def test_country_filtering(
        self,
        client,
        mock_auth,
        db_session,
        sample_country,
        sample_germany_country,
        create_citizenship,
        create_birth_date,
    ):
        """Test filtering politicians by country QIDs."""
        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
        )
        db_session.add(archived_page)
        db_session.flush()

        american_politician = Politician.create_with_entity(
            db_session, "Q2001", "American Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q2002", "German Politician"
        )

        db_session.add_all([american_politician, german_politician])
        db_session.flush()

        create_citizenship(american_politician, sample_country, archived_page)
        create_citizenship(german_politician, sample_germany_country, archived_page)
        db_session.flush()

        # US filter
        response = client.get("/politicians/next?countries=Q30", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] == "Q2001"

        # Germany filter
        response = client.get("/politicians/next?countries=Q183", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] == "Q2002"

        # Non-existent country
        response = client.get("/politicians/next?countries=Q999999", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert data["wikidata_id"] is None
