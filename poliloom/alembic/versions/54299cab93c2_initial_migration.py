"""Initial migration

Revision ID: 54299cab93c2
Revises:
Create Date: 2025-06-11 12:32:55.873670

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "54299cab93c2"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "politicians",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("wikidata_id", sa.String(), nullable=True),
        sa.Column("is_deceased", sa.Boolean(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_politicians_wikidata_id"), "politicians", ["wikidata_id"], unique=True
    )
    op.create_table(
        "positions",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("wikidata_id", sa.String(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_positions_wikidata_id"), "positions", ["wikidata_id"], unique=True
    )
    op.create_table(
        "sources",
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("extracted_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_table(
        "holds_position",
        sa.Column("politician_id", sa.String(), nullable=False),
        sa.Column("position_id", sa.String(), nullable=False),
        sa.Column("start_date", sa.String(), nullable=True),
        sa.Column("end_date", sa.String(), nullable=True),
        sa.Column("is_extracted", sa.Boolean(), nullable=True),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "politician_source",
        sa.Column("politician_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
        ),
        sa.PrimaryKeyConstraint("politician_id", "source_id"),
    )
    op.create_table(
        "properties",
        sa.Column("politician_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("is_extracted", sa.Boolean(), nullable=True),
        sa.Column("confirmed_by", sa.String(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["politician_id"],
            ["politicians.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "holdsposition_source",
        sa.Column("holdsposition_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["holdsposition_id"],
            ["holds_position.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
        ),
        sa.PrimaryKeyConstraint("holdsposition_id", "source_id"),
    )
    op.create_table(
        "property_source",
        sa.Column("property_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
        ),
        sa.PrimaryKeyConstraint("property_id", "source_id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("property_source")
    op.drop_table("holdsposition_source")
    op.drop_table("properties")
    op.drop_table("politician_source")
    op.drop_table("holds_position")
    op.drop_table("sources")
    op.drop_index(op.f("ix_positions_wikidata_id"), table_name="positions")
    op.drop_table("positions")
    op.drop_index(op.f("ix_politicians_wikidata_id"), table_name="politicians")
    op.drop_table("politicians")
    # ### end Alembic commands ###
