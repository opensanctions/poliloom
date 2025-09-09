"""rename wikidata_class to wikidata_entity and subclass_relation to wikidata_relation with direct foreign keys

Revision ID: a4ffd33b8abc
Revises: 4797852d86b9
Create Date: 2025-09-09 16:49:56.040648

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a4ffd33b8abc"
down_revision: Union[str, None] = "4797852d86b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Create new tables
    op.create_table(
        "wikidata_entities",
        sa.Column("wikidata_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("wikidata_id"),
    )

    # Step 2: Get connection and inspector for data migration
    connection = op.get_bind()
    inspector = sa.Inspector.from_engine(connection)
    existing_tables = inspector.get_table_names()

    # Step 3: Insert all position and location wikidata_ids into wikidata_entities
    # This ensures foreign key constraints will work
    if "positions" in existing_tables:
        connection.execute(
            sa.text("""
            INSERT INTO wikidata_entities (wikidata_id, name, created_at, updated_at)
            SELECT wikidata_id, name, created_at, updated_at
            FROM positions
            ON CONFLICT (wikidata_id) DO UPDATE SET 
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at
        """)
        )

    if "locations" in existing_tables:
        connection.execute(
            sa.text("""
            INSERT INTO wikidata_entities (wikidata_id, name, created_at, updated_at)
            SELECT wikidata_id, name, created_at, updated_at
            FROM locations
            ON CONFLICT (wikidata_id) DO UPDATE SET 
                name = EXCLUDED.name,
                updated_at = EXCLUDED.updated_at
        """)
        )

    # Step 4: Migrate data from wikidata_classes if it exists
    if "wikidata_classes" in existing_tables:
        connection.execute(
            sa.text("""
            INSERT INTO wikidata_entities (wikidata_id, name, created_at, updated_at)
            SELECT wikidata_id, name, created_at, updated_at
            FROM wikidata_classes
            ON CONFLICT (wikidata_id) DO UPDATE SET 
                name = COALESCE(EXCLUDED.name, wikidata_entities.name),
                updated_at = EXCLUDED.updated_at
        """)
        )

    # Step 5: Create wikidata_relations table with composite primary key
    op.create_table(
        "wikidata_relations",
        sa.Column("parent_entity_id", sa.String(), nullable=False),
        sa.Column("child_entity_id", sa.String(), nullable=False),
        sa.Column(
            "relation_type",
            sa.Enum("SUBCLASS_OF", name="relationtype"),
            nullable=False,
            server_default="SUBCLASS_OF",
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["child_entity_id"],
            ["wikidata_entities.wikidata_id"],
        ),
        sa.ForeignKeyConstraint(
            ["parent_entity_id"],
            ["wikidata_entities.wikidata_id"],
        ),
        sa.PrimaryKeyConstraint("parent_entity_id", "child_entity_id", "relation_type"),
    )

    # Step 6: Migrate subclass_relations data if it exists
    if "subclass_relations" in existing_tables:
        # No EXISTS check needed since wikidata_classes are already in wikidata_entities
        connection.execute(
            sa.text("""
            INSERT INTO wikidata_relations (parent_entity_id, child_entity_id, relation_type, created_at, updated_at)
            SELECT sr.parent_class_id, sr.child_class_id, 'SUBCLASS_OF', sr.created_at, sr.updated_at
            FROM subclass_relations sr
            ON CONFLICT (parent_entity_id, child_entity_id, relation_type) DO NOTHING
        """)
        )

    # Step 6b: Migrate position_classes relationships if they exist
    if "position_classes" in existing_tables:
        # Migrate position-class relationships as SUBCLASS_OF relationships
        # No EXISTS check needed since positions are already in wikidata_entities
        connection.execute(
            sa.text("""
            INSERT INTO wikidata_relations (parent_entity_id, child_entity_id, relation_type, created_at, updated_at)
            SELECT pc.class_id, pc.position_id, 'SUBCLASS_OF', NOW(), NOW()
            FROM position_classes pc
            ON CONFLICT (parent_entity_id, child_entity_id, relation_type) DO NOTHING
        """)
        )

    # Step 6c: Migrate location_classes relationships if they exist
    if "location_classes" in existing_tables:
        # Migrate location-class relationships as SUBCLASS_OF relationships
        # No EXISTS check needed since locations are already in wikidata_entities
        connection.execute(
            sa.text("""
            INSERT INTO wikidata_relations (parent_entity_id, child_entity_id, relation_type, created_at, updated_at)
            SELECT lc.class_id, lc.location_id, 'SUBCLASS_OF', NOW(), NOW()
            FROM location_classes lc
            ON CONFLICT (parent_entity_id, child_entity_id, relation_type) DO NOTHING
        """)
        )

    # Step 7: Create indexes after data migration
    op.create_index(
        op.f("ix_wikidata_relations_child_entity_id"),
        "wikidata_relations",
        ["child_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_wikidata_relations_parent_entity_id"),
        "wikidata_relations",
        ["parent_entity_id"],
        unique=False,
    )

    # Step 8: Add foreign key constraints to positions and locations
    op.create_foreign_key(
        None, "locations", "wikidata_entities", ["wikidata_id"], ["wikidata_id"]
    )
    op.create_foreign_key(
        None, "positions", "wikidata_entities", ["wikidata_id"], ["wikidata_id"]
    )

    # Step 9: Drop old tables
    if "position_classes" in existing_tables:
        op.drop_table("position_classes")
    if "location_classes" in existing_tables:
        op.drop_table("location_classes")
    if "subclass_relations" in existing_tables:
        op.drop_index(
            op.f("ix_subclass_relations_child_class_id"),
            table_name="subclass_relations",
        )
        op.drop_index(
            op.f("ix_subclass_relations_parent_class_id"),
            table_name="subclass_relations",
        )
        op.drop_table("subclass_relations")
    if "wikidata_classes" in existing_tables:
        op.drop_table("wikidata_classes")


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "positions", type_="foreignkey")
    op.drop_constraint(None, "locations", type_="foreignkey")
    op.create_table(
        "location_classes",
        sa.Column("location_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("class_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["wikidata_classes.wikidata_id"],
            name=op.f("location_classes_class_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.wikidata_id"],
            name=op.f("location_classes_location_id_fkey"),
        ),
        sa.PrimaryKeyConstraint(
            "location_id", "class_id", name=op.f("location_classes_pkey")
        ),
    )
    op.create_table(
        "subclass_relations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("parent_class_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("child_class_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["child_class_id"],
            ["wikidata_classes.wikidata_id"],
            name="subclass_relations_child_class_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["parent_class_id"],
            ["wikidata_classes.wikidata_id"],
            name="subclass_relations_parent_class_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="subclass_relations_pkey"),
        sa.UniqueConstraint(
            "parent_class_id", "child_class_id", name="uq_subclass_parent_child"
        ),
    )
    op.create_index(
        op.f("ix_subclass_relations_parent_class_id"),
        "subclass_relations",
        ["parent_class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subclass_relations_child_class_id"),
        "subclass_relations",
        ["child_class_id"],
        unique=False,
    )
    op.create_table(
        "position_classes",
        sa.Column("position_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("class_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["wikidata_classes.wikidata_id"],
            name=op.f("position_classes_class_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.wikidata_id"],
            name=op.f("position_classes_position_id_fkey"),
        ),
        sa.PrimaryKeyConstraint(
            "position_id", "class_id", name=op.f("position_classes_pkey")
        ),
    )
    op.create_table(
        "wikidata_classes",
        sa.Column("wikidata_id", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("wikidata_id", name=op.f("wikidata_classes_pkey")),
    )
    op.drop_index(
        op.f("ix_wikidata_relations_parent_entity_id"), table_name="wikidata_relations"
    )
    op.drop_index(
        op.f("ix_wikidata_relations_child_entity_id"), table_name="wikidata_relations"
    )
    op.drop_table("wikidata_relations")
    op.drop_table("wikidata_entities")
    # ### end Alembic commands ###
