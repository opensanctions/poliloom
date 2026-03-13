"""many-to-many politician archived pages

Revision ID: a1b2c3d4e5f6
Revises: 7e62c18f910b
Create Date: 2026-03-13 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7e62c18f910b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create junction table
    op.create_table(
        "politician_archived_pages",
        sa.Column("politician_id", sa.UUID(), nullable=False),
        sa.Column("archived_page_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["archived_page_id"],
            ["archived_pages.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("politician_id", "archived_page_id"),
    )

    # 2. Migrate: link pages that have property_references to their politician
    op.execute(
        """
        INSERT INTO politician_archived_pages (politician_id, archived_page_id)
        SELECT DISTINCT p.politician_id, pr.archived_page_id
        FROM property_references pr
        JOIN properties p ON pr.property_id = p.id
        WHERE p.politician_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # 3. Delete orphaned archived pages (no politician link via property_references)
    op.execute(
        """
        DELETE FROM archived_pages
        WHERE id NOT IN (
            SELECT archived_page_id FROM politician_archived_pages
        )
        """
    )

    # 5. Drop politician_id FK, index, and column from archived_pages
    op.drop_constraint(
        "archived_pages_politician_id_fkey", "archived_pages", type_="foreignkey"
    )
    op.drop_index("ix_archived_pages_politician_id", table_name="archived_pages")
    op.drop_column("archived_pages", "politician_id")


def downgrade() -> None:
    # Re-add politician_id column
    op.add_column(
        "archived_pages",
        sa.Column("politician_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_archived_pages_politician_id",
        "archived_pages",
        ["politician_id"],
    )
    op.create_foreign_key(
        "archived_pages_politician_id_fkey",
        "archived_pages",
        "politicians",
        ["politician_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Restore politician_id from junction table (pick first politician if multiple)
    op.execute(
        """
        UPDATE archived_pages ap
        SET politician_id = pap.politician_id
        FROM (
            SELECT DISTINCT ON (archived_page_id) archived_page_id, politician_id
            FROM politician_archived_pages
        ) pap
        WHERE ap.id = pap.archived_page_id
        """
    )

    op.drop_table("politician_archived_pages")
