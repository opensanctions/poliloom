"""Wikidata entity importing service for supporting entities (positions, locations, countries)."""

import logging
import multiprocessing as mp
from typing import Dict, Set, Tuple, List

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from .dump_reader import DumpReader
from ..database import get_engine
from ..models import (
    SubclassRelation,
    Position,
    Location,
    Country,
    PositionClass,
    LocationClass,
)
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


def _insert_positions_batch(positions: list[dict]) -> None:
    """Insert a batch of positions into the database."""
    if not positions:
        return

    with Session(get_engine()) as session:
        # Insert positions first
        stmt = insert(Position).values(
            [
                {
                    "wikidata_id": p["wikidata_id"],
                    "name": p["name"],
                    "embedding": None,  # Will be generated later
                }
                for p in positions
            ]
        )

        # On conflict, update the name and clear embedding (since embedding depends on name)
        stmt = stmt.on_conflict_do_update(
            index_elements=["wikidata_id"],
            set_={
                "name": stmt.excluded.name,
                "embedding": None,  # Clear embedding when name changes
            },
        )

        session.execute(stmt)

        # Insert position-class relationships
        position_class_data = []
        for p in positions:
            for class_id in p.get("wikidata_class_ids", []):
                position_class_data.append(
                    {"position_id": p["wikidata_id"], "class_id": class_id}
                )

        if position_class_data:
            # Clear existing relationships for these positions first
            position_ids = [p["wikidata_id"] for p in positions]
            session.query(PositionClass).filter(
                PositionClass.position_id.in_(position_ids)
            ).delete()

            # Insert new relationships
            stmt = insert(PositionClass).values(position_class_data)
            stmt = stmt.on_conflict_do_nothing()  # In case of duplicates
            session.execute(stmt)

        session.commit()
        logger.debug(
            f"Processed {len(positions)} positions with {len(position_class_data)} class relationships"
        )


def _insert_locations_batch(locations: list[dict]) -> None:
    """Insert a batch of locations into the database."""
    if not locations:
        return

    with Session(get_engine()) as session:
        # Insert locations first
        stmt = insert(Location).values(
            [
                {
                    "wikidata_id": loc["wikidata_id"],
                    "name": loc["name"],
                    "embedding": None,  # Will be generated later
                }
                for loc in locations
            ]
        )

        # On conflict, update the name and clear embedding (since embedding depends on name)
        stmt = stmt.on_conflict_do_update(
            index_elements=["wikidata_id"],
            set_={
                "name": stmt.excluded.name,
                "embedding": None,  # Clear embedding when name changes
            },
        )

        session.execute(stmt)

        # Insert location-class relationships
        location_class_data = []
        for loc in locations:
            for class_id in loc.get("wikidata_class_ids", []):
                location_class_data.append(
                    {"location_id": loc["wikidata_id"], "class_id": class_id}
                )

        if location_class_data:
            # Clear existing relationships for these locations first
            location_ids = [loc["wikidata_id"] for loc in locations]
            session.query(LocationClass).filter(
                LocationClass.location_id.in_(location_ids)
            ).delete()

            # Insert new relationships
            stmt = insert(LocationClass).values(location_class_data)
            stmt = stmt.on_conflict_do_nothing()  # In case of duplicates
            session.execute(stmt)

        session.commit()
        logger.debug(
            f"Processed {len(locations)} locations with {len(location_class_data)} class relationships"
        )


def _insert_countries_batch(countries: list[dict]) -> None:
    """Insert a batch of countries into the database using ON CONFLICT."""
    if not countries:
        return

    with Session(get_engine()) as session:
        # Prepare data for bulk insert
        country_data = [
            {
                "wikidata_id": c["wikidata_id"],
                "name": c["name"],
                "iso_code": c["iso_code"],
            }
            for c in countries
        ]

        # Use PostgreSQL's ON CONFLICT to handle duplicates
        # We need to handle both wikidata_id and iso_code constraints
        # Use ON CONFLICT DO UPDATE for wikidata_id to allow name updates
        stmt = insert(Country).values(country_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=["wikidata_id"],
            set_={
                "name": stmt.excluded.name,
                "iso_code": stmt.excluded.iso_code,
            },
        )

        session.execute(stmt)
        session.commit()
        logger.debug(f"Processed {len(countries)} countries (upserted)")


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
            # Check if entity is a position based on instance hierarchy
            instance_ids = entity.get_instance_of_ids()
            if any(
                instance_id in shared_position_classes for instance_id in instance_ids
            ):
                # Get all valid class IDs for this position
                valid_class_ids = [
                    class_id
                    for class_id in instance_ids
                    if class_id in shared_position_classes
                ]
                entity_data["wikidata_class_ids"] = valid_class_ids

                positions.append(entity_data)
                counts["positions"] += 1
            elif any(
                instance_id in shared_location_classes for instance_id in instance_ids
            ):
                # Get all valid class IDs for this location
                valid_class_ids = [
                    class_id
                    for class_id in instance_ids
                    if class_id in shared_location_classes
                ]
                entity_data["wikidata_class_ids"] = valid_class_ids

                locations.append(entity_data)
                counts["locations"] += 1
            elif bool(
                instance_ids.intersection(
                    {"Q6256", "Q3624078", "Q20181813", "Q1520223", "Q1489259"}
                )
            ):
                # Extract ISO 3166-1 alpha-2 code for countries
                iso_code = None
                iso_claims = entity.get_truthy_claims("P297")
                for claim in iso_claims:
                    try:
                        iso_code = claim["mainsnak"]["datavalue"]["value"]
                        break
                    except (KeyError, TypeError):
                        continue
                entity_data["iso_code"] = iso_code
                countries.append(entity_data)
                counts["countries"] += 1

            # Process batches when they reach the batch size
            if len(positions) >= batch_size:
                _insert_positions_batch(positions)
                positions = []

            if len(locations) >= batch_size:
                _insert_locations_batch(locations)
                locations = []

            if len(countries) >= batch_size:
                _insert_countries_batch(countries)
                countries = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        raise

    # Process remaining entities in final batches on successful completion
    if positions:
        _insert_positions_batch(positions)
    if locations:
        _insert_locations_batch(locations)
    if countries:
        _insert_countries_batch(countries)

    logger.info(f"Worker {worker_id}: finished processing {entity_count} entities")

    return counts, entity_count


class WikidataEntityImporter:
    """Extract supporting entities from the Wikidata dump using parallel processing."""

    def __init__(self):
        """Initialize the entity importer."""
        self.dump_reader = DumpReader()

    def _query_hierarchy_descendants(
        self, root_ids: List[str], session: Session, ignore_ids: List[str] = None
    ) -> Set[str]:
        """
        Query all descendants of multiple root entities from database using recursive SQL.
        Only returns classes that have names and excludes ignored IDs and their descendants.

        Args:
            root_ids: List of root entity QIDs
            session: Database session
            ignore_ids: List of entity QIDs to exclude along with their descendants

        Returns:
            Set of all descendant QIDs (including the roots) that have names
        """
        if not root_ids:
            return set()

        ignore_ids = ignore_ids or []

        # Use recursive CTEs - one for descendants, one for ignored descendants
        sql = text(
            """
            WITH RECURSIVE descendants AS (
                -- Base case: start with all root entities
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_classes 
                WHERE wikidata_id = ANY(:root_ids)
                UNION
                -- Recursive case: find all children
                SELECT sr.child_class_id AS wikidata_id
                FROM subclass_relations sr
                JOIN descendants d ON sr.parent_class_id = d.wikidata_id
            ),
            ignored_descendants AS (
                -- Base case: start with ignored IDs
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_classes 
                WHERE wikidata_id = ANY(:ignore_ids)
                UNION
                -- Recursive case: find all children of ignored IDs
                SELECT sr.child_class_id AS wikidata_id
                FROM subclass_relations sr
                JOIN ignored_descendants id ON sr.parent_class_id = id.wikidata_id
            )
            SELECT DISTINCT d.wikidata_id 
            FROM descendants d
            JOIN wikidata_classes wc ON d.wikidata_id = wc.wikidata_id
            WHERE wc.name IS NOT NULL
            AND d.wikidata_id NOT IN (SELECT wikidata_id FROM ignored_descendants)
        """
        )

        result = session.execute(sql, {"root_ids": root_ids, "ignore_ids": ignore_ids})
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
                    "Complete hierarchy not found in database. Run 'poliloom dump import-hierarchy' first."
                )

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
                "Q120560",  # minor basilica
                "Q2977",  # cathedral
            ]
            position_classes = self._query_hierarchy_descendants(
                position_root_ids, session, ignore_ids
            )
            location_classes = self._query_hierarchy_descendants(["Q2221906"], session)

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
