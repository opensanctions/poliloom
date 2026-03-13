"""replace error string with enum and http_status_code

Revision ID: f5d737043dbe
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13 17:20:11.483108

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f5d737043dbe"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

archivedpageerror = sa.Enum(
    "FETCH_ERROR",
    "TIMEOUT",
    "INVALID_CONTENT",
    "PIPELINE_ERROR",
    name="archivedpageerror",
)


def upgrade() -> None:
    """Upgrade schema."""
    # Clear any existing freetext error values (not meaningful as enum values)
    op.execute("UPDATE archived_pages SET error = NULL WHERE error IS NOT NULL")

    archivedpageerror.create(op.get_bind())

    op.alter_column(
        "archived_pages",
        "error",
        existing_type=sa.VARCHAR(),
        type_=archivedpageerror,
        existing_nullable=True,
        postgresql_using="error::archivedpageerror",
    )
    op.add_column(
        "archived_pages",
        sa.Column("http_status_code", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_archived_pages_http_status_code_requires_fetch_error",
        "archived_pages",
        "(error = 'FETCH_ERROR') = (http_status_code IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_archived_pages_http_status_code_requires_fetch_error",
        "archived_pages",
    )
    op.drop_column("archived_pages", "http_status_code")
    op.alter_column(
        "archived_pages",
        "error",
        existing_type=archivedpageerror,
        type_=sa.VARCHAR(),
        existing_nullable=True,
    )
    archivedpageerror.drop(op.get_bind())
