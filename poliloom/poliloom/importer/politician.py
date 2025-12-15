"""Wikidata politician importing functions."""

import logging
import multiprocessing as mp
from typing import Tuple
from datetime import date

from sqlalchemy.orm import Session

from .. import dump_reader
from ..database import create_engine, get_engine
from ..models import (
    Position,
    Location,
    Country,
    Politician,
    Property,
    PropertyType,
    WikidataEntity,
    WikidataEntityLabel,
    WikipediaLink,
    WikipediaProject,
)
from ..wikidata_entity_processor import WikidataEntityProcessor

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Worker config - set in parent process before fork, shared via copy-on-write
shared_position_qids: frozenset[str] | None = None
shared_location_qids: frozenset[str] | None = None
shared_country_qids: frozenset[str] | None = None
shared_wikipedia_projects: dict[str, str] | None = (
    None  # Maps official_website prefix to wikidata_id
)


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
    position_claims = entity.get_truthy_claims(PropertyType.POSITION.value)
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
    death_claims = entity.get_truthy_claims(PropertyType.DEATH_DATE.value)
    if len(death_claims) > 0:
        # Check any death claim to see if we should exclude this politician
        for claim in death_claims:
            death_info = entity.extract_date_from_claim(claim)
            if death_info:
                # Skip all BCE deaths (they died > 2000 years ago)
                if death_info.is_bce:
                    return False

                # Use the new to_python_date method
                death_date = death_info.to_python_date()
                if death_date:
                    # Skip if died more than 5 years ago
                    cutoff_date = date.today().replace(year=date.today().year - 5)
                    if death_date < cutoff_date:
                        return False
    else:
        # No death date - check if born over 120 years ago
        birth_claims = entity.get_truthy_claims(PropertyType.BIRTH_DATE.value)
        for claim in birth_claims:
            birth_info = entity.extract_date_from_claim(claim)
            if birth_info:
                # Skip all BCE births
                if birth_info.is_bce:
                    return False

                birth_date = birth_info.to_python_date()
                if birth_date:
                    current_year = date.today().year
                    # Skip if born over 120 years ago
                    if current_year - birth_date.year > 120:
                        return False

    return True


def _insert_politicians_batch(politicians: list[dict], session: Session) -> None:
    """Insert a batch of politicians into the database.

    Search indexing is handled separately by the index-build command.
    """
    if not politicians:
        return

    # First, ensure WikidataEntity records exist for all politicians (without labels)
    wikidata_data = [
        {
            "wikidata_id": p["wikidata_id"],
            "name": p["name"],
        }
        for p in politicians
    ]
    WikidataEntity.upsert_batch(session, wikidata_data)

    # Insert labels into separate table
    label_data = []
    for p in politicians:
        labels = p.get("labels")
        if labels:
            for label in labels:
                label_data.append(
                    {
                        "entity_id": p["wikidata_id"],
                        "label": label,
                    }
                )

    if label_data:
        WikidataEntityLabel.upsert_batch(session, label_data)

    # Use UpsertMixin for politicians with RETURNING to get IDs directly
    politician_data = [
        {
            "wikidata_id": p["wikidata_id"],
            "wikidata_id_numeric": p.get("wikidata_id_numeric"),
            "name": p["name"],
        }
        for p in politicians
    ]
    politician_rows = Politician.upsert_batch(
        session,
        politician_data,
        returning_columns=[Politician.id, Politician.wikidata_id],
    )

    # Process properties for each politician (order is guaranteed by PostgreSQL)
    for row, politician_data in zip(politician_rows, politicians):
        # Handle properties: all properties (birth/death dates, positions, citizenships, birthplaces) are stored in the unified Property model

        # Soft-delete matching extracted properties before upserting
        # This prevents duplicates when Wikidata has data matching our extracted properties
        for prop in politician_data.get("properties", []):
            Property.soft_delete_matching_extracted(
                session,
                politician_id=row.id,
                property_type=prop["type"],
                value=prop.get("value"),
                value_precision=prop.get("value_precision"),
                entity_id=prop.get("entity_id"),
                qualifiers_json=prop.get("qualifiers_json"),
            )

        # Add properties using batch UPSERT - update only if NOT extracted (preserve user evaluations)
        property_batch = [
            {"politician_id": row.id, "archived_page_id": None, **prop}
            for prop in politician_data.get("properties", [])
        ]

        if property_batch:
            Property.upsert_batch(session, property_batch)

        # All properties (positions, citizenships, birthplaces) are now handled above in the unified property_batch

        # Add Wikipedia links using batch UPSERT
        wikipedia_batch = [
            {
                "politician_id": row.id,
                "url": wiki_link["url"],
                "wikipedia_project_id": wiki_link["wikipedia_project_id"],
            }
            for wiki_link in politician_data.get("wikipedia_links", [])
        ]

        if wikipedia_batch:
            WikipediaLink.upsert_batch(session, wikipedia_batch)

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
    # Create fresh connections for this worker process
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
                wikidata_id = entity.get_wikidata_id()
                # Extract numeric ID from QID (strip 'Q' prefix)
                wikidata_id_numeric = None
                if wikidata_id and wikidata_id.startswith("Q"):
                    try:
                        wikidata_id_numeric = int(wikidata_id[1:])
                    except ValueError:
                        pass

                # Extract all labels for search functionality
                entity_labels = (
                    entity.get_all_labels()
                )  # Get all unique labels across languages

                politician_data = {
                    "wikidata_id": wikidata_id,
                    "wikidata_id_numeric": wikidata_id_numeric,
                    "name": entity.get_entity_name() or wikidata_id,
                    "labels": entity_labels if entity_labels else None,
                    "properties": [],
                    "wikipedia_links": [],
                }

                # Extract properties (birth date, death date, etc.)
                birth_claims = entity.get_truthy_claims(PropertyType.BIRTH_DATE.value)
                for claim in birth_claims:
                    birth_info = entity.extract_date_from_claim(claim)
                    if birth_info:
                        politician_data["properties"].append(
                            {
                                "type": PropertyType.BIRTH_DATE,
                                "value": birth_info.time_string,
                                "value_precision": birth_info.precision,
                                "entity_id": None,
                                "statement_id": claim["id"],
                                "qualifiers_json": claim.get("qualifiers"),
                                "references_json": claim.get("references"),
                            }
                        )

                death_claims = entity.get_truthy_claims(PropertyType.DEATH_DATE.value)
                for claim in death_claims:
                    death_info = entity.extract_date_from_claim(claim)
                    if death_info:
                        politician_data["properties"].append(
                            {
                                "type": PropertyType.DEATH_DATE,
                                "value": death_info.time_string,
                                "value_precision": death_info.precision,
                                "entity_id": None,
                                "statement_id": claim["id"],
                                "qualifiers_json": claim.get("qualifiers"),
                                "references_json": claim.get("references"),
                            }
                        )

                # Extract positions held - only include positions that exist in our database
                position_claims = entity.get_truthy_claims(PropertyType.POSITION.value)

                for claim in position_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        position_id = claim["mainsnak"]["datavalue"]["value"]["id"]

                        # Only include positions that are in our database
                        if (
                            shared_position_qids
                            and position_id not in shared_position_qids
                        ):
                            continue

                        politician_data["properties"].append(
                            {
                                "type": PropertyType.POSITION,
                                "value": None,
                                "value_precision": None,
                                "entity_id": position_id,
                                "statement_id": claim["id"],
                                "qualifiers_json": claim.get("qualifiers"),
                                "references_json": claim.get("references"),
                            }
                        )

                # Extract citizenships - only include countries that exist in our database
                citizenship_claims = entity.get_truthy_claims(
                    PropertyType.CITIZENSHIP.value
                )
                for claim in citizenship_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        citizenship_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        # Only include countries that are in our database
                        if (
                            shared_country_qids
                            and citizenship_id in shared_country_qids
                        ):
                            politician_data["properties"].append(
                                {
                                    "type": PropertyType.CITIZENSHIP,
                                    "value": None,
                                    "value_precision": None,
                                    "entity_id": citizenship_id,
                                    "statement_id": claim["id"],
                                    "qualifiers_json": claim.get("qualifiers"),
                                    "references_json": claim.get("references"),
                                }
                            )

                # Extract birthplaces - include all locations that exist in our database
                birthplace_claims = entity.get_truthy_claims(
                    PropertyType.BIRTHPLACE.value
                )
                for claim in birthplace_claims:
                    if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                        birthplace_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        # Only include locations that are in our database
                        if (
                            shared_location_qids
                            and birthplace_id in shared_location_qids
                        ):
                            politician_data["properties"].append(
                                {
                                    "type": PropertyType.BIRTHPLACE,
                                    "value": None,
                                    "value_precision": None,
                                    "entity_id": birthplace_id,
                                    "statement_id": claim["id"],
                                    "qualifiers_json": claim.get("qualifiers"),
                                    "references_json": claim.get("references"),
                                }
                            )

                # Extract Wikipedia links from sitelinks
                if entity.sitelinks:
                    for site_key, sitelink in entity.sitelinks.items():
                        if site_key.endswith("wiki") and site_key not in (
                            "commonswiki",
                            "simplewiki",
                        ):  # Wikipedia sites, exclude commons and simple
                            language = site_key.replace("wiki", "")
                            url = f"https://{language}.wikipedia.org/wiki/{sitelink['title'].replace(' ', '_')}"

                            # Match URL to wikipedia project
                            url_prefix = f"https://{language}.wikipedia.org"
                            wikipedia_project_id = shared_wikipedia_projects.get(
                                url_prefix
                            )

                            # Only add if we have a matching wikipedia project
                            if wikipedia_project_id:
                                politician_data["wikipedia_links"].append(
                                    {
                                        "url": url,
                                        "wikipedia_project_id": wikipedia_project_id,
                                    }
                                )

                politicians.append(politician_data)
                politician_count += 1

            # Process batches when they reach the batch size
            if len(politicians) >= batch_size:
                with Session(engine) as session:
                    _insert_politicians_batch(politicians, session)
                politicians = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batch on successful completion
    if politicians:
        with Session(engine) as session:
            _insert_politicians_batch(politicians, session)

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    return politician_count, entity_count


def import_politicians(
    dump_file_path: str,
    batch_size: int = 1000,
) -> None:
    """
    Import politicians from the Wikidata dump using parallel processing.

    Args:
        dump_file_path: Path to the Wikidata JSON dump file
        batch_size: Number of entities to process in each database batch
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

        # Load wikipedia projects to map URLs to project IDs
        wikipedia_project_rows = session.query(
            WikipediaProject.wikidata_id, WikipediaProject.official_website
        ).all()

        # Convert to sets of strings (flatten tuples)
        position_qids = {qid[0] for qid in position_qids}
        location_qids = {qid[0] for qid in location_qids}
        country_qids = {qid[0] for qid in country_qids}

        # Create mapping from URL prefix to wikidata_id
        # e.g., "https://en.wikipedia.org" -> "Q328"
        wikipedia_projects = {}
        for wikidata_id, official_website in wikipedia_project_rows:
            if official_website and "wikipedia.org" in official_website:
                # Extract base URL without path (e.g., https://en.wikipedia.org)
                url_parts = official_website.split("/")
                if len(url_parts) >= 3:
                    url_prefix = f"{url_parts[0]}//{url_parts[2]}"
                    wikipedia_projects[url_prefix] = wikidata_id

        logger.info(f"Filtering for {len(position_qids)} positions")
        logger.info(f"Filtering for {len(location_qids)} locations")
        logger.info(f"Filtering for {len(country_qids)} countries")
        logger.info(f"Loaded {len(wikipedia_projects)} wikipedia projects")

    # Set globals BEFORE creating Pool so workers inherit via fork copy-on-write
    global shared_position_qids, shared_location_qids, shared_country_qids
    global shared_wikipedia_projects
    shared_position_qids = frozenset(position_qids)
    shared_location_qids = frozenset(location_qids)
    shared_country_qids = frozenset(country_qids)
    shared_wikipedia_projects = wikipedia_projects

    num_workers = mp.cpu_count()
    logger.info(f"Using parallel processing with {num_workers} workers")

    # Split file into chunks for parallel processing
    logger.info("Calculating file chunks for parallel processing...")
    chunks = dump_reader.calculate_file_chunks(dump_file_path)
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
