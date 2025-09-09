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


def _process_hierarchy_chunk(
    dump_file_path: str,
    start_byte: int,
    end_byte: int,
    worker_id: int,
    batch_size: int = 1000,
) -> Tuple[Dict[str, Set[str]], int]:
    """
    Worker process: Extract names and P279 relationships in single pass.
    Inserts WikidataEntity records in batches during processing.
    Returns child_id -> parent_ids relationships for main thread to insert after all workers complete.
    """
    # Create a fresh engine for this worker process
    engine = create_engine(pool_size=2, max_overflow=3)

    # Collect data
    wikidata_entities = []  # For batch insertion
    child_parent_relations = defaultdict(
        set
    )  # Return to main thread: {child_id: {parent_ids}}
    entity_count = 0

    try:
        for entity in dump_reader.read_chunk_entities(
            dump_file_path, start_byte, end_byte
        ):
            entity: WikidataEntityProcessor
            entity_count += 1

            # Progress reporting for large chunks
            if entity_count % PROGRESS_REPORT_FREQUENCY == 0:
                logger.info(f"Worker {worker_id}: processed {entity_count} entities")

            entity_id = entity.get_wikidata_id()
            if not entity_id:
                continue

            # Extract P279 relationships
            subclass_claims = entity.get_truthy_claims("P279")

            for claim in subclass_claims:
                try:
                    parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    child_parent_relations[entity_id].add(parent_id)
                except (KeyError, TypeError):
                    continue

            # If entity has P279 relationships, add it for WikidataEntity insertion
            if subclass_claims:
                # Extract name
                name = entity.get_entity_name()
                wikidata_entities.append(
                    {
                        "wikidata_id": entity_id,
                        "name": name,
                    }
                )

            # Process batch when it reaches the batch size
            if len(wikidata_entities) >= batch_size:
                _insert_wikidata_entities_batch(wikidata_entities, worker_id, engine)
                wikidata_entities = []

    except Exception as e:
        logger.error(f"Worker {worker_id}: error during processing: {e}")
        raise

    # Process remaining entities in final batch
    if wikidata_entities:
        _insert_wikidata_entities_batch(wikidata_entities, worker_id, engine)

    logger.info(
        f"Worker {worker_id}: processed {entity_count} entities, found {len(child_parent_relations)} child-parent relationships"
    )

    return dict(child_parent_relations), entity_count


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


def import_hierarchy_trees(
    dump_file_path: str,
    batch_size: int = 1000,
) -> None:
    """
    Import hierarchy trees for positions and locations from Wikidata dump.

    Uses a single-pass approach:
    1. Workers extract names and relationships, inserting WikidataEntity records during processing
    2. Main thread collects all relationships and inserts WikidataRelation records in batches

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

    pool = None
    try:
        # Workers process chunks and insert WikidataEntity records during processing
        pool = mp.Pool(processes=num_workers)

        # Each worker processes its chunk and returns relationships
        async_result = pool.starmap_async(
            _process_hierarchy_chunk,
            [
                (dump_file_path, start, end, i, batch_size)
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
        raise KeyboardInterrupt("Hierarchy import interrupted by user")
    finally:
        if pool:
            pool.close()
            pool.join()

    # Merge relationships from all workers
    logger.info("Merging relationships from all workers...")
    child_parent_relations = defaultdict(set)
    total_entities = 0

    for chunk_relations, chunk_count in chunk_results:
        total_entities += chunk_count
        for child_id, parents in chunk_relations.items():
            child_parent_relations[child_id].update(parents)

    logger.info(f"Processing complete: Processed {total_entities} entities")
    logger.info(f"Found {len(child_parent_relations)} child-parent relationships")

    # Collect all parent entities and ensure they have WikidataEntity records
    all_parent_ids = set()
    for parents in child_parent_relations.values():
        all_parent_ids.update(parents)

    logger.info(f"Inserting {len(all_parent_ids)} parent WikidataEntity records...")
    parent_classes = [
        {"wikidata_id": parent_id, "name": None} for parent_id in all_parent_ids
    ]

    # Insert parent WikidataEntity records in batches
    batch_size_inserts = 10000
    total_parent_batches = (
        len(parent_classes) + batch_size_inserts - 1
    ) // batch_size_inserts
    for i in range(0, len(parent_classes), batch_size_inserts):
        batch = parent_classes[i : i + batch_size_inserts]
        with Session(get_engine()) as session:
            stmt = insert(WikidataEntity).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
            session.execute(stmt)
            session.commit()

        logger.info(
            f"Inserted parent WikidataEntity batch {i // batch_size_inserts + 1}/{total_parent_batches} ({len(batch)} records)"
        )

    # Build WikidataRelation data directly from child_parent_relations
    relation_data = [
        {
            "parent_entity_id": parent_id,
            "child_entity_id": child_id,
            "relation_type": RelationType.SUBCLASS_OF,
        }
        for child_id, parents in child_parent_relations.items()
        for parent_id in parents
    ]

    total_relation_batches = (
        len(relation_data) + batch_size_inserts - 1
    ) // batch_size_inserts
    logger.info(
        f"Inserting {len(relation_data)} subclass relations in {total_relation_batches} batches"
    )

    for i in range(0, len(relation_data), batch_size_inserts):
        batch = relation_data[i : i + batch_size_inserts]

        with Session(get_engine()) as session:
            stmt = insert(WikidataRelation).values(batch)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_wikidata_relation")
            session.execute(stmt)
            session.commit()

        logger.info(
            f"Inserted WikidataRelation batch {i // batch_size_inserts + 1}/{total_relation_batches} ({len(batch)} records)"
        )

    logger.info(f"✅ Completed inserting {len(relation_data)} wikidata relations")

    logger.info("✅ Hierarchy import complete")
