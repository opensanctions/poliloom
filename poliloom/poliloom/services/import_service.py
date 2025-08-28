"""Service for importing politician data into the database."""

import logging
import csv

from ..models import Position
from ..database import get_engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing politician data from Wikidata."""

    def __init__(self):
        pass

    def import_positions_from_csv(self, csv_file_path: str) -> int:
        """
        Import positions from a CSV file.

        Expected CSV format:
        "id","entity_id","caption","is_pep","countries","topics","dataset","created_at","modified_at","modified_by","deleted_at"

        Args:
            csv_file_path: Path to the CSV file

        Returns:
            Number of positions imported.
        """
        try:
            with Session(get_engine()) as db:
                imported_count = 0

                with open(csv_file_path, "r", encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)

                    for row in reader:
                        entity_id = row.get("entity_id", "").strip()
                        caption = row.get("caption", "").strip()
                        is_pep = row.get("is_pep", "").strip()

                        # Skip rows without required fields
                        if not entity_id or not caption:
                            logger.debug(
                                f"Skipping row with missing entity_id or caption: {row}"
                            )
                            continue

                        # Skip positions with is_pep = FALSE
                        if is_pep == "FALSE":
                            logger.debug(
                                f"Skipping position {caption} with is_pep=FALSE"
                            )
                            continue

                        # Check if position already exists
                        existing = (
                            db.query(Position).filter_by(wikidata_id=entity_id).first()
                        )

                        if existing:
                            logger.debug(
                                f"Position {caption} ({entity_id}) already exists"
                            )
                            continue

                        # Create position record
                        position = Position(name=caption, wikidata_id=entity_id)
                        db.add(position)
                        db.flush()  # Get the ID

                        imported_count += 1

                        # Process in batches to avoid memory issues
                        if imported_count % 1000 == 0:
                            # Flush to database but don't commit yet - let context manager handle it
                            db.flush()
                            logger.info(
                                f"Imported {imported_count} positions so far..."
                            )

                # Commit remaining positions
                db.commit()
                logger.info(
                    f"Successfully imported {imported_count} positions from CSV"
                )
                return imported_count

        except Exception as e:
            logger.error(f"Error importing positions from CSV: {e}")
            return 0

    def close(self):
        """Close the service."""
        pass
