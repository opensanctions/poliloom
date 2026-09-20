"""Tests for the entities API endpoints (languages, countries, entity search)."""

from datetime import UTC, datetime

import pytest

from poliloom.models import Politician, Statement

from ..conftest import make_terms


def set_terms(entity, *, labels=None, descriptions=None, aliases=None):
    """Set language-keyed term maps on an entity's WikidataEntity."""
    entity.wikidata_entity.labels = labels or {}
    entity.wikidata_entity.descriptions = descriptions or {}
    entity.wikidata_entity.aliases = aliases or {}


def citizenship_statement(politician, country, statement_id):
    """Build a live P27 citizenship statement for a politician."""
    return Statement(
        politician_id=politician.id,
        document={
            "id": statement_id,
            "rank": "normal",
            "property": {"id": "P27", "data_type": "wikibase-item"},
            "value": {"type": "value", "content": country.wikidata_id},
        },
    )


class TestGetLanguages:
    """Test the GET /languages endpoint."""

    def test_languages_carry_term_maps(
        self,
        client,
        mock_auth,
        db_session,
        sample_language,
        sample_politician,
        sample_wikipedia_project,
        create_wikipedia_link,
    ):
        """Languages should return language-keyed term maps and codes."""
        sample_language.wikimedia_code = "en"
        sample_language.iso_639_3 = "eng"
        set_terms(
            sample_language,
            labels={"en": "English", "sv": "engelska"},
            descriptions={"en": "West Germanic language"},
            aliases={"en": ["English language"]},
        )
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()
        english = next(lang for lang in languages if lang["wikidata_id"] == "Q1860")

        assert english["terms"] == {
            "labels": {"en": "English", "sv": "engelska"},
            "descriptions": {"en": "West Germanic language"},
            "aliases": {"en": ["English language"]},
        }
        assert english["wikimedia_code"] == "en"
        assert english["iso_639_1"] == "en"
        assert english["iso_639_3"] == "eng"
        assert english["sources_count"] == 1
        # Resolved names are gone; only term maps are exposed
        assert "name" not in english
        assert "description" not in english

    def test_languages_with_wikipedia_links(
        self,
        client,
        mock_auth,
        sample_language,
        sample_german_language,
        sample_french_language,
        sample_politician,
        sample_wikipedia_project,
        sample_german_wikipedia_project,
        sample_french_wikipedia_project,
        create_wikipedia_link,
        db_session,
    ):
        """Languages should count Wikipedia links through WikipediaProject relations."""
        politician2 = Politician.create_with_entity(
            db_session, "Q999888", make_terms("Second Politician")
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999777", make_terms("Third Politician")
        )
        db_session.flush()

        # English: 3 links
        create_wikipedia_link(sample_politician, sample_wikipedia_project)
        create_wikipedia_link(politician2, sample_wikipedia_project)
        create_wikipedia_link(politician3, sample_wikipedia_project)

        # German: 2 links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(politician2, sample_german_wikipedia_project)

        # French: 1 link
        create_wikipedia_link(politician3, sample_french_wikipedia_project)

        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Verify counts
        language_counts = {
            lang["wikidata_id"]: lang["sources_count"] for lang in languages
        }

        assert language_counts["Q1860"] == 3  # English
        assert language_counts["Q188"] == 2  # German
        assert language_counts["Q150"] == 1  # French

    def test_languages_ordered_by_source_count_desc(
        self,
        client,
        mock_auth,
        sample_language,
        sample_german_language,
        sample_politician,
        sample_wikipedia_project,
        sample_german_wikipedia_project,
        create_wikipedia_link,
        db_session,
    ):
        """Languages should be ordered by sources_count descending."""
        politician2 = Politician.create_with_entity(
            db_session, "Q999888", make_terms("Second Politician")
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999777", make_terms("Third Politician")
        )
        db_session.flush()

        # English: 1 link
        create_wikipedia_link(sample_politician, sample_wikipedia_project)

        # German: 3 links
        create_wikipedia_link(sample_politician, sample_german_wikipedia_project)
        create_wikipedia_link(politician2, sample_german_wikipedia_project)
        create_wikipedia_link(politician3, sample_german_wikipedia_project)

        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Find German and English in the results
        german = next(lang for lang in languages if lang["wikidata_id"] == "Q188")
        english = next(lang for lang in languages if lang["wikidata_id"] == "Q1860")

        # German should come before English due to higher count
        german_index = languages.index(german)
        english_index = languages.index(english)
        assert german_index < english_index

    def test_languages_filters_soft_deleted(
        self,
        client,
        mock_auth,
        sample_language,
        db_session,
    ):
        """Soft-deleted languages should not appear in results."""
        sample_language.wikidata_entity.deleted_at = datetime.now(UTC)
        db_session.flush()

        response = client.get("/languages", headers=mock_auth)
        assert response.status_code == 200

        languages = response.json()

        # Sample language should not be in results
        assert not any(lang["wikidata_id"] == "Q1860" for lang in languages)

    def test_languages_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/languages")
        assert response.status_code == 401


class TestGetCountries:
    """Test the GET /countries endpoint."""

    def test_countries_carry_term_maps(
        self, client, mock_auth, db_session, sample_country, sample_politician
    ):
        """Countries should return language-keyed term maps."""
        set_terms(
            sample_country,
            labels={"en": "United States", "sv": "USA"},
            descriptions={"en": "country in North America"},
            aliases={"en": ["USA", "America"]},
        )
        db_session.add(citizenship_statement(sample_politician, sample_country, "S1"))
        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()
        us = next(ctry for ctry in countries if ctry["wikidata_id"] == "Q30")

        assert us["terms"] == {
            "labels": {"en": "United States", "sv": "USA"},
            "descriptions": {"en": "country in North America"},
            "aliases": {"en": ["USA", "America"]},
        }
        assert us["citizenships_count"] == 1
        # Resolved names are gone; only term maps are exposed
        assert "name" not in us
        assert "description" not in us

    def test_countries_count_p27_statements(
        self,
        client,
        mock_auth,
        db_session,
        sample_country,
        sample_germany_country,
        sample_france_country,
    ):
        """Countries should count live P27 citizenship statements."""
        politician1 = Politician.create_with_entity(
            db_session, "Q999888", make_terms("First Politician")
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999777", make_terms("Second Politician")
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999666", make_terms("Third Politician")
        )
        db_session.flush()

        # US: 3 statements
        db_session.add(citizenship_statement(politician1, sample_country, "S1"))
        db_session.add(citizenship_statement(politician2, sample_country, "S2"))
        db_session.add(citizenship_statement(politician3, sample_country, "S3"))

        # Germany: 2 statements
        db_session.add(citizenship_statement(politician1, sample_germany_country, "S4"))
        db_session.add(citizenship_statement(politician2, sample_germany_country, "S5"))

        # France: 1 statement
        db_session.add(citizenship_statement(politician3, sample_france_country, "S6"))

        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        country_counts = {
            ctry["wikidata_id"]: ctry["citizenships_count"] for ctry in countries
        }

        assert country_counts["Q30"] == 3  # US
        assert country_counts["Q183"] == 2  # Germany
        assert country_counts["Q142"] == 1  # France

    def test_countries_ignore_deleted_statements(
        self, client, mock_auth, db_session, sample_country, sample_politician
    ):
        """Soft-deleted P27 statements should not count as citizenships."""
        statement = citizenship_statement(sample_politician, sample_country, "S1")
        db_session.add(statement)
        db_session.flush()
        statement.deleted_at = datetime.now(UTC)
        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()
        assert not any(ctry["wikidata_id"] == "Q30" for ctry in countries)

    def test_countries_ordered_by_citizenship_count_desc(
        self,
        client,
        mock_auth,
        db_session,
        sample_country,
        sample_germany_country,
    ):
        """Countries should be ordered by citizenships_count descending."""
        politician1 = Politician.create_with_entity(
            db_session, "Q999888", make_terms("First Politician")
        )
        politician2 = Politician.create_with_entity(
            db_session, "Q999777", make_terms("Second Politician")
        )
        politician3 = Politician.create_with_entity(
            db_session, "Q999666", make_terms("Third Politician")
        )
        db_session.flush()

        # Germany: 3 statements
        db_session.add(citizenship_statement(politician1, sample_germany_country, "S1"))
        db_session.add(citizenship_statement(politician2, sample_germany_country, "S2"))
        db_session.add(citizenship_statement(politician3, sample_germany_country, "S3"))

        # US: 1 statement
        db_session.add(citizenship_statement(politician1, sample_country, "S4"))

        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        germany = next(ctry for ctry in countries if ctry["wikidata_id"] == "Q183")
        us = next(ctry for ctry in countries if ctry["wikidata_id"] == "Q30")

        # Germany should come before US due to higher count
        germany_index = countries.index(germany)
        us_index = countries.index(us)
        assert germany_index < us_index

    def test_countries_filters_soft_deleted(
        self,
        client,
        mock_auth,
        sample_country,
        db_session,
    ):
        """Soft-deleted countries should not appear in results."""
        sample_country.wikidata_entity.deleted_at = datetime.now(UTC)
        db_session.flush()

        response = client.get("/countries", headers=mock_auth)
        assert response.status_code == 200

        countries = response.json()

        assert not any(ctry["wikidata_id"] == "Q30" for ctry in countries)

    def test_countries_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/countries")
        assert response.status_code == 401


class TestEntitySearch:
    """Test the unified /entities/search endpoint."""

    @pytest.mark.parametrize(
        "entity_type,model_name,names,query",
        [
            (
                "position",
                "Position",
                ["Mayor of Springfield", "Governor of California"],
                "springfield",
            ),
            (
                "location",
                "Location",
                ["Springfield, Illinois", "Los Angeles"],
                "springfield",
            ),
            ("country", "Country", ["United States of America", "Germany"], "united"),
        ],
    )
    def test_search_by_type(
        self, client, mock_auth, db_session, entity_type, model_name, names, query
    ):
        """Should search entities by type and return matches."""
        from poliloom import models

        model_class = getattr(models, model_name)
        for i, name in enumerate(names):
            model_class.create_with_entity(db_session, f"Q{i + 1}", make_terms(name))
        db_session.flush()

        response = client.get(
            f"/entities/search?type={entity_type}&q={query}",
            headers=mock_auth,
        )
        assert response.status_code == 200

        results = response.json()
        assert len(results) == 1
        assert results[0]["wikidata_id"] == "Q1"

    def test_search_returns_term_maps(self, client, mock_auth, db_session):
        """Results should carry language-keyed term maps, not resolved names."""
        from poliloom.models import Position

        position = Position.create_with_entity(
            db_session,
            "Q1",
            make_terms("Mayor of Springfield"),
        )
        db_session.flush()
        set_terms(
            position,
            labels={"en": "Mayor of Springfield", "sv": "Borgmästare i Springfield"},
            descriptions={"en": "mayoral position"},
            aliases={"en": ["Springfield Mayor"]},
        )
        db_session.flush()

        response = client.get(
            "/entities/search?type=position&q=springfield", headers=mock_auth
        )
        assert response.status_code == 200

        results = response.json()
        assert len(results) == 1
        result = results[0]
        assert result["wikidata_id"] == "Q1"
        assert result["terms"] == {
            "labels": {"en": "Mayor of Springfield", "sv": "Borgmästare i Springfield"},
            "descriptions": {"en": "mayoral position"},
            "aliases": {"en": ["Springfield Mayor"]},
        }
        # Resolved names and rich descriptions are gone
        assert "name" not in result
        assert "description" not in result

    def test_unknown_type_returns_422(self, client, mock_auth):
        """Should return 422 for unknown entity type."""
        response = client.get("/entities/search?type=bogus&q=test", headers=mock_auth)
        assert response.status_code == 422

    def test_requires_query(self, client, mock_auth):
        """Should return 422 when query is missing."""
        response = client.get("/entities/search?type=position", headers=mock_auth)
        assert response.status_code == 422

    def test_requires_authentication(self, client):
        """Endpoint should require authentication."""
        response = client.get("/entities/search?type=position&q=test")
        assert response.status_code == 401

    def test_filters_soft_deleted(self, client, mock_auth, db_session):
        """Should filter out soft-deleted entities from search results."""
        from poliloom.models import Position

        Position.create_with_entity(db_session, "Q1", make_terms("Active Position"))
        pos2 = Position.create_with_entity(
            db_session, "Q2", make_terms("Deleted Position")
        )
        db_session.flush()

        pos2.wikidata_entity.deleted_at = datetime.now(UTC)
        db_session.flush()

        response = client.get(
            "/entities/search?type=position&q=position", headers=mock_auth
        )
        assert response.status_code == 200

        results = response.json()
        assert len(results) == 1
        assert results[0]["wikidata_id"] == "Q1"

    def test_respects_limit(self, client, mock_auth, db_session):
        """Should respect limit parameter."""
        from poliloom.models import Position

        for i in range(5):
            Position.create_with_entity(
                db_session, f"Q{i}", make_terms(f"Test Position {i}")
            )
        db_session.flush()

        response = client.get(
            "/entities/search?type=position&q=test&limit=3", headers=mock_auth
        )
        assert response.status_code == 200

        results = response.json()
        assert len(results) == 3
