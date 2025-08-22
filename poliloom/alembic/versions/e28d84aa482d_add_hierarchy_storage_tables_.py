"""Add hierarchy storage tables (WikidataClass and SubclassRelation)

Revision ID: e28d84aa482d
Revises: 791c7593cd8a
Create Date: 2025-08-22 09:42:46.422091

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e28d84aa482d"
down_revision: Union[str, None] = "791c7593cd8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create wikidata_classes table
    op.create_table(
        "wikidata_classes",
        sa.Column("class_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_wikidata_classes_class_id"),
        "wikidata_classes",
        ["class_id"],
        unique=False,
    )

    # Create subclass_relations table
    op.create_table(
        "subclass_relations",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("parent_class_id", sa.String(), nullable=False),
        sa.Column("child_class_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["child_class_id"],
            ["wikidata_classes.class_id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_class_id"],
            ["wikidata_classes.class_id"],
        ),
        sa.UniqueConstraint(
            "parent_class_id", "child_class_id", name="uq_subclass_parent_child"
        ),
    )
    op.create_index(
        op.f("ix_subclass_relations_child_class_id"),
        "subclass_relations",
        ["child_class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subclass_relations_parent_class_id"),
        "subclass_relations",
        ["parent_class_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index(
        op.f("ix_subclass_relations_parent_class_id"), table_name="subclass_relations"
    )
    op.drop_index(
        op.f("ix_subclass_relations_child_class_id"), table_name="subclass_relations"
    )
    op.drop_table("subclass_relations")

    op.drop_index(op.f("ix_wikidata_classes_class_id"), table_name="wikidata_classes")
    op.drop_table("wikidata_classes")
