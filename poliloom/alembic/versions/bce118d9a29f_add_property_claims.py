"""add property claims

Revision ID: bce118d9a29f
Revises: 9c31f7d2e6a4
Create Date: 2026-07-26 00:07:31.667646

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "bce118d9a29f"
down_revision: str | None = "9c31f7d2e6a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id"),
    )
    op.create_index(
        op.f("ix_property_claims_claimed_at"), "property_claims", ["claimed_at"]
    )
    op.create_index(op.f("ix_property_claims_user_id"), "property_claims", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_property_claims_user_id"), table_name="property_claims")
    op.drop_index(op.f("ix_property_claims_claimed_at"), table_name="property_claims")
    op.drop_table("property_claims")
