"""Wikidata hierarchy building service for positions and locations."""

import logging
import multiprocessing as mp
from typing import Dict, Set, Tuple
from collections import defaultdict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text
from sqlalchemy.orm import Session

from .dump_reader import DumpReader
from ..database import get_engine
from ..models import WikidataClass, SubclassRelation
from ..wikidata_entity import WikidataEntity

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Define globals for workers
shared_target_qids: frozenset[str] | None = None


def init_hierarchy_worker(target_qids: frozenset[str]) -> None:
    """Initializer runs in each worker process once at startup."""
    global shared_target_qids
    shared_target_qids = target_qids


def _process_chunk_for_name_updates(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
) -> Tuple[int, int]:
    """
    Worker process: Extract names only for entities in target QIDs frozenset.
    Updates WikidataClass records in batches to reduce memory usage.
    Returns count of updates made.
    """
    global shared_target_qids

    # Fix multiprocessing connection issues per SQLAlchemy docs:
    # https://docs.sqlalchemy.org/en/20/core/pooling.html#using-connection-pools-with-multiprocessing-or-os-fork
    engine = get_engine()
    engine.dispose(close=False)

    dump_reader = DumpReader()
    batch_size = 1000  # Process name updates in batches of 1000
    name_updates = {}
    total_updates_count = 0
    entity_count = 0
    interrupted = False

    try:
        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntity
            if interrupted:
                break

            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"Worker {worker_id}: processed {entity_count} entities")

            entity_id = entity.get_wikidata_id()
            if not entity_id or entity_id not in shared_target_qids:
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
            logger.warning(f"Worker {worker_id}: error during cleanup: {cleanup_error}")

    if interrupted:
        logger.info(f"Worker {worker_id}: interrupted, returning partial results")
    else:
        logger.info(
            f"Worker {worker_id}: extracted {total_updates_count} names from {entity_count} entities"
        )

    return total_updates_count, entity_count


def _process_chunk_for_relationships(
    dump_file_path: str, start_byte: int, end_byte: int, worker_id: int
) -> Tuple[Dict[str, Set[str]], int]:
    """
    Worker process: Extract only P279 relationships, no entity names.

    This dramatically reduces memory usage by avoiding entity name collection.
    """
    dump_reader = DumpReader()
    interrupted = False

    try:
        subclass_relations = defaultdict(set)
        entity_count = 0

        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntity
            if interrupted:
                break

            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"Worker {worker_id}: processed {entity_count} entities")

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


class WikidataHierarchyBuilder:
    """Build hierarchy trees for positions and locations from Wikidata dump."""

    def __init__(self):
        """Initialize the hierarchy builder."""
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
                _process_chunk_for_relationships,
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
        Uses frozenset to efficiently share QIDs between workers with O(1) lookups.

        Args:
            dump_file_path: Path to the Wikidata JSON dump file
            target_qids: Set of QIDs to extract names for (already available from hierarchy building)
        """
        logger.info(f"Extracting names for {len(target_qids)} WikidataClass records")

        # Build frozenset once in parent, BEFORE starting Pool
        target_qids_frozen = frozenset(target_qids)
        logger.info(f"Prepared frozenset with {len(target_qids_frozen)} QIDs")

        num_workers = mp.cpu_count()
        logger.info(f"Using {num_workers} parallel workers for name extraction")

        # Split file into chunks for parallel processing
        chunks = self.dump_reader.calculate_file_chunks(dump_file_path)
        logger.info(f"Split file into {len(chunks)} chunks for {num_workers} workers")

        pool = None

        try:
            pool = mp.Pool(
                processes=num_workers,
                initializer=init_hierarchy_worker,
                initargs=(target_qids_frozen,),
            )

            async_result = pool.starmap_async(
                _process_chunk_for_name_updates,
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
