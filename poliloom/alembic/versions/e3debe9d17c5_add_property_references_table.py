"""add property_references table

Revision ID: e3debe9d17c5
Revises: 5e22c7045b45
Create Date: 2026-02-18 12:11:59.158027

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e3debe9d17c5"
down_revision: Union[str, None] = "5e22c7045b45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create property_references table
    op.create_table(
        "property_references",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("archived_page_id", sa.UUID(), nullable=False),
        sa.Column("supporting_quotes", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["archived_page_id"],
            ["archived_pages.id"],
        ),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "property_id", "archived_page_id", name="uq_property_ref_property_page"
        ),
    )
    op.create_index(
        "idx_property_references_property_id",
        "property_references",
        ["property_id"],
        unique=False,
    )

    # 2. Data migration: copy existing property→archived_page links to property_references
    op.execute("""
        INSERT INTO property_references (id, property_id, archived_page_id, supporting_quotes, created_at, updated_at)
        SELECT gen_random_uuid(), id, archived_page_id, supporting_quotes, created_at, updated_at
        FROM properties
        WHERE archived_page_id IS NOT NULL
    """)

    # 3. NULL out REST API format references_json — keep only Wikidata-format references.
    # REST API format (from our extraction) has objects with "property" key.
    # Wikidata Action API format (from import) has objects with "snaks" key.
    op.execute("""
        UPDATE properties SET references_json = NULL
        WHERE jsonb_typeof(references_json) = 'array'
          AND jsonb_typeof(references_json->0) = 'object'
          AND (references_json->0) ? 'property'
    """)

    # 4. Drop old indexes that reference archived_page_id
    op.drop_index(
        op.f("idx_properties_extracted"),
        table_name="properties",
        postgresql_where="((archived_page_id IS NOT NULL) AND (deleted_at IS NULL))",
    )
    op.drop_index(
        op.f("idx_properties_unevaluated"),
        table_name="properties",
        postgresql_where="((statement_id IS NULL) AND (deleted_at IS NULL))",
    )

    # 5. Create new unevaluated index (without archived_page_id)
    op.create_index(
        "idx_properties_unevaluated",
        "properties",
        ["politician_id"],
        unique=False,
        postgresql_where=sa.text("statement_id IS NULL AND deleted_at IS NULL"),
    )

    # 6. Drop archived_page_id and supporting_quotes columns
    op.drop_constraint(
        op.f("properties_archived_page_id_fkey"), "properties", type_="foreignkey"
    )
    op.drop_column("properties", "archived_page_id")
    op.drop_column("properties", "supporting_quotes")


def downgrade() -> None:
    """Downgrade schema."""
    # Re-add columns
    op.add_column(
        "properties",
        sa.Column(
            "supporting_quotes",
            postgresql.ARRAY(sa.VARCHAR()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "properties",
        sa.Column("archived_page_id", sa.UUID(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        op.f("properties_archived_page_id_fkey"),
        "properties",
        "archived_pages",
        ["archived_page_id"],
        ["id"],
    )

    # Migrate data back from property_references to properties
    op.execute("""
        UPDATE properties p
        SET archived_page_id = pr.archived_page_id,
            supporting_quotes = pr.supporting_quotes
        FROM (
            SELECT DISTINCT ON (property_id) property_id, archived_page_id, supporting_quotes
            FROM property_references
            ORDER BY property_id, created_at ASC
        ) pr
        WHERE p.id = pr.property_id
    """)

    # Restore indexes
    op.drop_index(
        "idx_properties_unevaluated",
        table_name="properties",
        postgresql_where=sa.text("statement_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        op.f("idx_properties_unevaluated"),
        "properties",
        ["politician_id", "archived_page_id"],
        unique=False,
        postgresql_where="((statement_id IS NULL) AND (deleted_at IS NULL))",
    )
    op.create_index(
        op.f("idx_properties_extracted"),
        "properties",
        ["politician_id", "archived_page_id"],
        unique=False,
        postgresql_where="((archived_page_id IS NOT NULL) AND (deleted_at IS NULL))",
    )

    # Drop property_references table
    op.drop_index(
        "idx_property_references_property_id", table_name="property_references"
    )
    op.drop_table("property_references")
