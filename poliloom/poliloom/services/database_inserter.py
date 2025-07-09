"""Database batch insertion operations for dump processing."""

import logging
import time
from datetime import datetime, timezone
from typing import List

from .worker_manager import get_worker_session

logger = logging.getLogger(__name__)


class DatabaseInserter:
    """Handles batch database insertions for dump processing."""

    def insert_positions_batch(self, positions: List[dict]) -> None:
        """Insert a batch of positions into the database."""
        if not positions:
            return

        from ..models import Position
        from sqlalchemy.exc import DisconnectionError

        max_retries = 3
        for attempt in range(max_retries):
            session = get_worker_session()
            try:
                # Check for existing positions to avoid duplicates
                existing_wikidata_ids = {
                    result[0]
                    for result in session.query(Position.wikidata_id)
                    .filter(
                        Position.wikidata_id.in_([p["wikidata_id"] for p in positions])
                    )
                    .all()
                }

                # Filter out duplicates
                new_positions = [
                    p
                    for p in positions
                    if p["wikidata_id"] not in existing_wikidata_ids
                ]

                if new_positions:
                    # Create Position objects
                    position_objects = [
                        Position(
                            wikidata_id=p["wikidata_id"],
                            name=p["name"],
                            embedding=None,  # Will be generated later
                        )
                        for p in new_positions
                    ]

                    session.add_all(position_objects)
                    session.commit()
                    logger.debug(f"Inserted {len(new_positions)} new positions")
                # Skip logging when no new positions - this is normal
                break  # Success, exit retry loop

            except (DisconnectionError, Exception) as e:
                session.rollback()
                logger.error(
                    f"Error inserting positions batch (attempt {attempt + 1}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Wait before retry
            finally:
                session.close()

    def insert_locations_batch(self, locations: List[dict]) -> None:
        """Insert a batch of locations into the database."""
        if not locations:
            return

        from ..models import Location
        from sqlalchemy.exc import DisconnectionError

        max_retries = 3
        for attempt in range(max_retries):
            session = get_worker_session()
            try:
                # Check for existing locations to avoid duplicates
                existing_wikidata_ids = {
                    result[0]
                    for result in session.query(Location.wikidata_id)
                    .filter(
                        Location.wikidata_id.in_(
                            [loc["wikidata_id"] for loc in locations]
                        )
                    )
                    .all()
                }

                # Filter out duplicates
                new_locations = [
                    loc
                    for loc in locations
                    if loc["wikidata_id"] not in existing_wikidata_ids
                ]

                if new_locations:
                    # Create Location objects
                    location_objects = [
                        Location(
                            wikidata_id=loc["wikidata_id"],
                            name=loc["name"],
                            embedding=None,  # Will be generated later
                        )
                        for loc in new_locations
                    ]

                    session.add_all(location_objects)
                    session.commit()
                    logger.debug(f"Inserted {len(new_locations)} new locations")
                # Skip logging when no new locations - this is normal
                break  # Success, exit retry loop

            except (DisconnectionError, Exception) as e:
                session.rollback()
                logger.error(
                    f"Error inserting locations batch (attempt {attempt + 1}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Wait before retry
            finally:
                session.close()

    def insert_countries_batch(self, countries: List[dict]) -> None:
        """Insert a batch of countries into the database using ON CONFLICT."""
        if not countries:
            return

        from ..models import Country
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy.exc import DisconnectionError

        max_retries = 3
        for attempt in range(max_retries):
            session = get_worker_session()
            try:
                # Prepare data for bulk insert
                country_data = [
                    {
                        "wikidata_id": c["wikidata_id"],
                        "name": c["name"],
                        "iso_code": c["iso_code"],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                    for c in countries
                ]

                # Use PostgreSQL's ON CONFLICT to handle duplicates
                # We need to handle both wikidata_id and iso_code constraints
                # Since PostgreSQL doesn't support multiple ON CONFLICT clauses,
                # we'll use a more robust approach with ON CONFLICT DO NOTHING
                stmt = insert(Country).values(country_data)
                stmt = stmt.on_conflict_do_nothing()

                result = session.execute(stmt)
                session.commit()

                inserted_count = result.rowcount
                logger.debug(
                    f"Inserted {inserted_count} new countries (skipped {len(countries) - inserted_count} duplicates)"
                )
                break  # Success, exit retry loop

            except (DisconnectionError, Exception) as e:
                session.rollback()
                logger.error(
                    f"Error inserting countries batch (attempt {attempt + 1}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Wait before retry
            finally:
                session.close()
