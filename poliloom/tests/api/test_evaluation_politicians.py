"""Tests for the /evaluations/politicians endpoint for evaluation workflow."""

import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any

from poliloom.models import (
    Politician,
    ArchivedPage,
    Evaluation,
)
from poliloom.wikidata_date import WikidataDate


def extract_properties_by_type(
    politician_data: Dict[str, Any], extracted: bool = True
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract properties from politician data based on whether they are extracted or Wikidata.

    Args:
        politician_data: The politician response data
        extracted: If True, return extracted properties (with archived_page), else Wikidata properties (without archived_page)

    Returns:
        Dictionary with keys by property type containing lists of matching properties
    """
    result = {
        "P569": [],  # BIRTH_DATE
        "P570": [],  # DEATH_DATE
        "P39": [],  # POSITION
        "P19": [],  # BIRTHPLACE
        "P27": [],  # CITIZENSHIP
    }

    # Extract properties by type
    for prop in politician_data.get("properties", []):
        if bool(prop.get("archived_page")) == extracted:
            prop_type = prop.get("type")
            if prop_type in result:
                result[prop_type].append(prop)

    return result


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


class TestGetPoliticiansForEvaluationEndpoint:
    """Test the behavior of the /evaluations/politicians endpoint for evaluation workflow."""

    def test_returns_politicians_with_unevaluated_extracted_data(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that politicians with unevaluated extracted data are returned."""
        response = client.get("/evaluations/politicians", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert "politicians" in data
        assert "meta" in data
        politicians = data["politicians"]
        assert len(politicians) == 1

        politician_data = politicians[0]
        assert politician_data["name"] == "Test Politician"
        assert politician_data["wikidata_id"] == "Q123456"

        # Should have single properties list
        assert "properties" in politician_data
        assert isinstance(politician_data["properties"], list)
        assert (
            len(politician_data["properties"]) == 6
        )  # birth_date, position, birthplace (extracted) + death_date, position, birthplace (wikidata)

        # Should NOT have old grouped fields
        assert "positions" not in politician_data
        assert "birthplaces" not in politician_data

        # Verify all property types in single list
        property_types = [prop["type"] for prop in politician_data["properties"]]
        assert "P569" in property_types  # BIRTH_DATE
        assert "P570" in property_types  # DEATH_DATE
        assert "P39" in property_types  # POSITION
        assert "P19" in property_types  # BIRTHPLACE

    def test_includes_politicians_with_evaluated_data_without_statement_id(
        self, client, mock_auth, politician_with_evaluated_data
    ):
        """Test that politicians with evaluated extracted data but no statement_id are included."""
        response = client.get("/evaluations/politicians", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        politicians = data["politicians"]
        assert (
            len(politicians) == 1
        )  # Should include since evaluation failed to push to Wikidata

    def test_excludes_politicians_with_only_wikidata(
        self, client, mock_auth, politician_with_only_wikidata
    ):
        """Test that politicians with only Wikidata data are excluded."""
        response = client.get("/evaluations/politicians", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        politicians = data["politicians"]
        assert len(politicians) == 0  # Should be empty since no extracted data exists

    def test_returns_empty_list_when_no_qualifying_politicians(self, client, mock_auth):
        """Test that endpoint returns empty list when no politicians have unevaluated data."""
        response = client.get("/evaluations/politicians", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()
        assert data["politicians"] == []

    def test_extracted_data_contains_supporting_quotes_and_archive_info(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that extracted data includes supporting_quotes and archived_page info."""
        response = client.get("/evaluations/politicians", headers=mock_auth)

        data = response.json()
        politician_data = data["politicians"][0]

        # Find extracted properties (those with supporting_quotes and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        # Check extracted property
        assert len(extracted_properties["P569"]) == 1  # BIRTH_DATE
        extracted_prop = extracted_properties["P569"][0]
        assert extracted_prop["supporting_quotes"] == ["Born on January 15, 1970"]
        assert extracted_prop["archived_page"] is not None
        assert "url" in extracted_prop["archived_page"]

        # Check extracted position
        assert len(extracted_properties["P39"]) == 1  # POSITION
        extracted_pos = extracted_properties["P39"][0]
        assert extracted_pos["supporting_quotes"] == [
            "Served as Mayor from 2020 to 2024"
        ]
        assert extracted_pos["archived_page"] is not None

        # Check extracted birthplace
        assert len(extracted_properties["P19"]) == 1  # BIRTHPLACE
        extracted_bp = extracted_properties["P19"][0]
        assert extracted_bp["supporting_quotes"] == ["Born in Springfield"]
        assert extracted_bp["archived_page"] is not None

    def test_wikidata_data_excludes_extraction_fields(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that Wikidata entries don't include extraction-specific fields."""
        response = client.get("/evaluations/politicians", headers=mock_auth)

        data = response.json()
        politician_data = data["politicians"][0]

        # Find Wikidata properties (those without supporting_quotes)
        wikidata_properties = extract_properties_by_type(
            politician_data, extracted=False
        )

        # Wikidata properties should not have supporting_quotes or archived_page
        assert len(wikidata_properties["P570"]) >= 1  # DEATH_DATE
        wikidata_prop = wikidata_properties["P570"][0]
        assert wikidata_prop.get("supporting_quotes") is None
        assert wikidata_prop.get("archived_page") is None

        # But they should have precision fields
        assert "value_precision" in wikidata_prop

    def test_pagination_limits_results(
        self, client, mock_auth, db_session, create_archived_page, create_birth_date
    ):
        """Test that pagination parameters limit results correctly."""
        # Create multiple politicians with unevaluated data
        politicians = []
        archived_pages = []

        for i in range(5):
            archived_page = create_archived_page(
                url=f"https://example.com/test{i}",
                content_hash=f"test{i}",
            )
            archived_pages.append(archived_page)

            politician = Politician.create_with_entity(
                db_session, f"Q{100000 + i}", f"Politician {i}"
            )
            politicians.append(politician)

        db_session.flush()  # Need IDs for properties

        # Add extracted properties
        for i, politician in enumerate(politicians):
            create_birth_date(
                politician,
                value=f"19{70 + i}-01-01",
                archived_page=archived_pages[i],
            )

        db_session.flush()

        # Test limit parameter
        response = client.get("/evaluations/politicians?limit=3", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 3

        # Test different limit value
        response = client.get("/evaluations/politicians?limit=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2

    def test_mixed_evaluation_states(
        self,
        client,
        mock_auth,
        db_session,
        sample_position,
        create_birth_date,
        create_position,
    ):
        """Test politician with mix of evaluated and unevaluated data appears in results."""
        # Create politician with both evaluated and unevaluated extracted data
        archived_page = ArchivedPage(
            url="https://example.com/mixed",
            content_hash="mixed123",
        )
        db_session.add(archived_page)

        politician = Politician.create_with_entity(
            db_session, "Q999999", "Mixed Evaluation"
        )
        db_session.add(politician)
        db_session.flush()  # Need IDs for properties

        # Add evaluated extracted property
        evaluated_prop = create_birth_date(
            politician, value="1975-03-15", archived_page=archived_page
        )
        db_session.flush()  # Need ID for evaluation

        evaluation = Evaluation(
            user_id="testuser",
            is_accepted=True,
            property_id=evaluated_prop.id,
        )

        # Add unevaluated extracted position
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

        # Should appear in results because has unevaluated position
        response = client.get("/evaluations/politicians", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        politicians = data["politicians"]
        assert len(politicians) == 1

        politician_data = politicians[0]

        # Find extracted properties (those with supporting_quotes and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        assert (
            len(extracted_properties["P569"]) == 1  # BIRTH_DATE
        )  # Evaluated but no statement_id, so still returned for re-evaluation
        assert (
            len(extracted_properties["P39"]) == 1
        )  # POSITION - Unevaluated, so returned

    def test_politician_with_partial_unevaluated_data_types(
        self, client, mock_auth, db_session, sample_location, create_birthplace
    ):
        """Test politicians appear even if they only have one type of unevaluated data."""
        archived_page = ArchivedPage(
            url="https://example.com/partial",
            content_hash="partial123",
        )
        db_session.add(archived_page)

        # Politician with only unevaluated birthplace
        politician = Politician.create_with_entity(
            db_session, "Q777777", "Birthplace Only"
        )
        db_session.add(politician)
        db_session.flush()  # Need IDs for properties

        create_birthplace(politician, sample_location, archived_page=archived_page)
        db_session.flush()

        response = client.get("/evaluations/politicians", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician_data = data["politicians"][0]

        # Find extracted properties (those with supporting_quotes and archived_page)
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        assert len(extracted_properties["P569"]) == 0  # BIRTH_DATE
        assert len(extracted_properties["P39"]) == 0  # POSITION
        assert len(extracted_properties["P19"]) == 1  # BIRTHPLACE

    def test_property_response_structure(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test property response has correct fields."""
        response = client.get("/evaluations/politicians", headers=mock_auth)
        politician = response.json()["politicians"][0]

        for prop in politician["properties"]:
            assert "id" in prop
            assert "type" in prop

            if prop["type"] in ["P569", "P570"]:  # BIRTH_DATE, DEATH_DATE
                assert prop["value"] is not None
                assert prop["entity_id"] is None
            elif prop["type"] in [
                "P19",
                "P39",
                "P27",
            ]:  # BIRTHPLACE, POSITION, CITIZENSHIP
                assert prop["entity_id"] is not None
                assert prop["value"] is None
                assert "entity_name" in prop

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
        """Test filtering politicians by language QIDs based on archived page languages."""
        # Create archived pages with language associations
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

        # Create politicians with properties from different language pages
        english_politician = Politician.create_with_entity(
            db_session, "Q1001", "English Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q1002", "German Politician"
        )
        no_lang_politician = Politician.create_with_entity(
            db_session, "Q1003", "No Language Politician"
        )

        db_session.add_all([english_politician, german_politician, no_lang_politician])
        db_session.flush()

        # Add properties linked to language-specific archived pages
        create_birth_date(
            english_politician, value="1970-01-01", archived_page=english_page
        )
        create_birth_date(
            german_politician, value="1971-01-01", archived_page=german_page
        )
        # Property without archived page (should not appear in language filtering)
        create_birth_date(no_lang_politician, value="1972-01-01")
        db_session.flush()

        # Test filtering by English language QID
        response = client.get(
            "/evaluations/politicians?languages=Q1860", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "English Politician"

        # Test filtering by German language QID
        response = client.get(
            "/evaluations/politicians?languages=Q188", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "German Politician"

        # Test filtering by multiple languages
        response = client.get(
            "/evaluations/politicians?languages=Q1860&languages=Q188",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {"English Politician", "German Politician"}

        # Test filtering by non-existent language
        response = client.get(
            "/evaluations/politicians?languages=Q999999", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 0

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
        """Test filtering politicians by country QIDs based on citizenship properties."""
        usa_country = sample_country
        germany_country = sample_germany_country

        # Create archived page
        archived_page = ArchivedPage(
            url="https://example.com/test",
            content_hash="test123",
        )
        db_session.add(archived_page)
        db_session.flush()

        # Create politicians
        american_politician = Politician.create_with_entity(
            db_session, "Q2001", "American Politician"
        )
        german_politician = Politician.create_with_entity(
            db_session, "Q2002", "German Politician"
        )
        dual_citizen_politician = Politician.create_with_entity(
            db_session, "Q2003", "Dual Citizen Politician"
        )
        no_citizenship_politician = Politician.create_with_entity(
            db_session, "Q2004", "No Citizenship Politician"
        )

        db_session.add_all(
            [
                american_politician,
                german_politician,
                dual_citizen_politician,
                no_citizenship_politician,
            ]
        )
        db_session.flush()

        # Add citizenship properties
        create_citizenship(american_politician, usa_country, archived_page)
        create_citizenship(german_politician, germany_country, archived_page)

        # Dual citizen - add both citizenships
        create_citizenship(dual_citizen_politician, usa_country, archived_page)
        create_citizenship(dual_citizen_politician, germany_country, archived_page)

        # Non-citizenship property for politician without citizenship
        create_birth_date(no_citizenship_politician, archived_page=archived_page)
        db_session.flush()

        # Test filtering by USA citizenship
        response = client.get(
            "/evaluations/politicians?countries=Q30&limit=10", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {"American Politician", "Dual Citizen Politician"}

        # Test filtering by German citizenship
        response = client.get(
            "/evaluations/politicians?countries=Q183&limit=10", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {"German Politician", "Dual Citizen Politician"}

        # Test filtering by multiple countries
        response = client.get(
            "/evaluations/politicians?countries=Q30&countries=Q183&limit=10",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 3
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {
            "American Politician",
            "German Politician",
            "Dual Citizen Politician",
        }

        # Test filtering by non-existent country
        response = client.get(
            "/evaluations/politicians?countries=Q999999&limit=10", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 0

    def test_combined_language_and_country_filtering(
        self,
        client,
        mock_auth,
        db_session,
        sample_language,
        sample_country,
        sample_germany_country,
        create_citizenship,
        create_archived_page,
        create_birth_date,
    ):
        """Test filtering by both language and country filters combined."""
        usa_country = sample_country
        germany_country = sample_germany_country

        # Create archived pages
        english_page = create_archived_page(
            url="https://en.example.com/test",
            content_hash="en123",
            languages=[sample_language],
        )

        # Create politicians
        american_english_politician = Politician.create_with_entity(
            db_session, "Q3001", "American English Speaking Politician"
        )
        german_english_politician = Politician.create_with_entity(
            db_session, "Q3002", "German English Speaking Politician"
        )
        american_non_english_politician = Politician.create_with_entity(
            db_session, "Q3003", "American Non-English Speaking Politician"
        )

        db_session.add_all(
            [
                american_english_politician,
                german_english_politician,
                american_non_english_politician,
            ]
        )
        db_session.flush()

        # Add properties for American English speaking politician
        create_citizenship(american_english_politician, usa_country, english_page)
        create_birth_date(
            american_english_politician,
            value="1970-01-01",
            archived_page=english_page,
        )

        # Add properties for German English speaking politician
        create_citizenship(german_english_politician, germany_country, english_page)
        create_birth_date(
            german_english_politician,
            value="1971-01-01",
            archived_page=english_page,
        )

        # Add properties for American non-English speaking politician
        create_citizenship(american_non_english_politician, usa_country)

        db_session.flush()

        # Test combined filtering: English language AND American citizenship
        response = client.get(
            "/evaluations/politicians?languages=Q1860&countries=Q30",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "American English Speaking Politician"

        # Test combined filtering: English language AND German citizenship
        response = client.get(
            "/evaluations/politicians?languages=Q1860&countries=Q183",
            headers=mock_auth,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["name"] == "German English Speaking Politician"

        # Test that individual filters work correctly
        # English language only - should return both English speaking politicians
        response = client.get(
            "/evaluations/politicians?languages=Q1860", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2
        politician_names = {p["name"] for p in data["politicians"]}
        assert politician_names == {
            "American English Speaking Politician",
            "German English Speaking Politician",
        }

    def test_language_filter_excludes_properties_from_other_languages(
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
        # Create archived pages with language associations
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
        no_lang_page = create_archived_page(
            url="https://example.com/test",
            content_hash="none123",
            # No languages
        )

        # Create politician with properties from multiple language pages
        politician = Politician.create_with_entity(
            db_session, "Q4001", "Multilingual Politician"
        )
        db_session.add(politician)
        db_session.flush()

        # Add properties from different language sources
        create_birth_date(
            politician,
            value="1970-01-01",
            archived_page=english_page,
            supporting_quotes=["Born on January 1, 1970"],
        )

        create_birth_date(
            politician,
            value="1970-01-02",  # Different date from German source
            archived_page=german_page,
            supporting_quotes=["Geboren am 2. Januar 1970"],
        )

        create_birth_date(
            politician,
            value="1970-01-03",
            archived_page=no_lang_page,
            supporting_quotes=["Unknown language source"],
        )

        # Add a Wikidata property (no archived page)
        create_death_date(
            politician,
            value="2024-01-01",
            statement_id="Q4001$12345678-1234-1234-1234-123456789012",
        )

        db_session.flush()

        # Test filtering by English - should only return English property
        response = client.get(
            "/evaluations/politicians?languages=Q1860", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician_data = data["politicians"][0]
        # Extract only properties with archived_page (extracted properties)
        extracted_props = [
            p for p in politician_data["properties"] if p.get("archived_page")
        ]

        # Should only have the English property, not German or no-language ones
        assert len(extracted_props) == 1
        english_prop = extracted_props[0]
        assert english_prop["value"] == "1970-01-01"
        assert english_prop["supporting_quotes"] == ["Born on January 1, 1970"]
        assert english_prop["archived_page"]["url"] == "https://en.wikipedia.org/test"

        # Test filtering by German - should only return German property
        response = client.get(
            "/evaluations/politicians?languages=Q188", headers=mock_auth
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1

        politician_data = data["politicians"][0]
        extracted_props = [
            p for p in politician_data["properties"] if p.get("archived_page")
        ]

        # Should only have the German property
        assert len(extracted_props) == 1
        german_prop = extracted_props[0]
        assert german_prop["value"] == "1970-01-02"
        assert german_prop["supporting_quotes"] == ["Geboren am 2. Januar 1970"]
        assert german_prop["archived_page"]["url"] == "https://de.wikipedia.org/test"

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
        # Add a normal unevaluated property
        create_birth_date(
            sample_politician,
            value="1980-01-01",
            archived_page=sample_archived_page,
            supporting_quotes=["Born on January 1, 1980"],
        )

        # Add a soft-deleted property
        deleted_property = create_position(
            sample_politician,
            sample_position,
            archived_page=sample_archived_page,
            supporting_quotes=["Served as Mayor"],
        )
        deleted_property.deleted_at = datetime.now(timezone.utc)  # Soft-delete it

        db_session.flush()

        # Request politicians
        response = client.get("/evaluations/politicians", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        # Should return the politician because they have normal_property
        assert len(data["politicians"]) == 1
        politician_data = data["politicians"][0]

        # Extract properties by type
        extracted_properties = extract_properties_by_type(
            politician_data, extracted=True
        )

        # Should have birth date property but NOT the soft-deleted position
        assert len(extracted_properties["P569"]) == 1  # BIRTH_DATE (normal)
        assert (
            len(extracted_properties["P39"]) == 0
        )  # POSITION (soft-deleted, excluded)

        # Verify the returned property is the correct one
        birth_prop = extracted_properties["P569"][0]
        assert birth_prop["value"] == "1980-01-01"
        assert birth_prop["supporting_quotes"] == ["Born on January 1, 1980"]

    def test_excludes_politicians_with_only_soft_deleted_properties(
        self,
        client,
        mock_auth,
        db_session,
        sample_archived_page,
        sample_position,
        create_birth_date,
        create_position,
    ):
        """Test that politicians with only soft-deleted unevaluated properties are excluded."""
        # Create politician with only soft-deleted properties
        politician = Politician.create_with_entity(
            db_session, "Q998877", "Only Deleted Properties Politician"
        )
        db_session.add(politician)
        db_session.flush()

        # Add only soft-deleted properties
        deleted_birth = create_birth_date(
            politician,
            value="1975-05-15",
            archived_page=sample_archived_page,
            supporting_quotes=["Born on May 15, 1975"],
        )
        deleted_birth.deleted_at = datetime.now(timezone.utc)

        deleted_position = create_position(
            politician,
            sample_position,
            archived_page=sample_archived_page,
            supporting_quotes=["Served as Deputy"],
        )
        deleted_position.deleted_at = datetime.now(timezone.utc)

        db_session.flush()

        # Request politicians
        response = client.get("/evaluations/politicians", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        # Should return empty because this politician has no non-deleted unevaluated properties
        assert len(data["politicians"]) == 0

    def test_excludes_politicians_with_soft_deleted_wikidata_entity(
        self, client, mock_auth, db_session, sample_archived_page, create_birth_date
    ):
        """Test that politicians whose WikidataEntity has been soft-deleted are excluded."""

        # Create politician with unevaluated properties
        politician = Politician.create_with_entity(
            db_session, "Q997766", "Soft Deleted Entity Politician"
        )
        db_session.add(politician)
        db_session.flush()

        # Add unevaluated property
        create_birth_date(
            politician,
            value="1985-07-20",
            archived_page=sample_archived_page,
            supporting_quotes=["Born on July 20, 1985"],
        )
        db_session.flush()

        # Verify politician appears before soft-delete
        response = client.get("/evaluations/politicians", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 1
        assert data["politicians"][0]["wikidata_id"] == "Q997766"

        # Soft-delete the WikidataEntity
        politician.wikidata_entity.soft_delete()
        db_session.flush()

        # Request politicians again
        response = client.get("/evaluations/politicians", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()

        # Should return empty because the WikidataEntity has been soft-deleted
        assert len(data["politicians"]) == 0
