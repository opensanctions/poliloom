"""Wikidata dump processing service for extracting entities."""

import logging
import multiprocessing as mp
from typing import Dict, Set
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from .dump_reader import DumpReader
from .hierarchy_builder import HierarchyBuilder
from .database_inserter import DatabaseInserter
from .worker_manager import (
    init_worker_with_db,
    init_worker_with_hierarchy,
    init_worker_with_db_and_qids,
    get_hierarchy_sets,
)
from ..database import get_db_session
from ..models import WikidataClass, SubclassRelation
from ..entities import WikidataEntity
from ..entities.factory import WikidataEntityFactory
from ..entities.politician import WikidataPolitician
from ..entities.position import WikidataPosition
from ..entities.location import WikidataLocation
from ..entities.country import WikidataCountry

logger = logging.getLogger(__name__)


class WikidataDumpProcessor:
    """Process Wikidata JSON dumps to extract entities and build hierarchy trees."""

    def __init__(self, session=None):
        """Initialize the dump processor.

        Args:
            session: Database session (optional, not used for hierarchy building)
        """
        self.dump_reader = DumpReader()
        self.hierarchy_builder = HierarchyBuilder()
        self.database_inserter = DatabaseInserter()

    def build_hierarchy_trees(
        self,
        dump_file_path: str,
    ) -> Dict[str, Set[str]]:
        """
        Build hierarchy trees for positions and locations from Wikidata dump.

        Uses a memory-efficient two-phase approach:
        1. Collect subclass relationships from dump
        2. Insert WikidataClass and SubclassRelation records in batches, then update names

        Args:
            dump_file_path: Path to the Wikidata JSON dump file

        Returns:
            Dictionary with 'positions' and 'locations' keys containing sets of QIDs
        """
        logger.info(f"Building hierarchy trees from dump file: {dump_file_path}")

        # Phase 1: Collect subclass relationships
        logger.info("Phase 1: Collecting subclass relationships...")
        subclass_relations = self._collect_subclass_relationships(dump_file_path)

        # Extract all unique QIDs that need WikidataClass records
        all_qids = set()
        for parent_qid, children in subclass_relations.items():
            all_qids.add(parent_qid)
            all_qids.update(children)

        logger.info(
            f"Found {len(all_qids)} unique entities in hierarchy (vs ~100M total entities)"
        )

        # Phase 2: Insert WikidataClass and SubclassRelation records in batches
        logger.info("Phase 2: Inserting WikidataClass and SubclassRelation records...")
        self._batch_insert_subclass_relations(subclass_relations)

        # Phase 3: Extract and batch update names for all WikidataClass records in database
        logger.info(
            "Phase 3: Extracting and updating names for all WikidataClass records..."
        )
        self._batch_update_wikidata_class_names(dump_file_path, all_qids)

        # Extract specific trees from the complete hierarchy
        descendants = self.hierarchy_builder.get_position_and_location_descendants(
            subclass_relations
        )

        logger.info("✅ Hierarchy building complete")
        logger.info(
            f"  • Positions: {len(descendants['positions'])} descendants of Q294414"
        )
        logger.info(
            f"  • Locations: {len(descendants['locations'])} descendants of Q2221906"
        )

        return descendants

    def _collect_subclass_relationships(
        self, dump_file_path: str
    ) -> Dict[str, Set[str]]:
        """
        Collect QIDs involved in P279 relationships (memory-efficient first step).

        This step only collects relationship data without entity names,
        dramatically reducing memory usage from 64GB+ to ~100MB.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file

        Returns:
            Dictionary mapping parent QIDs to sets of child QIDs
        """
        num_workers = mp.cpu_count()
        logger.info(f"Using {num_workers} parallel workers")

        # Split file into chunks for parallel processing
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Processing {len(chunks)} file chunks")

        pool = None
        try:
            # Pass 1 doesn't need database access, just file processing
            pool = mp.Pool(processes=num_workers)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_chunk_for_relationships,
                [
                    (dump_file_path, start, end, i)
                    for i, (start, end) in enumerate(chunks)
                ],
            )

            chunk_results = async_result.get()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, cleaning up workers...")
            if pool:
                pool.terminate()
                try:
                    pool.join(timeout=5)
                except Exception:
                    pass
            raise KeyboardInterrupt("Relationship collection interrupted by user")
        finally:
            if pool:
                pool.close()
                pool.join()

        # Merge results from all chunks (only relations, no names)
        subclass_relations = defaultdict(set)
        total_entities = 0

        for chunk_relations, chunk_count in chunk_results:
            total_entities += chunk_count
            for parent_id, children in chunk_relations.items():
                subclass_relations[parent_id].update(children)

        logger.info(
            f"Relationship collection complete: Processed {total_entities} entities"
        )
        logger.info(f"Found {len(subclass_relations)} entities with subclasses")

        return dict(subclass_relations)

    def _batch_insert_subclass_relations(
        self, subclass_relations: Dict[str, Set[str]]
    ) -> None:
        """
        Insert WikidataClass and SubclassRelation records in smaller committed batches.
        Each batch commits independently for better progress visibility and recovery.

        Args:
            subclass_relations: Mapping of parent QIDs to child QID sets
        """
        total_relations = sum(len(children) for children in subclass_relations.values())
        logger.info(f"Inserting {total_relations} subclass relations")

        # 1. Insert WikidataClass records in committed batches
        all_qids = set(subclass_relations.keys())
        for children in subclass_relations.values():
            all_qids.update(children)

        logger.info(f"Inserting {len(all_qids)} WikidataClass records")
        class_data = [{"wikidata_id": qid} for qid in all_qids]

        batch_size = 10000
        total_batches = (len(class_data) + batch_size - 1) // batch_size

        for i in range(0, len(class_data), batch_size):
            batch_num = i // batch_size + 1
            batch = class_data[i : i + batch_size]

            # Each batch gets its own committed transaction
            with get_db_session() as session:
                stmt = insert(WikidataClass).values(batch)
                stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
                session.execute(stmt)
                session.commit()

            logger.info(
                f"Inserted WikidataClass batch {batch_num}/{total_batches} ({len(batch)} records)"
            )

        logger.info(f"✅ Completed inserting {len(class_data)} WikidataClass records")

        # 2. Insert SubclassRelation records in committed batches
        relation_data = [
            {"parent_class_id": parent_qid, "child_class_id": child_qid}
            for parent_qid, children in subclass_relations.items()
            for child_qid in children
        ]

        total_relation_batches = (len(relation_data) + batch_size - 1) // batch_size
        logger.info(
            f"Inserting {len(relation_data)} subclass relations in {total_relation_batches} batches"
        )

        for i in range(0, len(relation_data), batch_size):
            batch_num = i // batch_size + 1
            batch = relation_data[i : i + batch_size]

            # Each batch gets its own committed transaction
            with get_db_session() as session:
                stmt = insert(SubclassRelation).values(batch)
                stmt = stmt.on_conflict_do_nothing(
                    constraint="uq_subclass_parent_child"
                )
                session.execute(stmt)
                session.commit()

            logger.info(
                f"Inserted SubclassRelation batch {batch_num}/{total_relation_batches} ({len(batch)} records)"
            )

        logger.info(f"✅ Completed inserting {len(relation_data)} subclass relations")

    def _batch_update_wikidata_class_names(
        self, dump_file_path: str, target_qids: set
    ) -> None:
        """
        Extract names from dump and batch update WikidataClass records for target QIDs.
        Uses shared memory to avoid passing millions of QIDs to each worker.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            target_qids: Set of QIDs to extract names for (already available from hierarchy building)
        """
        logger.info(f"Extracting names for {len(target_qids)} WikidataClass records")

        # Convert QIDs to a list that can be shared via process initialization
        # This avoids creating copies for each worker process
        qid_list = list(target_qids)

        logger.info(f"Prepared QID list for sharing: {len(target_qids)} QIDs")

        # Use parallel processing to extract names for all classes in database
        num_workers = mp.cpu_count()
        logger.info(f"Using {num_workers} parallel workers for name extraction")

        # Split file into chunks for parallel processing
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        pool = None

        try:

            def init_worker():
                init_worker_with_db_and_qids(qid_list)

            pool = mp.Pool(processes=num_workers, initializer=init_worker)

            # Each worker processes its chunk independently (no QIDs parameter needed)
            async_result = pool.starmap_async(
                self._process_chunk_for_name_updates,
                [
                    (dump_file_path, start, end, i)
                    for i, (start, end) in enumerate(chunks)
                ],
            )

            chunk_results = async_result.get()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, cleaning up workers...")
            if pool:
                pool.terminate()
                try:
                    pool.join(timeout=5)
                except Exception:
                    pass
            raise KeyboardInterrupt("Name extraction interrupted by user")
        finally:
            if pool:
                pool.close()
                pool.join()

        # Merge results from all chunks (workers now handle their own database updates)
        total_updates = 0
        total_entities = 0

        for updates_count, chunk_count in chunk_results:
            total_entities += chunk_count
            total_updates += updates_count

        logger.info(f"Name extraction complete: processed {total_entities} entities")
        logger.info(f"Updated names for {total_updates} entities")

        logger.info("✅ WikidataClass name updates complete")

    def _process_chunk_for_name_updates(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
    ):
        """
        Worker process: Extract names only for entities in shared QIDs set.
        Updates WikidataClass records directly in database at end of chunk processing.
        Returns count of updates made.
        """
        from .worker_manager import get_worker_session, get_shared_qids
        from sqlalchemy.dialects.postgresql import insert
        from ..models import WikidataClass

        # Get QIDs from shared memory instead of function parameter
        target_qids = get_shared_qids()

        name_updates = {}
        entity_count = 0
        interrupted = False

        try:
            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                if interrupted:
                    break

                entity_count += 1

                entity_id = entity.get("id", "")
                if not entity_id or entity_id not in target_qids:
                    continue

                # Extract name using base entity logic
                try:
                    name = WikidataEntity.extract_name(entity)
                    if name:
                        name_updates[entity_id] = name
                except Exception as e:
                    logger.debug(
                        f"Worker {worker_id}: failed to extract name for {entity_id}: {e}"
                    )
                    continue

        except KeyboardInterrupt:
            interrupted = True
            logger.info(f"Worker {worker_id}: name extraction interrupted")
        except Exception as e:
            logger.error(f"Worker {worker_id}: error during name extraction: {e}")

        # Update database with collected names at end of chunk processing
        updates_count = 0
        if name_updates and not interrupted:
            try:
                session = get_worker_session()
                try:
                    # Bulk update using PostgreSQL upsert
                    batch_updates = [
                        {
                            "wikidata_id": wikidata_id,
                            "name": name,
                            "updated_at": datetime.now(timezone.utc),
                        }
                        for wikidata_id, name in name_updates.items()
                    ]

                    stmt = insert(WikidataClass).values(batch_updates)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["wikidata_id"],
                        set_={
                            "name": stmt.excluded.name,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )

                    session.execute(stmt)
                    session.commit()
                    updates_count = len(name_updates)

                    logger.info(
                        f"Worker {worker_id}: updated {updates_count} WikidataClass names in database"
                    )

                except Exception as db_error:
                    session.rollback()
                    logger.error(
                        f"Worker {worker_id}: database update failed: {db_error}"
                    )
                finally:
                    session.close()

            except Exception as session_error:
                logger.error(
                    f"Worker {worker_id}: failed to get database session: {session_error}"
                )

        if interrupted:
            logger.info(f"Worker {worker_id}: interrupted, returning partial results")
        else:
            logger.info(
                f"Worker {worker_id}: extracted {len(name_updates)} names from {entity_count} entities"
            )

        return updates_count, entity_count

    def _process_chunk_for_relationships(
        self, dump_file_path: str, start_byte: int, end_byte: int, worker_id: int
    ):
        """
        Worker process: Extract only P279 relationships, no entity names.

        This dramatically reduces memory usage by avoiding entity name collection.
        """
        interrupted = False

        try:
            subclass_relations = defaultdict(set)
            entity_count = 0

            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                if interrupted:
                    break

                entity_count += 1

                # Progress reporting for large chunks
                if (
                    entity_count % 100000 == 0
                ):  # Increased frequency since no name processing
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                # Extract P279 relationships only (no entity names)
                chunk_relations = (
                    self.hierarchy_builder.extract_subclass_relations_from_entity(
                        entity
                    )
                )
                for parent_id, children in chunk_relations.items():
                    subclass_relations[parent_id].update(children)

            logger.info(
                f"Worker {worker_id}: Relationship extraction complete, processed {entity_count} entities"
            )
            return dict(subclass_relations), entity_count

        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id}: Relationship extraction interrupted")
            return dict(subclass_relations), entity_count
        except Exception as e:
            logger.error(f"Worker {worker_id}: Relationship extraction error: {e}")
            return {}, 0

    def extract_entities_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """
        Extract supporting entities from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch

        Returns:
            Dictionary with counts of extracted entities (positions, locations, countries)
        """
        # Load only position and location descendants from database (optimized)
        with get_db_session() as session:
            # Check if hierarchy data exists first
            relation_count = session.query(SubclassRelation).count()
            if relation_count == 0:
                raise ValueError(
                    "Complete hierarchy not found in database. Run 'poliloom dump build-hierarchy' first."
                )

            # Get descendant sets for filtering (optimized - only loads what we need)
            descendants = self.hierarchy_builder.get_position_and_location_descendants_from_database(
                session
            )
            position_descendants = descendants["positions"]
            location_descendants = descendants["locations"]

            logger.info(
                f"Filtering for {len(position_descendants)} position types and {len(location_descendants)} location types"
            )

        num_workers = mp.cpu_count()
        logger.info(f"Using parallel processing with {num_workers} workers")

        return self._extract_supporting_entities_parallel(
            dump_file_path,
            batch_size,
            position_descendants,
            location_descendants,
        )

    def extract_politicians_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 100,
    ) -> Dict[str, int]:
        """
        Extract politicians from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch

        Returns:
            Dictionary with counts of extracted entities
        """
        num_workers = mp.cpu_count()
        logger.info(f"Using parallel processing with {num_workers} workers")

        return self._extract_politicians_parallel(
            dump_file_path,
            batch_size,
        )

    def _extract_supporting_entities_parallel(
        self,
        dump_file_path: str,
        batch_size: int,
        position_descendants: Set[str],
        location_descendants: Set[str],
    ) -> Dict[str, int]:
        """Parallel implementation for supporting entities extraction (positions, locations, countries)."""
        num_workers = mp.cpu_count()

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            # Initialize workers with hierarchy data
            def init_worker():
                init_worker_with_hierarchy(
                    position_descendants,
                    location_descendants,
                )

            pool = mp.Pool(processes=num_workers, initializer=init_worker)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_supporting_entities_chunk,
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
                    pool.join(timeout=5)  # Wait up to 5 seconds for workers to finish
                except Exception:
                    pass  # If join times out, continue anyway
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
            "politicians": 0,
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

    def _extract_politicians_parallel(
        self,
        dump_file_path: str,
        batch_size: int,
    ) -> Dict[str, int]:
        """Parallel implementation for politician extraction."""
        num_workers = mp.cpu_count()

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            # Initialize workers with database only (politicians don't need hierarchy)
            pool = mp.Pool(processes=num_workers, initializer=init_worker_with_db)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_politicians_chunk,
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
                    pool.join(timeout=5)  # Wait up to 5 seconds for workers to finish
                except Exception:
                    pass  # If join times out, continue anyway
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
            "politicians": 0,
        }
        total_entities = 0

        for counts, chunk_count in chunk_results:
            total_entities += chunk_count
            for key in total_counts:
                total_counts[key] += counts[key]

        logger.info(f"Extraction complete. Total processed: {total_entities}")
        logger.info(f"Extracted: {total_counts['politicians']} politicians")

        return total_counts

    def _process_supporting_entities_chunk(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        batch_size: int,
    ):
        """
        Process a specific byte range of the dump file for supporting entities extraction.

        Each worker independently reads and parses its assigned chunk.
        Returns entity counts found in this chunk.
        """
        # Get hierarchy data from worker globals
        position_descendants, location_descendants = get_hierarchy_sets()

        positions = []
        locations = []
        countries = []
        counts = {"positions": 0, "locations": 0, "countries": 0, "politicians": 0}
        entity_count = 0
        interrupted = False

        try:
            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                entity_count += 1

                # Progress reporting for large chunks
                if entity_count % 50000 == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                entity_id = entity.get("id", "")
                if not entity_id:
                    continue

                # Use factory to create appropriate entity instance
                try:
                    # For supporting entities, create position/location/country entities
                    wikidata_entity = WikidataEntityFactory.create_entity(
                        entity,
                        position_descendants,
                        location_descendants,
                        allowed_types=["position", "location", "country"],
                    )

                    if wikidata_entity is None:
                        continue

                    # Route entity to appropriate batch based on type
                    if isinstance(wikidata_entity, WikidataPosition):
                        position_data = wikidata_entity.to_database_dict()
                        if position_data:
                            positions.append(position_data)
                            counts["positions"] += 1
                    elif isinstance(wikidata_entity, WikidataLocation):
                        location_data = wikidata_entity.to_database_dict()
                        if location_data:
                            locations.append(location_data)
                            counts["locations"] += 1
                    elif isinstance(wikidata_entity, WikidataCountry):
                        country_data = wikidata_entity.to_database_dict()
                        if country_data:
                            countries.append(country_data)
                            counts["countries"] += 1
                except Exception as e:
                    # Log entity processing errors but continue processing
                    logger.debug(
                        f"Worker {worker_id}: skipping entity {entity_id} due to error: {e}"
                    )
                    continue

                # Process batches when they reach the batch size
                if len(positions) >= batch_size:
                    self.database_inserter.insert_positions_batch(positions)
                    positions = []

                if len(locations) >= batch_size:
                    self.database_inserter.insert_locations_batch(locations)
                    locations = []

                if len(countries) >= batch_size:
                    self.database_inserter.insert_countries_batch(countries)
                    countries = []

        except KeyboardInterrupt:
            interrupted = True
            logger.info(f"Worker {worker_id}: interrupted")
        except Exception as e:
            logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        finally:
            # Always process remaining entities in final batches
            try:
                if positions:
                    self.database_inserter.insert_positions_batch(positions)
                if locations:
                    self.database_inserter.insert_locations_batch(locations)
                if countries:
                    self.database_inserter.insert_countries_batch(countries)
            except Exception as cleanup_error:
                logger.warning(
                    f"Worker {worker_id}: error during cleanup: {cleanup_error}"
                )

            if interrupted:
                logger.info(
                    f"Worker {worker_id}: interrupted, returning partial results"
                )
            else:
                logger.info(
                    f"Worker {worker_id}: finished processing {entity_count} entities"
                )

        return counts, entity_count

    def _process_politicians_chunk(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        batch_size: int,
    ):
        """
        Process a specific byte range of the dump file for politician extraction.

        Each worker independently reads and parses its assigned chunk.
        Returns entity counts found in this chunk.
        """
        politicians = []
        counts = {"positions": 0, "locations": 0, "countries": 0, "politicians": 0}
        entity_count = 0
        interrupted = False

        try:
            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                entity_count += 1

                # Progress reporting for large chunks
                if entity_count % 50000 == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                entity_id = entity.get("id", "")
                if not entity_id:
                    continue

                # Use factory to create appropriate entity instance
                try:
                    # For politicians, only create politician entities
                    wikidata_entity = WikidataEntityFactory.create_entity(
                        entity, set(), set(), allowed_types=["politician"]
                    )

                    if wikidata_entity is None:
                        continue

                    # Route entity to appropriate batch based on type
                    if isinstance(wikidata_entity, WikidataPolitician):
                        politician_data = wikidata_entity.to_database_dict()
                        if politician_data:
                            politicians.append(politician_data)
                            counts["politicians"] += 1
                except Exception as e:
                    # Log entity processing errors but continue processing
                    logger.debug(
                        f"Worker {worker_id}: skipping entity {entity_id} due to error: {e}"
                    )
                    continue

                # Process batches when they reach the batch size
                if len(politicians) >= batch_size:
                    self.database_inserter.insert_politicians_batch(politicians)
                    politicians = []

        except KeyboardInterrupt:
            interrupted = True
            logger.info(f"Worker {worker_id}: interrupted")
        except Exception as e:
            logger.error(f"Worker {worker_id}: error processing chunk: {e}")
        finally:
            # Always process remaining entities in final batches
            try:
                if politicians:
                    self.database_inserter.insert_politicians_batch(politicians)
            except Exception as cleanup_error:
                logger.warning(
                    f"Worker {worker_id}: error during cleanup: {cleanup_error}"
                )

            if interrupted:
                logger.info(
                    f"Worker {worker_id}: interrupted, returning partial results"
                )
            else:
                logger.info(
                    f"Worker {worker_id}: finished processing {entity_count} entities"
                )

        return counts, entity_count
