"""Tests for the Politician model."""

from datetime import datetime, timezone
from poliloom.models import (
    ArchivedPage,
    ArchivedPageLanguage,
    Country,
    Language,
    Location,
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


class TestPolitician:
    """Test cases for the Politician model."""

    def test_politician_cascade_delete_properties(self, db_session):
        """Test that deleting a politician cascades to properties."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
        )
        db_session.add(prop)
        db_session.flush()

        db_session.delete(politician)
        db_session.flush()

        assert (
            db_session.query(Property).filter_by(politician_id=politician.id).first()
            is None
        )

    def test_politician_with_all_property_types(self, db_session):
        """Test politician with all property types stored correctly."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Test Position")
        position.embedding = [0.1] * 384
        location = Location.create_with_entity(db_session, "Q28513", "Test Location")
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.flush()

        qualifiers = {
            "P580": [WikidataDate.from_date_string("2020").to_wikidata_qualifier()],
            "P582": [WikidataDate.from_date_string("2024").to_wikidata_qualifier()],
        }

        props = [
            Property(
                politician_id=politician.id,
                type=PropertyType.BIRTH_DATE,
                value="1970-01-15",
                value_precision=11,
            ),
            Property(
                politician_id=politician.id,
                type=PropertyType.DEATH_DATE,
                value="2020-12-31",
                value_precision=11,
            ),
            Property(
                politician_id=politician.id,
                type=PropertyType.BIRTHPLACE,
                entity_id=location.wikidata_id,
            ),
            Property(
                politician_id=politician.id,
                type=PropertyType.POSITION,
                entity_id=position.wikidata_id,
                qualifiers_json=qualifiers,
            ),
            Property(
                politician_id=politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=country.wikidata_id,
            ),
        ]
        db_session.add_all(props)
        db_session.flush()
        db_session.refresh(politician)

        properties = politician.properties
        assert len(properties) == 5

        properties_by_type = {prop.type: prop for prop in properties}

        assert PropertyType.BIRTH_DATE in properties_by_type
        assert properties_by_type[PropertyType.BIRTH_DATE].value == "1970-01-15"
        assert properties_by_type[PropertyType.BIRTH_DATE].entity_id is None

        assert PropertyType.DEATH_DATE in properties_by_type
        assert properties_by_type[PropertyType.DEATH_DATE].value == "2020-12-31"

        assert PropertyType.BIRTHPLACE in properties_by_type
        assert (
            properties_by_type[PropertyType.BIRTHPLACE].entity_id
            == location.wikidata_id
        )
        assert properties_by_type[PropertyType.BIRTHPLACE].value is None

        assert PropertyType.POSITION in properties_by_type
        assert (
            properties_by_type[PropertyType.POSITION].entity_id == position.wikidata_id
        )
        assert properties_by_type[PropertyType.POSITION].qualifiers_json is not None

        assert PropertyType.CITIZENSHIP in properties_by_type
        assert (
            properties_by_type[PropertyType.CITIZENSHIP].entity_id
            == country.wikidata_id
        )

    def test_get_priority_wikipedia_sources_no_links(self, db_session):
        """Test get_priority_wikipedia_sources when politician has no Wikipedia links."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()
        result = politician.get_priority_wikipedia_sources(db_session)
        assert result == []

    def test_get_priority_wikipedia_sources_english_only(self, db_session):
        """Test get_priority_wikipedia_sources when only English link available."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        language = Language.create_with_entity(db_session, "Q1860", "English")
        language.iso_639_1 = "en"
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test_Politician",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        result = politician.get_priority_wikipedia_sources(db_session)

        assert len(result) == 1
        url, wikipedia_project_id = result[0]
        assert "en.wikipedia.org" in url
        assert wikipedia_project_id == "Q328"

    def test_get_priority_wikipedia_sources_citizenship_priority(self, db_session):
        """Test get_priority_wikipedia_sources with citizenship-based prioritization."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )

        # Create German language and Wikipedia project
        german_language = Language.create_with_entity(db_session, "Q188", "German")
        german_language.iso_639_1 = "de"
        german_wp = WikipediaProject.create_with_entity(
            db_session, "Q48183", "German Wikipedia"
        )
        german_wp.official_website = "https://de.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q188",
                child_entity_id="Q48183",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="de_lang_rel",
            )
        )

        # Create Germany country
        germany = Country.create_with_entity(db_session, "Q183", "Germany")
        germany.iso_code = "DE"

        # Create English language and Wikipedia project
        english_language = Language.create_with_entity(db_session, "Q1860", "English")
        english_language.iso_639_1 = "en"
        english_wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        english_wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="en_lang_rel",
            )
        )

        # Create official language relation: German is official language of Germany
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q188",
                child_entity_id="Q183",
                relation_type=RelationType.OFFICIAL_LANGUAGE,
                statement_id="de_official",
            )
        )

        db_session.flush()

        # Create citizenship property
        db_session.add(
            Property(
                politician_id=politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=germany.wikidata_id,
            )
        )

        # Create multiple German links to simulate popularity
        for i in range(5):
            dummy = Politician.create_with_entity(
                db_session, f"Q{1000 + i}", f"Dummy {i}"
            )
            db_session.flush()
            db_session.add(
                WikipediaSource(
                    politician_id=dummy.id,
                    url=f"https://de.wikipedia.org/wiki/Dummy_{i}",
                    wikipedia_project_id=german_wp.wikidata_id,
                )
            )

        # Create the actual politician's links
        db_session.add(
            WikipediaSource(
                politician_id=politician.id,
                url="https://de.wikipedia.org/wiki/Test_Politician",
                wikipedia_project_id=german_wp.wikidata_id,
            )
        )
        db_session.add(
            WikipediaSource(
                politician_id=politician.id,
                url="https://en.wikipedia.org/wiki/Test_Politician",
                wikipedia_project_id=english_wp.wikidata_id,
            )
        )
        db_session.flush()

        result = politician.get_priority_wikipedia_sources(db_session)

        assert len(result) >= 1
        url, _ = result[0]
        assert "de.wikipedia.org" in url

    def test_get_priority_wikipedia_sources_no_citizenship(self, db_session):
        """Test get_priority_wikipedia_sources when politician has no citizenship."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )

        # Create languages and Wikipedia projects
        languages_data = [
            (
                "Q1860",
                "English",
                "en",
                "Q328",
                "English Wikipedia",
                "https://en.wikipedia.org",
                3,
            ),
            (
                "Q150",
                "French",
                "fr",
                "Q8447",
                "French Wikipedia",
                "https://fr.wikipedia.org",
                10,
            ),
            (
                "Q188",
                "German",
                "de",
                "Q48183",
                "German Wikipedia",
                "https://de.wikipedia.org",
                7,
            ),
            (
                "Q1321",
                "Spanish",
                "es",
                "Q8449",
                "Spanish Wikipedia",
                "https://es.wikipedia.org",
                5,
            ),
        ]

        wikipedia_projects = {}
        base_qid = 50000

        for (
            lang_qid,
            lang_name,
            iso,
            wp_qid,
            wp_name,
            wp_url,
            popularity,
        ) in languages_data:
            lang = Language.create_with_entity(db_session, lang_qid, lang_name)
            lang.iso_639_1 = iso
            wp = WikipediaProject.create_with_entity(db_session, wp_qid, wp_name)
            wp.official_website = wp_url
            db_session.add(
                WikidataRelation(
                    parent_entity_id=lang_qid,
                    child_entity_id=wp_qid,
                    relation_type=RelationType.LANGUAGE_OF_WORK,
                    statement_id=f"{iso}_lang",
                )
            )
            wikipedia_projects[iso] = wp

            # Create dummy politicians for popularity
            for i in range(popularity):
                dummy = Politician.create_with_entity(
                    db_session, f"Q{base_qid + i}", f"Dummy {iso} {i}"
                )
                db_session.flush()
                db_session.add(
                    WikipediaSource(
                        politician_id=dummy.id,
                        url=f"https://{iso}.wikipedia.org/wiki/Dummy_{i}",
                        wikipedia_project_id=wp.wikidata_id,
                    )
                )
            base_qid += popularity

        # Create politician's actual links
        for iso, wp in wikipedia_projects.items():
            db_session.add(
                WikipediaSource(
                    politician_id=politician.id,
                    url=f"https://{iso}.wikipedia.org/wiki/Test",
                    wikipedia_project_id=wp.wikidata_id,
                )
            )

        db_session.flush()

        result = politician.get_priority_wikipedia_sources(db_session)

        assert len(result) == 3
        returned_project_ids = {project_id for _, project_id in result}
        expected_top_3 = {"Q8447", "Q48183", "Q8449"}  # French, German, Spanish
        assert returned_project_ids == expected_top_3


class TestPoliticianQueryBase:
    """Test cases for Politician.query_base method."""

    def test_query_base_returns_non_deleted_politicians(self, db_session):
        """Test that query_base returns non-soft-deleted politicians."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == politician.id

    def test_query_base_excludes_soft_deleted_politicians(self, db_session):
        """Test that query_base excludes soft-deleted politicians."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()
        db_session.refresh(politician)
        politician.wikidata_entity.soft_delete()
        db_session.flush()

        query = Politician.query_base()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


class TestPoliticianFilterByUnevaluated:
    """Test cases for Politician.filter_by_unevaluated_properties method."""

    def test_filter_returns_politicians_with_unevaluated_properties(self, db_session):
        """Test that filter finds politicians with unevaluated properties."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Language.create_with_entity(db_session, "Q1860", "English")
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_source_id=ws.id,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=archived_page.id,
        )
        db_session.add(prop)
        db_session.flush()

        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == politician.id

    def test_filter_excludes_politicians_with_only_evaluated_properties(
        self, db_session
    ):
        """Test that filter excludes politicians with statement_id (pushed to Wikidata)."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Language.create_with_entity(db_session, "Q1860", "English")
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_source_id=ws.id,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=archived_page.id,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(prop)
        db_session.flush()

        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_filter_excludes_soft_deleted_properties(self, db_session):
        """Test that filter excludes soft-deleted properties."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Language.create_with_entity(db_session, "Q1860", "English")
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_source_id=ws.id,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)
        db_session.flush()

        prop = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="1980-01-01",
            value_precision=11,
            archived_page_id=archived_page.id,
            deleted_at=datetime.now(timezone.utc),
        )
        db_session.add(prop)
        db_session.flush()

        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query)
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_filter_with_language_parameter(self, db_session):
        """Test language filtering based on archived page languages."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )

        english_language = Language.create_with_entity(db_session, "Q1860", "English")
        english_language.iso_639_1 = "en"
        german_language = Language.create_with_entity(db_session, "Q188", "German")
        german_language.iso_639_1 = "de"

        # Create English archived page
        en_wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        en_wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="en_lang",
            )
        )
        db_session.flush()

        en_ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=en_wp.wikidata_id,
        )
        db_session.add(en_ws)
        db_session.flush()

        en_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_source_id=en_ws.id,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(en_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=en_page.id, language_id=english_language.wikidata_id
            )
        )

        # Create German archived page
        de_wp = WikipediaProject.create_with_entity(
            db_session, "Q48183", "German Wikipedia"
        )
        de_wp.official_website = "https://de.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q188",
                child_entity_id="Q48183",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="de_lang",
            )
        )
        db_session.flush()

        de_ws = WikipediaSource(
            politician_id=politician.id,
            url="https://de.wikipedia.org/wiki/Test",
            wikipedia_project_id=de_wp.wikidata_id,
        )
        db_session.add(de_ws)
        db_session.flush()

        de_page = ArchivedPage(
            url="https://de.wikipedia.org/wiki/Test",
            wikipedia_source_id=de_ws.id,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(de_page)
        db_session.flush()
        db_session.add(
            ArchivedPageLanguage(
                archived_page_id=de_page.id, language_id=german_language.wikidata_id
            )
        )

        db_session.add(
            Property(
                politician_id=politician.id,
                type=PropertyType.BIRTH_DATE,
                value="1970-01-01",
                value_precision=11,
                archived_page_id=en_page.id,
            )
        )
        db_session.add(
            Property(
                politician_id=politician.id,
                type=PropertyType.DEATH_DATE,
                value="2020-01-01",
                value_precision=11,
                archived_page_id=de_page.id,
            )
        )
        db_session.flush()

        query = Politician.query_base()
        query = Politician.filter_by_unevaluated_properties(query, languages=["Q1860"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == politician.id


class TestPoliticianFilterByCountries:
    """Test cases for Politician.filter_by_countries method."""

    def test_filter_by_countries_finds_matching_politicians(self, db_session):
        """Test that country filter finds politicians with matching citizenship."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Language.create_with_entity(db_session, "Q1860", "English")
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        archived_page = ArchivedPage(
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_source_id=ws.id,
            fetch_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(archived_page)

        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.flush()

        db_session.add(
            Property(
                politician_id=politician.id,
                type=PropertyType.CITIZENSHIP,
                entity_id=country.wikidata_id,
                archived_page_id=archived_page.id,
            )
        )
        db_session.flush()

        query = Politician.query_base()
        query = Politician.filter_by_countries(query, ["Q30"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == politician.id

    def test_filter_by_countries_excludes_non_matching(self, db_session):
        """Test that country filter excludes politicians without matching citizenship."""
        Politician.create_with_entity(db_session, "Q123456", "Test Politician")
        db_session.flush()

        query = Politician.query_base()
        query = Politician.filter_by_countries(query, ["Q30"])
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


class TestPoliticianQueryForEnrichment:
    """Test cases for Politician.query_for_enrichment method."""

    def test_query_returns_politicians_with_wikipedia_sources(self, db_session):
        """Test that query finds politicians with Wikipedia links."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Language.create_with_entity(db_session, "Q1860", "English")
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 1
        assert result[0].id == politician.id

    def test_query_excludes_politicians_without_wikipedia_sources(self, db_session):
        """Test that query excludes politicians without Wikipedia links."""
        Politician.create_with_entity(db_session, "Q123456", "Test Politician")
        db_session.flush()

        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0

    def test_query_excludes_soft_deleted_wikidata_entity(self, db_session):
        """Test that query excludes politicians with soft-deleted WikidataEntity."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        Language.create_with_entity(db_session, "Q1860", "English")
        wp = WikipediaProject.create_with_entity(
            db_session, "Q328", "English Wikipedia"
        )
        wp.official_website = "https://en.wikipedia.org"
        db_session.add(
            WikidataRelation(
                parent_entity_id="Q1860",
                child_entity_id="Q328",
                relation_type=RelationType.LANGUAGE_OF_WORK,
                statement_id="lang_rel",
            )
        )
        db_session.flush()

        ws = WikipediaSource(
            politician_id=politician.id,
            url="https://en.wikipedia.org/wiki/Test",
            wikipedia_project_id=wp.wikidata_id,
        )
        db_session.add(ws)
        db_session.flush()

        # Verify it appears first
        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()
        assert len(result) == 1

        # Now soft-delete
        politician.wikidata_entity.soft_delete()
        db_session.flush()

        query = Politician.query_for_enrichment()
        result = db_session.execute(query).scalars().all()

        assert len(result) == 0


class TestPropertyShouldStore:
    """Test cases for the Property.should_store() method."""

    def test_should_store_birth_date_no_existing(self, db_session):
        """Test storing birth date when no existing date exists."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1990-01-01T00:00:00Z",
            value_precision=11,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_position_no_existing(self, db_session):
        """Test storing position when no existing position exists."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        position = Position.create_with_entity(db_session, "Q30185", "Test Position")
        position.embedding = [0.1] * 384
        db_session.flush()

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id=position.wikidata_id,
            qualifiers_json={
                "P580": [
                    {
                        "datavalue": {
                            "value": {"time": "+2020-00-00T00:00:00Z", "precision": 9}
                        }
                    }
                ]
            },
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_birthplace_no_existing(self, db_session):
        """Test storing birthplace when no existing birthplace exists."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        location = Location.create_with_entity(db_session, "Q28513", "Test Location")
        db_session.flush()

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTHPLACE,
            entity_id=location.wikidata_id,
        )

        assert new_property.should_store(db_session) is True

    def test_should_store_citizenship_no_existing(self, db_session):
        """Test storing citizenship when no existing citizenship exists."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        country = Country.create_with_entity(db_session, "Q30", "United States")
        country.iso_code = "US"
        db_session.flush()

        new_property = Property(
            politician_id=politician.id,
            type=PropertyType.CITIZENSHIP,
            entity_id=country.wikidata_id,
        )

        assert new_property.should_store(db_session) is True


class TestPropertyExtractTimeframe:
    """Tests for Property._extract_timeframe_from_qualifiers."""

    def test_extract_both_dates(self):
        """Test extracting both start and end dates."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-15T00:00:00Z", "precision": 11}
                    }
                }
            ],
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-06-30T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is not None
        assert end is not None
        assert start.precision == 11
        assert end.precision == 11

    def test_extract_start_only(self):
        """Test extracting only start date."""
        qualifiers = {
            "P580": [
                {
                    "datavalue": {
                        "value": {"time": "+2020-01-01T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is not None
        assert end is None

    def test_extract_end_only(self):
        """Test extracting only end date."""
        qualifiers = {
            "P582": [
                {
                    "datavalue": {
                        "value": {"time": "+2024-12-31T00:00:00Z", "precision": 11}
                    }
                }
            ],
        }
        start, end = Property._extract_timeframe_from_qualifiers(qualifiers)

        assert start is None
        assert end is not None

    def test_extract_none_qualifiers(self):
        """Test with None qualifiers."""
        start, end = Property._extract_timeframe_from_qualifiers(None)
        assert start is None
        assert end is None

    def test_extract_empty_qualifiers(self):
        """Test with empty qualifiers dict."""
        start, end = Property._extract_timeframe_from_qualifiers({})
        assert start is None
        assert end is None


class TestPropertyCompareTo:
    """Tests for Property._compare_to method."""

    def test_different_types_no_match(self, db_session):
        """Test that different property types don't match."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        prop1 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=politician.id,
            type=PropertyType.DEATH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_birth_date_equal_precision(self, db_session):
        """Test birth dates with equal precision."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        prop1 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL

    def test_birth_date_self_more_precise(self, db_session):
        """Test birth date where self is more precise."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        prop1 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-15T00:00:00Z",
            value_precision=11,
        )
        prop2 = Property(
            politician_id=politician.id,
            type=PropertyType.BIRTH_DATE,
            value="+1950-05-00T00:00:00Z",
            value_precision=10,
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.SELF_MORE_PRECISE

    def test_position_different_entity_no_match(self, db_session):
        """Test positions with different entities don't match."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        prop1 = Property(
            politician_id=politician.id, type=PropertyType.POSITION, entity_id="Q123"
        )
        prop2 = Property(
            politician_id=politician.id, type=PropertyType.POSITION, entity_id="Q456"
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.NO_MATCH

    def test_birthplace_same_entity_equal(self, db_session):
        """Test birthplaces with same entity are equal."""
        politician = Politician.create_with_entity(
            db_session, "Q123456", "Test Politician"
        )
        db_session.flush()

        prop1 = Property(
            politician_id=politician.id, type=PropertyType.BIRTHPLACE, entity_id="Q60"
        )
        prop2 = Property(
            politician_id=politician.id, type=PropertyType.BIRTHPLACE, entity_id="Q60"
        )

        from poliloom.models import PropertyComparisonResult

        assert prop1._compare_to(prop2) == PropertyComparisonResult.EQUAL
