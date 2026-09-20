"""Tests for the /politicians endpoints (next/get/search)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from poliloom.api.politicians import get_next_politician
from poliloom.models import (
    Action,
    ActionClaim,
    ActionEvidence,
    ActionKind,
    ActionSkip,
    Politician,
    Statement,
)

from ..conftest import make_terms


def statement_document(
    statement_id, property_id, content=None, data_type="wikibase-item"
):
    """Build a canonical Wikibase REST statement document."""
    value = {"type": "value"}
    if content is not None:
        value["content"] = content
    return {
        "id": statement_id,
        "rank": "normal",
        "property": {"id": property_id, "data_type": data_type},
        "value": value,
    }


def birth_date_statement(statement_id):
    return statement_document(
        statement_id,
        "P569",
        {"time": "+1970-01-15T00:00:00Z", "precision": 11},
        "time",
    )


def birth_date_create_payload(statement_id="Q123456$birth-new"):
    return {"statement": birth_date_statement(statement_id)}


@pytest.fixture
def create_statement(db_session):
    """Factory to create cached Statement rows."""

    def _create(politician, document):
        statement = Statement(politician_id=politician.id, document=document)
        db_session.add(statement)
        db_session.flush()
        return statement

    return _create


@pytest.fixture
def create_action(db_session):
    """Factory to create pending create-actions with optional evidence."""

    def _create(
        politician, payload, *, sources=(), supporting_quotes=None, is_accepted=None
    ):
        action = Action(
            politician_id=politician.id,
            kind=ActionKind.CREATE_STATEMENT,
            payload=payload,
            is_accepted=is_accepted,
        )
        for source in sources:
            action.evidence.append(
                ActionEvidence(source_id=source.id, supporting_quotes=supporting_quotes)
            )
        db_session.add(action)
        db_session.flush()
        return action

    return _create


@pytest.fixture
def politician_with_pending_actions(
    db_session,
    sample_politician,
    sample_position,
    sample_source,
    create_statement,
    create_action,
):
    """Politician with term maps, context statements and pending actions.

    - Politician and position entities carry language-keyed term maps
    - Two context statements (birth date, position)
    - Two pending create actions with evidence on a source without language
      links (unknown-language evidence stays visible to everyone)
    """
    sample_politician.wikidata_entity.labels = {"en": "Test Politician"}
    sample_politician.wikidata_entity.descriptions = {"en": "American test politician"}
    sample_politician.wikidata_entity.aliases = {"en": ["John Doe"]}
    sample_position.wikidata_entity.labels = {"en": "Test Position"}

    create_statement(sample_politician, birth_date_statement("Q123456$birth-1"))
    create_statement(
        sample_politician,
        statement_document("Q123456$position-1", "P39", sample_position.wikidata_id),
    )

    create_action(
        sample_politician,
        birth_date_create_payload(),
        sources=[sample_source],
    )
    create_action(
        sample_politician,
        {
            "statement": statement_document(
                "Q123456$position-new", "P39", sample_position.wikidata_id
            )
        },
        sources=[sample_source],
        supporting_quotes=["Served as Mayor from 2020 to 2024"],
    )
    db_session.flush()
    return sample_politician


class TestGetNextPoliticianEndpoint:
    """Test the GET /politicians/next endpoint."""

    def test_returns_next_politician_qid(
        self, client, mock_auth, politician_with_pending_actions
    ):
        """Test that endpoint returns the next politician with pending actions."""
        response = client.get("/politicians/next?languages=Q1860", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        assert "wikidata_id" in data
        assert "meta" in data
        assert data["wikidata_id"] == "Q123456"

    def test_returns_null_when_no_politicians(self, client, mock_auth):
        """Test that endpoint returns null when no politicians available."""
        response = client.get("/politicians/next?languages=Q1860", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        assert data["wikidata_id"] is None
        assert "meta" in data

    def test_languages_are_required(self, client, mock_auth):
        response = client.get("/politicians/next", headers=mock_auth)
        assert response.status_code == 422

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/politicians/next")
        assert response.status_code in [401, 403]

    def test_meta_has_expected_fields(
        self, client, mock_auth, politician_with_pending_actions
    ):
        """Test that meta includes enrichment status fields."""
        response = client.get("/politicians/next?languages=Q1860", headers=mock_auth)
        data = response.json()

        assert set(data["meta"]) == {"has_enrichable_politicians"}

    def test_country_filter_excludes_non_matching(
        self,
        client,
        mock_auth,
        politician_with_pending_actions,
        sample_germany_country,
    ):
        """The sample politician has no citizenship statement, so a Germany filter excludes it."""
        response = client.get(
            f"/politicians/next?languages=Q1860&countries={sample_germany_country.wikidata_id}",
            headers=mock_auth,
        )
        assert response.status_code == 200
        assert response.json()["wikidata_id"] is None

    def test_country_filter_matches_citizenship_statement(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_country,
        sample_germany_country,
        create_statement,
        create_action,
    ):
        """Country filters match live P27 citizenship statements."""
        create_statement(
            sample_politician,
            statement_document("Q123456$citizen-1", "P27", sample_country.wikidata_id),
        )
        create_action(sample_politician, birth_date_create_payload())

        response = client.get(
            "/politicians/next?languages=Q1860&countries=Q30", headers=mock_auth
        )
        assert response.json()["wikidata_id"] == "Q123456"

        response = client.get(
            "/politicians/next?languages=Q1860&countries=Q183", headers=mock_auth
        )
        assert response.json()["wikidata_id"] is None

    def test_second_request_does_not_reserve_own_live_claim(
        self, client, mock_auth, politician_with_pending_actions
    ):
        first = client.get("/politicians/next?languages=Q1860", headers=mock_auth)
        second = client.get("/politicians/next?languages=Q1860", headers=mock_auth)
        assert first.json()["wikidata_id"] == "Q123456"
        assert second.json()["wikidata_id"] is None

    @pytest.mark.asyncio
    async def test_pool_hit_only_enriches_when_floor_is_empty(self):
        user = Mock(user_id="user")
        with (
            patch("poliloom.api.politicians.claim_next", return_value="Q1"),
            patch("poliloom.api.politicians.count_serveable", return_value=1),
            patch("poliloom.api.politicians.asyncio.create_task") as create_task,
        ):
            response = await get_next_politician(
                languages=["Q1860"], countries=[], db=Mock(), current_user=user
            )
        assert response.wikidata_id == "Q1"
        create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_last_pool_candidate_starts_floor_prefetch(self):
        user = Mock(user_id="user")
        task = Mock()
        with (
            patch("poliloom.api.politicians.claim_next", return_value="Q1"),
            patch("poliloom.api.politicians.count_serveable", return_value=0),
            patch(
                "poliloom.api.politicians.asyncio.create_task", return_value=task
            ) as create_task,
        ):
            response = await get_next_politician(
                languages=["Q1860"], countries=["Q30"], db=Mock(), current_user=user
            )
            create_task.call_args.args[0].close()
        assert response.wikidata_id == "Q1"
        create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_pool_with_candidates_enriches_in_background(self):
        user = Mock(user_id="user")
        with (
            patch("poliloom.api.politicians.claim_next", return_value=None),
            patch(
                "poliloom.api.politicians.has_enrichment_candidate", return_value=True
            ),
            patch("poliloom.api.politicians.asyncio.create_task") as create_task,
        ):
            response = await get_next_politician(
                languages=["Q1860"], countries=["Q30"], db=Mock(), current_user=user
            )
            create_task.call_args.args[0].close()
        assert response.wikidata_id is None
        assert response.meta.has_enrichable_politicians is True
        create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_pool_with_no_candidates_is_all_caught_up(self):
        user = Mock(user_id="user")
        with (
            patch("poliloom.api.politicians.claim_next", return_value=None),
            patch(
                "poliloom.api.politicians.has_enrichment_candidate", return_value=False
            ),
            patch("poliloom.api.politicians.asyncio.create_task") as create_task,
        ):
            response = await get_next_politician(
                languages=["Q1860"], countries=[], db=Mock(), current_user=user
            )
        assert response.wikidata_id is None
        assert response.meta.has_enrichable_politicians is False
        create_task.assert_not_called()


class TestGetPoliticianByQidEndpoint:
    """Test the GET /politicians/{qid} endpoint."""

    def test_returns_politician_with_terms_statements_and_actions(
        self, client, mock_auth, politician_with_pending_actions
    ):
        """Test fetching a politician by QID."""
        response = client.get("/politicians/Q123456?languages=Q1860", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        assert data["wikidata_id"] == "Q123456"
        assert data["terms"] == {
            "labels": {"en": "Test Politician"},
            "descriptions": {"en": "American test politician"},
            "aliases": {"en": ["John Doe"]},
        }
        assert "name" not in data
        assert "properties" not in data
        assert len(data["statements"]) == 2
        assert len(data["actions"]) == 2

    def test_returns_404_for_unknown_qid(self, client, mock_auth):
        """Test that 404 is returned for unknown QID."""
        response = client.get(
            "/politicians/Q999999999?languages=Q1860", headers=mock_auth
        )
        assert response.status_code == 404

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/politicians/Q123456")
        assert response.status_code in [401, 403]


class TestGetPoliticianStatements:
    """Statement (review context) shape in GET /politicians/{qid}."""

    def test_statements_include_all_non_deleted(
        self, client, mock_auth, politician_with_pending_actions
    ):
        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        statements = {s["document"]["id"]: s for s in data["statements"]}
        assert set(statements) == {"Q123456$birth-1", "Q123456$position-1"}
        assert set(statements["Q123456$birth-1"]) == {"id", "document", "entity_terms"}

    def test_statement_entity_terms_joined_via_entity_id(
        self, client, mock_auth, politician_with_pending_actions, sample_position
    ):
        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        statements = {s["document"]["id"]: s for s in data["statements"]}

        # Date-valued statements have no value entity
        assert statements["Q123456$birth-1"]["entity_terms"] is None
        # Entity-valued statements join the value entity's term maps
        assert statements["Q123456$position-1"]["entity_terms"]["labels"] == {
            "en": "Test Position"
        }

    def test_soft_deleted_statements_excluded(
        self, client, mock_auth, db_session, politician_with_pending_actions
    ):
        deleted = Statement(
            politician_id=politician_with_pending_actions.id,
            document=birth_date_statement("Q123456$death-1"),
        )
        deleted.deleted_at = datetime.now(UTC)
        db_session.add(deleted)
        db_session.flush()

        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        assert "Q123456$death-1" not in {
            s["document"]["id"] for s in data["statements"]
        }

    def test_excludes_politicians_with_soft_deleted_wikidata_entity(
        self, client, mock_auth, db_session, sample_politician
    ):
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        response = client.get("/politicians/Q123456?languages=Q1860", headers=mock_auth)
        assert response.status_code == 404


class TestGetPoliticianActions:
    """Action (review queue) shape and visibility in GET /politicians/{qid}."""

    def test_action_response_shape(
        self, client, mock_auth, politician_with_pending_actions, sample_source
    ):
        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        actions = {a["payload"]["statement"]["id"]: a for a in data["actions"]}

        birth = actions["Q123456$birth-new"]
        assert set(birth) == {
            "id",
            "kind",
            "statement_id",
            "payload",
            "entity_terms",
            "evidence",
            "is_accepted",
            "applied_at",
            "error",
        }
        assert birth["kind"] == "CREATE_STATEMENT"
        assert birth["statement_id"] is None
        assert birth["is_accepted"] is None
        assert birth["applied_at"] is None
        assert birth["error"] is None
        assert birth["payload"]["statement"]["property"]["id"] == "P569"
        # Date-valued create actions have no value entity
        assert birth["entity_terms"] is None
        assert len(birth["evidence"]) == 1
        assert set(birth["evidence"][0]) == {"id", "source", "supporting_quotes"}
        assert birth["evidence"][0]["source"]["id"] == str(sample_source.id)
        assert birth["evidence"][0]["supporting_quotes"] is None

    def test_action_entity_terms_joined_via_generated_entity_id(
        self, client, mock_auth, politician_with_pending_actions
    ):
        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        actions = {a["payload"]["statement"]["id"]: a for a in data["actions"]}

        position = actions["Q123456$position-new"]
        assert position["entity_terms"]["labels"] == {"en": "Test Position"}
        assert position["evidence"][0]["supporting_quotes"] == [
            "Served as Mayor from 2020 to 2024"
        ]

    def test_decided_actions_excluded(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_source,
        create_action,
    ):
        accepted = create_action(
            sample_politician,
            birth_date_create_payload("Q123456$accepted"),
            sources=[sample_source],
            is_accepted=True,
        )
        discarded = create_action(
            sample_politician,
            birth_date_create_payload("Q123456$discarded"),
            sources=[sample_source],
            is_accepted=False,
        )
        pending = create_action(
            sample_politician,
            birth_date_create_payload("Q123456$pending"),
            sources=[sample_source],
        )

        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        action_ids = {a["id"] for a in data["actions"]}
        assert str(pending.id) in action_ids
        assert str(accepted.id) not in action_ids
        assert str(discarded.id) not in action_ids

    def test_skipped_actions_hidden_only_for_the_skipping_user(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_source,
        create_action,
    ):
        skipped = create_action(
            sample_politician,
            birth_date_create_payload(),
            sources=[sample_source],
        )
        db_session.add(ActionSkip(user_id="12345", action_id=skipped.id))
        db_session.flush()

        response = client.get("/politicians/Q123456?languages=Q1860", headers=mock_auth)
        assert str(skipped.id) not in {a["id"] for a in response.json()["actions"]}

        from poliloom.api import app
        from poliloom.api.auth import User, get_current_user

        async def other_user():
            return User(user_id=67890, jwt_token="other-token")

        app.dependency_overrides[get_current_user] = other_user
        try:
            response = client.get(
                "/politicians/Q123456?languages=Q1860", headers=mock_auth
            )
            assert str(skipped.id) in {a["id"] for a in response.json()["actions"]}
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_language_visibility_filters_actions_by_evidence(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_language,
        sample_german_language,
        create_source,
        create_action,
    ):
        english_page = create_source(
            url="https://en.wikipedia.org/test",
            url_hash="en123",
            languages=[sample_language],
        )
        german_page = create_source(
            url="https://de.wikipedia.org/test",
            url_hash="de123",
            languages=[sample_german_language],
        )
        create_action(
            sample_politician,
            birth_date_create_payload("Q123456$en-new"),
            sources=[english_page],
        )
        create_action(
            sample_politician,
            birth_date_create_payload("Q123456$de-new"),
            sources=[german_page],
        )
        create_action(sample_politician, birth_date_create_payload("Q123456$any-new"))

        english = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        ids = {a["payload"]["statement"]["id"] for a in english["actions"]}
        assert "Q123456$en-new" in ids
        assert "Q123456$de-new" not in ids
        # Evidenceless actions are visible regardless of language
        assert "Q123456$any-new" in ids

        german = client.get(
            "/politicians/Q123456?languages=Q188", headers=mock_auth
        ).json()
        ids = {a["payload"]["statement"]["id"] for a in german["actions"]}
        assert "Q123456$de-new" in ids
        assert "Q123456$en-new" not in ids
        assert "Q123456$any-new" in ids

    def test_claim_visibility_filters_actions(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_source,
        create_action,
    ):
        from poliloom.review_queue import get_claim_ttl

        foreign_live = create_action(
            sample_politician, birth_date_create_payload("Q123456$foreign")
        )
        own = create_action(sample_politician, birth_date_create_payload("Q123456$own"))
        foreign_expired = create_action(
            sample_politician, birth_date_create_payload("Q123456$expired")
        )
        db_session.add(ActionClaim(user_id="other", action_id=foreign_live.id))
        db_session.add(ActionClaim(user_id="12345", action_id=own.id))
        db_session.add(
            ActionClaim(
                user_id="other",
                action_id=foreign_expired.id,
                claimed_at=datetime.now(UTC) - get_claim_ttl() - timedelta(seconds=1),
            )
        )
        db_session.flush()

        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        ids = {a["payload"]["statement"]["id"] for a in data["actions"]}
        # Live foreign claims hide actions; own claims and expired claims don't
        assert "Q123456$foreign" not in ids
        assert {"Q123456$own", "Q123456$expired"} <= ids

    def test_get_claims_all_visible_pending_actions(
        self, client, mock_auth, db_session, politician_with_pending_actions
    ):
        response = client.get("/politicians/Q123456?languages=Q1860", headers=mock_auth)
        assert response.status_code == 200

        claimed_ids = {
            claim.action_id
            for claim in db_session.query(ActionClaim).filter_by(user_id="12345")
        }
        action_ids = {action.id for action in politician_with_pending_actions.actions}
        assert claimed_ids == action_ids


class TestGetPoliticianSources:
    """Source filtering behavior retained by GET /politicians/{qid}."""

    def test_sources_filtered_by_language(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_language,
        create_source,
    ):
        english = create_source(
            url="https://en.wikipedia.org/wiki/Test_Page",
            url_hash="en-page",
            languages=[sample_language],
        )
        languageless = create_source(url="https://example.com/test", url_hash="test123")
        sample_politician.sources.extend([english, languageless])
        db_session.flush()

        data = client.get(
            "/politicians/Q123456?languages=Q1860", headers=mock_auth
        ).json()
        source_ids = {s["id"] for s in data["sources"]}
        assert source_ids == {str(english.id), str(languageless.id)}

        data = client.get(
            "/politicians/Q123456?languages=Q188", headers=mock_auth
        ).json()
        source_ids = {s["id"] for s in data["sources"]}
        assert source_ids == {str(languageless.id)}


class TestSearchPoliticiansEndpoint:
    """Test the GET /politicians/search endpoint."""

    def test_search_returns_terms_statements_and_actions(
        self,
        client,
        mock_auth,
        db_session,
        sample_source,
        create_statement,
        create_action,
    ):
        """Test searching politicians by label."""
        politician = Politician.create_with_entity(
            db_session,
            "Q999888",
            make_terms("Unique Search Test Name"),
        )
        db_session.add(politician)
        db_session.flush()

        create_statement(politician, birth_date_statement("Q999888$birth-1"))
        pending = create_action(
            politician,
            birth_date_create_payload("Q999888$birth-new"),
            sources=[sample_source],
        )
        decided = create_action(
            politician,
            birth_date_create_payload("Q999888$birth-decided"),
            is_accepted=True,
        )
        db_session.flush()

        response = client.get(
            "/politicians/search?q=Unique%20Search%20Test", headers=mock_auth
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        entry = next(p for p in data if p["wikidata_id"] == "Q999888")
        assert entry["terms"]["labels"] == {"en": "Unique Search Test Name"}
        assert [s["document"]["id"] for s in entry["statements"]] == ["Q999888$birth-1"]
        action_ids = {a["id"] for a in entry["actions"]}
        assert str(pending.id) in action_ids
        assert str(decided.id) not in action_ids
        evidence = next(a for a in entry["actions"] if a["id"] == str(pending.id))[
            "evidence"
        ]
        assert evidence[0]["source"]["id"] == str(sample_source.id)

    def test_search_requires_query(self, client, mock_auth):
        """Test that search endpoint requires a query parameter."""
        response = client.get("/politicians/search", headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_search_requires_authentication(self, client):
        """Test that search endpoint requires authentication."""
        response = client.get("/politicians/search?q=test")
        assert response.status_code in [401, 403]
