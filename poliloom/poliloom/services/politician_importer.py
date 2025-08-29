"""Wikidata politician importing service."""

import logging
import multiprocessing as mp
from typing import Tuple
from datetime import datetime, date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .dump_reader import DumpReader
from ..database import get_engine
from ..models import (
    Position,
    Location,
    Country,
    Politician,
    Property,
    HoldsPosition,
    HasCitizenship,
    BornAt,
    WikipediaLink,
)
from ..wikidata_entity import WikidataEntity

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000


def _insert_politicians_batch(politicians: list[dict]) -> None:
    """Insert a batch of politicians into the database."""
    if not politicians:
        return

    with Session(get_engine()) as session:
        # Use PostgreSQL UPSERT for politicians
        stmt = insert(Politician).values(
            [
                {
                    "wikidata_id": p["wikidata_id"],
                    "name": p["name"],
                }
                for p in politicians
            ]
        )

        # On conflict, update the name (in case it changed in Wikidata)
        stmt = stmt.on_conflict_do_update(
            index_elements=["wikidata_id"],
            set_={
                "name": stmt.excluded.name,
            },
        )

        session.execute(stmt)
        session.flush()

        # Get all politician objects (both new and existing)
        politician_objects = (
            session.query(Politician)
            .filter(Politician.wikidata_id.in_([p["wikidata_id"] for p in politicians]))
            .all()
        )

        # Create mapping for easy lookup
        politician_map = {pol.wikidata_id: pol for pol in politician_objects}

        # Now process related data for each politician
        for politician_data in politicians:
            politician_obj = politician_map[politician_data["wikidata_id"]]

            # Handle relationships: need to check if they already exist to avoid duplicates
            # For re-imports, we want to add new relationships but not duplicate existing ones

            # Add properties using UPSERT - update only if NOT extracted (preserve user evaluations)
            for prop in politician_data.get("properties", []):
                prop_stmt = insert(Property).values(
                    politician_id=politician_obj.id,
                    type=prop["type"],
                    value=prop["value"],
                    value_precision=prop.get("value_precision"),
                    archived_page_id=None,
                )

                # Update only if archived_page_id is None (preserve extracted data)
                prop_stmt = prop_stmt.on_conflict_do_update(
                    index_elements=["politician_id", "type"],
                    set_={
                        "value": prop_stmt.excluded.value,
                        "value_precision": prop_stmt.excluded.value_precision,
                        "updated_at": prop_stmt.excluded.updated_at,
                    },
                    where=Property.archived_page_id.is_(None),
                )

                session.execute(prop_stmt)

            # Add positions - only link to existing positions
            for pos in politician_data.get("positions", []):
                position_obj = (
                    session.query(Position)
                    .filter_by(wikidata_id=pos["wikidata_id"])
                    .first()
                )

                if position_obj:
                    # Check if this exact relationship already exists
                    existing_position = (
                        session.query(HoldsPosition)
                        .filter_by(
                            politician_id=politician_obj.id,
                            position_id=position_obj.id,
                            start_date=pos.get("start_date"),
                            end_date=pos.get("end_date"),
                        )
                        .first()
                    )

                    if existing_position:
                        # Update precision if this is NOT extracted data (preserve user evaluations)
                        if existing_position.archived_page_id is None:
                            existing_position.start_date_precision = pos.get(
                                "start_date_precision"
                            )
                            existing_position.end_date_precision = pos.get(
                                "end_date_precision"
                            )
                    else:
                        # Insert new position relationship
                        holds_position = HoldsPosition(
                            politician_id=politician_obj.id,
                            position_id=position_obj.id,
                            start_date=pos.get("start_date"),
                            start_date_precision=pos.get("start_date_precision"),
                            end_date=pos.get("end_date"),
                            end_date_precision=pos.get("end_date_precision"),
                            archived_page_id=None,
                        )
                        session.add(holds_position)

            # Add citizenships - only link to existing countries
            for citizenship_id in politician_data.get("citizenships", []):
                country_obj = (
                    session.query(Country).filter_by(wikidata_id=citizenship_id).first()
                )

                if country_obj:
                    # Check if this citizenship already exists
                    existing_citizenship = (
                        session.query(HasCitizenship)
                        .filter_by(
                            politician_id=politician_obj.id,
                            country_id=country_obj.id,
                        )
                        .first()
                    )

                    if not existing_citizenship:
                        has_citizenship = HasCitizenship(
                            politician_id=politician_obj.id,
                            country_id=country_obj.id,
                        )
                        session.add(has_citizenship)

            # Add birthplace - only link to existing locations
            birthplace_id = politician_data.get("birthplace")
            if birthplace_id:
                location_obj = (
                    session.query(Location).filter_by(wikidata_id=birthplace_id).first()
                )

                if location_obj:
                    # Check if this birthplace already exists
                    existing_birthplace = (
                        session.query(BornAt)
                        .filter_by(
                            politician_id=politician_obj.id,
                            location_id=location_obj.id,
                        )
                        .first()
                    )

                    if not existing_birthplace:
                        born_at = BornAt(
                            politician_id=politician_obj.id,
                            location_id=location_obj.id,
                            archived_page_id=None,
                        )
                        session.add(born_at)

            # Add Wikipedia links
            for wiki_link in politician_data.get("wikipedia_links", []):
                # Check if this Wikipedia link already exists
                existing_link = (
                    session.query(WikipediaLink)
                    .filter_by(
                        politician_id=politician_obj.id,
                        url=wiki_link["url"],
                    )
                    .first()
                )

                if not existing_link:
                    wikipedia_link = WikipediaLink(
                        politician_id=politician_obj.id,
                        url=wiki_link["url"],
                        language_code=wiki_link.get("language", "en"),
                    )
                    session.add(wikipedia_link)

        session.commit()
        logger.debug(f"Processed {len(politicians)} politicians (upserted)")


def _process_politicians_chunk(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
    batch_size: int,
) -> Tuple[int, int]:
    """
    Process a specific byte range of the dump file for politician extraction.

    Each worker independently reads and parses its assigned chunk.
    Returns entity counts found in this chunk.
    """
    # Fix multiprocessing connection issues per SQLAlchemy docs:
    # https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork
    engine = get_engine()
    engine.dispose(close=False)

    dump_reader = DumpReader()

    politicians = []
    politician_count = 0
    entity_count = 0
    try:
        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntity
            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"Worker {worker_id}: processed {entity_count} entities")

            entity_id = entity.get_wikidata_id()
            if not entity_id:
                continue

            # Check if it's a politician
            if entity.is_politician():
                # Skip deceased politicians who died before 1950
                if entity.is_deceased:
                    death_claims = entity.get_truthy_claims("P570")
                    death_info = entity.extract_date_from_claims(death_claims)
                    if death_info:
                        try:
                            death_date_str = death_info["date"]
                            precision = death_info["precision"]

                            # Parse date based on precision
                            if precision >= 11:  # day precision
                                death_date = datetime.strptime(
                                    death_date_str, "%Y-%m-%d"
                                ).date()
                            elif precision == 10:  # month precision
                                death_date = datetime.strptime(
                                    death_date_str + "-01", "%Y-%m-%d"
                                ).date()
                            elif precision == 9:  # year precision
                                death_date = datetime.strptime(
                                    death_date_str + "-01-01", "%Y-%m-%d"
                                ).date()
                            else:
                                death_date = None

                            # Skip if died before 1950
                            if death_date and death_date < date(1950, 1, 1):
                                continue
                        except (ValueError, TypeError):
                            pass  # Include if we can't parse the date

                # Build complete politician dict with all relationships
                politician_data = {
                    "wikidata_id": entity.get_wikidata_id(),
                    "name": entity.get_entity_name(),
                    "properties": [],
                    "positions": [],
                    "citizenships": [],
                    "birthplace": None,
                    "wikipedia_links": [],
                }

                # Extract properties (birth date, death date, etc.)
                birth_claims = entity.get_truthy_claims("P569")
                if birth_claims:
                    birth_info = entity.extract_date_from_claims(birth_claims)
                    if birth_info:
                        politician_data["properties"].append(
                            {
                                "type": "birth_date",
                                "value": birth_info["date"],
                                "value_precision": birth_info["precision"],
                            }
                        )

                death_claims = entity.get_truthy_claims("P570")
                if death_claims:
                    death_info = entity.extract_date_from_claims(death_claims)
                    if death_info:
                        politician_data["properties"].append(
                            {
                                "type": "death_date",
                                "value": death_info["date"],
                                "value_precision": death_info["precision"],
                            }
                        )

                # Extract positions held
                position_claims = entity.get_truthy_claims("P39")
                for claim in position_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        position_id = claim["mainsnak"]["datavalue"]["value"]["id"]

                        # Extract start and end dates from qualifiers
                        start_date = None
                        start_date_precision = None
                        end_date = None
                        end_date_precision = None

                        if "qualifiers" in claim:
                            # Start date (P580)
                            if "P580" in claim["qualifiers"]:
                                start_qual = claim["qualifiers"]["P580"][0]
                                if "datavalue" in start_qual:
                                    start_info = entity.extract_date_from_datavalue(
                                        start_qual["datavalue"]
                                    )
                                    if start_info:
                                        start_date = start_info["date"]
                                        start_date_precision = start_info["precision"]

                            # End date (P582)
                            if "P582" in claim["qualifiers"]:
                                end_qual = claim["qualifiers"]["P582"][0]
                                if "datavalue" in end_qual:
                                    end_info = entity.extract_date_from_datavalue(
                                        end_qual["datavalue"]
                                    )
                                    if end_info:
                                        end_date = end_info["date"]
                                        end_date_precision = end_info["precision"]

                        politician_data["positions"].append(
                            {
                                "wikidata_id": position_id,
                                "start_date": start_date,
                                "start_date_precision": start_date_precision,
                                "end_date": end_date,
                                "end_date_precision": end_date_precision,
                            }
                        )

                # Extract citizenships
                citizenship_claims = entity.get_truthy_claims("P27")
                for claim in citizenship_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        citizenship_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        politician_data["citizenships"].append(citizenship_id)

                # Extract birthplace
                birthplace_claims = entity.get_truthy_claims("P19")
                if birthplace_claims:
                    claim = birthplace_claims[0]  # Take first birthplace
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        birthplace_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        politician_data["birthplace"] = birthplace_id

                # Extract Wikipedia links from sitelinks
                if hasattr(entity, "entity_data") and "sitelinks" in entity.entity_data:
                    for site_key, sitelink in entity.entity_data["sitelinks"].items():
                        if site_key.endswith("wiki"):  # Wikipedia sites
                            language = site_key.replace("wiki", "")
                            url = f"https://{language}.wikipedia.org/wiki/{sitelink['title'].replace(' ', '_')}"
                            politician_data["wikipedia_links"].append(
                                {
                                    "url": url,
                                    "language": language,
                                }
                            )

                politicians.append(politician_data)
                politician_count += 1

            # Process batches when they reach the batch size
            if len(politicians) >= batch_size:
                _insert_politicians_batch(politicians)
                politicians = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batch on successful completion
    if politicians:
        _insert_politicians_batch(politicians)

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    return politician_count, entity_count


class WikidataPoliticianImporter:
    """Extract politicians from the Wikidata dump using parallel processing."""

    def __init__(self):
        """Initialize the politician importer."""
        self.dump_reader = DumpReader()

    def extract_politicians_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 1000,
    ) -> int:
        """
        Extract politicians from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch

        Returns:
            Total count of extracted politicians
        """
        num_workers = mp.cpu_count()
        logger.info(f"Using parallel processing with {num_workers} workers")

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(processes=num_workers)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                _process_politicians_chunk,
                [
                    (
                        dump_file_path,
                        start,
                        end,
                        i,
                        batch_size,
                    )
                    for i, (start, end) in enumerate(chunks)
                ],
            )

            # Wait for completion with proper interrupt handling
            chunk_results = async_result.get()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, cleaning up workers...")
            if pool:
                pool.terminate()
                try:
                    pool.join()  # Wait up to 5 seconds for workers to finish
                except Exception:
                    pass  # If join times out, continue anyway
            raise KeyboardInterrupt("Entity extraction interrupted by user")
        finally:
            if pool:
                pool.close()
                pool.join()

        # Merge results from all chunks
        total_politicians = 0
        total_entities = 0

        for politician_count, chunk_count in chunk_results:
            total_entities += chunk_count
            total_politicians += politician_count

        logger.info(f"Extraction complete. Total processed: {total_entities}")
        logger.info(f"Extracted: {total_politicians} politicians")

        return total_politicians
