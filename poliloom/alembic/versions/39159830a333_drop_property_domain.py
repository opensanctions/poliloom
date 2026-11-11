"""copy evaluated property decisions into statements/actions, then drop old domain

One-way production data migration. Live pushed properties become cached REST
statement documents with linked applied create Actions (id and timestamps
preserved). Pushed properties whose statements later vanished retain unlinked
applied creates, and rejected proposals become discarded creates.
Unevaluated properties, incomplete accepts, statement rejections, and pending
reference edits are omitted; the next dump import rebuilds the rest of the
statement cache. A count report is logged and invariants asserted before the
old Property/Evaluation tables, flat label storage, and denormalized
name/description columns are dropped. Terms live on wikidata_entities and
review data on actions/statements.

Revision ID: 39159830a333
Revises: 08cfa4a3f74f
Create Date: 2026-09-21 12:00:00.000000

"""

import json
import logging
import uuid
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from poliloom.models import PropertyType, Source
from poliloom.payloads import create_body
from poliloom.wikidata.rest import action_api_statement_to_rest

# revision identifiers, used by Alembic.
revision: str = "39159830a333"
down_revision: str | None = "08cfa4a3f74f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Child of the alembic logger so the count report is visible at INFO.
logger = logging.getLogger(f"alembic.versions.{revision}")

PROPERTY_TYPE_ENUM = postgresql.ENUM(
    "BIRTH_DATE",
    "DEATH_DATE",
    "BIRTHPLACE",
    "POSITION",
    "CITIZENSHIP",
    name="propertytype",
    create_type=False,
)

_DATE_TYPES = frozenset(("BIRTH_DATE", "DEATH_DATE"))
_ENTITY_SAMPLE_TYPES = ("BIRTHPLACE", "CITIZENSHIP")
_CALENDAR_MODEL = "http://www.wikidata.org/entity/Q1985727"
_BATCH_SIZE = 10_000

_PROPERTY_QUERY = sa.text("""
    SELECT id, politician_id, type, value, value_precision, entity_id,
           statement_id, qualifiers_json, references_json,
           created_at, updated_at, deleted_at
    FROM properties p
    WHERE EXISTS (
        SELECT 1 FROM evaluations e WHERE e.property_id = p.id
    )
""")

_STATEMENT_INSERT = sa.text("""
    INSERT INTO statements (id, politician_id, document, created_at, updated_at)
    VALUES (:id, :politician_id, CAST(:document AS jsonb), :created_at, :updated_at)
""")

_ACTION_INSERT = sa.text("""
    INSERT INTO actions (id, politician_id, kind, statement_id, payload,
                         is_accepted, decided_by_user_id, decided_at, applied_at,
                         created_at, updated_at)
    VALUES (:id, :politician_id, :kind, :statement_id, CAST(:payload AS jsonb),
            :is_accepted, :decided_by_user_id, :decided_at, :applied_at,
            :created_at, :updated_at)
""")

_EVIDENCE_INSERT = sa.text("""
    INSERT INTO action_evidence (id, action_id, source_id, supporting_quotes,
                                 created_at, updated_at)
    VALUES (:id, :action_id, :source_id, :supporting_quotes,
            :created_at, :updated_at)
""")


def _qualifier_snak(property_id: str, snak: dict) -> dict:
    """Rebuild a stored qualifier snak in full Action API shape.

    The old push flow stored WikidataDate.to_wikidata_qualifier() snaks,
    which omit ``property`` (the map key holds it), and a few early
    proposals store bare ``{"datavalue": {"value": {time, precision}}}``
    time snaks; both legacy shapes are reconstructed. Anything else fails
    in the converter.
    """
    if "snaktype" not in snak:
        value = snak["datavalue"]["value"]
        return {
            "property": property_id,
            "snaktype": "value",
            "datatype": "time",
            "datavalue": {
                "type": "time",
                "value": {
                    "time": value["time"],
                    "precision": value["precision"],
                    "timezone": 0,
                    "before": 0,
                    "after": 0,
                    "calendarmodel": _CALENDAR_MODEL,
                },
            },
        }
    if "property" not in snak:
        return {**snak, "property": property_id}
    return snak


def _claim(row) -> dict:
    """Synthesize the Action API claim a property row was derived from.

    Statement-backed rows mirror the dump import that created them;
    proposals mirror what the push flow posted to Wikidata.
    """
    property_id = PropertyType[row["type"]].value
    if row["type"] in _DATE_TYPES:
        datatype = "time"
        datavalue = {
            "type": "time",
            "value": {
                "time": row["value"],
                "precision": row["value_precision"],
                "timezone": 0,
                "before": 0,
                "after": 0,
                "calendarmodel": _CALENDAR_MODEL,
            },
        }
    else:
        datatype = "wikibase-item"
        datavalue = {
            "type": "wikibase-entityid",
            "value": {
                "id": row["entity_id"],
                "entity-type": "item",
                "numeric-id": int(row["entity_id"][1:]),
            },
        }
    claim = {
        "id": row["statement_id"],
        # Stopgap: the next dump import upserts by wikidata_statement_id and
        # replaces the document, restoring the real rank.
        "rank": "normal",
        "mainsnak": {
            "snaktype": "value",
            "property": property_id,
            "datatype": datatype,
            "datavalue": datavalue,
        },
    }
    # SQL NULL and JSON null are both absent; content is object/array.
    if isinstance(row["qualifiers_json"], dict):
        claim["qualifiers"] = {
            pid: [_qualifier_snak(pid, snak) for snak in snaks]
            for pid, snaks in row["qualifiers_json"].items()
        }
    if isinstance(row["references_json"], list):
        claim["references"] = row["references_json"]
    return claim


def _create_payload(row, references: list[dict]) -> dict:
    """Build the create Action payload for an evaluated property.

    Value and qualifiers are converted through the same claim-to-REST
    converter as statement documents; references are rebuilt from the
    property's evidence sources.
    """
    document = action_api_statement_to_rest(_claim(row))
    statement = {
        "property": {"id": document["property"]["id"]},
        "value": document["value"],
        "rank": "normal",
    }
    if "qualifiers" in document:
        # Create bodies carry bare property ids (planner candidate shape);
        # data_type is document-only.
        statement["qualifiers"] = [
            {
                "property": {"id": qualifier["property"]["id"]},
                "value": qualifier["value"],
            }
            for qualifier in document["qualifiers"]
        ]
    if references:
        statement["references"] = references
    return create_body(statement)


def _require(condition: bool, message: str) -> None:
    """Assert a data-phase invariant."""
    if not condition:
        raise AssertionError(message)


def _copy_property_data(conn) -> None:
    """Copy evaluated old-domain rows into the new domain.

    Classification is per property, anchored on the latest evaluation
    (max created_at). Every class is counted so the report accounts for all
    old rows, and invariants are asserted before upgrade() drops the tables.
    """
    totals = {
        name: conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
        for name, table in (
            ("properties", "properties"),
            ("evaluations", "evaluations"),
            ("references", "property_references"),
        )
    }
    totals["evaluated_properties"] = conn.execute(
        sa.text("SELECT count(DISTINCT property_id) FROM evaluations")
    ).scalar_one()

    sources = {}
    for source in conn.execute(
        sa.text("""
            SELECT id, url, permanent_url, wikipedia_project_id, fetch_timestamp
            FROM sources
        """)
    ).mappings():
        sources[source["id"]] = SimpleNamespace(
            url=source["url"],
            permanent_url=source["permanent_url"],
            wikipedia_project_id=source["wikipedia_project_id"],
            fetch_timestamp=source["fetch_timestamp"],
        )

    references_by_property = {}
    for reference in conn.execute(
        sa.text("""
            SELECT property_id, source_id, supporting_quotes, created_at,
                   updated_at
            FROM property_references pr
            WHERE EXISTS (
                SELECT 1 FROM evaluations e WHERE e.property_id = pr.property_id
            )
            ORDER BY property_id, created_at
        """)
    ).mappings():
        references_by_property.setdefault(reference["property_id"], []).append(
            reference
        )

    # Ordered by created_at and id, so the last element is the latest evaluation.
    evaluations_by_property = {}
    for evaluation in conn.execute(
        sa.text("""
            SELECT id, property_id, user_id, is_accepted, created_at
            FROM evaluations
            ORDER BY property_id, created_at, id
        """)
    ).mappings():
        evaluations_by_property.setdefault(evaluation["property_id"], []).append(
            evaluation
        )

    counts = {
        "statements": 0,
        "creates_applied_linked": 0,
        "creates_applied_unlinked": 0,
        "creates_discarded": 0,
        "evidence": 0,
        "dropped_props_unevaluated": totals["properties"]
        - totals["evaluated_properties"],
        "dropped_props_incomplete_accepts": 0,
        "dropped_props_statement_rejections": 0,
        "dropped_props_pushed_then_rejected": 0,
        "dropped_refs_unevaluated": conn.execute(
            sa.text("""
                SELECT count(*) FROM property_references pr
                WHERE NOT EXISTS (
                    SELECT 1 FROM evaluations e WHERE e.property_id = pr.property_id
                )
            """)
        ).scalar_one(),
        "dropped_refs_evaluated": 0,
        "eval_mapped": 0,
        "eval_superseded": 0,
        "eval_dropped": 0,
    }
    statement_rows = []
    actions = []
    evidence = []
    samples = {}

    def queue_evidence(action_id, refs) -> None:
        for ref in refs:
            evidence.append(
                {
                    "id": uuid.uuid4(),
                    "action_id": action_id,
                    "source_id": ref["source_id"],
                    "supporting_quotes": ref["supporting_quotes"],
                    "created_at": ref["created_at"],
                    "updated_at": ref["updated_at"],
                }
            )
            counts["evidence"] += 1

    def latest_accepted(evals):
        return max(
            (e for e in evals if e["is_accepted"]),
            key=lambda e: (e["created_at"], e["id"]),
        )

    def queue_create(row, refs, *, is_accepted, decided, statement_id) -> None:
        references = [
            {"parts": Source.create_references_json(sources[ref["source_id"]])}
            for ref in refs
        ]
        action = {
            "id": uuid.uuid4(),
            "politician_id": row["politician_id"],
            "kind": "CREATE_STATEMENT",
            "statement_id": statement_id,
            "payload": json.dumps(_create_payload(row, references)),
            "is_accepted": is_accepted,
            "decided_by_user_id": decided["user_id"],
            "decided_at": decided["created_at"],
            "applied_at": decided["created_at"] if is_accepted else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        actions.append(action)
        queue_evidence(action["id"], refs)

    def drop_evaluated(row, refs, evals, bucket) -> None:
        counts[bucket] += 1
        counts["dropped_refs_evaluated"] += len(refs)
        counts["eval_dropped"] += len(evals)

    def capture_sample(row, claim) -> None:
        if "date" not in samples and row["type"] in _DATE_TYPES:
            samples["date"] = (row, claim)
        elif (
            "position" not in samples
            and row["type"] == "POSITION"
            and isinstance(row["qualifiers_json"], dict)
            and row["qualifiers_json"]
        ):
            samples["position"] = (row, claim)
        elif "entity" not in samples and row["type"] in _ENTITY_SAMPLE_TYPES:
            samples["entity"] = (row, claim)

    streaming = conn.execution_options(stream_results=True)
    result = streaming.execute(_PROPERTY_QUERY)
    writing = streaming.execution_options(stream_results=False)

    for partition in result.mappings().partitions(_BATCH_SIZE):
        for row in partition:
            evals = evaluations_by_property[row["id"]]
            refs = references_by_property.get(row["id"], ())
            latest_eval = evals[-1]
            has_accepted_eval = any(e["is_accepted"] for e in evals)

            if row["statement_id"] is not None:
                if not has_accepted_eval:
                    # Rejecting an existing statement deprecates it upstream.
                    # Both completed and failed deprecations are outside the
                    # retained create-action history.
                    drop_evaluated(
                        row, refs, evals, "dropped_props_statement_rejections"
                    )
                    continue
                if not latest_eval["is_accepted"]:
                    # A pushed statement was subsequently rejected; do not
                    # resurrect either its create or its statement.
                    drop_evaluated(
                        row, refs, evals, "dropped_props_pushed_then_rejected"
                    )
                    continue

                statement_id = None
                if row["deleted_at"] is None:
                    claim = _claim(row)
                    document = action_api_statement_to_rest(claim)
                    statement_rows.append(
                        {
                            "id": row["id"],
                            "politician_id": row["politician_id"],
                            "document": json.dumps(document),
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
                    )
                    statement_id = row["id"]
                    counts["statements"] += 1
                    counts["creates_applied_linked"] += 1
                    capture_sample(row, claim)
                else:
                    # The statement vanished after the push. The create stays
                    # as applied history, legitimately without a statement.
                    counts["creates_applied_unlinked"] += 1

                queue_create(
                    row,
                    refs,
                    is_accepted=True,
                    decided=latest_accepted(evals),
                    statement_id=statement_id,
                )
                counts["eval_mapped"] += 1
                counts["eval_superseded"] += len(evals) - 1
            elif latest_eval["is_accepted"]:
                # An accepted proposal without a statement never completed its
                # Wikidata push. It is intentionally part of the reset.
                drop_evaluated(row, refs, evals, "dropped_props_incomplete_accepts")
            else:
                # Rejected proposals never existed on Wikidata. Preserve the
                # final decision as a discarded create without a statement.
                queue_create(
                    row,
                    refs,
                    is_accepted=False,
                    decided=latest_eval,
                    statement_id=None,
                )
                counts["creates_discarded"] += 1
                counts["eval_mapped"] += 1
                counts["eval_superseded"] += len(evals) - 1

    # Migrated statements are not import-verified, so the access tracker must
    # not record them. Transactional DDL restores the trigger on failure.
    conn.execute(
        sa.text("ALTER TABLE statements DISABLE TRIGGER track_statement_access")
    )
    for start in range(0, len(statement_rows), _BATCH_SIZE):
        writing.execute(_STATEMENT_INSERT, statement_rows[start : start + _BATCH_SIZE])
    conn.execute(
        sa.text("ALTER TABLE statements ENABLE TRIGGER track_statement_access")
    )

    for start in range(0, len(actions), _BATCH_SIZE):
        writing.execute(_ACTION_INSERT, actions[start : start + _BATCH_SIZE])
    for start in range(0, len(evidence), _BATCH_SIZE):
        writing.execute(_EVIDENCE_INSERT, evidence[start : start + _BATCH_SIZE])

    _report_counts(totals, counts)
    _assert_invariants(conn, totals, counts, samples)


def _report_counts(totals: dict, counts: dict) -> None:
    """Log per-class counts so every old row is accounted for."""
    logger.info(
        "Data copy: %d evaluated of %d properties -> %d statements; "
        "create actions: %d applied (statement linked), %d applied "
        "(unlinked), %d discarded; %d evidence rows",
        totals["evaluated_properties"],
        totals["properties"],
        counts["statements"],
        counts["creates_applied_linked"],
        counts["creates_applied_unlinked"],
        counts["creates_discarded"],
        counts["evidence"],
    )
    logger.info(
        "Data copy drops: %d unevaluated, %d incomplete accepts, %d statement "
        "rejections, %d pushed-then-rejected properties; %d references on "
        "unevaluated properties, %d on dropped evaluated properties",
        counts["dropped_props_unevaluated"],
        counts["dropped_props_incomplete_accepts"],
        counts["dropped_props_statement_rejections"],
        counts["dropped_props_pushed_then_rejected"],
        counts["dropped_refs_unevaluated"],
        counts["dropped_refs_evaluated"],
    )
    logger.info(
        "Data copy evaluations: %d total -> %d mapped decisions, %d "
        "superseded, %d on dropped properties",
        totals["evaluations"],
        counts["eval_mapped"],
        counts["eval_superseded"],
        counts["eval_dropped"],
    )


def _assert_invariants(conn, totals: dict, counts: dict, samples: dict) -> None:
    """Assert the data-phase invariants (all hold trivially when empty)."""
    statements_count = conn.execute(
        sa.text("SELECT count(*) FROM statements")
    ).scalar_one()
    _require(
        statements_count == counts["statements"] == counts["creates_applied_linked"],
        f"statements {statements_count}, copied {counts['statements']}, linked "
        f"creates {counts['creates_applied_linked']} do not match",
    )
    _require(
        conn.execute(
            sa.text(
                "SELECT count(*) FROM statements WHERE wikidata_statement_id IS NULL"
            )
        ).scalar_one()
        == 0,
        "statements with NULL wikidata_statement_id",
    )
    _require(
        conn.execute(
            sa.text(
                "SELECT count(*) - count(DISTINCT wikidata_statement_id) "
                "FROM statements"
            )
        ).scalar_one()
        == 0,
        "duplicate wikidata_statement_id in statements",
    )

    actions_count = conn.execute(sa.text("SELECT count(*) FROM actions")).scalar_one()
    retained_actions = sum(
        counts[key]
        for key in (
            "creates_applied_linked",
            "creates_applied_unlinked",
            "creates_discarded",
        )
    )
    _require(
        actions_count == retained_actions,
        f"actions count {actions_count} != retained actions {retained_actions}",
    )
    _require(
        conn.execute(
            sa.text("""
                SELECT count(*) FROM actions
                WHERE kind <> 'CREATE_STATEMENT'
                   OR is_accepted IS NULL
                   OR (is_accepted AND applied_at IS NULL)
                   OR (NOT is_accepted AND applied_at IS NOT NULL)
            """)
        ).scalar_one()
        == 0,
        "unexpected action kind or decision/application state",
    )
    _require(
        conn.execute(
            sa.text("""
                SELECT count(*) FROM actions a
                JOIN statements s ON a.statement_id = s.id
                WHERE a.politician_id <> s.politician_id
            """)
        ).scalar_one()
        == 0,
        "action politician does not match its statement's politician",
    )

    evidence_count = conn.execute(
        sa.text("SELECT count(*) FROM action_evidence")
    ).scalar_one()
    dropped_refs = counts["dropped_refs_unevaluated"] + counts["dropped_refs_evaluated"]
    _require(
        evidence_count == counts["evidence"] == totals["references"] - dropped_refs,
        f"evidence count {evidence_count} != {counts['evidence']} queued != "
        f"{totals['references'] - dropped_refs} retained property_references",
    )

    dropped_props = sum(
        counts[key]
        for key in (
            "dropped_props_unevaluated",
            "dropped_props_incomplete_accepts",
            "dropped_props_statement_rejections",
            "dropped_props_pushed_then_rejected",
        )
    )
    _require(
        totals["properties"]
        == counts["statements"]
        + counts["creates_applied_unlinked"]
        + counts["creates_discarded"]
        + dropped_props,
        "properties not fully accounted",
    )
    _require(
        totals["evaluations"]
        == counts["eval_mapped"] + counts["eval_superseded"] + counts["eval_dropped"],
        "evaluations not fully accounted",
    )
    _require(
        totals["references"] == evidence_count + dropped_refs,
        "property_references not fully accounted",
    )

    for label, (row, claim) in samples.items():
        stored = conn.execute(
            sa.text("SELECT document FROM statements WHERE id = :id"),
            {"id": row["id"]},
        ).scalar_one()
        _require(
            stored == action_api_statement_to_rest(claim),
            f"{label} sample statement does not round-trip",
        )
        if label == "date":
            content = stored["value"]["content"]
            _require(
                content["time"] == row["value"]
                and content["precision"] == row["value_precision"],
                "date sample value does not match old value/value_precision",
            )
        elif label == "position":
            _require(stored.get("qualifiers"), "position sample lost qualifiers")
        else:
            _require(
                stored["value"]["content"] == row["entity_id"],
                "entity sample value does not match old entity_id",
            )


def upgrade() -> None:
    """Copy evaluated old-domain data, then drop the old domain."""
    _copy_property_data(op.get_bind())

    # Import-tracking trigger on the dropped properties table
    op.execute("DROP TRIGGER IF EXISTS track_property_access ON properties;")

    op.drop_table("property_claims")
    op.drop_table("property_skips")
    op.drop_table("evaluations")
    op.drop_table("property_references")
    op.drop_table("properties")
    op.drop_table("wikidata_entity_labels")

    op.drop_column("wikidata_entities", "name")
    op.drop_column("wikidata_entities", "description")
    op.drop_column("politicians", "name")

    # Nothing references the property type enum anymore
    PROPERTY_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """One-way migration: roll back by restoring from a pre-migration backup."""
    raise RuntimeError(
        "39159830a333 copies evaluated production data into the "
        "statement/action domain and then drops the old tables; restore "
        "from a backup to roll back"
    )
