"""Wikidata entity importing functions for supporting entities (positions, locations, countries)."""

import logging
import multiprocessing as mp
from typing import Dict, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from .. import dump_reader
from ..database import create_engine, get_engine
from ..models import (
    Position,
    Location,
    Country,
    Language,
    OfficialLanguage,
    WikidataEntity,
    WikidataRelation,
)
from ..wikidata_entity_processor import WikidataEntityProcessor

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Define globals for workers
shared_position_classes: frozenset[str] | None = None
shared_location_classes: frozenset[str] | None = None
shared_country_classes: frozenset[str] | None = None
shared_language_classes: frozenset[str] | None = None


def init_entity_worker(
    pos_classes: frozenset[str],
    loc_classes: frozenset[str],
    country_classes: frozenset[str],
    lang_classes: frozenset[str],
) -> None:
    """Initializer runs in each worker process once at startup."""
    global \
        shared_position_classes, \
        shared_location_classes, \
        shared_country_classes, \
        shared_language_classes
    shared_position_classes = pos_classes
    shared_location_classes = loc_classes
    shared_country_classes = country_classes
    shared_language_classes = lang_classes


def _insert_entities_batch(
    entities: list[dict], relations: list[dict], model_class, entity_type: str, engine
) -> None:
    """Insert a batch of entities (positions or locations) and their relations into the database."""
    if not entities:
        return

    with Session(engine) as session:
        # Insert WikidataEntity records first
        entity_data = [
            {
                "wikidata_id": entity["wikidata_id"],
                "name": entity["name"],
            }
            for entity in entities
        ]

        stmt = insert(WikidataEntity).values(entity_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["wikidata_id"],
            set_={
                "name": stmt.excluded.name,
            },
        )
        session.execute(stmt)

        # Insert entities referencing the WikidataEntity records
        # Remove 'name' key since it's now stored in WikidataEntity
        for entity in entities:
            entity.pop("name", None)

        stmt = insert(model_class).values(entities)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])

        session.execute(stmt)

        # Insert relations for these entities
        if relations:
            stmt = insert(WikidataRelation).values(relations)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["parent_entity_id", "child_entity_id", "relation_type"]
            )
            session.execute(stmt)

        session.commit()
        logger.debug(
            f"Processed {len(entities)} {entity_type} with {len(relations)} relations"
        )


def _process_supporting_entities_chunk(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
    batch_size: int,
) -> Tuple[Dict[str, int], int, list[dict]]:
    """
    Process a specific byte range of the dump file for supporting entities extraction.
    Uses frozensets for descendant QID lookups with O(1) membership testing.

    Each worker independently reads and parses its assigned chunk.
    Returns entity counts found in this chunk and P37 official language relations.
    """
    global \
        shared_position_classes, \
        shared_location_classes, \
        shared_country_classes, \
        shared_language_classes

    # Create a fresh engine for this worker process
    engine = create_engine(pool_size=2, max_overflow=3)

    positions = []
    locations = []
    countries = []
    languages = []
    position_relations = []
    location_relations = []
    country_relations = []
    language_relations = []
    official_language_relations = []  # P37 relations to insert later
    counts = {"positions": 0, "locations": 0, "countries": 0, "languages": 0}
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

            # Create shared entity data
            entity_name = entity.get_entity_name()
            if not entity_name:
                continue  # Skip entities without names - needed for embeddings in enrichment

            entity_data = {
                "wikidata_id": entity_id,
                "name": entity_name,
            }

            # Check entity type and add type-specific fields
            # Check if entity is a position based on instance or subclass hierarchy
            instance_ids = entity.get_instance_of_ids()
            subclass_ids = entity.get_subclass_of_ids()
            all_class_ids = instance_ids.union(subclass_ids)

            if any(class_id in shared_position_classes for class_id in all_class_ids):
                positions.append(entity_data.copy())
                counts["positions"] += 1

                # Extract relations for this position
                entity_relations = entity.extract_all_relations()
                position_relations.extend(entity_relations)

            if any(class_id in shared_location_classes for class_id in all_class_ids):
                locations.append(entity_data.copy())
                counts["locations"] += 1

                # Extract relations for this location
                entity_relations = entity.extract_all_relations()
                location_relations.extend(entity_relations)

            if any(class_id in shared_country_classes for class_id in all_class_ids):
                # Extract ISO 3166-1 alpha-2 code for countries
                iso_code = None
                iso_claims = entity.get_truthy_claims("P297")
                for claim in iso_claims:
                    try:
                        iso_code = claim["mainsnak"]["datavalue"]["value"]
                        break
                    except (KeyError, TypeError):
                        continue

                # Create separate copy for countries with iso_code
                country_data = entity_data.copy()
                country_data["iso_code"] = iso_code
                countries.append(country_data)
                counts["countries"] += 1

                # Extract relations for this country
                entity_relations = entity.extract_all_relations()
                country_relations.extend(entity_relations)

                # Extract P37 (official language) relations for countries
                official_lang_claims = entity.get_truthy_claims("P37")
                for claim in official_lang_claims:
                    try:
                        language_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        official_language_relations.append(
                            {"country_id": entity_id, "language_id": language_id}
                        )
                    except (KeyError, TypeError):
                        continue

            if any(class_id in shared_language_classes for class_id in all_class_ids):
                languages.append(entity_data.copy())
                counts["languages"] += 1

                # Extract relations for this language
                entity_relations = entity.extract_all_relations()
                language_relations.extend(entity_relations)

            # Process batches when they reach the batch size
            if len(positions) >= batch_size:
                _insert_entities_batch(
                    positions, position_relations, Position, "positions", engine
                )
                positions = []
                position_relations = []

            if len(locations) >= batch_size:
                _insert_entities_batch(
                    locations, location_relations, Location, "locations", engine
                )
                locations = []
                location_relations = []

            if len(countries) >= batch_size:
                _insert_entities_batch(
                    countries, country_relations, Country, "countries", engine
                )
                countries = []
                country_relations = []

            if len(languages) >= batch_size:
                _insert_entities_batch(
                    languages, language_relations, Language, "languages", engine
                )
                languages = []
                language_relations = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batches on successful completion
    if positions:
        _insert_entities_batch(
            positions, position_relations, Position, "positions", engine
        )
    if locations:
        _insert_entities_batch(
            locations, location_relations, Location, "locations", engine
        )
    if countries:
        _insert_entities_batch(
            countries, country_relations, Country, "countries", engine
        )
    if languages:
        _insert_entities_batch(
            languages, language_relations, Language, "languages", engine
        )

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    return counts, entity_count, official_language_relations


def import_entities(
    dump_file_path: str,
    batch_size: int = 1000,
) -> Dict[str, int]:
    """
    Import supporting entities from the Wikidata dump using parallel processing.
    Uses frozensets to efficiently share descendant QIDs across workers with O(1) lookups.

    Args:
        dump_file_path: Path to the Wikidata JSON dump file
        batch_size: Number of entities to process in each database batch

    Returns:
        Dictionary with counts of imported entities (positions, locations, countries, languages)
    """
    # Load only position and location descendants from database (optimized)
    with Session(get_engine()) as session:
        # Use position basics approach with ignore IDs
        position_root_ids = [
            "Q4164871",  # position
            "Q29645880",  # ambassador of a country
            "Q29645886",  # ambassador to a country
            "Q707492",  # military chief of staff
        ]
        ignore_ids = [
            "Q114962596",  # historical position
            "Q193622",  # order
            "Q60754876",  # grade of an order
            "Q618779",  # award
            "Q4240305",  # cross
            # Why are these here?
            "Q120560",  # minor basilica
            "Q2977",  # cathedral
        ]
        position_classes = WikidataEntity.query_hierarchy_descendants(
            session, position_root_ids, ignore_ids
        )
        location_root_ids = ["Q27096213"]  # geographic entity
        location_classes = WikidataEntity.query_hierarchy_descendants(
            session, location_root_ids
        )

        country_root_ids = [
            "Q6256",  # country
            "Q3624078",  # sovereign state
            "Q20181813",  # disputed territory
            "Q1520223",  # constituent country
            "Q1489259",  # dependent territory
            "Q1048835",  # political territorial entity
        ]
        country_classes = WikidataEntity.query_hierarchy_descendants(
            session, country_root_ids
        )

        language_root_ids = ["Q23492"]  # official language
        language_classes = WikidataEntity.query_hierarchy_descendants(
            session, language_root_ids
        )

        logger.info(
            f"Filtering for {len(position_classes)} position types, {len(location_classes)} location types, {len(country_classes)} country types, and {len(language_classes)} language types"
        )

    # Build frozensets once in parent, BEFORE starting Pool
    position_classes = frozenset(position_classes)
    location_classes = frozenset(location_classes)
    country_classes = frozenset(country_classes)
    language_classes = frozenset(language_classes)

    logger.info(f"Prepared {len(position_classes)} position classes")
    logger.info(f"Prepared {len(location_classes)} location classes")
    logger.info(f"Prepared {len(country_classes)} country classes")
    logger.info(f"Prepared {len(language_classes)} language classes")

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
            initializer=init_entity_worker,
            initargs=(
                position_classes,
                location_classes,
                country_classes,
                language_classes,
            ),
        )

        async_result = pool.starmap_async(
            _process_supporting_entities_chunk,
            [
                (dump_file_path, start, end, i, batch_size)
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
                pool.join()
            except Exception:
                pass
        raise KeyboardInterrupt("Entity extraction interrupted by user")
    finally:
        if pool:
            pool.close()
            pool.join()

    # Merge results from all chunks
    total_counts = {
        "positions": 0,
        "locations": 0,
        "countries": 0,
        "languages": 0,
    }
    total_entities = 0
    all_official_language_relations = []

    for counts, chunk_count, official_lang_relations in chunk_results:
        total_entities += chunk_count
        for key in total_counts:
            total_counts[key] += counts[key]
        all_official_language_relations.extend(official_lang_relations)

    logger.info(f"Extraction complete. Total processed: {total_entities}")
    logger.info(
        f"Extracted: {total_counts['positions']} positions, {total_counts['locations']} locations, {total_counts['countries']} countries, {total_counts['languages']} languages"
    )
    logger.info(
        f"Inserting {len(all_official_language_relations)} P37 official language relations"
    )

    # Insert P37 official language relations after all entities are processed
    if all_official_language_relations:
        batch_size_relations = 10000
        for i in range(0, len(all_official_language_relations), batch_size_relations):
            batch = all_official_language_relations[i : i + batch_size_relations]
            with Session(get_engine()) as session:
                stmt = insert(OfficialLanguage).values(batch)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=["country_id", "language_id"]
                )
                session.execute(stmt)
                session.commit()
            logger.info(
                f"Inserted P37 batch {i // batch_size_relations + 1} ({len(batch)} relations)"
            )

    return total_counts
