"""Main CLI interface for PoliLoom."""

import asyncio
import click
import logging
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import httpx
from typing import Optional
from sqlalchemy import update, bindparam
from poliloom.enrichment import enrich_politician_from_wikipedia
from poliloom.storage import StorageFactory
from poliloom.importer.hierarchy import import_hierarchy_trees
from poliloom.importer.entity import import_entities
from poliloom.importer.politician import import_politicians
from poliloom.database import get_engine
from sqlalchemy.orm import Session
from poliloom.models import (
    Politician,
    HoldsPosition,
    HasCitizenship,
    BornAt,
    Position,
    Location,
    Property,
    WikidataDump,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def ensure_latest_dump(session, required_stage, allow_none=False):
    """
    Ensure the latest dump has completed the required stage and all prerequisite stages.

    Args:
        session: Database session
        required_stage: One of 'downloaded_at', 'extracted_at', 'imported_hierarchy_at',
                       'imported_entities_at', 'imported_politicians_at'
        allow_none: If True, returns None when no dump found instead of exiting

    Returns:
        WikidataDump instance or None (if allow_none=True and no dump found)

    Raises:
        SystemExit: If validation fails
    """
    # Define stage progression with their corresponding error messages
    stages = {
        "downloaded_at": "Dump download not completed. Check if 'poliloom dump-download' is still running or failed",
        "extracted_at": "Dump extraction not completed. Run 'poliloom dump-extract' to extract the downloaded dump",
        "imported_hierarchy_at": "Hierarchy import not completed. Run 'poliloom import-hierarchy' to import entity hierarchies",
        "imported_entities_at": "Entity import not completed. Run 'poliloom import-entities' to import entities",
        "imported_politicians_at": "Politician import not completed. Run 'poliloom import-politicians' to import politicians",
    }

    # Define stage order for prerequisite checking
    stage_order = [
        "downloaded_at",
        "extracted_at",
        "imported_hierarchy_at",
        "imported_entities_at",
        "imported_politicians_at",
    ]

    if required_stage not in stages:
        raise ValueError(
            f"Invalid stage: {required_stage}. Must be one of: {list(stages.keys())}"
        )

    # Get the latest dump from the database
    latest_dump = (
        session.query(WikidataDump).order_by(WikidataDump.created_at.desc()).first()
    )

    if not latest_dump:
        if allow_none:
            click.echo(
                "⚠️  No dump record found in database. Continuing without tracking..."
            )
            return None
        click.echo("❌ No dump found. Run 'poliloom dump-download' first")
        raise SystemExit(1)

    # Check all prerequisite stages up to and including the required stage
    required_index = stage_order.index(required_stage)

    for i in range(required_index + 1):
        stage = stage_order[i]
        error_message = stages[stage]

        if not getattr(latest_dump, stage):
            click.echo(f"❌ {error_message}")
            raise SystemExit(1)

    return latest_dump


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(verbose):
    """PoliLoom CLI - Extract politician metadata from Wikipedia and web sources."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@main.command("dump-download")
@click.option(
    "--output",
    required=True,
    help="Output path - local filesystem path or GCS path (gs://bucket/path)",
)
def dump_download(output):
    """Download latest Wikidata dump from Wikidata to specified location."""
    url = "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"

    click.echo(f"Checking for new Wikidata dump at {url}...")

    try:
        # Send HEAD request to get metadata
        with httpx.Client(timeout=30.0) as client:
            response = client.head(url, follow_redirects=True)
            response.raise_for_status()

            # Parse Last-Modified header
            last_modified_str = response.headers.get("last-modified")
            if not last_modified_str:
                click.echo(
                    "❌ No Last-Modified header in response. Cannot track dump version."
                )
                raise SystemExit(1)

            # Parse HTTP date format using datetime
            last_modified = datetime.strptime(
                last_modified_str, "%a, %d %b %Y %H:%M:%S %Z"
            ).replace(tzinfo=timezone.utc)

        # Check if we already have this dump (completed or in-progress)
        with Session(get_engine()) as session:
            existing_dump = (
                session.query(WikidataDump)
                .filter(WikidataDump.url == url)
                .filter(WikidataDump.last_modified == last_modified)
                .first()
            )

            if existing_dump:
                if existing_dump.downloaded_at:
                    click.echo(
                        f"❌ Dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already downloaded"
                    )
                    click.echo("No new dump available. Exiting.")
                    raise SystemExit(1)
                else:
                    click.echo(
                        f"❌ Download for dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already in progress"
                    )
                    click.echo("Another download process is running. Exiting.")
                    raise SystemExit(1)

            # Create new dump record
            click.echo(
                f"📝 New dump found from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            new_dump = WikidataDump(url=url, last_modified=last_modified)
            session.add(new_dump)
            session.commit()

        # Download the file
        click.echo(f"Downloading Wikidata dump to {output}...")
        click.echo(
            "This is a large file (~100GB compressed) and may take several hours."
        )

        StorageFactory.download_from_url(url, output)

        # Mark as downloaded
        new_dump.downloaded_at = datetime.now(timezone.utc)
        with Session(get_engine()) as session:
            session.merge(new_dump)
            session.commit()

        click.echo(f"✅ Successfully downloaded dump to {output}")

    except Exception as e:
        click.echo(f"❌ Download failed: {e}")
        raise SystemExit(1)


@main.command("dump-extract")
@click.option(
    "--input",
    required=True,
    help="Input path to compressed dump - local filesystem path or GCS path (gs://bucket/path)",
)
@click.option(
    "--output",
    required=True,
    help="Output path for extracted JSON - local filesystem path or GCS path (gs://bucket/path)",
)
def dump_extract(input, output):
    """Extract compressed Wikidata dump to JSON format."""

    # Get the latest dump and check its status
    with Session(get_engine()) as session:
        latest_dump = ensure_latest_dump(session, "downloaded_at")

        if latest_dump.extracted_at:
            click.echo(
                f"❌ Dump from {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already extracted"
            )
            raise SystemExit(1)

    click.echo(f"Extracting {input} to {output}...")

    # Check if source exists
    backend = StorageFactory.get_backend(input)
    if not backend.exists(input):
        click.echo(f"❌ Source file not found: {input}")
        click.echo("Run 'poliloom dump-download' first")
        raise SystemExit(1)

    try:
        click.echo("⏳ Extracting dump file...")
        click.echo("This will produce a file ~10x larger than the compressed version.")

        # Get storage backends for source and destination
        source_backend = StorageFactory.get_backend(input)
        dest_backend = StorageFactory.get_backend(output)

        # Extract using source backend
        source_backend.extract_bz2_to(input, dest_backend, output)

        # Mark as extracted
        latest_dump.extracted_at = datetime.now(timezone.utc)
        with Session(get_engine()) as session:
            session.merge(latest_dump)
            session.commit()

        click.echo(f"✅ Successfully extracted dump to {output}")
    except Exception as e:
        click.echo(f"❌ Extraction failed: {e}")
        raise SystemExit(1)


@main.command("enrich-wikipedia")
@click.option(
    "--limit",
    type=int,
    help="Enrich politicians until N have unevaluated extracted data available for evaluation",
)
def enrich_wikipedia(limit: Optional[int]) -> None:
    """Enrich politician entities by extracting data from their linked Wikipedia articles.

    Usage modes:
    - --limit <N>: Enrich up to N politicians
    - No arguments: Enrich all politicians with Wikipedia links
    """
    try:
        with Session(get_engine()) as session:
            query = (
                session.query(Politician)
                .filter(Politician.wikipedia_links.any(language_code="en"))
                .order_by(Politician.enriched_at.asc().nullsfirst())
            )

            if limit:
                politicians = query.limit(limit).all()
            else:
                politicians = query.all()

        if not politicians:
            click.echo("✅ No politicians found that need enrichment")
            return

        click.echo(f"Found {len(politicians)} politician(s) to enrich")

        success_count = 0
        for i, politician in enumerate(politicians, 1):
            click.echo(
                f"[{i}/{len(politicians)}] Enriching {politician.wikidata_id} ({politician.name})..."
            )

            try:
                asyncio.run(enrich_politician_from_wikipedia(politician))
                success_count += 1
                click.echo(f"  ✅ Successfully enriched {politician.wikidata_id}")
            except Exception as e:
                click.echo(f"  ❌ Failed to enrich {politician.wikidata_id}: {e}")

        click.echo(
            f"✅ Successfully enriched {success_count}/{len(politicians)} politicians"
        )

    except Exception as e:
        click.echo(f"❌ Error enriching politician(s): {e}")
        exit(1)


@main.command("show-politician")
@click.option(
    "--id",
    "wikidata_id",
    required=True,
    help="Wikidata ID of politician to show (e.g., Q123456)",
)
def show_politician(wikidata_id):
    """Display comprehensive information about a politician, distinguishing between imported and generated data."""
    click.echo(f"Showing information for politician with Wikidata ID: {wikidata_id}")

    try:
        with Session(get_engine()) as session:
            # Query politician with all related data including evaluations
            politician = (
                session.query(Politician)
                .filter(Politician.wikidata_id == wikidata_id)
                .options(
                    joinedload(Politician.properties).joinedload(Property.evaluations),
                    joinedload(Politician.positions_held).joinedload(
                        HoldsPosition.position
                    ),
                    joinedload(Politician.positions_held).joinedload(
                        HoldsPosition.evaluations
                    ),
                    joinedload(Politician.citizenships).joinedload(
                        HasCitizenship.country
                    ),
                    joinedload(Politician.birthplaces).joinedload(BornAt.location),
                    joinedload(Politician.birthplaces).joinedload(BornAt.evaluations),
                    joinedload(Politician.wikipedia_links),
                )
                .first()
            )

            if not politician:
                click.echo(
                    f"❌ Politician with Wikidata ID '{wikidata_id}' not found in database."
                )
                exit(1)

        # Display basic information
        click.echo()
        click.echo("=" * 80)
        click.echo(f"🏛️  POLITICIAN: {politician.name}")
        click.echo("=" * 80)
        click.echo(f"Wikidata ID: {politician.wikidata_id}")
        click.echo(
            f"Wikidata Link: https://www.wikidata.org/wiki/{politician.wikidata_id}"
        )
        click.echo(f"Database ID: {politician.id}")
        click.echo(f"Deceased: {'Yes' if politician.is_deceased else 'No'}")
        click.echo(f"Created: {politician.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Updated: {politician.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

        # Display Wikipedia links
        if politician.wikipedia_links:
            click.echo()
            click.echo("📖 WIKIPEDIA LINKS:")
            click.echo("-" * 40)
            for wiki_link in politician.wikipedia_links:
                click.echo(f"    • [{wiki_link.language_code.upper()}] {wiki_link.url}")

        # Display citizenships
        if politician.citizenships:
            click.echo()
            click.echo("🌍 CITIZENSHIPS:")
            click.echo("-" * 40)
            for citizenship in politician.citizenships:
                country_info = f"{citizenship.country.name}"
                if citizenship.country.iso_code:
                    country_info += f" ({citizenship.country.iso_code})"
                if citizenship.country.wikidata_id:
                    country_info += f" [{citizenship.country.wikidata_id}]"
                click.echo(f"  • {country_info}")

        # Display properties
        if politician.properties:
            click.echo()
            click.echo("📋 PROPERTIES:")
            click.echo("-" * 40)

            # Separate imported vs extracted properties
            imported_props = [p for p in politician.properties if not p.is_extracted]
            extracted_props = [p for p in politician.properties if p.is_extracted]

            if imported_props:
                click.echo("  📥 IMPORTED FROM WIKIDATA:")
                for prop in imported_props:
                    click.echo(f"    • {prop.type}: {prop.value}")

            if extracted_props:
                click.echo("  🤖 EXTRACTED FROM WEB SOURCES:")
                for prop in extracted_props:
                    if prop.evaluations:
                        # Show evaluation status
                        confirmed_evals = [
                            e for e in prop.evaluations if e.is_confirmed
                        ]
                        discarded_evals = [
                            e for e in prop.evaluations if not e.is_confirmed
                        ]

                        if confirmed_evals:
                            status = f"✅ CONFIRMED by {len(confirmed_evals)} user(s)"
                            if len(confirmed_evals) == 1:
                                status += f" ({confirmed_evals[0].user_id})"
                        elif discarded_evals:
                            status = f"❌ REJECTED by {len(discarded_evals)} user(s)"
                            if len(discarded_evals) == 1:
                                status += f" ({discarded_evals[0].user_id})"
                        else:
                            status = "⏳ PENDING"
                    else:
                        status = "⏳ PENDING"

                    click.echo(f"    • {prop.type}: {prop.value} [{status}]")

        # Display birthplaces
        if politician.birthplaces:
            click.echo()
            click.echo("📍 BIRTHPLACES:")
            click.echo("-" * 40)

            # Separate imported vs extracted birthplaces
            imported_birthplaces = [
                b for b in politician.birthplaces if not b.is_extracted
            ]
            extracted_birthplaces = [
                b for b in politician.birthplaces if b.is_extracted
            ]

            if imported_birthplaces:
                click.echo("  📥 IMPORTED FROM WIKIDATA:")
                for birthplace in imported_birthplaces:
                    location_info = f"{birthplace.location.name}"
                    if birthplace.location.wikidata_id:
                        location_info += f" [{birthplace.location.wikidata_id}]"
                    click.echo(f"    • {location_info}")

            if extracted_birthplaces:
                click.echo("  🤖 EXTRACTED FROM WEB SOURCES:")
                for birthplace in extracted_birthplaces:
                    if birthplace.evaluations:
                        # Show evaluation status
                        confirmed_evals = [
                            e for e in birthplace.evaluations if e.is_confirmed
                        ]
                        discarded_evals = [
                            e for e in birthplace.evaluations if not e.is_confirmed
                        ]

                        if confirmed_evals:
                            status = f"✅ CONFIRMED by {len(confirmed_evals)} user(s)"
                            if len(confirmed_evals) == 1:
                                status += f" ({confirmed_evals[0].user_id})"
                        elif discarded_evals:
                            status = f"❌ REJECTED by {len(discarded_evals)} user(s)"
                            if len(discarded_evals) == 1:
                                status += f" ({discarded_evals[0].user_id})"
                        else:
                            status = "⏳ PENDING"
                    else:
                        status = "⏳ PENDING"

                    location_info = f"{birthplace.location.name}"
                    if birthplace.location.wikidata_id:
                        location_info += f" [{birthplace.location.wikidata_id}]"

                    click.echo(f"    • {location_info} [{status}]")

        # Display positions
        if politician.positions_held:
            click.echo()
            click.echo("🏛️  POSITIONS HELD:")
            click.echo("-" * 40)

            # Separate imported vs extracted positions
            imported_positions = [
                p for p in politician.positions_held if not p.is_extracted
            ]
            extracted_positions = [
                p for p in politician.positions_held if p.is_extracted
            ]

            if imported_positions:
                click.echo("  📥 IMPORTED FROM WIKIDATA:")
                for pos in imported_positions:
                    date_info = ""
                    if pos.start_date or pos.end_date:
                        start = pos.start_date or "?"
                        end = pos.end_date or "present"
                        date_info = f" ({start} - {end})"

                    position_info = f"{pos.position.name}{date_info}"
                    if pos.position.wikidata_id:
                        position_info += f" [{pos.position.wikidata_id}]"

                    click.echo(f"    • {position_info}")

            if extracted_positions:
                click.echo("  �🤖 EXTRACTED FROM WEB SOURCES:")
                for pos in extracted_positions:
                    if pos.evaluations:
                        # Show evaluation status
                        confirmed_evals = [e for e in pos.evaluations if e.is_confirmed]
                        discarded_evals = [
                            e for e in pos.evaluations if not e.is_confirmed
                        ]

                        if confirmed_evals:
                            status = f"✅ CONFIRMED by {len(confirmed_evals)} user(s)"
                            if len(confirmed_evals) == 1:
                                status += f" ({confirmed_evals[0].user_id})"
                        elif discarded_evals:
                            status = f"❌ REJECTED by {len(discarded_evals)} user(s)"
                            if len(discarded_evals) == 1:
                                status += f" ({discarded_evals[0].user_id})"
                        else:
                            status = "⏳ PENDING"
                    else:
                        status = "⏳ PENDING"

                    date_info = ""
                    if pos.start_date or pos.end_date:
                        start = pos.start_date or "?"
                        end = pos.end_date or "present"
                        date_info = f" ({start} - {end})"

                    position_info = f"{pos.position.name}{date_info}"
                    if pos.position.wikidata_id:
                        position_info += f" [{pos.position.wikidata_id}]"

                    click.echo(f"    • {position_info} [{status}]")

            click.echo()
            click.echo("=" * 80)

    except Exception as e:
        click.echo(f"❌ Error showing politician information: {e}")
        exit(1)


@main.command("embed-entities")
@click.option(
    "--batch-size",
    default=2000,
    help="Number of entities to read from DB per batch",
)
@click.option(
    "--encode-batch-size",
    default=1024,
    help="Number of texts to encode at once (CPU or GPU)",
)
def embed_entities(batch_size, encode_batch_size):
    """Generate embeddings for all positions and locations missing embeddings, efficiently and cleanly."""
    import torch
    from sentence_transformers import SentenceTransformer

    # Use GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    click.echo(f"Using device for encoding: {device}")

    model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

    try:
        with Session(get_engine()) as session:
            for model_class, entity_name in [
                (Position, "positions"),
                (Location, "locations"),
            ]:
                click.echo(f"Processing {entity_name}...")

                # Get total count
                total_count = (
                    session.query(model_class)
                    .filter(model_class.embedding.is_(None))
                    .count()
                )

                if total_count == 0:
                    click.echo(f"✅ All {entity_name} already have embeddings")
                    continue

                click.echo(f"Found {total_count} {entity_name} without embeddings")
                processed = 0

                # Deterministic keyset pagination by primary key to avoid rescans
                last_id = None
                while True:
                    q = session.query(model_class.wikidata_id, model_class.name).filter(
                        model_class.embedding.is_(None)
                    )
                    if last_id is not None:
                        q = q.filter(model_class.wikidata_id > last_id)
                    batch = q.order_by(model_class.wikidata_id).limit(batch_size).all()

                    if not batch:
                        break

                    wikidata_ids = [row[0] for row in batch]
                    names = [row[1] for row in batch]

                    # Generate embeddings (typed lists). Use encode_batch_size for both CPU/GPU
                    embeddings = model.encode(
                        names, convert_to_tensor=False, batch_size=encode_batch_size
                    )

                    # Update using typed executemany with pgvector adapter (no casts)
                    params = [
                        {
                            "pk": wid,
                            "embedding": emb.tolist()
                            if hasattr(emb, "tolist")
                            else emb,
                        }
                        for wid, emb in zip(wikidata_ids, embeddings)
                    ]

                    table = model_class.__table__
                    stmt = (
                        update(table)
                        .where(table.c.wikidata_id == bindparam("pk"))
                        .values(embedding=bindparam("embedding"))
                        .execution_options(synchronize_session=False)
                    )
                    session.execute(stmt, params)
                    session.commit()

                    processed += len(batch)
                    last_id = wikidata_ids[-1]
                    click.echo(f"Processed {processed}/{total_count} {entity_name}")

                click.echo(f"✅ Generated embeddings for {processed} {entity_name}")

    except Exception as e:
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)


@main.command("import-hierarchy")
@click.option(
    "--file",
    required=True,
    help="Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)",
)
def dump_import_hierarchy(file):
    """Import hierarchy trees for positions and locations from Wikidata dump."""

    # Get the latest dump and check its status
    with Session(get_engine()) as session:
        latest_dump = ensure_latest_dump(session, "extracted_at", allow_none=True)

        if latest_dump is not None and latest_dump.imported_hierarchy_at:
            click.echo(
                f"⚠️  Warning: Hierarchy for dump from {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already imported"
            )
            click.echo("Continuing anyway...")

    click.echo(f"Importing hierarchy trees from dump file: {file}")

    # Check if dump file exists using storage backend
    backend = StorageFactory.get_backend(file)
    if not backend.exists(file):
        click.echo(f"❌ Dump file not found: {file}")
        click.echo(
            "Please run 'poliloom dump-download' and 'poliloom dump-extract' first"
        )
        raise SystemExit(1)

    try:
        click.echo("⏳ Extracting P279 (subclass of) relationships...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Import the trees (always parallel)
        import_hierarchy_trees(file)

        # Mark as imported
        if latest_dump is not None:
            latest_dump.imported_hierarchy_at = datetime.now(timezone.utc)
            with Session(get_engine()) as session:
                session.merge(latest_dump)
                session.commit()

    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user. Cleaning up...")
        click.echo("❌ Hierarchy tree import was cancelled.")
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error importing hierarchy trees: {e}")
        raise SystemExit(1)


@main.command("import-entities")
@click.option(
    "--file",
    required=True,
    help="Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Number of entities to process in each database batch (default: 100)",
)
def dump_import_entities(file, batch_size):
    """Import supporting entities (positions, locations, countries) from a Wikidata dump file."""

    # Get the latest dump and check its status
    with Session(get_engine()) as session:
        latest_dump = ensure_latest_dump(
            session, "imported_hierarchy_at", allow_none=True
        )

        if latest_dump is not None and latest_dump.imported_entities_at:
            click.echo(
                f"⚠️  Warning: Entities for dump from {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already imported"
            )
            click.echo("Continuing anyway...")

    click.echo(f"Importing supporting entities from dump file: {file}")
    click.echo(f"Using batch size: {batch_size}")

    # Check if dump file exists using storage backend
    backend = StorageFactory.get_backend(file)
    if not backend.exists(file):
        click.echo(f"❌ Dump file not found: {file}")
        click.echo(
            "Please run 'poliloom dump-download' and 'poliloom dump-extract' first"
        )
        raise SystemExit(1)

    try:
        click.echo("⏳ Extracting supporting entities from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Import supporting entities only
        counts = import_entities(file, batch_size=batch_size)

        # Mark as imported
        if latest_dump is not None:
            with Session(get_engine()) as session:
                dump_record = (
                    session.query(WikidataDump)
                    .filter(WikidataDump.id == latest_dump.id)
                    .first()
                )
                if dump_record is not None:
                    dump_record.imported_entities_at = datetime.now(timezone.utc)
                    session.commit()

        click.echo("✅ Successfully imported supporting entities from dump:")
        click.echo(f"  • Positions: {counts['positions']}")
        click.echo(f"  • Locations: {counts['locations']}")
        click.echo(f"  • Countries: {counts['countries']}")
        click.echo(f"  • Total: {sum(counts.values())}")

        # Suggest next steps
        click.echo()
        click.echo("💡 Next steps:")
        click.echo("  • Run 'poliloom import-politicians' to import politicians")
        click.echo("  • Run 'poliloom embed-entities' to generate embeddings")
    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user. Cleaning up...")
        click.echo("❌ Supporting entities import was cancelled.")
        click.echo(
            "⚠️  Note: Some entities may have been partially imported to the database."
        )
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error importing supporting entities: {e}")
        raise SystemExit(1)


@main.command("import-politicians")
@click.option(
    "--file",
    required=True,
    help="Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Number of entities to process in each database batch (default: 100)",
)
def dump_import_politicians(file, batch_size):
    """Import politicians from a Wikidata dump file, linking them to existing entities."""

    # Get the latest dump and check its status
    with Session(get_engine()) as session:
        latest_dump = ensure_latest_dump(
            session, "imported_entities_at", allow_none=True
        )

        if latest_dump is not None and latest_dump.imported_politicians_at:
            click.echo(
                f"⚠️  Warning: Politicians for dump from {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already imported"
            )
            click.echo("Continuing anyway...")

    click.echo(f"Importing politicians from dump file: {file}")
    click.echo(f"Using batch size: {batch_size}")

    # Check if dump file exists using storage backend
    backend = StorageFactory.get_backend(file)
    if not backend.exists(file):
        click.echo(f"❌ Dump file not found: {file}")
        click.echo(
            "Please run 'poliloom dump-download' and 'poliloom dump-extract' first"
        )
        raise SystemExit(1)

    try:
        click.echo("⏳ Extracting politicians from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Import politicians only
        politicians_count = import_politicians(file, batch_size=batch_size)

        # Mark as imported
        if latest_dump is not None:
            latest_dump.imported_politicians_at = datetime.now(timezone.utc)
            with Session(get_engine()) as session:
                session.merge(latest_dump)
                session.commit()

        click.echo("✅ Successfully imported politicians from dump:")
        click.echo(f"  • Politicians: {politicians_count}")

        # Suggest next steps
        click.echo()
        click.echo("💡 Next steps:")
        click.echo(
            "  • Run 'poliloom enrich-wikipedia --id <wikidata_id>' to enrich politician data"
        )
    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user. Cleaning up...")
        click.echo("❌ Politicians import was cancelled.")
        click.echo(
            "⚠️  Note: Some politicians may have been partially imported to the database."
        )
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error importing politicians: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
