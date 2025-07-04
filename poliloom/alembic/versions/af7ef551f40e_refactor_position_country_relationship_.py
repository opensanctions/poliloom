"""refactor position country relationship to many-to-many

Revision ID: af7ef551f40e
Revises: cd9dab1bc0ad
Create Date: 2025-06-12 16:06:09.472987

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "af7ef551f40e"
down_revision: Union[str, None] = "cd9dab1bc0ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create position_country association table
    op.create_table(
        "position_country",
        sa.Column("position_id", sa.String(), nullable=False),
        sa.Column("country_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["country_id"],
            ["countries.id"],
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.id"],
        ),
        sa.PrimaryKeyConstraint("position_id", "country_id"),
    )

    # Migrate existing data from positions.country_id to position_country table
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
        INSERT INTO position_country (position_id, country_id)
        SELECT id, country_id FROM positions WHERE country_id IS NOT NULL
    """
        )
    )

    # Drop the old country_id column from positions table
    with op.batch_alter_table("positions", schema=None) as batch_op:
        batch_op.drop_constraint("fk_positions_country_id", type_="foreignkey")
        batch_op.drop_column("country_id")


def downgrade() -> None:
    """Downgrade schema."""
    # Add back the country_id column to positions table
    with op.batch_alter_table("positions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("country_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_positions_country_id", "countries", ["country_id"], ["id"]
        )

    # Migrate data back from position_country to positions.country_id
    # Note: This will only work if positions have at most one country
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
        UPDATE positions 
        SET country_id = (
            SELECT country_id FROM position_country 
            WHERE position_country.position_id = positions.id 
            LIMIT 1
        )
    """
        )
    )

    # Drop the position_country association table
    op.drop_table("position_country")
