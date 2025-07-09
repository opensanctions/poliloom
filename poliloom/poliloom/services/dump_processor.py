"""Wikidata dump processing service for extracting entities."""

import json
import logging
import os
import multiprocessing as mp
from typing import Dict, Set, Optional, Iterator, Any, Tuple
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Global variable to store worker-specific database session
_worker_session = None

# Global variables for memory-mapped files in worker processes
_shared_position_descendants = None
_shared_location_descendants = None


def _init_worker_db():
    """Initialize database session for worker process."""
    global _worker_session
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from dotenv import load_dotenv

    load_dotenv()
    DATABASE_URL = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/poliloom"
    )

    # Create a separate engine for this worker process
    worker_engine = create_engine(
        DATABASE_URL,
        pool_size=5,  # Smaller pool per worker
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

    # Create sessionmaker for this worker
    WorkerSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=worker_engine
    )
    _worker_session = WorkerSessionLocal

    logger.info(f"Initialized database session for worker process {os.getpid()}")


def _get_worker_session():
    """Get the worker-specific database session."""
    global _worker_session
    if _worker_session is None:
        _init_worker_db()
    return _worker_session()


def _create_shared_memory_from_set(data_set: Set[str], name: str) -> str:
    """Create memory-mapped file from a set of strings."""
    import tempfile
    import os

    # Convert set to JSON string
    json_data = json.dumps(sorted(list(data_set)))
    json_bytes = json_data.encode("utf-8")

    # Create temporary file for memory mapping
    temp_dir = tempfile.gettempdir()
    filename = os.path.join(temp_dir, f"{name}.json")

    with open(filename, "wb") as f:
        f.write(json_bytes)

    return filename


def _load_set_from_shared_memory(filename: str) -> Set[str]:
    """Load a set from memory-mapped file."""
    import mmap

    with open(filename, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
            # Read and decode JSON data
            json_data = mmapped_file[:].decode("utf-8")
            data_list = json.loads(json_data)

            # Convert back to set
            return set(data_list)


def _init_worker_hierarchy(position_filename: str, location_filename: str):
    """Initialize hierarchy data in worker process from memory-mapped files."""
    global _shared_position_descendants, _shared_location_descendants

    try:
        _shared_position_descendants = _load_set_from_shared_memory(position_filename)
        _shared_location_descendants = _load_set_from_shared_memory(location_filename)

        logger.info(
            f"Worker {os.getpid()}: Loaded {len(_shared_position_descendants)} position descendants and {len(_shared_location_descendants)} location descendants from memory-mapped files"
        )

    except Exception as e:
        logger.error(
            f"Worker {os.getpid()}: Failed to load hierarchy from memory-mapped files: {e}"
        )
        raise


def _get_hierarchy_sets() -> Tuple[Set[str], Set[str]]:
    """Get hierarchy sets for current worker."""
    global _shared_position_descendants, _shared_location_descendants

    if _shared_position_descendants is None or _shared_location_descendants is None:
        raise RuntimeError("Hierarchy data not initialized in worker process")

    return _shared_position_descendants, _shared_location_descendants


class WikidataDumpProcessor:
    """Process Wikidata JSON dumps to extract entities and build hierarchy trees."""

    def __init__(self):
        self.position_root = "Q294414"  # public office
        self.location_root = "Q2221906"  # geographic location

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
        position_descendants = self._get_all_descendants(
            self.position_root, subclass_relations
        )
        location_descendants = self._get_all_descendants(
            self.location_root, subclass_relations
        )

        return {"positions": position_descendants, "locations": location_descendants}

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
        chunks = self._calculate_file_chunks(dump_file_path, num_workers)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(processes=num_workers, initializer=_init_worker_db)

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
        self.save_complete_hierarchy_trees(subclass_relations, output_dir)

        # Extract specific trees from the complete tree for convenience
        position_descendants = self._get_all_descendants(
            self.position_root, subclass_relations
        )
        location_descendants = self._get_all_descendants(
            self.location_root, subclass_relations
        )

        logger.info(
            f"Found {len(position_descendants)} position descendants of {self.position_root}"
        )
        logger.info(
            f"Found {len(location_descendants)} location descendants of {self.location_root}"
        )

        return subclass_relations

    def _calculate_file_chunks(self, dump_file_path: str, num_workers: int) -> list:
        """
        Calculate byte ranges for each worker to process independently.

        Splits the file into roughly equal chunks while respecting JSON line boundaries.
        For very large files (1TB), this ensures each worker gets a substantial chunk.
        """
        file_size = os.path.getsize(dump_file_path)

        # For small files, don't create more chunks than needed
        if file_size < num_workers * 1024 * 1024:  # Less than 1MB per worker
            num_workers = max(1, file_size // (1024 * 1024))

        chunk_size = file_size // num_workers
        chunks = []

        with open(dump_file_path, "rb") as f:
            current_pos = 0

            for i in range(num_workers):
                start_pos = current_pos

                if i == num_workers - 1:
                    # Last chunk gets everything remaining
                    end_pos = file_size
                else:
                    # Move to approximate chunk boundary
                    target_pos = start_pos + chunk_size
                    f.seek(target_pos)

                    # Find next newline to respect line boundaries
                    while target_pos < file_size:
                        char = f.read(1)
                        target_pos += 1
                        if char == b"\n":
                            break

                    end_pos = target_pos

                if start_pos < end_pos:
                    chunks.append((start_pos, end_pos))

                current_pos = end_pos

                if current_pos >= file_size:
                    break

        return chunks

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

            with open(dump_file_path, "rb") as f:
                f.seek(start_byte)

                # Track our position in the file
                current_pos = start_byte

                while current_pos < end_byte and not interrupted:
                    line = f.readline()
                    if not line:
                        break

                    current_pos = f.tell()

                    # Skip array brackets and empty lines
                    line = line.strip()
                    if line in [b"[", b"]"] or not line:
                        continue

                    # Remove trailing comma if present
                    if line.endswith(b","):
                        line = line[:-1]

                    try:
                        entity = json.loads(line.decode("utf-8"))
                        entity_count += 1

                        # Progress reporting for large chunks
                        if entity_count % 50000 == 0:
                            logger.info(
                                f"Worker {worker_id}: processed {entity_count} entities"
                            )

                        # Extract P279 (subclass of) relationships
                        entity_id = entity.get("id", "")
                        claims = entity.get("claims", {})

                        subclass_claims = claims.get("P279", [])
                        for claim in subclass_claims:
                            try:
                                parent_id = claim["mainsnak"]["datavalue"]["value"][
                                    "id"
                                ]
                                subclass_relations[parent_id].add(entity_id)
                            except (KeyError, TypeError):
                                continue

                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Skip malformed lines
                        continue
                    except KeyboardInterrupt:
                        interrupted = True
                        break

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

    def _stream_dump_entities(self, dump_file_path: str) -> Iterator[Dict[str, Any]]:
        """
        Stream entities from a Wikidata JSON dump file.

        The dump format has one JSON object per line, with a trailing comma.
        First line is '[', last line is ']'.

        Args:
            dump_file_path: Path to the JSON dump file

        Yields:
            Parsed entity dictionaries
        """
        with open(dump_file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip array brackets
                if line in ["[", "]"]:
                    continue

                # Remove trailing comma if present
                if line.endswith(","):
                    line = line[:-1]

                # Skip empty lines
                if not line:
                    continue

                try:
                    entity = json.loads(line)
                    yield entity
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON line: {e}")
                    continue

    def _get_all_descendants(
        self,
        root_id: str,
        subclass_relations: Dict[str, Set[str]],
    ) -> Set[str]:
        """
        Get all descendants of a root entity using BFS, traversing only subclass relationships.

        Args:
            root_id: The root entity QID
            subclass_relations: Dict mapping parent QIDs to sets of child QIDs (P279)

        Returns:
            Set of all descendant QIDs (including the root and its subclasses)
        """
        descendants = {root_id}
        queue = [root_id]

        while queue:
            current = queue.pop(0)

            # Get direct subclasses
            subclasses = subclass_relations.get(current, set())
            for subclass in subclasses:
                if subclass not in descendants:
                    descendants.add(subclass)
                    queue.append(subclass)

        return descendants

    def save_complete_hierarchy_trees(
        self,
        subclass_relations: Dict[str, Set[str]],
        output_dir: str = ".",
    ) -> None:
        """
        Save the complete hierarchy (P279 subclass relationships) to JSON file.

        This creates a comprehensive reference of all subclass relationships in Wikidata,
        enabling extraction of any entity type hierarchy without re-processing the dump.

        Args:
            subclass_relations: Dictionary mapping parent QIDs to sets of child QIDs (P279)
            output_dir: Directory to save the JSON file
        """
        hierarchy_file = os.path.join(output_dir, "complete_hierarchy.json")

        # Convert sets to sorted lists for JSON serialization
        hierarchy_data = {
            "subclass_of": {},  # P279 relationships
        }

        # Process subclass relations
        for parent_id, children in subclass_relations.items():
            if children:
                hierarchy_data["subclass_of"][parent_id] = sorted(list(children))

        # Sort keys for consistent output
        hierarchy_data["subclass_of"] = dict(
            sorted(hierarchy_data["subclass_of"].items())
        )

        with open(hierarchy_file, "w", encoding="utf-8") as f:
            json.dump(hierarchy_data, f, indent=2, ensure_ascii=False)

        # Calculate and log file size
        file_size = os.path.getsize(hierarchy_file)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Saved complete hierarchy to {hierarchy_file}")
        logger.info(
            f"Hierarchy contains {len(hierarchy_data['subclass_of'])} entities with subclasses"
        )
        logger.info(f"File size: {file_size_mb:.1f} MB ({file_size:,} bytes)")

    def load_complete_hierarchy(
        self, tree_dir: str = "."
    ) -> Optional[Dict[str, Set[str]]]:
        """
        Load the complete hierarchy from JSON file.

        Args:
            tree_dir: Directory containing the complete hierarchy file

        Returns:
            Dictionary of subclass_relations, or None if file doesn't exist
        """
        hierarchy_file = os.path.join(tree_dir, "complete_hierarchy.json")

        if not os.path.exists(hierarchy_file):
            logger.warning(f"Complete hierarchy file not found: {hierarchy_file}")
            return None

        try:
            with open(hierarchy_file, "r", encoding="utf-8") as f:
                hierarchy_data = json.load(f)

            # Convert lists back to sets
            subclass_relations = {}
            for parent_id, children in hierarchy_data.get("subclass_of", {}).items():
                subclass_relations[parent_id] = set(children)

            logger.info(f"Loaded complete hierarchy from {hierarchy_file}")
            logger.info(
                f"Hierarchy contains {len(subclass_relations)} entities with subclasses"
            )

            return subclass_relations

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load complete hierarchy: {e}")
            return None

    def extract_entities_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 100,
        num_workers: Optional[int] = None,
        hierarchy_dir: str = ".",
    ) -> Dict[str, int]:
        """
        Extract locations, positions, and countries from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch
            num_workers: Number of worker processes (default: CPU count)
            hierarchy_dir: Directory containing the complete hierarchy file (default: current directory)

        Returns:
            Dictionary with counts of extracted entities
        """
        # Load the hierarchy trees
        subclass_relations = self.load_complete_hierarchy(hierarchy_dir)
        if subclass_relations is None:
            raise ValueError(
                "Complete hierarchy not found. Run 'poliloom dump build-hierarchy' first."
            )

        # Get descendant sets for filtering
        position_descendants = self._get_all_descendants(
            self.position_root, subclass_relations
        )
        location_descendants = self._get_all_descendants(
            self.location_root, subclass_relations
        )

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
        )

    def _extract_entities_parallel(
        self,
        dump_file_path: str,
        batch_size: int,
        num_workers: int,
        position_descendants: Set[str],
        location_descendants: Set[str],
    ) -> Dict[str, int]:
        """Parallel implementation for entity extraction using shared memory."""

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self._calculate_file_chunks(dump_file_path, num_workers)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Create memory-mapped files for hierarchy data
        logger.info("Creating memory-mapped files for hierarchy data...")
        position_filename = _create_shared_memory_from_set(
            position_descendants, f"poliloom_positions_{os.getpid()}"
        )
        location_filename = _create_shared_memory_from_set(
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
                _init_worker_db()
                _init_worker_hierarchy(position_filename, location_filename)

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
        total_counts = {"positions": 0, "locations": 0, "countries": 0}
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

    def _process_entity_chunk(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        batch_size: int,
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
            position_descendants, location_descendants = _get_hierarchy_sets()

            positions = []
            locations = []
            countries = []
            counts = {"positions": 0, "locations": 0, "countries": 0}
            entity_count = 0

            with open(dump_file_path, "rb") as f:
                f.seek(start_byte)

                # Track our position in the file
                current_pos = start_byte

                while current_pos < end_byte and not interrupted:
                    line = f.readline()
                    if not line:
                        break

                    current_pos = f.tell()

                    # Skip array brackets and empty lines
                    line = line.strip()
                    if line in [b"[", b"]"] or not line:
                        continue

                    # Remove trailing comma if present
                    if line.endswith(b","):
                        line = line[:-1]

                    try:
                        entity = json.loads(line.decode("utf-8"))
                        entity_count += 1

                        # Progress reporting for large chunks
                        if entity_count % 50000 == 0:
                            logger.info(
                                f"Worker {worker_id}: processed {entity_count} entities"
                            )

                        entity_id = entity.get("id", "")
                        if not entity_id:
                            continue

                        # Check if this entity is a position, location, or country
                        is_position = self._is_instance_of_position(
                            entity, position_descendants
                        )
                        is_location = self._is_instance_of_location(
                            entity, location_descendants
                        )
                        is_country = self._is_country_entity(entity)

                        if is_position:
                            position_data = self._extract_position_data(entity)
                            if position_data:
                                positions.append(position_data)
                                counts["positions"] += 1

                        if is_location:
                            location_data = self._extract_location_data(entity)
                            if location_data:
                                locations.append(location_data)
                                counts["locations"] += 1

                        if is_country:
                            country_data = self._extract_country_data(entity)
                            if country_data:
                                countries.append(country_data)
                                counts["countries"] += 1

                        # Process batches when they reach the batch size
                        if len(positions) >= batch_size:
                            self._insert_positions_batch(positions)
                            positions = []

                        if len(locations) >= batch_size:
                            self._insert_locations_batch(locations)
                            locations = []

                        if len(countries) >= batch_size:
                            self._insert_countries_batch(countries)
                            countries = []

                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Skip malformed lines
                        continue
                    except KeyboardInterrupt:
                        interrupted = True
                        break

            # Process remaining entities in final batches
            try:
                if positions:
                    self._insert_positions_batch(positions)
                if locations:
                    self._insert_locations_batch(locations)
                if countries:
                    self._insert_countries_batch(countries)
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
                if positions:
                    self._insert_positions_batch(positions)
                if locations:
                    self._insert_locations_batch(locations)
                if countries:
                    self._insert_countries_batch(countries)
            except Exception as cleanup_error:
                logger.warning(
                    f"Worker {worker_id}: error during cleanup: {cleanup_error}"
                )

            logger.info(f"Worker {worker_id}: interrupted, returning partial results")
            return counts, entity_count
        except Exception as e:
            logger.error(f"Worker {worker_id}: error processing chunk: {e}")
            return {"positions": 0, "locations": 0, "countries": 0}, 0

    def _is_instance_of_position(
        self, entity: Dict[str, Any], position_descendants: Set[str]
    ) -> bool:
        """Check if an entity is an instance of any position type (P31 instance of position descendants) or is a position type itself."""
        entity_id = entity.get("id", "")

        # Check if this entity is itself a position type
        if entity_id in position_descendants:
            return True

        # Check if this entity is an instance of a position type
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in position_descendants:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def _is_instance_of_location(
        self, entity: Dict[str, Any], location_descendants: Set[str]
    ) -> bool:
        """Check if an entity is an instance of any location type (P31 instance of location descendants) or is a location type itself."""
        entity_id = entity.get("id", "")

        # Check if this entity is itself a location type
        if entity_id in location_descendants:
            return True

        # Check if this entity is an instance of a location type
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in location_descendants:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def _is_country_entity(self, entity: Dict[str, Any]) -> bool:
        """Check if an entity is a country based on its instance of (P31) properties."""
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        # Common country instance types
        country_types = {
            "Q6256",  # country
            "Q3624078",  # sovereign state
            "Q3624078",  # country
            "Q20181813",  # historic country
            "Q1520223",  # independent city
            "Q1489259",  # city-state
        }

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in country_types:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def _extract_position_data(
        self, entity: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract position data from a Wikidata entity."""
        name = self._get_entity_name(entity)
        if not name:
            return None

        return {
            "wikidata_id": entity["id"],
            "name": name,
        }

    def _extract_location_data(
        self, entity: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract location data from a Wikidata entity."""
        name = self._get_entity_name(entity)
        if not name:
            return None

        return {
            "wikidata_id": entity["id"],
            "name": name,
        }

    def _extract_country_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract country data from a Wikidata entity."""
        name = self._get_entity_name(entity)
        if not name:
            return None

        # Try to get ISO code from claims
        iso_code = None
        claims = entity.get("claims", {})

        # P297 is the property for ISO 3166-1 alpha-2 code
        iso_claims = claims.get("P297", [])
        for claim in iso_claims:
            try:
                iso_code = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        return {
            "wikidata_id": entity["id"],
            "name": name,
            "iso_code": iso_code,
        }

    def _get_entity_name(self, entity: Dict[str, Any]) -> Optional[str]:
        """Extract the primary name from a Wikidata entity."""
        labels = entity.get("labels", {})

        # Try English first
        if "en" in labels:
            return labels["en"]["value"]

        # Fallback to any available language
        if labels:
            return next(iter(labels.values()))["value"]

        return None

    def _insert_positions_batch(self, positions: list) -> None:
        """Insert a batch of positions into the database."""
        if not positions:
            return

        from ..models import Position
        from sqlalchemy.exc import DisconnectionError
        import time

        max_retries = 3
        for attempt in range(max_retries):
            session = _get_worker_session()
            try:
                # Check for existing positions to avoid duplicates
                existing_wikidata_ids = {
                    result[0]
                    for result in session.query(Position.wikidata_id)
                    .filter(
                        Position.wikidata_id.in_([p["wikidata_id"] for p in positions])
                    )
                    .all()
                }

                # Filter out duplicates
                new_positions = [
                    p
                    for p in positions
                    if p["wikidata_id"] not in existing_wikidata_ids
                ]

                if new_positions:
                    # Create Position objects
                    position_objects = [
                        Position(
                            wikidata_id=p["wikidata_id"],
                            name=p["name"],
                            embedding=None,  # Will be generated later
                        )
                        for p in new_positions
                    ]

                    session.add_all(position_objects)
                    session.commit()
                    logger.debug(f"Inserted {len(new_positions)} new positions")
                # Skip logging when no new positions - this is normal
                break  # Success, exit retry loop

            except (DisconnectionError, Exception) as e:
                session.rollback()
                logger.error(
                    f"Error inserting positions batch (attempt {attempt + 1}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Wait before retry
            finally:
                session.close()

    def _insert_locations_batch(self, locations: list) -> None:
        """Insert a batch of locations into the database."""
        if not locations:
            return

        from ..models import Location
        from sqlalchemy.exc import DisconnectionError
        import time

        max_retries = 3
        for attempt in range(max_retries):
            session = _get_worker_session()
            try:
                # Check for existing locations to avoid duplicates
                existing_wikidata_ids = {
                    result[0]
                    for result in session.query(Location.wikidata_id)
                    .filter(
                        Location.wikidata_id.in_(
                            [loc["wikidata_id"] for loc in locations]
                        )
                    )
                    .all()
                }

                # Filter out duplicates
                new_locations = [
                    loc
                    for loc in locations
                    if loc["wikidata_id"] not in existing_wikidata_ids
                ]

                if new_locations:
                    # Create Location objects
                    location_objects = [
                        Location(
                            wikidata_id=loc["wikidata_id"],
                            name=loc["name"],
                            embedding=None,  # Will be generated later
                        )
                        for loc in new_locations
                    ]

                    session.add_all(location_objects)
                    session.commit()
                    logger.debug(f"Inserted {len(new_locations)} new locations")
                # Skip logging when no new locations - this is normal
                break  # Success, exit retry loop

            except (DisconnectionError, Exception) as e:
                session.rollback()
                logger.error(
                    f"Error inserting locations batch (attempt {attempt + 1}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Wait before retry
            finally:
                session.close()

    def _insert_countries_batch(self, countries: list) -> None:
        """Insert a batch of countries into the database using ON CONFLICT."""
        if not countries:
            return

        from ..models import Country
        from sqlalchemy.dialects.postgresql import insert
        from sqlalchemy.exc import DisconnectionError
        import time

        max_retries = 3
        for attempt in range(max_retries):
            session = _get_worker_session()
            try:
                # Prepare data for bulk insert
                country_data = [
                    {
                        "wikidata_id": c["wikidata_id"],
                        "name": c["name"],
                        "iso_code": c["iso_code"],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                    for c in countries
                ]

                # Use PostgreSQL's ON CONFLICT to handle duplicates
                # We need to handle both wikidata_id and iso_code constraints
                # Since PostgreSQL doesn't support multiple ON CONFLICT clauses,
                # we'll use a more robust approach with ON CONFLICT DO NOTHING
                stmt = insert(Country).values(country_data)
                stmt = stmt.on_conflict_do_nothing()

                result = session.execute(stmt)
                session.commit()

                inserted_count = result.rowcount
                logger.debug(
                    f"Inserted {inserted_count} new countries (skipped {len(countries) - inserted_count} duplicates)"
                )
                break  # Success, exit retry loop

            except (DisconnectionError, Exception) as e:
                session.rollback()
                logger.error(
                    f"Error inserting countries batch (attempt {attempt + 1}): {e}"
                )
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)  # Wait before retry
            finally:
                session.close()
