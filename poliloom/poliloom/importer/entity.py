"""Wikidata entity importing functions for supporting entities (positions, locations, countries)."""

import logging
import multiprocessing as mp
from typing import Dict, Tuple, Type
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .. import dump_reader
from ..database import create_engine, get_engine
from ..models import (
    Position,
    Location,
    Country,
    Language,
    WikidataEntity,
    WikidataRelation,
)
from ..wikidata_entity_processor import WikidataEntityProcessor

logger = logging.getLogger(__name__)


@dataclass
class EntityCollection:
    """Collection for tracking entities, relations, and metadata for a specific entity type."""

    model_class: Type
    shared_classes: frozenset[str]
    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    count: int = 0

    def add_entity(self, entity_data: dict) -> None:
        """Add an entity to the collection."""
        self.entities.append(entity_data)
        self.count += 1

    def add_relations(self, relations: list[dict]) -> None:
        """Add relations for the last added entity."""
        self.relations.extend(relations)

    def clear_batch(self) -> None:
        """Clear entities and relations for batch processing."""
        self.entities = []
        self.relations = []

    def has_entities(self) -> bool:
        """Check if collection has entities."""
        return len(self.entities) > 0

    def batch_size(self) -> int:
        """Get current batch size."""
        return len(self.entities)


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
    language_classes: frozenset[str],
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
    shared_language_classes = language_classes


def _insert_entities_batch(collection: EntityCollection, engine) -> None:
    """Insert a batch of entities and their relations into the database."""
    if not collection.has_entities():
        return

    with Session(engine) as session:
        # Insert WikidataEntity records first (without labels)
        entity_data = [
            {
                "wikidata_id": entity["wikidata_id"],
                "name": entity["name"],
                "description": entity["description"],
            }
            for entity in collection.entities
        ]

        WikidataEntity.upsert_batch(session, entity_data)

        # Insert labels into separate table
        from ..models import WikidataEntityLabel

        label_data = []
        for entity in collection.entities:
            labels = entity.get("labels")
            if labels:
                for label in labels:
                    label_data.append(
                        {
                            "entity_id": entity["wikidata_id"],
                            "label": label,
                        }
                    )

        if label_data:
            WikidataEntityLabel.upsert_batch(session, label_data)

        # Insert entities referencing the WikidataEntity records
        # Remove 'name', 'description', and 'labels' keys since they're now stored separately
        for entity in collection.entities:
            entity.pop("name", None)
            entity.pop("description", None)
            entity.pop("labels", None)

        collection.model_class.upsert_batch(session, collection.entities)

        # Insert relations for these entities
        if collection.relations:
            WikidataRelation.upsert_batch(session, collection.relations)

        session.commit()
        logger.debug(
            f"Processed {len(collection.entities)} {collection.model_class.__name__.lower()}s with {len(collection.relations)} relations"
        )


def _process_supporting_entities_chunk(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
    batch_size: int,
) -> Tuple[Dict[str, int], int]:
    """
    Process a specific byte range of the dump file for supporting entities extraction.
    Uses frozensets for descendant QID lookups with O(1) membership testing.

    Each worker independently reads and parses its assigned chunk.
    Returns entity counts found in this chunk.
    """
    global \
        shared_position_classes, \
        shared_location_classes, \
        shared_country_classes, \
        shared_language_classes

    # Create a fresh engine for this worker process
    engine = create_engine(pool_size=2, max_overflow=3)

    # Entity collections organized by type
    entity_collections = [
        EntityCollection(
            model_class=Position,
            shared_classes=shared_position_classes,
        ),
        EntityCollection(
            model_class=Location,
            shared_classes=shared_location_classes,
        ),
        EntityCollection(
            model_class=Country,
            shared_classes=shared_country_classes,
        ),
        EntityCollection(
            model_class=Language,
            shared_classes=shared_language_classes,
        ),
    ]
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

            entity_description = entity.get_entity_description()
            entity_labels = (
                entity.get_all_labels()
            )  # Get all unique labels across languages
            entity_data = {
                "wikidata_id": entity_id,
                "name": entity_name,
                "description": entity_description,
                "labels": entity_labels if entity_labels else None,
            }

            # Check entity type and add type-specific fields
            # Check if entity is a position based on instance or subclass hierarchy
            instance_ids = entity.get_instance_of_ids()
            subclass_ids = entity.get_subclass_of_ids()
            all_class_ids = instance_ids.union(subclass_ids)

            # Process each entity type
            for collection in entity_collections:
                if any(
                    class_id in collection.shared_classes for class_id in all_class_ids
                ):
                    # Handle special case for countries requiring ISO code
                    if collection.model_class is Country:
                        # Extract ISO 3166-1 alpha-2 code for countries
                        iso_code = None
                        iso_claims = entity.get_truthy_claims("P297")
                        for claim in iso_claims:
                            try:
                                iso_code = claim["mainsnak"]["datavalue"]["value"]
                                break
                            except (KeyError, TypeError):
                                continue

                        # Only import countries that have an ISO code
                        if iso_code:
                            # Create separate copy for countries with iso_code
                            country_data = entity_data.copy()
                            country_data["iso_code"] = iso_code
                            collection.add_entity(country_data)
                    # Handle special case for languages requiring ISO codes
                    elif collection.model_class is Language:
                        # Extract ISO 639-1 code for languages (P218)
                        iso1_code = None
                        iso1_claims = entity.get_truthy_claims("P218")
                        for claim in iso1_claims:
                            try:
                                iso1_code = claim["mainsnak"]["datavalue"]["value"]
                                break
                            except (KeyError, TypeError):
                                continue

                        # Extract ISO 639-3 code for languages (P219)
                        iso3_code = None
                        iso3_claims = entity.get_truthy_claims("P219")
                        for claim in iso3_claims:
                            try:
                                iso3_code = claim["mainsnak"]["datavalue"]["value"]
                                break
                            except (KeyError, TypeError):
                                continue

                        # Import languages that have either ISO code (or both)
                        if iso1_code or iso3_code:
                            # Create separate copy for languages with ISO codes
                            language_data = entity_data.copy()
                            language_data["iso1_code"] = iso1_code
                            language_data["iso3_code"] = iso3_code
                            collection.add_entity(language_data)
                    else:
                        # Standard processing for all other entity types
                        collection.add_entity(entity_data.copy())

                        # Extract relations for this entity
                        entity_relations = entity.extract_all_relations()
                        collection.add_relations(entity_relations)

            # Process batches when they reach the batch size
            for collection in entity_collections:
                if collection.batch_size() >= batch_size:
                    _insert_entities_batch(collection, engine)
                    collection.clear_batch()

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batches on successful completion
    for collection in entity_collections:
        if collection.has_entities():
            _insert_entities_batch(collection, engine)

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    # Extract counts from collections
    counts = {
        collection.model_class.__name__.lower(): collection.count
        for collection in entity_collections
    }
    return counts, entity_count


def import_entities(
    dump_file_path: str,
    batch_size: int = 1000,
) -> None:
    """
    Import supporting entities from the Wikidata dump using parallel processing.
    Uses frozensets to efficiently share descendant QIDs across workers with O(1) lookups.

    Args:
        dump_file_path: Path to the Wikidata JSON dump file
        batch_size: Number of entities to process in each database batch
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
            # Religious positions (not political positions)
            "Q63187345",  # religious occupation
            "Q29982545",  # function in the Evangelical Church of Czech Brethren
            # General occupations (too broad, includes all professions)
            "Q12737077",  # occupation
        ]
        position_classes = WikidataEntity.query_hierarchy_descendants(
            session, position_root_ids, ignore_ids
        )
        # Location leaf classes with >5k politicians that make sense for birthplace matching
        # Focuses on classes where extracted text strings would meaningfully match
        location_root_ids = [
            "Q486972",  # human settlement (cities, towns, villages)
            "Q82794",  # region (states, provinces)
            "Q1306755",  # administrative centre (capitals)
            "Q3257686",  # locality
            "Q48907157",  # section of populated place (boroughs, districts)
        ]
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

        # Language root IDs (languoid)
        language_root_ids = ["Q17376908"]  # languoid
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
        "position": 0,
        "location": 0,
        "country": 0,
        "language": 0,
    }
    total_entities = 0

    for counts, chunk_count in chunk_results:
        total_entities += chunk_count
        for key in total_counts:
            total_counts[key] += counts[key]

    logger.info(f"Extraction complete. Total processed: {total_entities}")
    logger.info(
        f"Extracted: {total_counts['position']} positions, {total_counts['location']} locations, {total_counts['country']} countries, {total_counts['language']} languages"
    )
