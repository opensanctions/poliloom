"""Tests for the /user API endpoints."""

from sqlalchemy import text

from poliloom.models import (
    Language,
    PreferenceType,
    UserFilterPreference,
    UserSettings,
)
from poliloom.models.wikidata import WikidataEntity


# The mock_auth fixture sets user_id=12345; the endpoint stringifies it.
USER_ID = "12345"


class TestGetUser:
    def test_requires_authentication(self, client):
        response = client.get("/user")
        assert response.status_code == 401

    def test_lazy_creates_row_on_first_get(self, client, db_session, mock_auth):
        response = client.get("/user", headers=mock_auth)
        assert response.status_code == 200
        body = response.json()
        assert body["settings"]["advanced_mode"] is False
        assert body["filters"] == {"language": [], "country": []}

        assert db_session.get(UserSettings, USER_ID) is not None

    def test_seeds_language_filters_from_accept_language(
        self, client, db_session, mock_auth
    ):
        db_session.add_all(
            [
                WikidataEntity(wikidata_id="Q1860", name="English"),
                WikidataEntity(wikidata_id="Q150", name="French"),
                WikidataEntity(wikidata_id="Q188", name="German"),
            ]
        )
        db_session.flush()
        db_session.add_all(
            [
                Language(wikidata_id="Q1860", iso_639_1="en"),
                Language(wikidata_id="Q150", iso_639_1="fr"),
                Language(wikidata_id="Q188", iso_639_1="de"),
            ]
        )
        db_session.commit()

        response = client.get(
            "/user",
            headers={**mock_auth, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7"},
        )
        assert response.status_code == 200
        body = response.json()
        # Priority order preserved: French first, English second.
        assert [e["wikidata_id"] for e in body["filters"]["language"]] == [
            "Q150",
            "Q1860",
        ]

    def test_seed_skips_unknown_codes(self, client, db_session, mock_auth):
        db_session.add(WikidataEntity(wikidata_id="Q1860", name="English"))
        db_session.flush()
        db_session.add(Language(wikidata_id="Q1860", iso_639_1="en"))
        db_session.commit()

        response = client.get(
            "/user",
            headers={**mock_auth, "Accept-Language": "xx,en;q=0.5"},
        )
        assert response.status_code == 200
        assert [e["wikidata_id"] for e in response.json()["filters"]["language"]] == [
            "Q1860"
        ]

    def test_seed_does_not_re_fire_on_second_get(self, client, db_session, mock_auth):
        db_session.add(WikidataEntity(wikidata_id="Q1860", name="English"))
        db_session.flush()
        db_session.add(Language(wikidata_id="Q1860", iso_639_1="en"))
        db_session.commit()

        client.get("/user", headers={**mock_auth, "Accept-Language": "en"})

        # User clears their language filter via PATCH.
        client.patch("/user", headers=mock_auth, json={"filters": {"language": []}})

        # Second GET (with Accept-Language present) must NOT re-seed.
        response = client.get("/user", headers={**mock_auth, "Accept-Language": "en"})
        assert response.json()["filters"]["language"] == []

    def test_returns_populated_shape(self, client, db_session, mock_auth):
        db_session.add_all(
            [
                WikidataEntity(wikidata_id="Q1860", name="English"),
                WikidataEntity(wikidata_id="Q30", name="United States"),
            ]
        )
        db_session.flush()
        db_session.add(
            UserSettings(user_id=USER_ID, advanced_mode=True, stats_unlocked=True)
        )
        db_session.add_all(
            [
                UserFilterPreference(
                    user_id=USER_ID,
                    preference_type=PreferenceType.LANGUAGE,
                    entity_id="Q1860",
                ),
                UserFilterPreference(
                    user_id=USER_ID,
                    preference_type=PreferenceType.COUNTRY,
                    entity_id="Q30",
                ),
            ]
        )
        db_session.commit()

        response = client.get("/user", headers=mock_auth)
        assert response.status_code == 200

        data = response.json()
        assert data["settings"] == {
            "advanced_mode": True,
            "basic_tutorial_completed": False,
            "advanced_tutorial_completed": False,
            "stats_unlocked": True,
        }
        assert data["filters"] == {
            "language": [{"wikidata_id": "Q1860", "name": "English"}],
            "country": [{"wikidata_id": "Q30", "name": "United States"}],
        }


class TestPatchUser:
    def test_creates_row_on_first_patch(self, client, db_session, mock_auth):
        # Empty body still creates the row (auto-detect path can PATCH {} or with empty filters).
        response = client.patch("/user", headers=mock_auth, json={"settings": {}})
        assert response.status_code == 200

        settings = db_session.get(UserSettings, USER_ID)
        assert settings is not None
        assert settings.advanced_mode is False

    def test_partial_settings_leaves_others_default(
        self, client, db_session, mock_auth
    ):
        response = client.patch(
            "/user",
            headers=mock_auth,
            json={"settings": {"basic_tutorial_completed": True}},
        )
        assert response.status_code == 200

        body = response.json()
        assert body["settings"]["basic_tutorial_completed"] is True
        assert body["settings"]["advanced_mode"] is False
        assert body["settings"]["advanced_tutorial_completed"] is False
        assert body["settings"]["stats_unlocked"] is False

    def test_filters_replace_by_type(self, client, db_session, mock_auth):
        db_session.add_all(
            [
                WikidataEntity(wikidata_id="Q1860", name="English"),
                WikidataEntity(wikidata_id="Q150", name="French"),
                WikidataEntity(wikidata_id="Q30", name="United States"),
            ]
        )
        db_session.flush()
        db_session.add(UserSettings(user_id=USER_ID))
        db_session.add_all(
            [
                UserFilterPreference(
                    user_id=USER_ID,
                    preference_type=PreferenceType.LANGUAGE,
                    entity_id="Q1860",
                ),
                UserFilterPreference(
                    user_id=USER_ID,
                    preference_type=PreferenceType.LANGUAGE,
                    entity_id="Q150",
                ),
                UserFilterPreference(
                    user_id=USER_ID,
                    preference_type=PreferenceType.COUNTRY,
                    entity_id="Q30",
                ),
            ]
        )
        db_session.commit()

        response = client.patch(
            "/user",
            headers=mock_auth,
            json={"filters": {"language": ["Q1860"]}},
        )
        assert response.status_code == 200

        body = response.json()
        assert [e["wikidata_id"] for e in body["filters"]["language"]] == ["Q1860"]
        # COUNTRY untouched
        assert [e["wikidata_id"] for e in body["filters"]["country"]] == ["Q30"]

    def test_filters_empty_list_clears_type(self, client, db_session, mock_auth):
        db_session.add(WikidataEntity(wikidata_id="Q1860", name="English"))
        db_session.flush()
        db_session.add(UserSettings(user_id=USER_ID))
        db_session.add(
            UserFilterPreference(
                user_id=USER_ID,
                preference_type=PreferenceType.LANGUAGE,
                entity_id="Q1860",
            )
        )
        db_session.commit()

        response = client.patch(
            "/user",
            headers=mock_auth,
            json={"filters": {"language": []}},
        )
        assert response.status_code == 200
        assert response.json()["filters"]["language"] == []

    def test_unknown_qid_returns_400(self, client, db_session, mock_auth):
        response = client.patch(
            "/user",
            headers=mock_auth,
            json={"filters": {"language": ["Q99999999"]}},
        )
        assert response.status_code == 400

    def test_cascade_delete_of_wikidata_entity(self, client, db_session, mock_auth):
        db_session.add(WikidataEntity(wikidata_id="Q1860", name="English"))
        db_session.flush()
        db_session.add(UserSettings(user_id=USER_ID))
        db_session.add(
            UserFilterPreference(
                user_id=USER_ID,
                preference_type=PreferenceType.LANGUAGE,
                entity_id="Q1860",
            )
        )
        db_session.commit()

        # Hard-delete the wikidata entity (the FK is ON DELETE CASCADE).
        db_session.execute(
            text("DELETE FROM wikidata_entities WHERE wikidata_id = :qid"),
            {"qid": "Q1860"},
        )
        db_session.commit()

        remaining = db_session.execute(
            text("SELECT COUNT(*) FROM user_filter_preferences WHERE user_id = :uid"),
            {"uid": USER_ID},
        ).scalar()
        assert remaining == 0

    def test_dedupes_input_qids(self, client, db_session, mock_auth):
        db_session.add(WikidataEntity(wikidata_id="Q1860", name="English"))
        db_session.commit()

        response = client.patch(
            "/user",
            headers=mock_auth,
            json={"filters": {"language": ["Q1860", "Q1860"]}},
        )
        assert response.status_code == 200

        body = response.json()
        assert [e["wikidata_id"] for e in body["filters"]["language"]] == ["Q1860"]
