"""drop property domain

Drop the old Property/Evaluation tables, flat label storage, and the
denormalized name/description columns. Terms live on wikidata_entities and
review data on actions/statements.

Revision ID: 39159830a333
Revises: 08cfa4a3f74f
Create Date: 2026-09-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39159830a333"
down_revision: str | None = "08cfa4a3f74f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROPERTY_TYPE_ENUM = postgresql.ENUM(
    "BIRTH_DATE",
    "DEATH_DATE",
    "BIRTHPLACE",
    "POSITION",
    "CITIZENSHIP",
    name="propertytype",
    create_type=False,
)


def upgrade() -> None:
    """Drop the old property domain tables, columns, and their triggers."""
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
    """Recreate the old property domain tables, columns, and triggers."""
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE propertytype AS ENUM "
        "('BIRTH_DATE', 'DEATH_DATE', 'BIRTHPLACE', 'POSITION', 'CITIZENSHIP'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )

    op.add_column(
        "wikidata_entities",
        sa.Column("name", sa.String(), nullable=True),
    )
    op.add_column(
        "wikidata_entities",
        sa.Column("description", sa.String(), nullable=True),
    )
    op.add_column(
        "politicians",
        sa.Column("name", sa.String(), nullable=False, server_default=""),
    )
    op.alter_column("politicians", "name", server_default=None)

    op.create_table(
        "wikidata_entity_labels",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
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
            ["entity_id"],
            ["wikidata_entities.wikidata_id"],
            name="wikidata_entity_labels_entity_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_wikidata_entity_labels_entity_id",
        "wikidata_entity_labels",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "uq_wikidata_entity_labels_entity_label",
        "wikidata_entity_labels",
        ["entity_id", "label"],
        unique=True,
    )

    op.create_table(
        "properties",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("politician_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", PROPERTY_TYPE_ENUM, nullable=False),
        sa.Column("value", sa.String(), nullable=True),
        sa.Column("value_precision", sa.Integer(), nullable=True),
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
        sa.Column("statement_id", sa.String(), nullable=True),
        sa.Column(
            "qualifiers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "references_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(type IN ('BIRTH_DATE', 'DEATH_DATE') AND value IS NOT NULL AND value_precision IS NOT NULL AND entity_id IS NULL) "
            "OR (type IN ('BIRTHPLACE', 'POSITION', 'CITIZENSHIP') AND entity_id IS NOT NULL AND value IS NULL)",
            name="check_property_fields",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["wikidata_entities.wikidata_id"],
            name="properties_entity_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            name="properties_politician_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_properties_deleted_at", "properties", ["deleted_at"], unique=False
    )
    op.create_index(
        "ix_properties_entity_id", "properties", ["entity_id"], unique=False
    )
    op.create_index(
        "ix_properties_politician_id", "properties", ["politician_id"], unique=False
    )
    op.create_index("ix_properties_type", "properties", ["type"], unique=False)
    op.create_index(
        "idx_properties_updated_at",
        "properties",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_properties_unevaluated",
        "properties",
        ["politician_id"],
        unique=False,
        postgresql_where=sa.text("statement_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "idx_properties_type_entity",
        "properties",
        ["type", "entity_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_properties_citizenship_lookup",
        "properties",
        ["politician_id", "type", "entity_id"],
        unique=False,
        postgresql_where=sa.text("type = 'CITIZENSHIP' AND deleted_at IS NULL"),
    )
    op.create_index(
        "idx_properties_wikidata_citizenship",
        "properties",
        ["politician_id"],
        unique=False,
        postgresql_where=sa.text(
            "type = 'CITIZENSHIP' AND statement_id IS NOT NULL AND deleted_at IS NULL"
        ),
    )

    op.create_table(
        "evaluations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
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
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_accepted", sa.Boolean(), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="evaluations_property_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_evaluations_created_at", "evaluations", ["created_at"], unique=False
    )
    op.create_index(
        "idx_evaluations_property_created",
        "evaluations",
        ["property_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "property_references",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="property_references_property_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name="property_references_archived_page_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "property_id", "source_id", name="uq_property_ref_property_source"
        ),
    )
    op.create_index(
        "idx_property_references_property_id",
        "property_references",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        "idx_property_references_source_id",
        "property_references",
        ["source_id"],
        unique=False,
    )

    op.create_table(
        "property_claims",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="property_claims_property_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id"),
    )
    op.create_index(
        "ix_property_claims_claimed_at", "property_claims", ["claimed_at"], unique=False
    )
    op.create_index(
        "ix_property_claims_user_id", "property_claims", ["user_id"], unique=False
    )

    op.create_table(
        "property_skips",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            ["property_id"],
            ["properties.id"],
            name="property_skips_property_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "property_id"),
    )
    op.create_index(
        "ix_property_skips_user_id", "property_skips", ["user_id"], unique=False
    )

    # Triggers for the recreated tables
    op.execute(
        """
        CREATE TRIGGER track_property_access
        AFTER INSERT OR UPDATE ON properties
        FOR EACH ROW EXECUTE FUNCTION track_statement_access();
    """
    )
    op.execute(
        """
        CREATE TRIGGER trigger_update_properties_updated_at
        BEFORE UPDATE ON properties
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """
    )
    op.execute(
        """
        CREATE TRIGGER trigger_update_evaluations_updated_at
        BEFORE UPDATE ON evaluations
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """
    )
