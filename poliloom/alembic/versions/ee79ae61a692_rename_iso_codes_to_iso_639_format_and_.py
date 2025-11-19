"""rename_iso_codes_to_iso_639_format_and_add_iso_639_2

Revision ID: ee79ae61a692
Revises: 4e5af7bd6700
Create Date: 2025-11-19 21:09:53.142181

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ee79ae61a692"
down_revision: Union[str, None] = "4e5af7bd6700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Rename iso1_code -> iso_639_1
    Rename iso3_code -> iso_639_2 (it currently contains P219/ISO 639-2 data)
    Add iso_639_3 for P220 data
    """
    # Process languages table
    # Rename columns
    op.alter_column("languages", "iso1_code", new_column_name="iso_639_1")
    op.alter_column("languages", "iso3_code", new_column_name="iso_639_2")

    # Add new iso_639_3 column
    op.add_column("languages", sa.Column("iso_639_3", sa.String(), nullable=True))

    # Update indexes for languages
    op.drop_index(op.f("ix_languages_iso1_code"), table_name="languages")
    op.drop_index(op.f("ix_languages_iso3_code"), table_name="languages")
    op.create_index(
        op.f("ix_languages_iso_639_1"), "languages", ["iso_639_1"], unique=False
    )
    op.create_index(
        op.f("ix_languages_iso_639_2"), "languages", ["iso_639_2"], unique=False
    )
    op.create_index(
        op.f("ix_languages_iso_639_3"), "languages", ["iso_639_3"], unique=False
    )

    # Process archived_pages table
    # Rename columns
    op.alter_column("archived_pages", "iso1_code", new_column_name="iso_639_1")
    op.alter_column("archived_pages", "iso3_code", new_column_name="iso_639_2")

    # Add new iso_639_3 column
    op.add_column("archived_pages", sa.Column("iso_639_3", sa.String(), nullable=True))

    # Update indexes for archived_pages
    op.drop_index(op.f("ix_archived_pages_iso1_code"), table_name="archived_pages")
    op.drop_index(op.f("ix_archived_pages_iso3_code"), table_name="archived_pages")
    op.create_index(
        op.f("ix_archived_pages_iso_639_1"),
        "archived_pages",
        ["iso_639_1"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archived_pages_iso_639_2"),
        "archived_pages",
        ["iso_639_2"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archived_pages_iso_639_3"),
        "archived_pages",
        ["iso_639_3"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Process archived_pages table
    op.drop_index(op.f("ix_archived_pages_iso_639_3"), table_name="archived_pages")
    op.drop_index(op.f("ix_archived_pages_iso_639_2"), table_name="archived_pages")
    op.drop_index(op.f("ix_archived_pages_iso_639_1"), table_name="archived_pages")
    op.create_index(
        op.f("ix_archived_pages_iso3_code"),
        "archived_pages",
        ["iso3_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_archived_pages_iso1_code"),
        "archived_pages",
        ["iso1_code"],
        unique=False,
    )

    op.drop_column("archived_pages", "iso_639_3")
    op.alter_column("archived_pages", "iso_639_2", new_column_name="iso3_code")
    op.alter_column("archived_pages", "iso_639_1", new_column_name="iso1_code")

    # Process languages table
    op.drop_index(op.f("ix_languages_iso_639_3"), table_name="languages")
    op.drop_index(op.f("ix_languages_iso_639_2"), table_name="languages")
    op.drop_index(op.f("ix_languages_iso_639_1"), table_name="languages")
    op.create_index(
        op.f("ix_languages_iso3_code"), "languages", ["iso3_code"], unique=False
    )
    op.create_index(
        op.f("ix_languages_iso1_code"), "languages", ["iso1_code"], unique=False
    )

    op.drop_column("languages", "iso_639_3")
    op.alter_column("languages", "iso_639_2", new_column_name="iso3_code")
    op.alter_column("languages", "iso_639_1", new_column_name="iso1_code")
