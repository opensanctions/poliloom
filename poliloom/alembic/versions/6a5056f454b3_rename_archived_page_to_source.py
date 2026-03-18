"""rename archived_page to source

Revision ID: 6a5056f454b3
Revises: c672027b4236
Create Date: 2026-03-18 17:53:58.206193

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6a5056f454b3"
down_revision: Union[str, None] = "c672027b4236"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Rename enum types ---
    op.execute("ALTER TYPE archivedpagestatus RENAME TO sourcestatus")
    op.execute("ALTER TYPE archivedpageerror RENAME TO sourceerror")

    # --- Rename tables ---
    op.rename_table("archived_pages", "sources")
    op.rename_table("politician_archived_pages", "politician_sources")
    op.rename_table("archived_page_languages", "source_languages")

    # --- Rename columns ---
    op.alter_column(
        "politician_sources", "archived_page_id", new_column_name="source_id"
    )
    op.alter_column("source_languages", "archived_page_id", new_column_name="source_id")
    op.alter_column(
        "property_references", "archived_page_id", new_column_name="source_id"
    )

    # --- Rename constraints ---
    op.execute(
        "ALTER TABLE sources RENAME CONSTRAINT ck_archived_pages_http_status_code_requires_fetch_error TO ck_sources_http_status_code_requires_fetch_error"
    )

    # Rename unique constraint on property_references
    op.execute(
        "ALTER TABLE property_references RENAME CONSTRAINT uq_property_ref_property_page TO uq_property_ref_property_source"
    )

    # --- Rename indexes ---
    op.execute(
        "ALTER INDEX ix_archived_pages_content_hash RENAME TO ix_sources_content_hash"
    )
    op.execute("ALTER INDEX ix_archived_pages_user_id RENAME TO ix_sources_user_id")
    op.execute(
        "ALTER INDEX ix_archived_pages_wikipedia_project_id RENAME TO ix_sources_wikipedia_project_id"
    )
    op.execute(
        "ALTER INDEX ix_archived_page_languages_language_id RENAME TO ix_source_languages_language_id"
    )
    op.execute(
        "ALTER INDEX idx_property_references_archived_page_id RENAME TO idx_property_references_source_id"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # --- Rename indexes back ---
    op.execute(
        "ALTER INDEX idx_property_references_source_id RENAME TO idx_property_references_archived_page_id"
    )
    op.execute(
        "ALTER INDEX ix_source_languages_language_id RENAME TO ix_archived_page_languages_language_id"
    )
    op.execute(
        "ALTER INDEX ix_sources_wikipedia_project_id RENAME TO ix_archived_pages_wikipedia_project_id"
    )
    op.execute("ALTER INDEX ix_sources_user_id RENAME TO ix_archived_pages_user_id")
    op.execute(
        "ALTER INDEX ix_sources_content_hash RENAME TO ix_archived_pages_content_hash"
    )

    # --- Rename constraints back ---
    op.execute(
        "ALTER TABLE property_references RENAME CONSTRAINT uq_property_ref_property_source TO uq_property_ref_property_page"
    )
    op.execute(
        "ALTER TABLE sources RENAME CONSTRAINT ck_sources_http_status_code_requires_fetch_error TO ck_archived_pages_http_status_code_requires_fetch_error"
    )

    # --- Rename columns back ---
    op.alter_column(
        "property_references", "source_id", new_column_name="archived_page_id"
    )
    op.alter_column("source_languages", "source_id", new_column_name="archived_page_id")
    op.alter_column(
        "politician_sources", "source_id", new_column_name="archived_page_id"
    )

    # --- Rename tables back ---
    op.rename_table("source_languages", "archived_page_languages")
    op.rename_table("politician_sources", "politician_archived_pages")
    op.rename_table("sources", "archived_pages")

    # --- Rename enum types back ---
    op.execute("ALTER TYPE sourceerror RENAME TO archivedpageerror")
    op.execute("ALTER TYPE sourcestatus RENAME TO archivedpagestatus")
