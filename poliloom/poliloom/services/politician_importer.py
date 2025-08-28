"""Wikidata politician importing service."""

import logging
import multiprocessing as mp
from typing import Tuple
from datetime import datetime, date

from .dump_reader import DumpReader
from .database_inserter import DatabaseInserter
from ..database import get_engine
from ..wikidata_entity import WikidataEntity

logger = logging.getLogger(__name__)

# Progress reporting frequency for chunk processing
PROGRESS_REPORT_FREQUENCY = 50000


def _process_politicians_chunk(
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

    dump_reader = DumpReader()
    database_inserter = DatabaseInserter()

    politicians = []
    politician_count = 0
    entity_count = 0
    interrupted = False

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
                database_inserter.insert_politicians_batch(politicians)
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
                database_inserter.insert_politicians_batch(politicians)
        except Exception as cleanup_error:
            logger.warning(f"Worker {worker_id}: error during cleanup: {cleanup_error}")

        if interrupted:
            logger.info(f"Worker {worker_id}: interrupted, returning partial results")
        else:
            logger.info(
                f"Worker {worker_id}: finished processing {entity_count} entities"
            )

    return politician_count, entity_count


class WikidataPoliticianImporter:
    """Extract politicians from the Wikidata dump using parallel processing."""

    def __init__(self):
        """Initialize the politician importer."""
        self.dump_reader = DumpReader()

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
                _process_politicians_chunk,
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
