"""Wikidata dump processing service for extracting entities."""

import logging
import os
import multiprocessing as mp
from typing import Dict, Set, Optional
from collections import defaultdict

from .dump_reader import DumpReader
from .hierarchy_builder import HierarchyBuilder
from .entity_extractor import EntityExtractor
from .database_inserter import DatabaseInserter
from .worker_manager import (
    init_worker_with_db,
    init_worker_with_hierarchy,
    create_shared_memory_from_set,
    get_hierarchy_sets,
)

logger = logging.getLogger(__name__)


class WikidataDumpProcessor:
    """Process Wikidata JSON dumps to extract entities and build hierarchy trees."""

    def __init__(self):
        self.dump_reader = DumpReader()
        self.hierarchy_builder = HierarchyBuilder()
        self.entity_extractor = EntityExtractor()
        self.database_inserter = DatabaseInserter()

    def build_hierarchy_trees(
        self,
        dump_file_path: str,
        num_workers: Optional[int] = None,
        output_dir: str = ".",
    ) -> Dict[str, Set[str]]:
        """
        Build hierarchy trees for positions and locations from Wikidata dump.

        Uses parallel processing to extract all P279 (subclass of) relationships
        and build complete descendant trees.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            num_workers: Number of worker processes (default: CPU count)
            output_dir: Directory to save the complete hierarchy file (default: current directory)

        Returns:
            Dictionary with 'positions' and 'locations' keys containing sets of QIDs
        """
        logger.info(f"Building hierarchy trees from dump file: {dump_file_path}")

        if num_workers is None:
            num_workers = mp.cpu_count()

        logger.info(f"Using parallel processing with {num_workers} workers")

        subclass_relations = self._build_hierarchy_trees_parallel(
            dump_file_path, num_workers, output_dir
        )

        # Extract specific trees from the complete hierarchy
        descendants = self.hierarchy_builder.get_position_and_location_descendants(
            subclass_relations
        )

        return descendants

    def _build_hierarchy_trees_parallel(
        self, dump_file_path: str, num_workers: int, output_dir: str = "."
    ) -> Dict[str, Set[str]]:
        """
        Parallel implementation using chunk-based file reading.

        Returns:
            Dictionary of subclass_relations
        """

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path, num_workers)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(processes=num_workers, initializer=init_worker_with_db)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_chunk,
                [
                    (dump_file_path, start, end, i)
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
            raise KeyboardInterrupt("Hierarchy tree building interrupted by user")
        finally:
            if pool:
                pool.close()
                pool.join()

        # Merge results from all chunks
        subclass_relations = defaultdict(set)
        total_entities = 0

        for chunk_subclass, chunk_count in chunk_results:
            total_entities += chunk_count
            for parent_id, children in chunk_subclass.items():
                subclass_relations[parent_id].update(children)

        logger.info(f"Processed {total_entities} total entities")
        logger.info(f"Found {len(subclass_relations)} entities with subclasses")

        # Save complete hierarchy trees for future use
        self.hierarchy_builder.save_complete_hierarchy_trees(
            subclass_relations, output_dir
        )

        # Extract specific trees from the complete tree for convenience
        descendants = self.hierarchy_builder.get_position_and_location_descendants(
            subclass_relations
        )
        position_descendants = descendants["positions"]
        location_descendants = descendants["locations"]

        logger.info(
            f"Found {len(position_descendants)} position descendants of {self.hierarchy_builder.position_root}"
        )
        logger.info(
            f"Found {len(location_descendants)} location descendants of {self.hierarchy_builder.location_root}"
        )

        return subclass_relations

    def _process_chunk(
        self, dump_file_path: str, start_byte: int, end_byte: int, worker_id: int
    ):
        """
        Process a specific byte range of the dump file.

        Each worker independently reads and parses its assigned chunk.
        Returns subclass (P279) relationships found in this chunk.
        """
        # Simple interrupt flag without signal handlers to avoid cascading issues
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
                if entity_count % 50000 == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                # Extract P279 (subclass of) relationships using hierarchy builder
                chunk_relations = (
                    self.hierarchy_builder.extract_subclass_relations_from_entity(
                        entity
                    )
                )
                for parent_id, children in chunk_relations.items():
                    subclass_relations[parent_id].update(children)

            if interrupted:
                logger.info(
                    f"Worker {worker_id}: interrupted, returning partial results"
                )
            else:
                logger.info(
                    f"Worker {worker_id}: finished processing {entity_count} entities"
                )

            return dict(subclass_relations), entity_count

        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id}: interrupted, returning partial results")
            return dict(subclass_relations), entity_count
        except Exception as e:
            logger.error(f"Worker {worker_id}: error processing chunk: {e}")
            return {}, 0

    def extract_entities_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 100,
        num_workers: Optional[int] = None,
        hierarchy_dir: str = ".",
    ) -> Dict[str, int]:
        """
        Extract supporting entities (positions, locations, countries) from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch
            num_workers: Number of worker processes (default: CPU count)
            hierarchy_dir: Directory containing the complete hierarchy file (default: current directory)

        Returns:
            Dictionary with counts of extracted entities
        """
        # Load the hierarchy trees
        subclass_relations = self.hierarchy_builder.load_complete_hierarchy(
            hierarchy_dir
        )
        if subclass_relations is None:
            raise ValueError(
                "Complete hierarchy not found. Run 'poliloom dump build-hierarchy' first."
            )

        # Get descendant sets for filtering
        descendants = self.hierarchy_builder.get_position_and_location_descendants(
            subclass_relations
        )
        position_descendants = descendants["positions"]
        location_descendants = descendants["locations"]

        logger.info(
            f"Filtering for {len(position_descendants)} position types and {len(location_descendants)} location types"
        )

        if num_workers is None:
            num_workers = mp.cpu_count()

        logger.info(f"Using parallel processing with {num_workers} workers")

        return self._extract_entities_parallel(
            dump_file_path,
            batch_size,
            num_workers,
            position_descendants,
            location_descendants,
            include_politicians=False,
        )

    def extract_politicians_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 100,
        num_workers: Optional[int] = None,
        hierarchy_dir: str = ".",
    ) -> Dict[str, int]:
        """
        Extract politicians from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch
            num_workers: Number of worker processes (default: CPU count)
            hierarchy_dir: Directory containing the complete hierarchy file (default: current directory)

        Returns:
            Dictionary with counts of extracted entities
        """
        # Load the hierarchy trees (still needed for validation)
        subclass_relations = self.hierarchy_builder.load_complete_hierarchy(
            hierarchy_dir
        )
        if subclass_relations is None:
            raise ValueError(
                "Complete hierarchy not found. Run 'poliloom dump build-hierarchy' first."
            )

        # Get descendant sets for filtering (still needed for some validation)
        descendants = self.hierarchy_builder.get_position_and_location_descendants(
            subclass_relations
        )
        position_descendants = descendants["positions"]
        location_descendants = descendants["locations"]

        if num_workers is None:
            num_workers = mp.cpu_count()

        logger.info(f"Using parallel processing with {num_workers} workers")

        return self._extract_entities_parallel(
            dump_file_path,
            batch_size,
            num_workers,
            position_descendants,
            location_descendants,
            include_politicians=True,
        )

    def _extract_entities_parallel(
        self,
        dump_file_path: str,
        batch_size: int,
        num_workers: int,
        position_descendants: Set[str],
        location_descendants: Set[str],
        include_politicians: bool = False,
    ) -> Dict[str, int]:
        """Parallel implementation for entity extraction using shared memory."""

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path, num_workers)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Create memory-mapped files for hierarchy data
        logger.info("Creating memory-mapped files for hierarchy data...")
        position_filename = create_shared_memory_from_set(
            position_descendants, f"poliloom_positions_{os.getpid()}"
        )
        location_filename = create_shared_memory_from_set(
            location_descendants, f"poliloom_locations_{os.getpid()}"
        )

        logger.info(
            f"Created memory-mapped files: positions={len(position_descendants)} items, locations={len(location_descendants)} items"
        )

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            # Initialize workers with database and hierarchy data
            def init_worker():
                init_worker_with_hierarchy(position_filename, location_filename)

            pool = mp.Pool(processes=num_workers, initializer=init_worker)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_entity_chunk,
                [
                    (
                        dump_file_path,
                        start,
                        end,
                        i,
                        batch_size,
                        include_politicians,
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

            # Clean up memory-mapped files
            try:
                if os.path.exists(position_filename):
                    os.unlink(position_filename)
                if os.path.exists(location_filename):
                    os.unlink(location_filename)
                logger.info("Cleaned up memory-mapped files")
            except Exception as e:
                logger.warning(f"Error cleaning up memory-mapped files: {e}")

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
            f"Extracted: {total_counts['positions']} positions, {total_counts['locations']} locations, {total_counts['countries']} countries, {total_counts['politicians']} politicians"
        )

        return total_counts

    def _process_entity_chunk(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        batch_size: int,
        include_politicians: bool = False,
    ):
        """
        Process a specific byte range of the dump file for entity extraction.

        Each worker independently reads and parses its assigned chunk.
        Returns entity counts found in this chunk.
        """
        # Simple interrupt flag without signal handlers to avoid cascading issues
        interrupted = False

        try:
            # Get hierarchy data from shared memory
            position_descendants, location_descendants = get_hierarchy_sets()

            positions = []
            locations = []
            countries = []
            politicians = []
            counts = {"positions": 0, "locations": 0, "countries": 0, "politicians": 0}
            entity_count = 0

            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                if interrupted:
                    break

                entity_count += 1

                # Progress reporting for large chunks
                if entity_count % 50000 == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                entity_id = entity.get("id", "")
                if not entity_id:
                    continue

                if include_politicians:
                    # Only process politicians
                    is_politician = self.entity_extractor.is_politician(entity)
                    if is_politician:
                        politician_data = self.entity_extractor.extract_politician_data(
                            entity
                        )
                        if politician_data:
                            politicians.append(politician_data)
                            counts["politicians"] += 1
                else:
                    # Only process supporting entities (positions, locations, countries)
                    is_position = self.entity_extractor.is_instance_of_position(
                        entity, position_descendants
                    )
                    is_location = self.entity_extractor.is_instance_of_location(
                        entity, location_descendants
                    )
                    is_country = self.entity_extractor.is_country_entity(entity)

                    if is_position:
                        position_data = self.entity_extractor.extract_position_data(
                            entity
                        )
                        if position_data:
                            positions.append(position_data)
                            counts["positions"] += 1

                    if is_location:
                        location_data = self.entity_extractor.extract_location_data(
                            entity
                        )
                        if location_data:
                            locations.append(location_data)
                            counts["locations"] += 1

                    if is_country:
                        country_data = self.entity_extractor.extract_country_data(
                            entity
                        )
                        if country_data:
                            countries.append(country_data)
                            counts["countries"] += 1

                # Process batches when they reach the batch size
                if include_politicians:
                    if len(politicians) >= batch_size:
                        self.database_inserter.insert_politicians_batch(politicians)
                        politicians = []
                else:
                    if len(positions) >= batch_size:
                        self.database_inserter.insert_positions_batch(positions)
                        positions = []

                    if len(locations) >= batch_size:
                        self.database_inserter.insert_locations_batch(locations)
                        locations = []

                    if len(countries) >= batch_size:
                        self.database_inserter.insert_countries_batch(countries)
                        countries = []

            # Process remaining entities in final batches
            try:
                if include_politicians:
                    if politicians:
                        self.database_inserter.insert_politicians_batch(politicians)
                else:
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

        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id}: interrupted, processing final batches...")
            # Process remaining entities in final batches even when interrupted
            try:
                if include_politicians:
                    if politicians:
                        self.database_inserter.insert_politicians_batch(politicians)
                else:
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

            logger.info(f"Worker {worker_id}: interrupted, returning partial results")
            return counts, entity_count
        except Exception as e:
            logger.error(f"Worker {worker_id}: error processing chunk: {e}")
            return {"positions": 0, "locations": 0, "countries": 0, "politicians": 0}, 0
