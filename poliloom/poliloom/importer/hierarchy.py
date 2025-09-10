"""Wikidata hierarchy importing functions for positions and locations."""

import logging
import multiprocessing as mp
from typing import Dict, Set, Tuple
from collections import defaultdict

from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .. import dump_reader
from ..database import create_engine, get_engine
from ..models import WikidataEntity, WikidataRelation, RelationType
from ..wikidata_entity import WikidataEntity as WikidataEntityProcessor

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000

# Global for workers to access target QIDs in second pass
shared_target_qids: frozenset[str] | None = None


def init_second_pass_worker(target_qids: frozenset[str]) -> None:
    """Initializer for second pass workers."""
    global shared_target_qids
    shared_target_qids = target_qids


def _process_first_pass_chunk(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
) -> Tuple[Set[str], int]:
    """
    First pass: Collect all parent IDs from relations.
    Returns:
        - Set of all parent IDs from all relation types
        - Total entity count
    """
    all_parent_ids = set()  # All parent IDs from all relations
    entity_count = 0

    # Get tracked properties from RelationType enum
    tracked_properties = [rt.value for rt in RelationType]

    try:
        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntityProcessor
            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"First pass - Worker {worker_id}: processed {entity_count} entities")

            entity_id = entity.get_wikidata_id()
            if not entity_id:
                continue

            # Collect parent IDs from all tracked relations
            for property_id in tracked_properties:
                claims = entity.get_truthy_claims(property_id)
                for claim in claims:
                    try:
                        parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        all_parent_ids.add(parent_id)
                    except (KeyError, TypeError):
                        continue

    except Exception as e:
        logger.error(f"First pass - Worker {worker_id}: error during processing: {e}")
        raise

    logger.info(
        f"First pass - Worker {worker_id}: processed {entity_count} entities, "
        f"found {len(all_parent_ids)} unique parent IDs"
    )
    
    return all_parent_ids, entity_count


def _process_second_pass_chunk(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
    batch_size: int = 1000,
) -> int:
    """
    Second pass: Process entities that are in the target set.
    Updates names and inserts all relations.
    """
    # Create a fresh engine for this worker process
    engine = create_engine(pool_size=2, max_overflow=3)

    # Collect data for batch insertion
    wikidata_entities = []  # For WikidataEntity updates
    wikidata_relations = []  # For WikidataRelation insertion
    entity_count = 0
    processed_count = 0

    try:
        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntityProcessor
            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"Second pass - Worker {worker_id}: processed {entity_count} entities")

            entity_id = entity.get_wikidata_id()
            if not entity_id or entity_id not in shared_target_qids:
                continue

            processed_count += 1

            # Extract name for update
            name = entity.get_entity_name()
            wikidata_entities.append({
                "wikidata_id": entity_id,
                "name": name,
            })

            # Extract all relations using tracked properties
            for relation_type in RelationType:
                property_id = relation_type.value
                claims = entity.get_truthy_claims(property_id)
                for claim in claims:
                    try:
                        parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                        wikidata_relations.append({
                            "parent_entity_id": parent_id,
                            "child_entity_id": entity_id,
                            "relation_type": relation_type,
                        })
                    except (KeyError, TypeError):
                        continue

            # Process batches when they reach the batch size
            if len(wikidata_entities) >= batch_size:
                _insert_wikidata_entities_batch(wikidata_entities, worker_id, engine)
                wikidata_entities = []
            
            if len(wikidata_relations) >= batch_size:
                _insert_wikidata_relations_batch(wikidata_relations, worker_id, engine)
                wikidata_relations = []

    except Exception as e:
        logger.error(f"Second pass - Worker {worker_id}: error during processing: {e}")
        raise

    # Process remaining batches
    if wikidata_entities:
        _insert_wikidata_entities_batch(wikidata_entities, worker_id, engine)
    if wikidata_relations:
        _insert_wikidata_relations_batch(wikidata_relations, worker_id, engine)

    logger.info(
        f"Second pass - Worker {worker_id}: processed {entity_count} entities, "
        f"updated {processed_count} target entities"
    )
    
    return processed_count


def _insert_wikidata_entities_batch(
    wikidata_entities: list[dict], worker_id: int, engine: Engine
) -> None:
    """Insert a batch of WikidataEntity records into the database."""
    if not wikidata_entities:
        return

    try:
        with Session(engine) as session:
            stmt = insert(WikidataEntity).values(wikidata_entities)
            stmt = stmt.on_conflict_do_update(
                index_elements=["wikidata_id"],
                set_={"name": stmt.excluded.name},
            )
            session.execute(stmt)
            session.commit()

            logger.debug(
                f"Worker {worker_id}: inserted batch of {len(wikidata_entities)} WikidataEntity records"
            )
    except Exception as e:
        logger.error(f"Worker {worker_id}: failed to insert WikidataEntity batch: {e}")
        raise


def _insert_wikidata_relations_batch(
    wikidata_relations: list[dict], worker_id: int, engine: Engine
) -> None:
    """Insert a batch of WikidataRelation records into the database."""
    if not wikidata_relations:
        return

    try:
        with Session(engine) as session:
            stmt = insert(WikidataRelation).values(wikidata_relations)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["parent_entity_id", "child_entity_id", "relation_type"]
            )
            session.execute(stmt)
            session.commit()

            logger.debug(
                f"Worker {worker_id}: inserted batch of {len(wikidata_relations)} WikidataRelation records"
            )
    except Exception as e:
        logger.error(f"Worker {worker_id}: failed to insert WikidataRelation batch: {e}")
        raise


def import_hierarchy_trees(
    dump_file_path: str,
    batch_size: int = 1000,
) -> None:
    """
    Import hierarchy trees for positions and locations from Wikidata dump.

    Uses a two-pass approach:
    1. First pass: Collect all parent IDs and entities with P279 relations
    2. Second pass: Process all collected entities - update names and insert relations

    Args:
        dump_file_path: Path to the Wikidata JSON dump file
        batch_size: Number of entities to process in each database batch
    """
    logger.info(f"Importing hierarchy trees from dump file: {dump_file_path}")

    num_workers = mp.cpu_count()
    logger.info(f"Using {num_workers} parallel workers")

    # Split file into chunks for parallel processing
    chunks = dump_reader.calculate_file_chunks(dump_file_path)
    logger.info(f"Processing {len(chunks)} file chunks")

    # ========== FIRST PASS: Collect parent IDs ==========
    logger.info("Starting first pass: collecting parent IDs...")
    
    pool = None
    try:
        pool = mp.Pool(processes=num_workers)

        async_result = pool.starmap_async(
            _process_first_pass_chunk,
            [
                (dump_file_path, start, end, i)
                for i, (start, end) in enumerate(chunks)
            ],
        )

        first_pass_results = async_result.get()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, cleaning up workers...")
        if pool:
            pool.terminate()
            try:
                pool.join()
            except Exception:
                pass
        raise KeyboardInterrupt("Hierarchy import interrupted by user")
    finally:
        if pool:
            pool.close()
            pool.join()

    # Merge first pass results
    logger.info("Merging first pass results...")
    all_parent_ids = set()  # All parent IDs
    total_entities = 0

    for chunk_parent_ids, chunk_count in first_pass_results:
        total_entities += chunk_count
        all_parent_ids.update(chunk_parent_ids)

    logger.info(f"First pass complete: Processed {total_entities} entities")
    logger.info(f"Found {len(all_parent_ids)} unique parent IDs")

    # Get existing QIDs from database
    logger.info("Loading existing QIDs from database...")
    with Session(get_engine()) as session:
        existing_qids = session.query(WikidataEntity.wikidata_id).all()
        existing_qids = {qid[0] for qid in existing_qids}
        logger.info(f"Found {len(existing_qids)} existing entities in database")

    # Combine all target QIDs for second pass
    target_qids = all_parent_ids | existing_qids
    logger.info(f"Total target entities for second pass: {len(target_qids)}")

    # Insert initial WikidataEntity records for new parent entities
    # (without names, will be updated in second pass)
    new_entities = all_parent_ids - existing_qids
    if new_entities:
        logger.info(f"Inserting {len(new_entities)} new WikidataEntity records...")
        entity_data = [{"wikidata_id": qid, "name": None} for qid in new_entities]
        
        batch_size_inserts = 10000
        for i in range(0, len(entity_data), batch_size_inserts):
            batch = entity_data[i : i + batch_size_inserts]
            with Session(get_engine()) as session:
                stmt = insert(WikidataEntity).values(batch)
                stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
                session.execute(stmt)
                session.commit()
            logger.info(f"Inserted batch {i // batch_size_inserts + 1} ({len(batch)} records)")

    # ========== SECOND PASS: Update names and insert relations ==========
    logger.info("Starting second pass: updating names and inserting relations...")
    
    # Convert to frozenset for efficient sharing across workers
    target_qids = frozenset(target_qids)
    
    pool = None
    try:
        pool = mp.Pool(
            processes=num_workers,
            initializer=init_second_pass_worker,
            initargs=(target_qids,)
        )

        async_result = pool.starmap_async(
            _process_second_pass_chunk,
            [
                (dump_file_path, start, end, i, batch_size)
                for i, (start, end) in enumerate(chunks)
            ],
        )

        second_pass_results = async_result.get()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, cleaning up workers...")
        if pool:
            pool.terminate()
            try:
                pool.join()
            except Exception:
                pass
        raise KeyboardInterrupt("Hierarchy import interrupted by user")
    finally:
        if pool:
            pool.close()
            pool.join()

    # Summarize second pass results
    total_processed = sum(second_pass_results)
    logger.info(f"Second pass complete: Processed {total_processed} target entities")

    logger.info("✅ Hierarchy import complete")
