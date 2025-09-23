"""Wikidata politician importing functions."""

import logging
import multiprocessing as mp
from typing import Tuple
from datetime import datetime, date
from types import SimpleNamespace

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy import text

from .. import dump_reader
from ..database import create_engine, get_engine
from ..models import (
    Position,
    Location,
    Country,
    Politician,
    Property,
    PropertyType,
    HoldsPosition,
    HasCitizenship,
    BornAt,
    WikipediaLink,
)
from ..wikidata_entity_processor import WikidataEntityProcessor

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Define globals for workers
shared_position_qids: frozenset[str] | None = None
shared_location_qids: frozenset[str] | None = None
shared_country_qids: frozenset[str] | None = None


def init_politician_worker(
    position_qids: frozenset[str],
    location_qids: frozenset[str],
    country_qids: frozenset[str],
) -> None:
    """Initializer runs in each worker process once at startup."""
    global shared_position_qids, shared_location_qids, shared_country_qids
    shared_position_qids = position_qids
    shared_location_qids = location_qids
    shared_country_qids = country_qids


def _is_politician(
    entity: WikidataEntityProcessor, relevant_position_qids: frozenset[str]
) -> bool:
    """Check if entity is a politician based on occupation or positions held in our database."""
    # Must be human first
    instance_ids = entity.get_instance_of_ids()
    if "Q5" not in instance_ids:
        return False

    # Check occupation for politician
    occupation_claims = entity.get_truthy_claims("P106")
    for claim in occupation_claims:
        try:
            occupation_id = claim["mainsnak"]["datavalue"]["value"]["id"]
            if occupation_id == "Q82955":  # politician
                return True
        except (KeyError, TypeError):
            continue

    # Check if they have any position held that exists in our database
    position_claims = entity.get_truthy_claims("P39")
    for claim in position_claims:
        try:
            position_id = claim["mainsnak"]["datavalue"]["value"]["id"]
            if position_id in relevant_position_qids:
                return True
        except (KeyError, TypeError):
            continue
    return False


def _should_import_politician(entity: WikidataEntityProcessor) -> bool:
    """Check if politician should be imported based on death/birth date filtering."""
    # Check if politician is deceased (has death date P570)
    death_claims = entity.get_truthy_claims("P570")
    if len(death_claims) > 0:
        # Check any death claim to see if we should exclude this politician
        for claim in death_claims:
            death_info = entity.extract_date_from_claim(claim)
            if death_info:
                # Skip all BCE deaths (they died > 2000 years ago)
                if death_info.is_bce:
                    return False

                try:
                    death_date_str = death_info.date
                    precision = death_info.precision

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

                    # Skip if died more than 5 years ago
                    cutoff_date = date.today().replace(year=date.today().year - 5)
                    if death_date and death_date < cutoff_date:
                        return False
                except (ValueError, TypeError):
                    pass  # Include if we can't parse the date
    else:
        # No death date - check if born over 120 years ago
        birth_claims = entity.get_truthy_claims("P569")
        for claim in birth_claims:
            birth_info = entity.extract_date_from_claim(claim)
            if birth_info:
                # Skip all BCE births
                if birth_info.is_bce:
                    return False

                try:
                    birth_date_str = birth_info.date
                    precision = birth_info.precision

                    # Parse birth year based on precision
                    if precision >= 9:  # year precision or better
                        birth_year = int(birth_date_str.split("-")[0])
                        current_year = date.today().year

                        # Skip if born over 120 years ago
                        if current_year - birth_year > 120:
                            return False
                except (ValueError, TypeError, IndexError):
                    pass  # Include if we can't parse the birth date

    return True


def _insert_politicians_batch(politicians: list[dict], engine) -> None:
    """Insert a batch of politicians into the database."""
    if not politicians:
        return

    with Session(engine) as session:
        # First, ensure WikidataEntity records exist for all politicians
        from ..models import WikidataEntity

        wikidata_stmt = insert(WikidataEntity).values(
            [
                {
                    "wikidata_id": p["wikidata_id"],
                    "name": p["name"],
                }
                for p in politicians
            ]
        )
        # On conflict, update the name (in case it changed in Wikidata)
        wikidata_stmt = wikidata_stmt.on_conflict_do_nothing()
        session.execute(wikidata_stmt)

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

        # Execute UPSERT with RETURNING to get IDs directly
        stmt = stmt.returning(Politician.id, Politician.wikidata_id)
        result = session.execute(stmt)
        politician_rows = result.fetchall()

        # Create mapping directly from RETURNING results
        politician_map = {
            row.wikidata_id: SimpleNamespace(id=row.id, wikidata_id=row.wikidata_id)
            for row in politician_rows
        }

        # Now process related data for each politician
        for politician_data in politicians:
            politician_obj = politician_map[politician_data["wikidata_id"]]

            # Handle relationships: need to check if they already exist to avoid duplicates
            # For re-imports, we want to add new relationships but not duplicate existing ones

            # Add properties using batch UPSERT - update only if NOT extracted (preserve user evaluations)
            property_batch = [
                {
                    "politician_id": politician_obj.id,
                    "type": prop["type"],
                    "value": prop["value"],
                    "value_precision": prop.get("value_precision"),
                    "statement_id": prop["statement_id"],
                    "qualifiers_json": prop.get("qualifiers_json"),
                    "references_json": prop.get("references_json"),
                    "archived_page_id": None,
                }
                for prop in politician_data.get("properties", [])
            ]

            if property_batch:
                stmt = insert(Property).values(property_batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["statement_id"],
                    index_where=text("statement_id IS NOT NULL"),
                    set_={
                        "value": stmt.excluded.value,
                        "value_precision": stmt.excluded.value_precision,
                        "qualifiers_json": stmt.excluded.qualifiers_json,
                        "references_json": stmt.excluded.references_json,
                    },
                )
                session.execute(stmt)

            # Add positions using batch UPSERT - we already filtered during extraction so we know they exist
            position_batch = [
                {
                    "politician_id": politician_obj.id,
                    "position_id": pos["wikidata_id"],
                    "start_date": pos.get("start_date"),
                    "start_date_precision": pos.get("start_date_precision"),
                    "end_date": pos.get("end_date"),
                    "end_date_precision": pos.get("end_date_precision"),
                    "statement_id": pos["statement_id"],
                    "archived_page_id": None,
                    "qualifiers_json": pos.get("qualifiers_json"),
                    "references_json": pos.get("references_json"),
                }
                for pos in politician_data.get("positions", [])
            ]

            if position_batch:
                stmt = insert(HoldsPosition).values(position_batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["statement_id"],
                    index_where=text("statement_id IS NOT NULL"),
                    set_={
                        "start_date": stmt.excluded.start_date,
                        "start_date_precision": stmt.excluded.start_date_precision,
                        "end_date": stmt.excluded.end_date,
                        "end_date_precision": stmt.excluded.end_date_precision,
                        "qualifiers_json": stmt.excluded.qualifiers_json,
                        "references_json": stmt.excluded.references_json,
                    },
                )
                session.execute(stmt)

            # Add citizenships using batch UPSERT - we already filtered during extraction so we know they exist
            citizenship_batch = [
                {
                    "politician_id": politician_obj.id,
                    "country_id": citizenship["country_id"],
                    "statement_id": citizenship["statement_id"],
                }
                for citizenship in politician_data.get("citizenships", [])
            ]

            if citizenship_batch:
                stmt = insert(HasCitizenship).values(citizenship_batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["statement_id"],
                    index_where=text("statement_id IS NOT NULL"),
                    set_={
                        "country_id": stmt.excluded.country_id,
                    },
                )
                session.execute(stmt)

            # Add birthplaces using UPSERT - we already filtered during extraction so we know they exist
            birthplace_batch = [
                {
                    "politician_id": politician_obj.id,
                    "location_id": birthplace["location_id"],
                    "statement_id": birthplace["statement_id"],
                    "archived_page_id": None,
                    "qualifiers_json": birthplace.get("qualifiers_json"),
                    "references_json": birthplace.get("references_json"),
                }
                for birthplace in politician_data.get("birthplaces", [])
            ]

            if birthplace_batch:
                stmt = insert(BornAt).values(birthplace_batch)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["statement_id"],
                    index_where=text("statement_id IS NOT NULL"),
                )
                session.execute(stmt)

            # Add Wikipedia links using batch UPSERT
            wikipedia_batch = [
                {
                    "politician_id": politician_obj.id,
                    "url": wiki_link["url"],
                    "language_code": wiki_link.get("language", "en"),
                }
                for wiki_link in politician_data.get("wikipedia_links", [])
            ]

            if wikipedia_batch:
                stmt = insert(WikipediaLink).values(wikipedia_batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["politician_id", "language_code"],
                    set_={
                        "url": stmt.excluded.url,
                    },
                )
                session.execute(stmt)

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
    # Create a fresh engine for this worker process
    engine = create_engine(pool_size=2, max_overflow=3)

    politicians = []
    politician_count = 0
    entity_count = 0
    try:
        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntityProcessor
            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"Worker {worker_id}: processed {entity_count} entities")

            entity_id = entity.get_wikidata_id()
            if not entity_id:
                continue

            # Check if it's a politician and should be imported
            if _is_politician(
                entity, shared_position_qids
            ) and _should_import_politician(entity):
                # Build complete politician dict with all relationships
                politician_data = {
                    "wikidata_id": entity.get_wikidata_id(),
                    "name": entity.get_entity_name() or entity.get_wikidata_id(),
                    "properties": [],
                    "positions": [],
                    "citizenships": [],
                    "birthplaces": [],
                    "wikipedia_links": [],
                }

                # Extract properties (birth date, death date, etc.)
                birth_claims = entity.get_truthy_claims("P569")
                for claim in birth_claims:
                    birth_info = entity.extract_date_from_claim(claim)
                    if birth_info:
                        # Store all qualifiers as JSON for data preservation
                        qualifiers_json = claim.get("qualifiers")
                        # Store all references as JSON for data preservation
                        references_json = claim.get("references")

                        politician_data["properties"].append(
                            {
                                "type": PropertyType.BIRTH_DATE,
                                "value": birth_info.date,
                                "value_precision": birth_info.precision,
                                "statement_id": claim["id"],
                                "qualifiers_json": qualifiers_json,
                                "references_json": references_json,
                            }
                        )

                death_claims = entity.get_truthy_claims("P570")
                for claim in death_claims:
                    death_info = entity.extract_date_from_claim(claim)
                    if death_info:
                        # Store all qualifiers as JSON for data preservation
                        qualifiers_json = claim.get("qualifiers")
                        # Store all references as JSON for data preservation
                        references_json = claim.get("references")

                        politician_data["properties"].append(
                            {
                                "type": PropertyType.DEATH_DATE,
                                "value": death_info.date,
                                "value_precision": death_info.precision,
                                "statement_id": claim["id"],
                                "qualifiers_json": qualifiers_json,
                                "references_json": references_json,
                            }
                        )

                # Extract positions held - only include positions that exist in our database
                position_claims = entity.get_truthy_claims("P39")
                # Wikidata can contain duplicate P39 statements for the same position with identical qualifiers
                # This happens due to multiple statement IDs or data quality issues, so we deduplicate here
                seen_positions = (
                    set()
                )  # Track unique (position_id, start_date, end_date) combinations

                for claim in position_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        position_id = claim["mainsnak"]["datavalue"]["value"]["id"]

                        # Only include positions that are in our database
                        if (
                            shared_position_qids
                            and position_id not in shared_position_qids
                        ):
                            continue

                        # Extract start and end dates from qualifiers
                        start_date = None
                        start_date_precision = None
                        end_date = None
                        end_date_precision = None
                        qualifiers_json = None
                        references_json = None

                        if "qualifiers" in claim:
                            # Store all qualifiers as JSON for data preservation
                            qualifiers_json = claim["qualifiers"]
                            # Start date (P580)
                            if "P580" in claim["qualifiers"]:
                                start_qual = claim["qualifiers"]["P580"][0]
                                if "datavalue" in start_qual:
                                    start_info = entity.extract_date_from_claim(
                                        start_qual
                                    )
                                    if start_info:
                                        start_date = start_info.date
                                        start_date_precision = start_info.precision

                            # End date (P582)
                            if "P582" in claim["qualifiers"]:
                                end_qual = claim["qualifiers"]["P582"][0]
                                if "datavalue" in end_qual:
                                    end_info = entity.extract_date_from_claim(end_qual)
                                    if end_info:
                                        end_date = end_info.date
                                        end_date_precision = end_info.precision

                        if "references" in claim:
                            # Store all references as JSON for data preservation
                            references_json = claim["references"]

                        # Create unique key for deduplication
                        position_key = (position_id, start_date, end_date)
                        if position_key not in seen_positions:
                            seen_positions.add(position_key)
                            politician_data["positions"].append(
                                {
                                    "wikidata_id": position_id,
                                    "start_date": start_date,
                                    "start_date_precision": start_date_precision,
                                    "end_date": end_date,
                                    "end_date_precision": end_date_precision,
                                    "statement_id": claim["id"],
                                    "qualifiers_json": qualifiers_json,
                                    "references_json": references_json,
                                }
                            )

                # Extract citizenships - only include countries that exist in our database
                citizenship_claims = entity.get_truthy_claims("P27")
                for claim in citizenship_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        citizenship_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        # Only include countries that are in our database
                        if (
                            shared_country_qids
                            and citizenship_id in shared_country_qids
                        ):
                            politician_data["citizenships"].append(
                                {
                                    "country_id": citizenship_id,
                                    "statement_id": claim["id"],
                                }
                            )

                # Extract birthplaces - include all locations that exist in our database
                birthplace_claims = entity.get_truthy_claims("P19")
                politician_data["birthplaces"] = []
                for claim in birthplace_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        birthplace_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        # Store all qualifiers as JSON for data preservation
                        qualifiers_json = claim.get("qualifiers")
                        # Store all references as JSON for data preservation
                        references_json = claim.get("references")
                        # Only include locations that are in our database
                        if (
                            shared_location_qids
                            and birthplace_id in shared_location_qids
                        ):
                            politician_data["birthplaces"].append(
                                {
                                    "location_id": birthplace_id,
                                    "statement_id": claim["id"],
                                    "qualifiers_json": qualifiers_json,
                                    "references_json": references_json,
                                }
                            )

                # Extract Wikipedia links from sitelinks
                if entity.sitelinks:
                    for site_key, sitelink in entity.sitelinks.items():
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
                _insert_politicians_batch(politicians, engine)
                politicians = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batch on successful completion
    if politicians:
        _insert_politicians_batch(politicians, engine)

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    return politician_count, entity_count


def import_politicians(
    dump_file_path: str,
    batch_size: int = 1000,
) -> int:
    """
    Import politicians from the Wikidata dump using parallel processing.

    Args:
        dump_file_path: Path to the Wikidata JSON dump file
        batch_size: Number of entities to process in each database batch

    Returns:
        Total count of imported politicians
    """
    # Load existing entity QIDs from database for filtering
    with Session(get_engine()) as session:
        position_qids = set(
            session.query(Position.wikidata_id)
            .filter(Position.wikidata_id.isnot(None))
            .all()
        )
        location_qids = set(
            session.query(Location.wikidata_id)
            .filter(Location.wikidata_id.isnot(None))
            .all()
        )
        country_qids = set(
            session.query(Country.wikidata_id)
            .filter(Country.wikidata_id.isnot(None))
            .all()
        )

        # Convert to sets of strings (flatten tuples)
        position_qids = {qid[0] for qid in position_qids}
        location_qids = {qid[0] for qid in location_qids}
        country_qids = {qid[0] for qid in country_qids}

        logger.info(f"Filtering for {len(position_qids)} positions")
        logger.info(f"Filtering for {len(location_qids)} locations")
        logger.info(f"Filtering for {len(country_qids)} countries")

    # Build frozensets once in parent, BEFORE starting Pool
    position_qids = frozenset(position_qids)
    location_qids = frozenset(location_qids)
    country_qids = frozenset(country_qids)

    num_workers = mp.cpu_count()
    logger.info(f"Using parallel processing with {num_workers} workers")

    # Split file into chunks for parallel processing
    logger.info("Calculating file chunks for parallel processing...")
    chunks = dump_reader.calculate_file_chunks(dump_file_path)
    logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

    # Process chunks in parallel with proper KeyboardInterrupt handling
    pool = None
    try:
        pool = mp.Pool(
            processes=num_workers,
            initializer=init_politician_worker,
            initargs=(position_qids, location_qids, country_qids),
        )

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
