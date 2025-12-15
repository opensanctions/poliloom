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
    WikipediaProject,
    WikidataEntity,
    WikidataEntityLabel,
    WikidataRelation,
)
from ..wikidata_entity_processor import WikidataEntityProcessor

logger = logging.getLogger(__name__)


@dataclass
class EntityCollection:
    """Collection for tracking entities, relations, and metadata for a specific entity type."""

    model_class: Type
    shared_classes: frozenset[str]
    ignored_classes: frozenset[str] = field(default_factory=frozenset)
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

    def has_entities(self) -> bool:
        """Check if collection has entities."""
        return len(self.entities) > 0

    def batch_size(self) -> int:
        """Get current batch size."""
        return len(self.entities)

    def insert(self, session: Session) -> None:
        """Insert entities and relations into database.

        Commits the transaction and clears the batch after completion.
        Search indexing is handled separately by the index-build command.
        """
        if not self.has_entities():
            return

        # Insert WikidataEntity records first (without labels)
        entity_data = [
            {
                "wikidata_id": entity["wikidata_id"],
                "name": entity["name"],
                "description": entity["description"],
            }
            for entity in self.entities
        ]

        WikidataEntity.upsert_batch(session, entity_data)

        # Insert labels into separate table
        label_data = []
        for entity in self.entities:
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
        for entity in self.entities:
            entity.pop("name", None)
            entity.pop("description", None)
            entity.pop("labels", None)

        self.model_class.upsert_batch(session, self.entities)

        # Insert relations for these entities
        if self.relations:
            WikidataRelation.upsert_batch(session, self.relations)

        session.commit()

        logger.debug(
            f"Processed {len(self.entities)} {self.model_class.__name__.lower()}s "
            f"with {len(self.relations)} relations"
        )

        # Clear batch after successful insert
        self.entities = []
        self.relations = []


# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Worker configuration - set in parent process before fork, shared via copy-on-write
# Structure: {model_name: {"classes": frozenset, "ignored": frozenset}}
worker_config: dict | None = None


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
    global worker_config

    # Create fresh connections for this worker process
    engine = create_engine(pool_size=2, max_overflow=3)
    session = Session(engine)

    # Entity collections organized by type, built from worker_config
    entity_collections = [
        EntityCollection(
            model_class=model_class,
            shared_classes=worker_config[model_class.__name__]["classes"],
            ignored_classes=worker_config[model_class.__name__]["ignored"],
        )
        for model_class in [Position, Location, Country, Language, WikipediaProject]
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
                continue  # Skip entities without names - needed for search indexing

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
                # Check if entity matches hierarchy classes
                if not any(
                    class_id in collection.shared_classes for class_id in all_class_ids
                ):
                    continue

                # Skip if entity matches any ignored hierarchy classes
                if collection.ignored_classes and any(
                    class_id in collection.ignored_classes for class_id in all_class_ids
                ):
                    continue

                # Ask the model class if this entity should be imported
                additional_fields = collection.model_class.should_import(
                    entity, instance_ids, subclass_ids
                )

                if additional_fields is not None:
                    # Create entity data with additional fields
                    import_data = entity_data.copy()
                    import_data.update(additional_fields)
                    collection.add_entity(import_data)

                    # Extract relations for this entity
                    entity_relations = entity.extract_all_relations()
                    collection.add_relations(entity_relations)

            # Process batches when they reach the batch size
            for collection in entity_collections:
                if collection.batch_size() >= batch_size:
                    collection.insert(session)

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        session.rollback()
        session.close()
        raise

    # Process remaining entities in final batches on successful completion
    for collection in entity_collections:
        if collection.has_entities():
            collection.insert(session)

    session.close()
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

    Entities with WikidataEntityMixin are indexed to the search service during import.

    Args:
        dump_file_path: Path to the Wikidata JSON dump file
        batch_size: Number of entities to process in each database batch
    """
    global worker_config

    # Load hierarchy descendants and ignored classes from database
    # Set global BEFORE creating Pool so workers inherit via fork copy-on-write
    with Session(get_engine()) as session:
        worker_config = {
            "Position": {
                "classes": frozenset(Position.query_hierarchy_descendants(session)),
                "ignored": frozenset(
                    Position.query_ignored_hierarchy_descendants(session)
                ),
            },
            "Location": {
                "classes": frozenset(Location.query_hierarchy_descendants(session)),
                "ignored": frozenset(
                    Location.query_ignored_hierarchy_descendants(session)
                ),
            },
            "Country": {
                "classes": frozenset(Country.query_hierarchy_descendants(session)),
                "ignored": frozenset(
                    Country.query_ignored_hierarchy_descendants(session)
                ),
            },
            "Language": {
                "classes": frozenset(Language.query_hierarchy_descendants(session)),
                "ignored": frozenset(
                    Language.query_ignored_hierarchy_descendants(session)
                ),
            },
            # Wikipedia projects have a flat structure - no hierarchy or ignored classes
            "WikipediaProject": {
                "classes": frozenset(["Q10876391"]),
                "ignored": frozenset(),
            },
        }

    # Log statistics
    for name, cfg in worker_config.items():
        logger.info(
            f"Prepared {len(cfg['classes'])} {name} classes, "
            f"{len(cfg['ignored'])} ignored"
        )

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
        "wikipediaproject": 0,
    }
    total_entities = 0

    for counts, chunk_count in chunk_results:
        total_entities += chunk_count
        for key in total_counts:
            total_counts[key] += counts[key]

    logger.info(f"Extraction complete. Total processed: {total_entities}")
    logger.info(
        f"Extracted: {total_counts['position']} positions, {total_counts['location']} locations, "
        f"{total_counts['country']} countries, {total_counts['language']} languages, "
        f"{total_counts['wikipediaproject']} wikipedia projects"
    )
