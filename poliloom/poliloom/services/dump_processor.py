"""Wikidata dump processing service for extracting entities."""

import logging
import multiprocessing as mp
from typing import Dict, Set, Tuple
from collections import defaultdict
from multiprocessing import Manager
from datetime import datetime, date

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

from .dump_reader import DumpReader
from .database_inserter import DatabaseInserter
from ..database import get_engine
from sqlalchemy.orm import Session
from ..models import WikidataClass, SubclassRelation

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000


class WikidataDumpProcessor:
    """Process Wikidata JSON dumps to extract entities and build hierarchy trees."""

    def __init__(self):
        """Initialize the dump processor."""
        self.dump_reader = DumpReader()
        self.database_inserter = DatabaseInserter()

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

    def build_hierarchy_trees(
        self,
        dump_file_path: str,
    ) -> None:
        """
        Build hierarchy trees for positions and locations from Wikidata dump.

        Uses a memory-efficient three-phase approach:
        1. Collect subclass relationships from dump
        2. Insert WikidataClass and SubclassRelation records in batches
        3. Update names for all WikidataClass records

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
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

        logger.info(f"Found {len(all_qids)} unique entities in hierarchy")

        # Phase 2: Insert WikidataClass and SubclassRelation records in batches
        logger.info("Phase 2: Inserting WikidataClass and SubclassRelation records...")
        self._batch_insert_subclass_relations(subclass_relations)

        # Phase 3: Extract and batch update names for all WikidataClass records in database
        logger.info(
            "Phase 3: Extracting and updating names for all WikidataClass records..."
        )
        self._batch_update_wikidata_class_names(dump_file_path, all_qids)

        logger.info("✅ Hierarchy building complete")

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
                    pool.join()
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
            with Session(get_engine()) as session:
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
            with Session(get_engine()) as session:
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
        Uses Manager dictionary to efficiently share QIDs between workers with O(1) lookups.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            target_qids: Set of QIDs to extract names for (already available from hierarchy building)
        """
        logger.info(f"Extracting names for {len(target_qids)} WikidataClass records")

        # Use Manager for shared dictionary with O(1) lookups
        with Manager() as manager:
            # Create shared dictionary from QIDs for O(1) membership testing
            logger.info(f"Creating shared dictionary for {len(target_qids)} QIDs")
            shared_qids = manager.dict()
            for qid in target_qids:
                shared_qids[qid] = True

            num_workers = mp.cpu_count()
            logger.info(f"Using {num_workers} parallel workers for name extraction")

            # Split file into chunks for parallel processing
            chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
            pool = None

            try:
                pool = mp.Pool(processes=num_workers)

                # Pass shared dictionary to workers
                async_result = pool.starmap_async(
                    self._process_chunk_for_name_updates,
                    [
                        (dump_file_path, start, end, i, shared_qids)
                        for i, (start, end) in enumerate(chunks)
                    ],
                )

                chunk_results = async_result.get()

            except KeyboardInterrupt:
                logger.info("Received interrupt signal, cleaning up workers...")
                if pool:
                    pool.terminate()
                    try:
                        pool.join()
                    except Exception:
                        pass
                raise KeyboardInterrupt("Name extraction interrupted by user")
            finally:
                if pool:
                    pool.close()
                    pool.join()

            # Manager automatically cleans up shared dictionary

            # Merge results from all chunks (workers now handle their own database updates)
            total_updates = 0
            total_entities = 0

            for updates_count, chunk_count in chunk_results:
                total_entities += chunk_count
                total_updates += updates_count

            logger.info(
                f"Name extraction complete: processed {total_entities} entities"
            )
            logger.info(f"Updated names for {total_updates} entities")

        logger.info("✅ WikidataClass name updates complete")

    def _process_chunk_for_name_updates(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        shared_qids: dict,
    ) -> Tuple[int, int]:
        """
        Worker process: Extract names only for entities in target QIDs dictionary.
        Updates WikidataClass records in batches to reduce memory usage.
        Returns count of updates made.
        """
        from sqlalchemy.orm import Session
        from sqlalchemy.dialects.postgresql import insert
        from ..models import WikidataClass

        # Fix multiprocessing connection issues per SQLAlchemy docs:
        # https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork
        engine = get_engine()
        engine.dispose(close=False)

        # Use shared dictionary directly for O(1) membership testing

        batch_size = 1000  # Process name updates in batches of 1000
        name_updates = {}
        total_updates_count = 0
        entity_count = 0
        interrupted = False

        try:
            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                if interrupted:
                    break

                entity_count += 1

                # Progress reporting for large chunks
                if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                entity_id = entity.get_wikidata_id()
                if not entity_id or entity_id not in shared_qids:
                    continue

                # Extract name using base entity logic
                try:
                    name = entity.get_entity_name()
                    if name:
                        name_updates[entity_id] = name
                except Exception as e:
                    logger.debug(
                        f"Worker {worker_id}: failed to extract name for {entity_id}: {e}"
                    )
                    continue

                # Process batches when they reach the batch size
                if len(name_updates) >= batch_size:
                    try:
                        with Session(get_engine()) as session:
                            # Bulk update using PostgreSQL upsert
                            batch_updates = [
                                {
                                    "wikidata_id": wikidata_id,
                                    "name": name,
                                }
                                for wikidata_id, name in name_updates.items()
                            ]

                            stmt = insert(WikidataClass).values(batch_updates)
                            stmt = stmt.on_conflict_do_update(
                                index_elements=["wikidata_id"],
                                set_={"name": stmt.excluded.name},
                            )

                            session.execute(stmt)
                            session.commit()
                            total_updates_count += len(name_updates)

                            logger.info(
                                f"Worker {worker_id}: updated batch of {len(name_updates)} WikidataClass names in database"
                            )

                    except Exception as db_error:
                        logger.error(
                            f"Worker {worker_id}: database batch update failed: {db_error}"
                        )

                    name_updates = {}

        except KeyboardInterrupt:
            interrupted = True
            logger.info(f"Worker {worker_id}: name extraction interrupted")
        except Exception as e:
            logger.error(f"Worker {worker_id}: error during name extraction: {e}")
        finally:
            # Always process remaining entities in final batch
            try:
                if name_updates and not interrupted:
                    with Session(get_engine()) as session:
                        # Bulk update using PostgreSQL upsert
                        batch_updates = [
                            {
                                "wikidata_id": wikidata_id,
                                "name": name,
                            }
                            for wikidata_id, name in name_updates.items()
                        ]

                        stmt = insert(WikidataClass).values(batch_updates)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["wikidata_id"],
                            set_={
                                "name": stmt.excluded.name,
                            },
                        )

                        session.execute(stmt)
                        session.commit()
                        total_updates_count += len(name_updates)

                        logger.info(
                            f"Worker {worker_id}: updated final batch of {len(name_updates)} WikidataClass names in database"
                        )

            except Exception as cleanup_error:
                logger.warning(
                    f"Worker {worker_id}: error during cleanup: {cleanup_error}"
                )

        if interrupted:
            logger.info(f"Worker {worker_id}: interrupted, returning partial results")
        else:
            logger.info(
                f"Worker {worker_id}: extracted {total_updates_count} names from {entity_count} entities"
            )

        return total_updates_count, entity_count

    def _process_chunk_for_relationships(
        self, dump_file_path: str, start_byte: int, end_byte: int, worker_id: int
    ) -> Tuple[Dict[str, Set[str]], int]:
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
                if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                # Extract P279 relationships using WikidataEntity logic
                entity_id = entity.get_wikidata_id()
                if entity_id:
                    subclass_claims = entity.get_truthy_claims("P279")

                    for claim in subclass_claims:
                        try:
                            parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                            subclass_relations[parent_id].add(entity_id)
                        except (KeyError, TypeError):
                            continue

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
        batch_size: int = 1000,
    ) -> Dict[str, int]:
        """
        Extract supporting entities from the Wikidata dump using parallel processing.
        Uses Manager dictionaries to efficiently share descendant QIDs across workers with O(1) lookups.

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

        num_workers = mp.cpu_count()
        logger.info(f"Using parallel processing with {num_workers} workers")

        # Use Manager to share descendant dictionaries across workers
        with Manager() as manager:
            logger.info(
                f"Creating shared dictionary for {len(position_classes)} position classes"
            )
            shared_position_classes = manager.dict()
            for qid in position_classes:
                shared_position_classes[qid] = True

            logger.info(
                f"Creating shared dictionary for {len(location_classes)} location classes"
            )
            shared_location_classes = manager.dict()
            for qid in location_classes:
                shared_location_classes[qid] = True

            # Split file into chunks for parallel processing
            logger.info("Calculating file chunks for parallel processing...")
            chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
            logger.info(
                f"Split file into {len(chunks)} chunks for {num_workers} workers"
            )

            # Process chunks in parallel with proper KeyboardInterrupt handling
            pool = None
            try:
                pool = mp.Pool(processes=num_workers)

                # Pass shared dictionaries to workers
                async_result = pool.starmap_async(
                    self._process_supporting_entities_chunk,
                    [
                        (
                            dump_file_path,
                            start,
                            end,
                            i,
                            batch_size,
                            shared_position_classes,
                            shared_location_classes,
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

    def extract_politicians_from_dump(
        self,
        dump_file_path: str,
        batch_size: int = 1000,
    ) -> int:
        """
        Extract politicians from the Wikidata dump using parallel processing.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            batch_size: Number of entities to process in each database batch

        Returns:
            Total count of extracted politicians
        """
        num_workers = mp.cpu_count()
        logger.info(f"Using parallel processing with {num_workers} workers")

        # Split file into chunks for parallel processing
        logger.info("Calculating file chunks for parallel processing...")
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        # Process chunks in parallel with proper KeyboardInterrupt handling
        pool = None
        try:
            pool = mp.Pool(processes=num_workers)

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
                    pool.join()  # Wait up to 5 seconds for workers to finish
                except Exception:
                    pass  # If join times out, continue anyway
            raise KeyboardInterrupt("Entity extraction interrupted by user")
        finally:
            if pool:
                pool.close()
                pool.join()

        # Merge results from all chunks
        total_politicians = 0
        total_entities = 0

        for politician_count, chunk_count in chunk_results:
            total_entities += chunk_count
            total_politicians += politician_count

        logger.info(f"Extraction complete. Total processed: {total_entities}")
        logger.info(f"Extracted: {total_politicians} politicians")

        return total_politicians

    def _process_supporting_entities_chunk(
        self,
        dump_file_path: str,
        start_byte: int,
        end_byte: int,
        worker_id: int,
        batch_size: int,
        shared_position_classes: dict,
        shared_location_classes: dict,
    ) -> Tuple[Dict[str, int], int]:
        """
        Process a specific byte range of the dump file for supporting entities extraction.
        Uses Manager dictionaries for descendant QID lookups with O(1) membership testing.

        Each worker independently reads and parses its assigned chunk.
        Returns entity counts found in this chunk.
        """
        # Fix multiprocessing connection issues per SQLAlchemy docs:
        # https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork
        engine = get_engine()
        engine.dispose(close=False)

        # Use shared dictionaries directly for O(1) membership testing

        positions = []
        locations = []
        countries = []
        counts = {"positions": 0, "locations": 0, "countries": 0}
        entity_count = 0
        interrupted = False

        try:
            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                entity_count += 1

                # Progress reporting for large chunks
                if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

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
    ) -> Tuple[int, int]:
        """
        Process a specific byte range of the dump file for politician extraction.

        Each worker independently reads and parses its assigned chunk.
        Returns entity counts found in this chunk.
        """
        # Fix multiprocessing connection issues per SQLAlchemy docs:
        # https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork
        engine = get_engine()
        engine.dispose(close=False)

        politicians = []
        politician_count = 0
        entity_count = 0
        interrupted = False

        try:
            for entity in self.dump_reader.read_chunk_entities(
                dump_file_path, start_byte, end_byte
            ):
                entity_count += 1

                # Progress reporting for large chunks
                if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                    logger.info(
                        f"Worker {worker_id}: processed {entity_count} entities"
                    )

                entity_id = entity.get_wikidata_id()
                if not entity_id:
                    continue

                # Check if it's a politician
                if entity.is_politician():
                    # Skip deceased politicians who died before 1950
                    if entity.is_deceased:
                        death_claims = entity.get_truthy_claims("P570")
                        death_info = entity.extract_date_from_claims(death_claims)
                        if death_info:
                            try:
                                death_date_str = death_info["date"]
                                precision = death_info["precision"]

                                # Parse date based on precision
                                if precision >= 11:  # day precision
                                    death_date = datetime.strptime(
                                        death_date_str, "%Y-%m-%d"
                                    ).date()
                                elif precision == 10:  # month precision
                                    death_date = datetime.strptime(
                                        death_date_str + "-01", "%Y-%m-%d"
                                    ).date()
                                elif precision == 9:  # year precision
                                    death_date = datetime.strptime(
                                        death_date_str + "-01-01", "%Y-%m-%d"
                                    ).date()
                                else:
                                    death_date = None

                                # Skip if died before 1950
                                if death_date and death_date < date(1950, 1, 1):
                                    continue
                            except (ValueError, TypeError):
                                pass  # Include if we can't parse the date

                    politician_data = {
                        "wikidata_id": entity.get_wikidata_id(),
                        "name": entity.get_entity_name(),
                    }
                    politicians.append(politician_data)
                    politician_count += 1

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

        return politician_count, entity_count
