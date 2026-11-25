"""add statement and action models

Revision ID: 0858a2e5b2e2
Revises: e43ce4ff123a
Create Date: 2026-09-20 17:57:12.123456

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0858a2e5b2e2"
down_revision: str | None = "e43ce4ff123a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# New tables that carry the TimestampMixin updated_at column
TABLES_WITH_UPDATED_AT = [
    "statements",
    "actions",
    "action_evidence",
    "action_claims",
    "action_skips",
]


def upgrade() -> None:
    """Create statement and action tables with triggers."""
    op.create_table(
        "statements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("politician_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "wikidata_statement_id",
            sa.String(),
            sa.Computed("document ->> 'id'"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.String(),
            sa.Computed("document #>> '{property,id}'"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            sa.String(),
            sa.Computed(
                "CASE WHEN document #>> '{property,id}' IN ('P19','P27','P39') "
                "THEN document #>> '{value,content}' END"
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["politician_id"], ["politicians.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["wikidata_entities.wikidata_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wikidata_statement_id", name="uq_statements_wikidata_statement_id"
        ),
    )
    op.create_index(
        op.f("ix_statements_politician_id"), "statements", ["politician_id"]
    )
    op.create_index(op.f("ix_statements_deleted_at"), "statements", ["deleted_at"])
    op.create_index(
        "idx_statements_politician_property",
        "statements",
        ["politician_id", "property_id"],
    )
    op.create_index(
        "idx_statements_politician_property_entity",
        "statements",
        ["politician_id", "property_id", "entity_id"],
    )
    op.create_index("idx_statements_updated_at", "statements", ["updated_at"])

    op.create_table(
        "actions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("politician_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_wikidata_statement_id", sa.String(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "references_to_add",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("applied_wikidata_statement_id", sa.String(), nullable=True),
        sa.Column(
            "entity_id",
            sa.String(),
            sa.Computed(
                "CASE WHEN target_wikidata_statement_id IS NULL "
                "AND \"after\" #>> '{property,id}' IN ('P19','P27','P39') "
                "THEN \"after\" #>> '{value,content}' END"
            ),
            nullable=True,
        ),
        sa.Column("is_accepted", sa.Boolean(), nullable=True),
        sa.Column("decided_by_user_id", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"], ["politicians.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["wikidata_entities.wikidata_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(target_wikidata_statement_id IS NULL) = (before IS NULL) "
            "AND (before IS NULL OR jsonb_typeof(before) = 'object')",
            name="ck_actions_target_before",
        ),
    )
    op.create_index(op.f("ix_actions_politician_id"), "actions", ["politician_id"])
    op.create_index(
        "idx_actions_politician_pending",
        "actions",
        ["politician_id"],
        postgresql_where=sa.text("is_accepted IS NULL"),
    )
    op.create_index(
        "idx_actions_target_pending",
        "actions",
        ["target_wikidata_statement_id"],
        postgresql_where=sa.text(
            "is_accepted IS NULL AND target_wikidata_statement_id IS NOT NULL"
        ),
    )

    op.create_table(
        "action_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supporting_quotes", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_id", "source_id", name="uq_action_evidence_pair"),
    )
    op.create_index("idx_action_evidence_action_id", "action_evidence", ["action_id"])
    op.create_index("idx_action_evidence_source_id", "action_evidence", ["source_id"])

    op.create_table(
        "action_claims",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_id"),
    )
    op.create_index(op.f("ix_action_claims_user_id"), "action_claims", ["user_id"])
    op.create_index(
        op.f("ix_action_claims_claimed_at"), "action_claims", ["claimed_at"]
    )

    op.create_table(
        "action_skips",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["action_id"], ["actions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "action_id"),
    )
    op.create_index(op.f("ix_action_skips_user_id"), "action_skips", ["user_id"])

    # updated_at triggers (function created by e6cee728924e)
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"""
            CREATE TRIGGER trigger_update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )

    # Import tracking: record statements seen by the current dump import.
    # Mirrors the track_property_access trigger on properties, but keyed on
    # the generated wikidata_statement_id column.
    op.execute("""
        CREATE OR REPLACE FUNCTION track_statement_document_access()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO current_import_statements (statement_id)
            VALUES (NEW.wikidata_statement_id)
            ON CONFLICT (statement_id) DO NOTHING;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER track_statement_access
        AFTER INSERT OR UPDATE ON statements
        FOR EACH ROW EXECUTE FUNCTION track_statement_document_access();
    """)


def downgrade() -> None:
    """Drop statement and action tables with triggers."""
    op.execute("DROP TRIGGER IF EXISTS track_statement_access ON statements;")
    op.execute("DROP FUNCTION IF EXISTS track_statement_document_access();")

    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"DROP TRIGGER IF EXISTS trigger_update_{table}_updated_at ON {table}"
        )

    op.drop_index(op.f("ix_action_skips_user_id"), table_name="action_skips")
    op.drop_table("action_skips")

    op.drop_index(op.f("ix_action_claims_claimed_at"), table_name="action_claims")
    op.drop_index(op.f("ix_action_claims_user_id"), table_name="action_claims")
    op.drop_table("action_claims")

    op.drop_index("idx_action_evidence_source_id", table_name="action_evidence")
    op.drop_index("idx_action_evidence_action_id", table_name="action_evidence")
    op.drop_table("action_evidence")

    op.drop_index("idx_actions_target_pending", table_name="actions")
    op.drop_index("idx_actions_politician_pending", table_name="actions")
    op.drop_index(op.f("ix_actions_politician_id"), table_name="actions")
    op.drop_table("actions")

    op.drop_index("idx_statements_updated_at", table_name="statements")
    op.drop_index("idx_statements_politician_property_entity", table_name="statements")
    op.drop_index("idx_statements_politician_property", table_name="statements")
    op.drop_index(op.f("ix_statements_deleted_at"), table_name="statements")
    op.drop_index(op.f("ix_statements_politician_id"), table_name="statements")
    op.drop_table("statements")
