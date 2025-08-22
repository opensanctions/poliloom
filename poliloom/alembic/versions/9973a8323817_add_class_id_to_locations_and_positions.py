"""add_class_id_to_locations_and_positions

Revision ID: 9973a8323817
Revises: 6345bbdce2e7
Create Date: 2025-08-22 11:42:58.303868

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9973a8323817"
down_revision: Union[str, None] = "6345bbdce2e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add class_id column to locations table
    op.add_column("locations", sa.Column("class_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_locations_class_id", "locations", "wikidata_classes", ["class_id"], ["id"]
    )
    op.create_index("ix_locations_class_id", "locations", ["class_id"])

    # Add class_id column to positions table
    op.add_column("positions", sa.Column("class_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_positions_class_id", "positions", "wikidata_classes", ["class_id"], ["id"]
    )
    op.create_index("ix_positions_class_id", "positions", ["class_id"])


def downgrade() -> None:
    """Downgrade schema."""
    # Remove indexes and foreign keys for positions
    op.drop_index("ix_positions_class_id", "positions")
    op.drop_constraint("fk_positions_class_id", "positions", type_="foreignkey")
    op.drop_column("positions", "class_id")

    # Remove indexes and foreign keys for locations
    op.drop_index("ix_locations_class_id", "locations")
    op.drop_constraint("fk_locations_class_id", "locations", type_="foreignkey")
    op.drop_column("locations", "class_id")
