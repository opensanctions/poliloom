"""Unify property models and consolidate evaluations

Revision ID: 5537fc850c51
Revises: 8ae356a55936
Create Date: 2025-09-23 21:39:37.297736

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5537fc850c51"
down_revision: Union[str, None] = "8ae356a55936"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Add entity_id column to properties table
    op.add_column("properties", sa.Column("entity_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "properties_entity_id_fkey",
        "properties",
        "wikidata_entities",
        ["entity_id"],
        ["wikidata_id"],
    )

    # 2. Make value column nullable for entity relationships
    op.alter_column("properties", "value", nullable=True)

    # 3. Create new evaluations table (renamed from property_evaluations)
    op.create_table(
        "evaluations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("property_id", sa.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. Add trigger for evaluations updated_at
    op.execute("""
        CREATE TRIGGER trigger_update_evaluations_updated_at
        BEFORE UPDATE ON evaluations
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # 5. Migrate data from born_at table to properties
    op.execute("""
        INSERT INTO properties (id, politician_id, type, entity_id, archived_page_id, proof_line, statement_id, qualifiers_json, references_json, created_at, updated_at)
        SELECT gen_random_uuid(), politician_id, 'BIRTHPLACE', location_id, archived_page_id, proof_line, statement_id, qualifiers_json, references_json, created_at, updated_at
        FROM born_at;
    """)

    # 6. Migrate data from holds_position table to properties
    op.execute("""
        INSERT INTO properties (id, politician_id, type, entity_id, archived_page_id, proof_line, statement_id, qualifiers_json, references_json, created_at, updated_at)
        SELECT gen_random_uuid(), politician_id, 'POSITION', position_id, archived_page_id, proof_line, statement_id, qualifiers_json, references_json, created_at, updated_at
        FROM holds_position;
    """)

    # 7. Migrate data from has_citizenship table to properties
    op.execute("""
        INSERT INTO properties (id, politician_id, type, entity_id, statement_id, created_at, updated_at)
        SELECT gen_random_uuid(), politician_id, 'CITIZENSHIP', country_id, statement_id, created_at, updated_at
        FROM has_citizenship;
    """)

    # 8. Migrate evaluation data to new evaluations table
    # First, migrate property evaluations (already exist in property_evaluations)
    op.execute("""
        INSERT INTO evaluations (id, user_id, is_confirmed, property_id, created_at, updated_at)
        SELECT id, user_id, is_confirmed, property_id, created_at, updated_at
        FROM property_evaluations;
    """)

    # 9. Migrate position evaluations
    op.execute("""
        INSERT INTO evaluations (id, user_id, is_confirmed, property_id, created_at, updated_at)
        SELECT pe.id, pe.user_id, pe.is_confirmed, p.id, pe.created_at, pe.updated_at
        FROM position_evaluations pe
        JOIN holds_position hp ON pe.holds_position_id = hp.id
        JOIN properties p ON p.politician_id = hp.politician_id
            AND p.entity_id = hp.position_id
            AND p.type = 'POSITION'
            AND p.statement_id IS NOT DISTINCT FROM hp.statement_id;
    """)

    # 10. Migrate birthplace evaluations
    op.execute("""
        INSERT INTO evaluations (id, user_id, is_confirmed, property_id, created_at, updated_at)
        SELECT be.id, be.user_id, be.is_confirmed, p.id, be.created_at, be.updated_at
        FROM birthplace_evaluations be
        JOIN born_at ba ON be.born_at_id = ba.id
        JOIN properties p ON p.politician_id = ba.politician_id
            AND p.entity_id = ba.location_id
            AND p.type = 'BIRTHPLACE'
            AND p.statement_id IS NOT DISTINCT FROM ba.statement_id;
    """)

    # 11. Drop old tables
    op.drop_table("position_evaluations")
    op.drop_table("birthplace_evaluations")
    op.drop_table("property_evaluations")
    op.drop_table("holds_position")
    op.drop_table("born_at")
    op.drop_table("has_citizenship")

    # 12. Add check constraint to ensure correct field usage based on type
    op.execute("""
        ALTER TABLE properties ADD CONSTRAINT check_property_fields
        CHECK (
            (type IN ('BIRTH_DATE', 'DEATH_DATE') AND value IS NOT NULL AND entity_id IS NULL)
            OR
            (type IN ('BIRTHPLACE', 'POSITION', 'CITIZENSHIP') AND entity_id IS NOT NULL AND value IS NULL)
        );
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # This is a complex migration that would be very difficult to reverse
    # Given the data consolidation and model changes, we'll implement a basic reversal
    # that recreates the tables but doesn't restore the original data

    # Remove check constraint
    op.execute(
        "ALTER TABLE properties DROP CONSTRAINT IF EXISTS check_property_fields;"
    )

    # Recreate old tables (structure only, data would need manual restoration)
    op.create_table(
        "has_citizenship",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("politician_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("country_id", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("statement_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["country_id"], ["countries.wikidata_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"], ["politicians.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "born_at",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("politician_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", sa.String(), nullable=False),
        sa.Column("archived_page_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("proof_line", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("statement_id", sa.String(), nullable=True),
        sa.Column("qualifiers_json", sa.JSON(), nullable=True),
        sa.Column("references_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["archived_page_id"],
            ["archived_pages.id"],
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.wikidata_id"],
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"], ["politicians.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "holds_position",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("politician_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("position_id", sa.String(), nullable=False),
        sa.Column("archived_page_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("proof_line", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("statement_id", sa.String(), nullable=True),
        sa.Column("qualifiers_json", sa.JSON(), nullable=True),
        sa.Column("references_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["archived_page_id"],
            ["archived_pages.id"],
        ),
        sa.ForeignKeyConstraint(
            ["politician_id"], ["politicians.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.wikidata_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Recreate evaluation tables
    op.create_table(
        "property_evaluations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("property_id", sa.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "position_evaluations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("holds_position_id", sa.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["holds_position_id"],
            ["holds_position.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "birthplace_evaluations",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("born_at_id", sa.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["born_at_id"],
            ["born_at.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Drop new tables
    op.drop_table("evaluations")

    # Remove entity_id from properties
    op.drop_constraint("properties_entity_id_fkey", "properties")
    op.drop_column("properties", "entity_id")

    # Make value column non-nullable again
    op.alter_column("properties", "value", nullable=False)
