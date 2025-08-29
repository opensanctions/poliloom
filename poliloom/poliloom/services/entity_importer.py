"""Wikidata entity importing service for supporting entities (positions, locations, countries)."""

import logging
import multiprocessing as mp
from typing import Dict, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from .dump_reader import DumpReader
from .database_inserter import DatabaseInserter
from ..database import get_engine
from ..models import SubclassRelation
from ..wikidata_entity import WikidataEntity

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Define globals for workers
shared_position_classes: frozenset[str] | None = None
shared_location_classes: frozenset[str] | None = None


def init_entity_worker(
    pos_classes: frozenset[str], loc_classes: frozenset[str]
) -> None:
    """Initializer runs in each worker process once at startup."""
    global shared_position_classes, shared_location_classes
    shared_position_classes = pos_classes
    shared_location_classes = loc_classes


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
    global shared_position_classes, shared_location_classes

    # Fix multiprocessing connection issues per SQLAlchemy docs:
    # https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork
    engine = get_engine()
    engine.dispose(close=False)

    dump_reader = DumpReader()
    database_inserter = DatabaseInserter()

    positions = []
    locations = []
    countries = []
    counts = {"positions": 0, "locations": 0, "countries": 0}
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

            # Create shared entity data
            entity_name = entity.get_entity_name()
            if not entity_name:
                continue  # Skip entities without names - needed for embeddings in enrichment

            entity_data = {
                "wikidata_id": entity_id,
                "name": entity_name,
            }

            # Check entity type and add type-specific fields
            if entity.is_position(shared_position_classes):
                most_specific_class_id = entity.get_most_specific_class_wikidata_id(
                    shared_position_classes
                )
                if most_specific_class_id:
                    entity_data["wikidata_class_id"] = most_specific_class_id

                positions.append(entity_data)
                counts["positions"] += 1
            elif entity.is_location(shared_location_classes):
                most_specific_class_id = entity.get_most_specific_class_wikidata_id(
                    shared_location_classes
                )
                if most_specific_class_id:
                    entity_data["wikidata_class_id"] = most_specific_class_id

                locations.append(entity_data)
                counts["locations"] += 1
            elif entity.is_country():
                entity_data["iso_code"] = entity.extract_iso_code()
                countries.append(entity_data)
                counts["countries"] += 1

            # Process batches when they reach the batch size
            if len(positions) >= batch_size:
                database_inserter.insert_positions_batch(positions)
                positions = []

            if len(locations) >= batch_size:
                database_inserter.insert_locations_batch(locations)
                locations = []

            if len(countries) >= batch_size:
                database_inserter.insert_countries_batch(countries)
                countries = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batches on successful completion
    if positions:
        database_inserter.insert_positions_batch(positions)
    if locations:
        database_inserter.insert_locations_batch(locations)
    if countries:
        database_inserter.insert_countries_batch(countries)

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    return counts, entity_count


class WikidataEntityImporter:
    """Extract supporting entities from the Wikidata dump using parallel processing."""

    def __init__(self):
        """Initialize the entity importer."""
        self.dump_reader = DumpReader()

    def _query_hierarchy_descendants(self, root_id: str, session: Session) -> Set[str]:
        """
        Query all descendants of a root entity from database using recursive SQL.
        Only returns classes that have names (needed for embeddings in enrichment).

        Args:
            root_id: The root entity QID
            session: Database session

        Returns:
            Set of all descendant QIDs (including the root) that have names
        """
        # Use recursive CTE to find all descendants, filtered by classes with names
        sql = text(
            """
            WITH RECURSIVE descendants AS (
                -- Base case: start with the root entity
                SELECT CAST(:root_id AS VARCHAR) AS wikidata_id
                UNION
                -- Recursive case: find all children
                SELECT sr.child_class_id AS wikidata_id
                FROM subclass_relations sr
                JOIN descendants d ON sr.parent_class_id = d.wikidata_id
            )
            SELECT DISTINCT d.wikidata_id 
            FROM descendants d
            JOIN wikidata_classes wc ON d.wikidata_id = wc.wikidata_id
            WHERE wc.name IS NOT NULL
        """
        )

        result = session.execute(sql, {"root_id": root_id})
        return {row[0] for row in result.fetchall()}

    def extract_entities_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 1000,
    ) -> Dict[str, int]:
        """
        Extract supporting entities from the Wikidata dump using parallel processing.
        Uses frozensets to efficiently share descendant QIDs across workers with O(1) lookups.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch

        Returns:
            Dictionary with counts of extracted entities (positions, locations, countries)
        """
        # Load only position and location descendants from database (optimized)
        with Session(get_engine()) as session:
            # Check if hierarchy data exists first
            relation_count = session.query(SubclassRelation).count()
            if relation_count == 0:
                raise ValueError(
                    "Complete hierarchy not found in database. Run 'poliloom dump build-hierarchy' first."
                )

            # Get descendant sets for filtering (optimized - only loads what we need)
            position_classes = self._query_hierarchy_descendants("Q294414", session)
            location_classes = self._query_hierarchy_descendants("Q2221906", session)

            logger.info(
                f"Filtering for {len(position_classes)} position types and {len(location_classes)} location types"
            )

        # Build frozensets once in parent, BEFORE starting Pool
        position_classes = frozenset(position_classes)
        location_classes = frozenset(location_classes)

        logger.info(f"Prepared {len(position_classes)} position classes")
        logger.info(f"Prepared {len(location_classes)} location classes")

        num_workers = mp.cpu_count()
        logger.info(f"Using parallel processing with {num_workers} workers")

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(
                processes=num_workers,
                initializer=init_entity_worker,
                initargs=(position_classes, location_classes),
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
        }
        total_entities = 0

        for counts, chunk_count in chunk_results:
            total_entities += chunk_count
            for key in total_counts:
                total_counts[key] += counts[key]

        logger.info(f"Extraction complete. Total processed: {total_entities}")
        logger.info(
            f"Extracted: {total_counts['positions']} positions, {total_counts['locations']} locations, {total_counts['countries']} countries"
        )

        return total_counts
