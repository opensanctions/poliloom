"""Service for importing politician data into the database."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
import csv
import json
import time

from ..models import (
    Politician,
    Property,
    Position,
    HoldsPosition,
    Source,
    Country,
    HasCitizenship,
    Location,
    BornAt,
)
from ..database import SessionLocal
from .wikidata import WikidataClient

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing politician data from Wikidata."""

    def __init__(self):
        self.wikidata_client = WikidataClient()

    def import_politician_by_id(self, wikidata_id: str) -> Optional[str]:
        """
        Import a politician from Wikidata by their ID.
        Only links politician to positions that already exist in the database.

        Returns:
            The politician's database ID if successful, None otherwise.
        """
        # Fetch data from Wikidata
        politician_data = self.wikidata_client.get_politician_by_id(wikidata_id)
        if not politician_data:
            logger.error(f"Could not fetch politician data for {wikidata_id}")
            return None

        db = SessionLocal()
        try:
            # Check if politician already exists
            existing = (
                db.query(Politician)
                .filter_by(wikidata_id=politician_data["wikidata_id"])
                .first()
            )

            if existing:
                logger.info(f"Politician {wikidata_id} already exists in database")
                return existing.id

            # Create politician record
            politician = self._create_politician(db, politician_data)

            # Create property records
            self._create_properties(
                db, politician, politician_data.get("properties", [])
            )

            # Create citizenship records
            self._create_citizenships(
                db, politician, politician_data.get("citizenships", [])
            )

            # Link to existing positions only
            self._link_to_existing_positions(
                db, politician, politician_data.get("positions", [])
            )

            # Link to existing birthplace location only
            self._link_to_existing_birthplace(
                db, politician, politician_data.get("birthplace")
            )

            # Create source records for Wikipedia links
            self._create_sources(
                db, politician, politician_data.get("wikipedia_links", [])
            )

            db.commit()
            logger.info(
                f"Successfully imported politician {wikidata_id} as {politician.id}"
            )
            return politician.id

        except Exception as e:
            db.rollback()
            logger.error(f"Error importing politician {wikidata_id}: {e}")
            return None
        finally:
            db.close()

    def _create_politician(self, db: Session, data: Dict[str, Any]) -> Politician:
        """Create a politician record."""
        politician = Politician(
            name=data["name"],
            wikidata_id=data["wikidata_id"],
            is_deceased=data.get("is_deceased", False),
        )
        db.add(politician)
        db.flush()  # Get the ID
        return politician

    def _create_properties(self, db: Session, politician: Politician, properties: list):
        """Create property records for the politician."""
        for prop_data in properties:
            if prop_data.get("value"):  # Only create if there's a value
                prop = Property(
                    politician_id=politician.id,
                    type=prop_data["type"],
                    value=prop_data["value"],
                    is_extracted=False,  # From Wikidata, so considered confirmed
                )
                db.add(prop)

    def _create_citizenships(
        self, db: Session, politician: Politician, citizenships: list
    ):
        """Create citizenship records for the politician."""
        for country_code in citizenships:
            if country_code:  # Only create if there's a value
                # Get or create the country
                country = self._get_or_create_country(db, country_code)
                if country:
                    # Check if citizenship relationship already exists
                    existing_citizenship = (
                        db.query(HasCitizenship)
                        .filter_by(politician_id=politician.id, country_id=country.id)
                        .first()
                    )

                    if not existing_citizenship:
                        citizenship = HasCitizenship(
                            politician_id=politician.id, country_id=country.id
                        )
                        db.add(citizenship)

    def _link_to_existing_positions(
        self, db: Session, politician: Politician, positions: list
    ):
        """Link politician to existing positions only - do not create new positions."""
        for pos_data in positions:
            # Check if position already exists
            position = (
                db.query(Position)
                .filter_by(wikidata_id=pos_data["wikidata_id"])
                .first()
            )

            if position:
                # Only create holds_position relationship if position exists
                holds_position = HoldsPosition(
                    politician_id=politician.id,
                    position_id=position.id,
                    start_date=pos_data.get("start_date"),
                    end_date=pos_data.get("end_date"),
                    is_extracted=False,  # From Wikidata, so considered confirmed
                )
                db.add(holds_position)
                logger.debug(
                    f"Linked politician {politician.name} to existing position {position.name}"
                )
            else:
                logger.debug(
                    f"Position {pos_data['name']} ({pos_data['wikidata_id']}) not found in database - skipping"
                )

    def _link_to_existing_birthplace(
        self,
        db: Session,
        politician: Politician,
        birthplace_data: Optional[Dict[str, Any]],
    ):
        """Link politician to existing birthplace location only - do not create new locations."""
        if not birthplace_data:
            return

        # Check if location already exists
        location = (
            db.query(Location)
            .filter_by(wikidata_id=birthplace_data["wikidata_id"])
            .first()
        )

        if location:
            # Only create born_at relationship if location exists
            born_at = BornAt(
                politician_id=politician.id,
                location_id=location.id,
                is_extracted=False,  # From Wikidata, so considered confirmed
            )
            db.add(born_at)
            logger.debug(
                f"Linked politician {politician.name} to birthplace {location.name}"
            )
        else:
            logger.debug(
                f"Birthplace {birthplace_data['name']} ({birthplace_data['wikidata_id']}) not found in database - skipping"
            )

    def _get_or_create_country(
        self, db: Session, country_code: str
    ) -> Optional[Country]:
        """Get existing country or create it on-demand from country code."""
        if not country_code:
            return None

        country_code = country_code.upper()

        # Check if country already exists
        country = db.query(Country).filter_by(iso_code=country_code).first()
        if country:
            return country

        # Create new country with basic info
        # For now, we'll use the country code as the name placeholder
        # In a production system, you might want to use a country name lookup library
        try:
            import pycountry

            country_info = pycountry.countries.get(alpha_2=country_code)
            country_name = country_info.name if country_info else country_code
        except ImportError:
            # Fallback if pycountry is not available
            country_name = country_code

        country = Country(
            name=country_name,
            iso_code=country_code,
            wikidata_id=None,  # Will be populated later if needed
        )
        db.add(country)
        db.flush()  # Get the ID
        logger.info(f"Created country on-demand: {country_name} ({country_code})")
        return country


    def _create_sources(
        self, db: Session, politician: Politician, wikipedia_links: list
    ):
        """Create source records for Wikipedia links."""
        for link in wikipedia_links:
            try:
                # Check if source already exists
                source = db.query(Source).filter_by(url=link["url"]).first()

                if not source:
                    source = Source(url=link["url"])
                    db.add(source)
                    db.flush()  # Get the ID

                # Link source to politician
                if source not in politician.sources:
                    politician.sources.append(source)

            except IntegrityError:
                # Source already exists, skip
                db.rollback()
                continue

    def import_all_positions(self) -> int:
        """
        Import all political positions from Wikidata.

        Returns:
            Number of positions imported.
        """
        # Fetch all positions from Wikidata
        positions_data = self.wikidata_client.get_all_positions()
        if not positions_data:
            logger.error("Could not fetch positions data from Wikidata")
            return 0

        db = SessionLocal()
        try:
            imported_count = 0

            for position_data in positions_data:
                # Check if position already exists
                existing = (
                    db.query(Position)
                    .filter_by(wikidata_id=position_data["wikidata_id"])
                    .first()
                )

                if existing:
                    logger.debug(f"Position {position_data['name']} already exists")
                    continue

                # Create position record
                position = Position(
                    name=position_data["name"], wikidata_id=position_data["wikidata_id"]
                )

                try:
                    db.add(position)
                    db.flush()  # Get the ID and check constraints


                    imported_count += 1
                except IntegrityError:
                    # Position already exists (race condition), skip
                    db.rollback()
                    logger.debug(
                        f"Position {position_data['name']} already exists (caught during flush)"
                    )
                    continue

                # Process in batches to avoid memory issues
                if imported_count % 1000 == 0:
                    db.commit()
                    logger.info(f"Imported {imported_count} positions so far...")

            # Commit remaining positions

            db.commit()
            logger.info(f"Successfully imported {imported_count} positions")
            return imported_count

        except Exception as e:
            db.rollback()
            logger.error(f"Error importing positions: {e}")
            return 0
        finally:
            db.close()

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
        db = SessionLocal()
        try:
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
                        logger.debug(f"Skipping position {caption} with is_pep=FALSE")
                        continue

                    # Check if position already exists
                    existing = (
                        db.query(Position).filter_by(wikidata_id=entity_id).first()
                    )

                    if existing:
                        logger.debug(f"Position {caption} ({entity_id}) already exists")
                        continue


                    # Create position record
                    position = Position(name=caption, wikidata_id=entity_id)
                    db.add(position)
                    db.flush()  # Get the ID


                    imported_count += 1

                    # Process in batches to avoid memory issues
                    if imported_count % 1000 == 0:
                        db.commit()
                        logger.info(f"Imported {imported_count} positions so far...")

            # Commit remaining positions

            db.commit()
            logger.info(f"Successfully imported {imported_count} positions from CSV")
            return imported_count

        except Exception as e:
            db.rollback()
            logger.error(f"Error importing positions from CSV: {e}")
            return 0
        finally:
            db.close()

    def import_all_locations(self) -> int:
        """
        Import all geographic locations from Wikidata using pagination.

        Returns:
            Number of locations imported.
        """
        db = SessionLocal()
        try:
            imported_count = 0
            offset = 0
            page_size = 10000

            while True:
                # Add small delay between requests to be respectful to Wikidata
                if offset > 0:
                    time.sleep(0.5)  # 500ms delay between batches

                # Fetch locations from Wikidata in batches
                locations_data = self.wikidata_client.get_all_locations(
                    limit=page_size, offset=offset
                )

                if not locations_data:
                    logger.info(f"No more locations to fetch at offset {offset}")
                    break

                for location_data in locations_data:
                    # Check if location already exists
                    existing = (
                        db.query(Location)
                        .filter_by(wikidata_id=location_data["wikidata_id"])
                        .first()
                    )

                    if existing:
                        logger.debug(f"Location {location_data['name']} already exists")
                        continue

                    # Create location record
                    location = Location(
                        name=location_data["name"],
                        wikidata_id=location_data["wikidata_id"],
                    )

                    try:
                        db.add(location)
                        db.flush()  # Force database check immediately
                        imported_count += 1
                    except IntegrityError:
                        # Location already exists (race condition), skip
                        db.rollback()
                        logger.debug(
                            f"Location {location_data['name']} already exists (caught during flush)"
                        )
                        continue

                    # Process in batches to avoid memory issues
                    if imported_count % 1000 == 0:
                        db.commit()
                        logger.info(f"Imported {imported_count} locations so far...")

                # If we got fewer results than the page size, we're done
                if len(locations_data) < page_size:
                    logger.info(
                        f"Reached end of results with {len(locations_data)} locations in final batch"
                    )
                    break

                offset += page_size
                logger.info(f"Moving to next page with offset {offset}")

            # Commit remaining locations

            db.commit()
            logger.info(f"Successfully imported {imported_count} locations")
            return imported_count

        except Exception as e:
            db.rollback()
            logger.error(f"Error importing locations: {e}")
            return 0
        finally:
            db.close()

    def close(self):
        """Close the Wikidata client."""
        self.wikidata_client.close()
