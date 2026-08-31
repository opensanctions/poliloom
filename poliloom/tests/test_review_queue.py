"""Tests for the claim-based politician review queue."""

from datetime import UTC, datetime, timedelta

from poliloom.models import (
    Politician,
    Property,
    PropertyClaim,
    PropertySkip,
    PropertyType,
)
from poliloom.review_queue import claim_next, count_serveable


class TestReviewQueue:
    def test_claims_basic_serve(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        prop = create_birth_date(sample_politician, source=sample_source)
        db_session.flush()

        assert claim_next(db_session, "user-a", ["Q1860"]) == "Q123456"
        claim = db_session.query(PropertyClaim).filter_by(property_id=prop.id).one()
        assert claim.user_id == "user-a"
        assert claim_next(db_session, "user-a", ["Q1860"]) is None

    def test_excludes_evaluated_deleted_and_soft_deleted_entities(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        create_birth_date(
            sample_politician,
            source=sample_source,
            statement_id="Q123456$12345678-1234-1234-1234-123456789012",
        )
        db_session.add(
            Property(
                politician_id=sample_politician.id,
                type=PropertyType.BIRTH_DATE,
                value="1980-01-01",
                value_precision=11,
                deleted_at=datetime.now(UTC),
            )
        )
        db_session.flush()
        assert claim_next(db_session, "user", ["Q1860"]) is None

        create_birth_date(sample_politician, source=sample_source)
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()
        assert claim_next(db_session, "user", ["Q1860"]) is None

    def test_language_filter_and_referenceless_visibility(
        self,
        db_session,
        sample_politician,
        sample_language,
        create_source,
        create_birth_date,
    ):
        source = create_source(
            url="https://en.example/test",
            url_hash="english",
            languages=[sample_language],
        )
        create_birth_date(sample_politician, source=source)
        db_session.flush()
        assert count_serveable(db_session, ["Q188"]) == 0
        assert count_serveable(db_session, ["Q1860"]) == 1

        create_birth_date(sample_politician)
        db_session.flush()
        assert count_serveable(db_session, ["Q188"]) == 1

    def test_unknown_source_language_is_visible_to_everyone(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        create_birth_date(sample_politician, source=sample_source)
        db_session.flush()
        assert count_serveable(db_session, ["Q188"]) == 1

    def test_country_filter(
        self,
        db_session,
        sample_politician,
        sample_country,
        sample_source,
        create_birth_date,
        create_citizenship,
    ):
        create_citizenship(sample_politician, sample_country, sample_source)
        create_birth_date(sample_politician, source=sample_source)
        db_session.flush()
        assert count_serveable(db_session, ["Q1860"], ["Q30"]) == 1
        assert count_serveable(db_session, ["Q1860"], ["Q183"]) == 0

    def test_skips_are_per_user_but_count_is_user_agnostic(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        prop = create_birth_date(sample_politician, source=sample_source)
        db_session.add(PropertySkip(user_id="user-a", property_id=prop.id))
        db_session.flush()
        assert count_serveable(db_session, ["Q1860"]) == 1
        assert claim_next(db_session, "user-a", ["Q1860"]) is None
        assert claim_next(db_session, "user-b", ["Q1860"]) == "Q123456"

    def test_disjoint_languages_can_claim_same_politician(
        self,
        db_session,
        sample_politician,
        sample_language,
        sample_german_language,
        create_source,
        create_birth_date,
    ):
        english = create_source(
            url="https://en.example/claim",
            url_hash="claim-en",
            languages=[sample_language],
        )
        german = create_source(
            url="https://de.example/claim",
            url_hash="claim-de",
            languages=[sample_german_language],
        )
        create_birth_date(sample_politician, source=english)
        create_birth_date(sample_politician, source=german)
        db_session.flush()

        assert claim_next(db_session, "user-a", ["Q1860"]) == "Q123456"
        assert claim_next(db_session, "user-b", ["Q188"]) == "Q123456"
        assert claim_next(db_session, "user-c", ["Q1860"]) is None

    def test_housekeeping_keeps_two_most_recent_politicians(
        self, db_session, sample_source, create_birth_date
    ):
        politicians = []
        for number in (7001, 7002, 7003):
            politician = Politician.create_with_entity(
                db_session, f"Q{number}", f"Politician {number}"
            )
            db_session.add(politician)
            db_session.flush()
            create_birth_date(politician, source=sample_source)
            politicians.append(politician)
        db_session.flush()

        served = []
        for index in range(3):
            served.append(claim_next(db_session, "user-a", ["Q1860"]))
            if index < 2:
                claim = (
                    db_session.query(PropertyClaim)
                    .join(Property, PropertyClaim.property_id == Property.id)
                    .join(Politician, Property.politician_id == Politician.id)
                    .filter(Politician.wikidata_id == served[-1])
                    .one()
                )
                claim.claimed_at = datetime.now(UTC) - timedelta(minutes=3 - index)
                db_session.commit()
        assert set(served) == {politician.wikidata_id for politician in politicians}

        claimed_politicians = {
            politician_id
            for (politician_id,) in db_session.query(Property.politician_id)
            .join(PropertyClaim, PropertyClaim.property_id == Property.id)
            .filter(PropertyClaim.user_id == "user-a")
            .all()
        }
        ids_by_qid = {
            politician.wikidata_id: politician.id for politician in politicians
        }
        assert claimed_politicians == {ids_by_qid[qid] for qid in served[-2:]}

    def test_other_and_own_live_claims_exclude_but_expired_claim_does_not(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        prop = create_birth_date(sample_politician, source=sample_source)
        db_session.add(PropertyClaim(user_id="user-a", property_id=prop.id))
        db_session.commit()
        assert claim_next(db_session, "user-b", ["Q1860"]) is None
        assert claim_next(db_session, "user-a", ["Q1860"]) is None

        claim = db_session.query(PropertyClaim).filter_by(property_id=prop.id).one()
        claim.claimed_at = datetime.now(UTC) - timedelta(hours=1)
        db_session.commit()
        assert claim_next(db_session, "user-b", ["Q1860"]) == "Q123456"
        assert (
            db_session.query(PropertyClaim).filter_by(property_id=prop.id).one().user_id
            == "user-b"
        )
