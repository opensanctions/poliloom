"""refactor evaluations to separate tables

Revision ID: e87044d9ae51
Revises: 37f7fcd0368b
Create Date: 2025-08-06 18:29:48.986166

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e87044d9ae51"
down_revision: Union[str, None] = "37f7fcd0368b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old polymorphic evaluations table
    op.drop_table("evaluations")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS evaluationresult")

    # Create new separate evaluation tables
    op.create_table(
        "property_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "position_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("holds_position_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["holds_position_id"],
            ["holds_position.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "birthplace_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("born_at_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["born_at_id"],
            ["born_at.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the new separate evaluation tables
    op.drop_table("birthplace_evaluations")
    op.drop_table("position_evaluations")
    op.drop_table("property_evaluations")

    # Recreate the enum type
    op.execute("CREATE TYPE evaluationresult AS ENUM ('CONFIRMED', 'DISCARDED')")

    # Recreate the old polymorphic evaluations table
    op.create_table(
        "evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "result",
            sa.Enum("CONFIRMED", "DISCARDED", name="evaluationresult"),
            nullable=False,
        ),
        sa.Column("property_id", sa.UUID(), nullable=True),
        sa.Column("holds_position_id", sa.UUID(), nullable=True),
        sa.Column("born_at_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["born_at_id"],
            ["born_at.id"],
        ),
        sa.ForeignKeyConstraint(
            ["holds_position_id"],
            ["holds_position.id"],
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
