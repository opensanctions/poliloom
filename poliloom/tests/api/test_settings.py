"""Tests for the /settings API endpoints."""

from poliloom.models import UserSettings

# The mock_auth fixture sets user_id=12345; the endpoint stringifies it.
USER_ID = "12345"


class TestGetSettings:
    def test_requires_authentication(self, client):
        response = client.get("/settings")
        assert response.status_code == 401

    def test_returns_defaults_without_creating_row(self, client, db_session, mock_auth):
        response = client.get("/settings", headers=mock_auth)
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "advanced_mode": False,
            "basic_tutorial_completed": False,
            "advanced_tutorial_completed": False,
            "stats_unlocked": False,
        }
        assert db_session.get(UserSettings, USER_ID) is None

    def test_returns_persisted_values(self, client, db_session, mock_auth):
        db_session.add(
            UserSettings(user_id=USER_ID, advanced_mode=True, stats_unlocked=True)
        )
        db_session.commit()

        response = client.get("/settings", headers=mock_auth)
        assert response.status_code == 200
        assert response.json() == {
            "advanced_mode": True,
            "basic_tutorial_completed": False,
            "advanced_tutorial_completed": False,
            "stats_unlocked": True,
        }


class TestPatchSettings:
    def test_creates_row_on_first_patch(self, client, db_session, mock_auth):
        response = client.patch("/settings", headers=mock_auth, json={})
        assert response.status_code == 200

        settings = db_session.get(UserSettings, USER_ID)
        assert settings is not None
        assert settings.advanced_mode is False

    def test_partial_update_leaves_others_default(self, client, db_session, mock_auth):
        response = client.patch(
            "/settings",
            headers=mock_auth,
            json={"basic_tutorial_completed": True},
        )
        assert response.status_code == 200

        body = response.json()
        assert body["basic_tutorial_completed"] is True
        assert body["advanced_mode"] is False
        assert body["advanced_tutorial_completed"] is False
        assert body["stats_unlocked"] is False

    def test_subsequent_patch_preserves_existing_fields(
        self, client, db_session, mock_auth
    ):
        client.patch(
            "/settings",
            headers=mock_auth,
            json={"advanced_mode": True},
        )
        response = client.patch(
            "/settings",
            headers=mock_auth,
            json={"basic_tutorial_completed": True},
        )
        assert response.status_code == 200

        body = response.json()
        assert body["advanced_mode"] is True
        assert body["basic_tutorial_completed"] is True
