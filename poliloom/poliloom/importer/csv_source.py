"""CSV source importer — bulk import of QID→URL pairs to Sources with extraction."""

from __future__ import annotations

import asyncio
import csv
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_engine
from ..models import Politician, Source
from ..scheduling import process_source_task

logger = logging.getLogger(__name__)

_EXTRACTION_PROGRESS_INTERVAL = 10
_HEADER = ["qid", "url"]


class MissingPoliticiansError(Exception):
    """Raised when a CSV references politicians that don't exist.

    Carries the missing QIDs so the caller can report them. When raised,
    nothing has been imported.
    """

    def __init__(self, qids: list[str]):
        self.qids = qids
        super().__init__(f"{len(qids)} politician(s) not found")


def parse_csv_file(path: str) -> list[tuple[str, str]]:
    """Read a CSV and return a list of (qid, url) tuples.

    The file must have a header row that is exactly ``qid,url`` and every data
    row must have exactly those two columns with a valid QID and an http(s) URL.
    Anything else is a malformed file and raises.

    Raises:
        ValueError: If the file is missing/empty, the header is not exactly
                    ``qid,url``, or a row has the wrong column count, an invalid
                    QID, or an invalid URL.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise ValueError(f"File not found: {path}")

    rows: list[tuple[str, str]] = []

    with file_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)

        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"CSV file {path} is empty")

        if header != _HEADER:
            raise ValueError(
                f"CSV header must be exactly 'qid,url', got: {','.join(header)!r}"
            )

        for lineno, row in enumerate(reader, start=2):  # 1-indexed, after header
            if len(row) != 2:
                raise ValueError(
                    f"Line {lineno}: expected 2 columns, got {len(row)}: {row!r}"
                )

            qid, url = row
            if not (qid.startswith("Q") and qid[1:].isdigit()):
                raise ValueError(f"Line {lineno}: invalid QID: {qid!r}")
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Line {lineno}: invalid URL: {url!r}")

            rows.append((qid, url))

    return rows


async def _run_extractions(tasks: list[tuple[uuid.UUID, uuid.UUID]]) -> None:
    """Run ``process_source_task`` for every (source_id, politician_id) pair.

    Logs progress every ``_EXTRACTION_PROGRESS_INTERVAL`` items.
    """
    total = len(tasks)
    for idx, (source_id, politician_id) in enumerate(tasks, start=1):
        await process_source_task(source_id, politician_id)
        if idx % _EXTRACTION_PROGRESS_INTERVAL == 0 or idx == total:
            logger.info("Extraction progress: %d/%d", idx, total)


def import_csv_sources(
    path: str,
    *,
    dry_run: bool = False,
) -> int:
    """Import sources from a CSV and run extraction for each.

    All politicians are verified to exist before anything is created: if any
    QID is missing, nothing is imported.

    Args:
        path: Path to a CSV file with exactly ``qid`` and ``url`` columns.
        dry_run: If True, only parse and verify existence; no database writes
                 and no extraction.

    Returns:
        The number of sources created (0 for an empty file or a dry run).

    Raises:
        ValueError: If the CSV file is malformed.
        MissingPoliticiansError: If any QID has no matching politician.
    """
    pairs = parse_csv_file(path)

    if not pairs:
        logger.warning("CSV file %s contains no rows", path)
        return 0

    with Session(get_engine()) as db:
        qids = [qid for qid, _ in pairs]
        by_qid = {
            p.wikidata_id: p
            for p in db.execute(
                select(Politician).where(Politician.wikidata_id.in_(qids))
            ).scalars()
        }

        missing = [qid for qid in dict.fromkeys(qids) if qid not in by_qid]
        if missing:
            raise MissingPoliticiansError(missing)

        if dry_run:
            return 0

        links: list[tuple[Source, Politician]] = []
        for qid, url in pairs:
            politician = by_qid[qid]
            source = Source(url=url)
            politician.sources.append(source)
            links.append((source, politician))
        db.flush()  # assigns source.id

        tasks = [(source.id, politician.id) for source, politician in links]
        db.commit()
        logger.info("Created %d sources", len(tasks))

    asyncio.run(_run_extractions(tasks))

    return len(tasks)
