"""preserve_evaluated_records_during_reimport

Revision ID: 97de81eb2339
Revises: 6b960f49e7df
Create Date: 2025-01-19 16:17:27.089041

This migration:
1. Deletes all non-evaluated records from holds_position, born_at, properties, and has_citizenship
2. Preserves all records that have associated evaluations
3. Allows for re-import of Wikidata dump with statement_ids
4. Keeps evaluated records as training data even if they lack statement_ids
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "97de81eb2339"
down_revision: Union[str, None] = "6238599a40c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Delete all records that don't have evaluations, preserving evaluated records
    for training data purposes.
    """

    # Delete non-evaluated has_citizenship records (no evaluation table exists for this)
    op.execute("""
        DELETE FROM has_citizenship
        WHERE statement_id IS NULL
    """)

    # Delete non-evaluated holds_position records
    op.execute("""
        DELETE FROM holds_position
        WHERE id NOT IN (
            SELECT DISTINCT holds_position_id
            FROM position_evaluations
        )
        AND statement_id IS NULL
    """)

    # Delete non-evaluated born_at records
    op.execute("""
        DELETE FROM born_at
        WHERE id NOT IN (
            SELECT DISTINCT born_at_id
            FROM birthplace_evaluations
        )
        AND statement_id IS NULL
    """)

    # Delete non-evaluated properties records
    op.execute("""
        DELETE FROM properties
        WHERE id NOT IN (
            SELECT DISTINCT property_id
            FROM property_evaluations
        )
        AND statement_id IS NULL
    """)


def downgrade() -> None:
    """
    This migration is not reversible as it deletes data.
    The data can only be restored by re-importing from Wikidata dump.
    """
    raise NotImplementedError(
        "This migration cannot be reversed. Data must be restored from Wikidata dump."
    )
