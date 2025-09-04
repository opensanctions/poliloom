"""Main CLI interface for PoliLoom."""

import asyncio
import click
import logging
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import httpx
from ..enrichment import enrich_politician_from_wikipedia
from ..storage import StorageFactory
from ..importer.hierarchy import import_hierarchy_trees
from ..importer.entity import import_entities
from ..importer.politician import import_politicians
from ..database import get_engine
from sqlalchemy.orm import Session
from ..models import (
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


def get_latest_dump(session, allow_none=False):
    """Get the latest dump from the database."""
    latest_dump = (
        session.query(WikidataDump).order_by(WikidataDump.last_modified.desc()).first()
    )

    if not latest_dump:
        if allow_none:
            click.echo(
                "⚠️  No dump record found in database. Continuing without tracking..."
            )
            return None
        click.echo("❌ No dump found. Run 'poliloom dump-download' first")
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

            # Parse HTTP date format using httpx's built-in parser
            last_modified = httpx._utils.parse_header_date(last_modified_str)

        # Check if we already have this dump
        with Session(get_engine()) as session:
            existing_dump = (
                session.query(WikidataDump)
                .filter(WikidataDump.url == url)
                .filter(WikidataDump.last_modified == last_modified)
                .filter(WikidataDump.downloaded_at.isnot(None))
                .first()
            )

            if existing_dump:
                click.echo(
                    f"✅ Dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already downloaded"
                )
                click.echo("No new dump available. Exiting.")
                return

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
        latest_dump = get_latest_dump(session)

        if not latest_dump.downloaded_at:
            click.echo(
                f"❌ Dump from {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC not fully downloaded yet"
            )
            raise SystemExit(1)

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
    "--id",
    "wikidata_id",
    help="Wikidata ID of politician to enrich (e.g., Q123456)",
)
@click.option(
    "--limit",
    type=int,
    help="Enrich politicians until N have unevaluated extracted data available for evaluation",
)
def enrich_wikipedia(wikidata_id, limit):
    """Enrich politician entities by extracting data from their linked Wikipedia articles.

    Usage modes:
    - --id <wikidata_id>: Enrich single politician (existing behavior)
    - --limit <N>: Enrich politicians until N have unevaluated extracted data available for evaluation
    - No arguments: Enrich all politicians with Wikipedia links
    """
    # Validate arguments
    if wikidata_id and limit:
        click.echo("❌ Cannot specify both --id and --limit options")
        exit(1)

    try:
        if wikidata_id:
            # Single politician mode
            with Session(get_engine()) as session:
                politician = (
                    session.query(Politician)
                    .filter(Politician.wikidata_id == wikidata_id)
                    .filter(Politician.wikipedia_links.any(language_code="en"))
                    .first()
                )

                if not politician:
                    click.echo(
                        f"❌ Politician with ID {wikidata_id} not found or has no English Wikipedia link"
                    )
                    return

                click.echo(f"Enriching {politician.wikidata_id} ({politician.name})...")
                try:
                    asyncio.run(enrich_politician_from_wikipedia(politician))
                    click.echo(f"✅ Successfully enriched {politician.wikidata_id}")
                except Exception as e:
                    click.echo(f"❌ Failed to enrich {politician.wikidata_id}: {e}")
                return

        elif limit:
            # Limit mode: keep enriching until we have N politicians with unevaluated extracted data
            enriched_count = 0

            while True:
                with Session(get_engine()) as session:
                    # Check current count of politicians with unevaluated extracted data
                    current_count = (
                        session.query(Politician)
                        .filter(Politician.has_unevaluated_extracted_data)
                        .count()
                    )

                    if current_count >= limit:
                        click.echo(
                            f"✅ Target reached: {current_count} politicians have unevaluated extracted data"
                        )
                        break

                    # Get next politician to enrich (prioritize never enriched, then oldest)
                    next_politician = (
                        session.query(Politician)
                        .filter(Politician.wikipedia_links.any(language_code="en"))
                        .order_by(Politician.enriched_at.asc().nullsfirst())
                        .first()
                    )

                    if not next_politician:
                        click.echo("❌ No more politicians available to enrich")
                        break

                enriched_count += 1
                click.echo(
                    f"[{enriched_count}] Enriching {next_politician.wikidata_id} ({next_politician.name})..."
                )
                click.echo(
                    f"  Current count: {current_count}/{limit} politicians with unevaluated extracted data"
                )

                try:
                    asyncio.run(enrich_politician_from_wikipedia(next_politician))
                    click.echo(
                        f"  ✅ Successfully enriched {next_politician.wikidata_id}"
                    )
                except Exception as e:
                    click.echo(
                        f"  ❌ Failed to enrich {next_politician.wikidata_id}: {e}"
                    )

            # Show final statistics
            with Session(get_engine()) as session:
                final_count = (
                    session.query(Politician)
                    .filter(Politician.has_unevaluated_extracted_data)
                    .count()
                )
                click.echo(
                    f"✅ Enriched {enriched_count} politicians. Final count: {final_count} politicians with unevaluated extracted data"
                )

        else:
            # All politicians mode (original behavior)
            with Session(get_engine()) as session:
                politicians_to_enrich = (
                    session.query(Politician)
                    .filter(Politician.wikipedia_links.any(language_code="en"))
                    .order_by(Politician.enriched_at.asc().nullsfirst())
                    .all()
                )

            if not politicians_to_enrich:
                click.echo("✅ No politicians found that need enrichment")
                return

            click.echo(f"Found {len(politicians_to_enrich)} politician(s) to enrich")

            success_count = 0
            for i, politician in enumerate(politicians_to_enrich, 1):
                click.echo(
                    f"[{i}/{len(politicians_to_enrich)}] Enriching {politician.wikidata_id} ({politician.name})..."
                )

                try:
                    asyncio.run(enrich_politician_from_wikipedia(politician))
                    success_count += 1
                    click.echo(f"  ✅ Successfully enriched {politician.wikidata_id}")
                except Exception as e:
                    click.echo(f"  ❌ Failed to enrich {politician.wikidata_id}: {e}")

            click.echo(
                f"✅ Successfully enriched {success_count}/{len(politicians_to_enrich)} politicians"
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
    default=2048 * 50,
    help="Number of entities to process in each batch",
)
@click.option(
    "--gpu-batch-size", default=2048, help="Number of texts to encode at once on GPU"
)
def embed_entities(batch_size, gpu_batch_size):
    """Generate embeddings for all positions and locations that don't have embeddings yet."""
    import torch
    from sentence_transformers import SentenceTransformer

    # Use GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    click.echo(f"Using device: {device}")

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

                while processed < total_count:
                    # Get batch of entities without embeddings
                    batch = (
                        session.query(model_class)
                        .filter(model_class.embedding.is_(None))
                        .limit(batch_size)
                        .all()
                    )

                    if not batch:
                        break

                    # Generate embeddings
                    names = [entity.name for entity in batch]
                    embeddings = model.encode(
                        names, convert_to_tensor=False, batch_size=gpu_batch_size
                    )

                    # Update entities
                    for entity, embedding in zip(batch, embeddings):
                        entity.embedding = embedding.tolist()

                    session.commit()
                    processed += len(batch)
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
        latest_dump = get_latest_dump(session, allow_none=True)

        if latest_dump is not None:
            if not latest_dump.extracted_at:
                click.echo(
                    "❌ Dump not extracted yet. Run 'poliloom dump-extract' first"
                )
                raise SystemExit(1)

            if latest_dump.imported_hierarchy_at:
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
        latest_dump = get_latest_dump(session, allow_none=True)

        if latest_dump is not None:
            if not latest_dump.imported_hierarchy_at:
                click.echo(
                    "❌ Hierarchy not imported yet. Run 'poliloom import-hierarchy' first"
                )
                raise SystemExit(1)

            if latest_dump.imported_entities_at:
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
        latest_dump = get_latest_dump(session, allow_none=True)

        if latest_dump is not None:
            if not latest_dump.imported_entities_at:
                click.echo(
                    "❌ Entities not imported yet. Run 'poliloom import-entities' first"
                )
                raise SystemExit(1)

            if latest_dump.imported_politicians_at:
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
