"""Wikidata dump processing service for extracting entities."""

import logging
import multiprocessing as mp
from typing import Dict, Set, List
from collections import defaultdict

from .dump_reader import DumpReader
from .hierarchy_builder import HierarchyBuilder
from .database_inserter import DatabaseInserter
from .worker_manager import (
    init_worker_with_db,
    init_worker_with_hierarchy,
)
from ..database import get_db_session
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

        Uses a memory-efficient three-step approach:
        1. Collect QIDs involved in P279 relationships (~100MB memory)
        2. Insert WikidataClass records for those QIDs only
        3. Insert SubclassRelation records with proper foreign keys

        Args:
            dump_file_path: Path to the Wikidata JSON dump file

        Returns:
            Dictionary with 'positions' and 'locations' keys containing sets of QIDs
        """
        logger.info(f"Building hierarchy trees from dump file: {dump_file_path}")

        # Step 1: Collect QIDs involved in P279 relationships (memory-efficient)
        logger.info("Step 1: Collecting QIDs involved in P279 relationships...")
        subclass_relations = self._collect_subclass_relationships(dump_file_path)

        # Extract all unique QIDs that need WikidataClass records
        all_qids = set()
        for parent_qid, children in subclass_relations.items():
            all_qids.add(parent_qid)
            all_qids.update(children)

        logger.info(
            f"Found {len(all_qids)} unique entities in hierarchy (vs ~100M total entities)"
        )

        # Step 2: Insert WikidataClass records for filtered QIDs
        logger.info("Step 2: Inserting WikidataClass records...")
        self._extract_and_store_entity_names(dump_file_path, all_qids)

        # Step 3: Insert SubclassRelation records
        logger.info("Step 3: Inserting SubclassRelation records...")
        self._store_hierarchy_relationships(subclass_relations)

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

    def _extract_and_store_entity_names(
        self, dump_file_path: str, qids_to_extract: Set[str]
    ) -> None:
        """
        Extract and insert WikidataClass records for filtered QIDs only.

        This step processes the dump again but only extracts names for entities
        that are involved in the hierarchy, dramatically reducing memory usage.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            qids_to_extract: Set of QIDs to extract names for
        """
        num_workers = mp.cpu_count()
        logger.info(f"Using {num_workers} parallel workers")
        logger.info(f"Extracting names for {len(qids_to_extract)} filtered entities")

        # Split file into chunks for parallel processing
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)

        pool = None
        try:
            pool = mp.Pool(processes=num_workers)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_chunk_for_entity_names,
                [
                    (dump_file_path, start, end, i, qids_to_extract)
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
            raise KeyboardInterrupt("Entity name extraction interrupted by user")
        finally:
            if pool:
                pool.close()
                pool.join()

        # Collect all entity data from workers and batch insert
        all_entity_data = []
        total_entities = 0

        for entity_data_list, chunk_count in chunk_results:
            total_entities += chunk_count
            all_entity_data.extend(entity_data_list)

        logger.info(
            f"Entity name extraction complete: Processed {total_entities} entities"
        )
        logger.info(f"Collected {len(all_entity_data)} entities for batch insertion")

        if all_entity_data:
            self._batch_insert_wikidata_classes(all_entity_data)
            logger.info(
                f"WikidataClass records inserted for {len(all_entity_data)} entities"
            )

    def _store_hierarchy_relationships(
        self, subclass_relations: Dict[str, Set[str]]
    ) -> None:
        """
        Insert SubclassRelation records using existing WikidataClass records.

        All required WikidataClass records now exist, so we can safely create
        SubclassRelation records with proper foreign key references.

        Args:
            subclass_relations: Mapping of parent QIDs to child QID sets
        """
        logger.info(
            f"Inserting {sum(len(children) for children in subclass_relations.values())} subclass relations"
        )

        with get_db_session() as session:
            self.hierarchy_builder.insert_subclass_relations_batch(
                subclass_relations, session
            )

        logger.info(
            "Hierarchy relationship storage complete: All SubclassRelation records inserted"
        )

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

    def _process_chunk_for_entity_names(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        qids_to_extract: Set[str],
    ):
        """
        Worker process: Extract names for filtered QIDs and insert WikidataClass records.

        Only processes entities whose QIDs are in the filter set, dramatically
        reducing memory usage and processing time.
        """
        interrupted = False
        try:
            entity_data = []
            entity_count = 0
            extracted_count = 0

            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                if interrupted:
                    break

                entity_count += 1

                # Progress reporting
                if entity_count % 100000 == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities, extracted {extracted_count}"
                    )

                # Only process entities in our filter set
                entity_id = entity.get("id", "")
                if entity_id not in qids_to_extract:
                    continue

                name = self.hierarchy_builder.extract_entity_name_from_entity(entity)
                entity_data.append(
                    {
                        "wikidata_id": entity_id,
                        "name": name,
                    }
                )
                extracted_count += 1

            logger.info(
                f"Worker {worker_id}: Entity name extraction complete, processed {entity_count} entities, extracted {extracted_count}"
            )
            return entity_data, entity_count

        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id}: Entity name extraction interrupted")
            return entity_data, entity_count
        except Exception as e:
            logger.error(f"Worker {worker_id}: Entity name extraction error: {e}")
            return [], 0

    def _batch_insert_wikidata_classes(
        self, wikidata_classes: List[Dict[str, str]]
    ) -> None:
        """Insert WikidataClass records in manageable batches."""
        if not wikidata_classes:
            return

        batch_size = 10000
        total_batches = (len(wikidata_classes) + batch_size - 1) // batch_size

        logger.info(
            f"Inserting {len(wikidata_classes)} records in {total_batches} batches of {batch_size}"
        )

        try:
            from ..models import WikidataClass
            from sqlalchemy.dialects.postgresql import insert

            for i in range(0, len(wikidata_classes), batch_size):
                batch = wikidata_classes[i : i + batch_size]
                batch_num = (i // batch_size) + 1

                with get_db_session() as session:
                    stmt = insert(WikidataClass).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["wikidata_id"],
                        set_=dict(name=stmt.excluded.name),
                    )
                    session.execute(stmt)
                    session.commit()

                if batch_num % 5 == 0 or batch_num == total_batches:
                    logger.info(f"Completed batch {batch_num}/{total_batches}")

        except Exception as e:
            logger.error(f"Failed to insert WikidataClass batch: {e}")
            raise

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
            from ..models import SubclassRelation

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
        from .worker_manager import get_hierarchy_sets

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
