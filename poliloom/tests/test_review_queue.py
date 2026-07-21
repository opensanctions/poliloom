"""Tests for the unevaluated politician review queue."""

from datetime import datetime, timezone

from poliloom.models import Property, PropertyType
from poliloom.review_queue import ReviewQueueResult, get_random_unevaluated


class TestReviewQueue:
    def test_returns_candidate_and_total_for_unevaluated_property(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        create_birth_date(sample_politician, source=sample_source)
        db_session.flush()

        result = get_random_unevaluated(db_session)

        assert result == ReviewQueueResult("Q123456", 1)

    def test_excludes_evaluated_and_deleted_properties(
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
                deleted_at=datetime.now(timezone.utc),
            )
        )
        db_session.flush()

        assert get_random_unevaluated(db_session) == ReviewQueueResult(None, 0)

    def test_excludes_soft_deleted_wikidata_entities(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        create_birth_date(sample_politician, source=sample_source)
        sample_politician.wikidata_entity.soft_delete()
        db_session.flush()

        assert get_random_unevaluated(db_session) == ReviewQueueResult(None, 0)

    def test_language_filter_uses_property_references(
        self,
        db_session,
        sample_politician,
        sample_language,
        create_source,
        create_birth_date,
    ):
        source = create_source(
            url="https://en.example.com/test",
            url_hash="en123",
            languages=[sample_language],
        )
        create_birth_date(sample_politician, source=source)
        db_session.flush()

        assert get_random_unevaluated(
            db_session, languages=["Q1860"]
        ) == ReviewQueueResult("Q123456", 1)
        assert get_random_unevaluated(
            db_session, languages=["Q188"]
        ) == ReviewQueueResult(None, 0)

    def test_country_filter_uses_active_citizenship(
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

        assert get_random_unevaluated(
            db_session, countries=["Q30"]
        ) == ReviewQueueResult("Q123456", 1)
        assert get_random_unevaluated(
            db_session, countries=["Q183"]
        ) == ReviewQueueResult(None, 0)

    def test_exclusions_only_affect_candidate_selection(
        self, db_session, sample_politician, sample_source, create_birth_date
    ):
        create_birth_date(sample_politician, source=sample_source)
        db_session.flush()

        assert get_random_unevaluated(
            db_session, exclude_ids=[sample_politician.wikidata_id]
        ) == ReviewQueueResult(None, 1)
