"""retain action claim history

Revision ID: 4944c37e9b32
Revises: 7c4d1f9a2e58
Create Date: 2026-11-10 16:07:51.858114

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4944c37e9b32"
down_revision: str | None = "7c4d1f9a2e58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Retain released claims and enforce uniqueness only for unreleased claims."""
    op.add_column(
        "action_claims",
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint("action_claims_action_id_key", "action_claims", type_="unique")
    op.create_index(op.f("ix_action_claims_action_id"), "action_claims", ["action_id"])
    op.create_index(
        "uq_action_claims_unreleased_action",
        "action_claims",
        ["action_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )


def downgrade() -> None:
    """Restore one claim row per action, discarding older history."""
    op.drop_index(
        "uq_action_claims_unreleased_action",
        table_name="action_claims",
        postgresql_where=sa.text("released_at IS NULL"),
    )
    op.drop_index(op.f("ix_action_claims_action_id"), table_name="action_claims")
    op.execute(
        """
        DELETE FROM action_claims
        WHERE id NOT IN (
            SELECT DISTINCT ON (action_id) id
            FROM action_claims
            ORDER BY action_id, claimed_at DESC, id DESC
        )
        """
    )
    op.drop_column("action_claims", "released_at")
    op.create_unique_constraint(
        "action_claims_action_id_key", "action_claims", ["action_id"]
    )
