"""rename_campaign_source_to_source_make_campaign_id_nullable

Revision ID: c7fe72738f78
Revises: a90debddd6e1
Create Date: 2025-12-09 20:51:42.933385

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7fe72738f78"
down_revision: Union[str, None] = "a90debddd6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename campaign_sources to sources and make campaign_id nullable."""

    # 1. Drop the old CHECK constraint on archived_pages first (references old column name)
    op.drop_constraint("check_exactly_one_source", "archived_pages", type_="check")

    # 2. Rename campaign_source_id to source_id in archived_pages
    op.alter_column("archived_pages", "campaign_source_id", new_column_name="source_id")

    # 3. Drop old indexes on archived_pages
    op.drop_index(
        op.f("ix_archived_pages_campaign_source_id"), table_name="archived_pages"
    )

    # 4. Create new index with new name
    op.create_index(
        op.f("ix_archived_pages_source_id"),
        "archived_pages",
        ["source_id"],
        unique=False,
    )

    # 5. Drop old trigger on campaign_sources before rename
    op.execute(
        "DROP TRIGGER IF EXISTS trigger_update_campaign_sources_updated_at ON campaign_sources;"
    )

    # 6. Drop old indexes on campaign_sources
    op.drop_index(
        op.f("ix_campaign_sources_campaign_id"), table_name="campaign_sources"
    )
    op.drop_index(
        op.f("ix_campaign_sources_politician_id"), table_name="campaign_sources"
    )

    # 7. Rename the table
    op.rename_table("campaign_sources", "sources")

    # 8. Make campaign_id nullable (was NOT NULL before)
    op.alter_column("sources", "campaign_id", nullable=True)

    # 9. Create new indexes with new names
    op.create_index(
        op.f("ix_sources_campaign_id"), "sources", ["campaign_id"], unique=False
    )
    op.create_index(
        op.f("ix_sources_politician_id"), "sources", ["politician_id"], unique=False
    )

    # 10. Add CHECK constraint: at least one of politician_id or campaign_id must be set
    op.create_check_constraint(
        "check_source_has_politician_or_campaign",
        "sources",
        "NOT (politician_id IS NULL AND campaign_id IS NULL)",
    )

    # 11. Re-create the CHECK constraint on archived_pages with new column name
    op.create_check_constraint(
        "check_exactly_one_source",
        "archived_pages",
        "(wikipedia_source_id IS NOT NULL AND source_id IS NULL) OR "
        "(wikipedia_source_id IS NULL AND source_id IS NOT NULL)",
    )

    # 12. Create updated_at trigger for renamed table
    op.execute("""
        CREATE OR REPLACE TRIGGER trigger_update_sources_updated_at
        BEFORE UPDATE ON sources
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Revert sources back to campaign_sources."""

    # 1. Drop the CHECK constraints
    op.drop_constraint("check_exactly_one_source", "archived_pages", type_="check")
    op.drop_constraint(
        "check_source_has_politician_or_campaign", "sources", type_="check"
    )

    # 2. Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trigger_update_sources_updated_at ON sources;")

    # 3. Drop indexes on sources
    op.drop_index(op.f("ix_sources_politician_id"), table_name="sources")
    op.drop_index(op.f("ix_sources_campaign_id"), table_name="sources")

    # 4. Make campaign_id NOT NULL again (will fail if there are rows with NULL)
    op.alter_column("sources", "campaign_id", nullable=False)

    # 5. Rename table back
    op.rename_table("sources", "campaign_sources")

    # 6. Create old indexes
    op.create_index(
        op.f("ix_campaign_sources_campaign_id"),
        "campaign_sources",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_sources_politician_id"),
        "campaign_sources",
        ["politician_id"],
        unique=False,
    )

    # 7. Drop new index on archived_pages
    op.drop_index(op.f("ix_archived_pages_source_id"), table_name="archived_pages")

    # 8. Rename column back
    op.alter_column("archived_pages", "source_id", new_column_name="campaign_source_id")

    # 9. Create old index
    op.create_index(
        op.f("ix_archived_pages_campaign_source_id"),
        "archived_pages",
        ["campaign_source_id"],
        unique=False,
    )

    # 10. Re-create CHECK constraint with old column name
    op.create_check_constraint(
        "check_exactly_one_source",
        "archived_pages",
        "(wikipedia_source_id IS NOT NULL AND campaign_source_id IS NULL) OR "
        "(wikipedia_source_id IS NULL AND campaign_source_id IS NOT NULL)",
    )

    # 11. Create trigger for renamed table
    op.execute("""
        CREATE OR REPLACE TRIGGER trigger_update_campaign_sources_updated_at
        BEFORE UPDATE ON campaign_sources
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
