"""Wikidata dump processing service for extracting entities."""

import json
import logging
import os
import multiprocessing as mp
from typing import Dict, Set, Optional, Iterator, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class WikidataDumpProcessor:
    """Process Wikidata JSON dumps to extract entities and build hierarchy trees."""

    def __init__(self):
        self.position_root = "Q294414"  # public office
        self.location_root = "Q2221906"  # geographic location

    def build_hierarchy_trees(
        self, dump_file_path: str, num_workers: Optional[int] = None
    ) -> Dict[str, Set[str]]:
        """
        Build hierarchy trees for positions and locations from Wikidata dump.

        Uses parallel processing with Producer-Consumer pattern to extract all P279
        (subclass of) relationships and build complete descendant trees.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            num_workers: Number of worker processes (default: CPU count)

        Returns:
            Dictionary with 'positions' and 'locations' keys containing sets of QIDs
        """
        logger.info(f"Building hierarchy trees from dump file: {dump_file_path}")

        if num_workers is None:
            num_workers = mp.cpu_count()

        logger.info(f"Using parallel processing with {num_workers} workers")

        return self._build_hierarchy_trees_parallel(dump_file_path, num_workers)

    def _build_hierarchy_trees_parallel(
        self, dump_file_path: str, num_workers: int
    ) -> Dict[str, Set[str]]:
        """Parallel implementation using chunk-based file reading."""

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self._calculate_file_chunks(dump_file_path, num_workers)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(processes=num_workers)

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

        for chunk_relations, chunk_count in chunk_results:
            total_entities += chunk_count
            for parent_id, children in chunk_relations.items():
                subclass_relations[parent_id].update(children)

        logger.info(f"Processed {total_entities} total entities")
        logger.info(f"Found {len(subclass_relations)} entities with subclasses")

        # Save complete subclass tree for future use
        self.save_complete_subclass_tree(subclass_relations)

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

        return {"positions": position_descendants, "locations": location_descendants}

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
        Returns subclass relationships found in this chunk.
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

                        # Extract P279 relationships
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
        self, root_id: str, subclass_relations: Dict[str, Set[str]]
    ) -> Set[str]:
        """
        Get all descendants of a root entity using BFS.

        Args:
            root_id: The root entity QID
            subclass_relations: Dict mapping parent QIDs to sets of child QIDs

        Returns:
            Set of all descendant QIDs (including the root)
        """
        descendants = {root_id}
        queue = [root_id]

        while queue:
            current = queue.pop(0)
            children = subclass_relations.get(current, set())

            for child in children:
                if child not in descendants:
                    descendants.add(child)
                    queue.append(child)

        return descendants

    def save_complete_subclass_tree(
        self, subclass_relations: Dict[str, Set[str]], output_dir: str = "."
    ) -> None:
        """
        Save the complete subclass tree (all P279 relationships) to JSON file.

        This creates a comprehensive reference of all subclass relationships in Wikidata,
        enabling extraction of any entity type hierarchy without re-processing the dump.

        Args:
            subclass_relations: Dictionary mapping parent QIDs to sets of child QIDs
            output_dir: Directory to save the JSON file
        """
        complete_tree_file = os.path.join(output_dir, "complete_subclass_tree.json")

        # Convert sets to sorted lists for JSON serialization and consistency
        json_tree = {}
        for parent_id, children in subclass_relations.items():
            if children:  # Only include entities that have subclasses
                json_tree[parent_id] = sorted(list(children))

        # Sort by parent QID for consistent output
        sorted_tree = dict(sorted(json_tree.items()))

        with open(complete_tree_file, "w", encoding="utf-8") as f:
            json.dump(sorted_tree, f, indent=2, ensure_ascii=False)

        # Calculate and log file size
        file_size = os.path.getsize(complete_tree_file)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Saved complete subclass tree to {complete_tree_file}")
        logger.info(
            f"Complete tree contains {len(sorted_tree)} entities with subclasses"
        )
        logger.info(f"File size: {file_size_mb:.1f} MB ({file_size:,} bytes)")

    def load_complete_subclass_tree(
        self, tree_dir: str = "."
    ) -> Optional[Dict[str, Set[str]]]:
        """
        Load the complete subclass tree from JSON file.

        Args:
            tree_dir: Directory containing the complete subclass tree file

        Returns:
            Dictionary mapping parent QIDs to sets of child QIDs, or None if file doesn't exist
        """
        tree_file = os.path.join(tree_dir, "complete_subclass_tree.json")

        if not os.path.exists(tree_file):
            logger.warning(f"Complete subclass tree file not found: {tree_file}")
            return None

        try:
            with open(tree_file, "r", encoding="utf-8") as f:
                json_tree = json.load(f)

            # Convert lists back to sets
            subclass_relations = {}
            for parent_id, children in json_tree.items():
                subclass_relations[parent_id] = set(children)

            logger.info(f"Loaded complete subclass tree from {tree_file}")
            logger.info(
                f"Tree contains {len(subclass_relations)} entities with subclasses"
            )

            return subclass_relations

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load complete subclass tree: {e}")
            return None

    def get_descendants_from_complete_tree(
        self, root_qid: str, tree_dir: str = "."
    ) -> Optional[Set[str]]:
        """
        Extract descendants of any entity from the complete subclass tree.

        This allows querying any entity type without re-processing the dump.

        Args:
            root_qid: The root entity QID (e.g., "Q515" for city)
            tree_dir: Directory containing the complete subclass tree file

        Returns:
            Set of all descendant QIDs (including the root), or None if tree not found
        """
        complete_tree = self.load_complete_subclass_tree(tree_dir)
        if complete_tree is None:
            return None

        descendants = self._get_all_descendants(root_qid, complete_tree)

        logger.info(f"Found {len(descendants)} descendants of {root_qid}")
        return descendants

    def extract_entities_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 100,
        num_workers: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Extract locations, positions, and countries from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch
            num_workers: Number of worker processes (default: CPU count)

        Returns:
            Dictionary with counts of extracted entities
        """
        # Load the hierarchy trees
        complete_tree = self.load_complete_subclass_tree()
        if complete_tree is None:
            raise ValueError(
                "Complete subclass tree not found. Run 'poliloom dump build-trees' first."
            )

        # Get descendant sets for filtering
        position_descendants = self._get_all_descendants(
            self.position_root, complete_tree
        )
        location_descendants = self._get_all_descendants(
            self.location_root, complete_tree
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
        """Parallel implementation for entity extraction."""

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self._calculate_file_chunks(dump_file_path, num_workers)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(processes=num_workers)

            # Each worker processes its chunk independently
            async_result = pool.starmap_async(
                self._process_entity_chunk,
                [
                    (
                        dump_file_path,
                        start,
                        end,
                        i,
                        position_descendants,
                        location_descendants,
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
        position_descendants: Set[str],
        location_descendants: Set[str],
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
                        is_position = entity_id in position_descendants
                        is_location = entity_id in location_descendants
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

        from ..database import SessionLocal
        from ..models import Position

        session = SessionLocal()
        try:
            # Check for existing positions to avoid duplicates
            existing_wikidata_ids = {
                result[0]
                for result in session.query(Position.wikidata_id)
                .filter(Position.wikidata_id.in_([p["wikidata_id"] for p in positions]))
                .all()
            }

            # Filter out duplicates
            new_positions = [
                p for p in positions if p["wikidata_id"] not in existing_wikidata_ids
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
                logger.info(f"Inserted {len(new_positions)} new positions")
            else:
                logger.info("No new positions to insert in this batch")

        except Exception as e:
            session.rollback()
            logger.error(f"Error inserting positions batch: {e}")
            raise
        finally:
            session.close()

    def _insert_locations_batch(self, locations: list) -> None:
        """Insert a batch of locations into the database."""
        if not locations:
            return

        from ..database import SessionLocal
        from ..models import Location

        session = SessionLocal()
        try:
            # Check for existing locations to avoid duplicates
            existing_wikidata_ids = {
                result[0]
                for result in session.query(Location.wikidata_id)
                .filter(
                    Location.wikidata_id.in_([loc["wikidata_id"] for loc in locations])
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
                logger.info(f"Inserted {len(new_locations)} new locations")
            else:
                logger.info("No new locations to insert in this batch")

        except Exception as e:
            session.rollback()
            logger.error(f"Error inserting locations batch: {e}")
            raise
        finally:
            session.close()

    def _insert_countries_batch(self, countries: list) -> None:
        """Insert a batch of countries into the database."""
        if not countries:
            return

        from ..database import SessionLocal
        from ..models import Country

        session = SessionLocal()
        try:
            # Check for existing countries to avoid duplicates
            existing_wikidata_ids = {
                result[0]
                for result in session.query(Country.wikidata_id)
                .filter(Country.wikidata_id.in_([c["wikidata_id"] for c in countries]))
                .all()
            }

            # Filter out duplicates
            new_countries = [
                c for c in countries if c["wikidata_id"] not in existing_wikidata_ids
            ]

            if new_countries:
                # Create Country objects
                country_objects = [
                    Country(
                        wikidata_id=c["wikidata_id"],
                        name=c["name"],
                        iso_code=c["iso_code"],
                    )
                    for c in new_countries
                ]

                session.add_all(country_objects)
                session.commit()

                logger.info(f"Inserted {len(new_countries)} new countries")
            else:
                logger.info("No new countries to insert in this batch")

        except Exception as e:
            session.rollback()
            logger.error(f"Error inserting countries batch: {e}")
            raise
        finally:
            session.close()
