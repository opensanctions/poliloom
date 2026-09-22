"""Drop soft delete and add cascade foreign keys

Removes the deleted_at columns (and their indexes) from statements,
wikidata_entities, and wikidata_relations. Rows that were still tombstoned at
migration time are hard-deleted first; deletion becomes permanent everywhere.

Foreign keys are redefined so hard-deleting a wikidata_entity takes its
politician (and everything cascading from it), its entity-subclass rows, and
statements/actions that point at it as a value entity. Deleting a statement
keeps decided actions as history (statement_id set to NULL); pending edit
actions are deleted with their target by the cleanup SQL.

Revision ID: 7c4d1f9a2e58
Revises: 39159830a333
Create Date: 2026-09-22 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c4d1f9a2e58"
down_revision: str | None = "39159830a333"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (constraint, table, column) -> referent column and ON DELETE behavior.
# Old behavior was NO ACTION for all of these.
FK_ONDELETE = {
    "actions_statement_id_fkey": (
        "actions",
        "statement_id",
        "statements.id",
        "SET NULL",
    ),
    "actions_entity_id_fkey": (
        "actions",
        "entity_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "statements_entity_id_fkey": (
        "statements",
        "entity_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "politicians_wikidata_id_fkey": (
        "politicians",
        "wikidata_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "countries_wikidata_id_fkey": (
        "countries",
        "wikidata_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "languages_wikidata_id_fkey": (
        "languages",
        "wikidata_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "locations_wikidata_id_fkey": (
        "locations",
        "wikidata_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "positions_wikidata_id_fkey": (
        "positions",
        "wikidata_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    "wikipedia_projects_wikidata_id_fkey": (
        "wikipedia_projects",
        "wikidata_id",
        "wikidata_entities.wikidata_id",
        "CASCADE",
    ),
    # Pending actions are bulk-deleted by cleanup SQL; their skips must not block it
    "action_skips_action_id_fkey": (
        "action_skips",
        "action_id",
        "actions.id",
        "CASCADE",
    ),
}


def _recreate_fks(ondelete: str | None) -> None:
    for name, (table, column, ref, behavior) in FK_ONDELETE.items():
        op.drop_constraint(name, table, type_="foreignkey")
        ref_table, ref_column = ref.split(".")
        op.create_foreign_key(
            name,
            table,
            ref_table,
            [column],
            [ref_column],
            ondelete=ondelete if ondelete is not None else behavior,
        )


def upgrade() -> None:
    """Redefine FKs, hard-delete tombstoned rows, drop deleted_at columns."""
    _recreate_fks(None)

    # Defensive cleanup: on a fresh-cutover DB these are empty, on a dev DB
    # they remove whatever was still tombstoned. Pending edit actions die with
    # their target statement; decided actions keep their payload (statement_id
    # is nulled by the FK); referencing rows cascade from the deleted entities.
    op.execute(
        """
        DELETE FROM actions
        WHERE is_accepted IS NULL
        AND kind = 'EDIT_STATEMENT'
        AND statement_id IN (SELECT id FROM statements WHERE deleted_at IS NOT NULL)
    """
    )
    op.execute("DELETE FROM statements WHERE deleted_at IS NOT NULL")
    op.execute("DELETE FROM wikidata_relations WHERE deleted_at IS NOT NULL")
    op.execute("DELETE FROM wikidata_entities WHERE deleted_at IS NOT NULL")

    op.drop_index("ix_statements_deleted_at", table_name="statements")
    op.drop_index("ix_wikidata_entities_deleted_at", table_name="wikidata_entities")
    op.drop_index("ix_wikidata_relations_deleted_at", table_name="wikidata_relations")

    op.drop_column("statements", "deleted_at")
    op.drop_column("wikidata_entities", "deleted_at")
    op.drop_column("wikidata_relations", "deleted_at")


def downgrade() -> None:
    """Restore soft-delete columns, indexes, and NO ACTION foreign keys.

    Rows hard-deleted while the soft-delete schema was gone cannot be restored.
    """
    op.add_column(
        "wikidata_relations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "wikidata_entities",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "statements",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_wikidata_relations_deleted_at", "wikidata_relations", ["deleted_at"]
    )
    op.create_index(
        "ix_wikidata_entities_deleted_at", "wikidata_entities", ["deleted_at"]
    )
    op.create_index("ix_statements_deleted_at", "statements", ["deleted_at"])

    _recreate_fks("NO ACTION")
