"""Main CLI interface for PoliLoom."""

import click
import logging
from datetime import datetime, timezone
import httpx
from poliloom.enrichment import enrich_politician_from_wikipedia
from poliloom.storage import StorageFactory
from poliloom.importer.hierarchy import import_hierarchy_trees
from poliloom.importer.entity import import_entities
from poliloom.importer.politician import import_politicians
from poliloom.database import get_engine
from poliloom.logging import setup_logging
from sqlalchemy.orm import Session
from poliloom.models import (
    WikidataDump,
    CurrentImportEntity,
    CurrentImportStatement,
)

# Configure logging
setup_logging()


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
@click.option(
    "--force",
    is_flag=True,
    help="Force new download, bypassing existing download check",
)
def dump_download(output, force):
    """Download latest Wikidata dump from Wikidata to specified location."""
    url = "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"

    click.echo(f"⏳ Checking for new Wikidata dump at {url}...")

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

        # Check if we already have this dump (completed or in-progress) unless --force is used
        with Session(get_engine()) as session:
            existing_dump = (
                session.query(WikidataDump)
                .filter(WikidataDump.url == url)
                .filter(WikidataDump.last_modified == last_modified)
                .first()
            )

            if existing_dump and not force:
                if existing_dump.downloaded_at:
                    click.echo(
                        f"❌ Dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already downloaded"
                    )
                    click.echo("No new dump available. Use --force to download anyway.")
                    raise SystemExit(1)
                else:
                    click.echo(
                        f"❌ Download for dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already in progress"
                    )
                    click.echo(
                        "Another download process is running. Use --force to start new download."
                    )
                    raise SystemExit(1)
            elif existing_dump and force:
                click.echo(
                    f"⚠️  Forcing new download for dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC (bypassing existing check)"
                )

            # Create new dump record
            if not existing_dump:
                click.echo(
                    f"📝 New dump found from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
            new_dump = WikidataDump(url=url, last_modified=last_modified)
            session.add(new_dump)
            session.commit()

        # Download the file
        click.echo(f"⏳ Downloading Wikidata dump to {output}...")
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

    click.echo(f"⏳ Extracting {input} to {output}...")

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
    "--count",
    type=int,
    default=5,
    help="Number of politicians to enrich (default: 5)",
)
@click.option(
    "--languages",
    multiple=True,
    help="Filter by language QIDs (can be specified multiple times)",
)
@click.option(
    "--countries",
    multiple=True,
    help="Filter by country QIDs (can be specified multiple times)",
)
def enrich_wikipedia(
    count: int, languages: tuple[str, ...], countries: tuple[str, ...]
) -> None:
    """Enrich a specified number of politicians from Wikipedia.

    This command enriches politicians by extracting data from their Wikipedia articles.

    Examples:
    - poliloom enrich-wikipedia --count 20
    - poliloom enrich-wikipedia --count 10 --countries Q30 --countries Q38
    - poliloom enrich-wikipedia --count 5 --languages Q1860 --languages Q150
    """
    import asyncio

    try:
        # Convert tuples to lists (or None if empty)
        languages_list = list(languages) if languages else None
        countries_list = list(countries) if countries else None

        click.echo(f"⏳ Enriching {count} politicians...")
        if languages_list:
            click.echo(f"   Filtering by languages: {', '.join(languages_list)}")
        if countries_list:
            click.echo(f"   Filtering by countries: {', '.join(countries_list)}")

        enriched_count = 0
        for i in range(count):
            politician_found = asyncio.run(
                enrich_politician_from_wikipedia(
                    languages=languages_list, countries=countries_list
                )
            )

            if not politician_found:
                click.echo("⚠️  No more politicians available to enrich")
                break

            enriched_count += 1
            click.echo(f"   Progress: {enriched_count}/{count}")

        if enriched_count == 0:
            click.echo("✅ No politicians enriched")
        else:
            click.echo(f"✅ Successfully enriched {enriched_count} politicians")

    except Exception as e:
        click.echo(f"❌ Error enriching politicians: {e}")
        raise SystemExit(1)


@main.command("embed-entities")
@click.option(
    "--batch-size",
    default=8192,
    help="Number of entities to read from DB per batch",
)
@click.option(
    "--encode-batch-size",
    default=2048,
    help="Number of texts to encode at once (CPU or GPU)",
)
def embed_entities(batch_size, encode_batch_size):
    """Generate embeddings for all positions missing embeddings."""
    import torch
    from poliloom.embeddings import get_embedding_model
    from poliloom.models import Position

    logger = logging.getLogger(__name__)

    try:
        # Use GPU if available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device for encoding: {device}")

        model = get_embedding_model()

        with Session(get_engine()) as session:
            # Get total count
            total_count = (
                session.query(Position).filter(Position.embedding.is_(None)).count()
            )

            if total_count == 0:
                click.echo("✅ All positions already have embeddings")
                return

            logger.info(f"Found {total_count} positions without embeddings")
            processed = 0

            # Process positions in batches
            while True:
                # Query full ORM objects to use the name property
                batch = (
                    session.query(Position)
                    .filter(Position.embedding.is_(None))
                    .limit(batch_size)
                    .all()
                )

                if not batch:
                    break

                # Use the name property from ORM objects
                names = [position.name for position in batch]

                # Generate embeddings
                embeddings = model.encode(
                    names, convert_to_tensor=False, batch_size=encode_batch_size
                )

                # Update embeddings on the ORM objects
                for position, embedding in zip(batch, embeddings):
                    position.embedding = embedding

                session.commit()

                processed += len(batch)
                logger.info(f"Processed {processed}/{total_count} positions")

            click.echo(f"✅ Generated embeddings for {processed} positions")

    except Exception as e:
        click.echo(f"❌ Error generating embeddings: {e}")
        raise SystemExit(1)


@main.command("import-hierarchy")
@click.option(
    "--file",
    required=True,
    help="Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)",
)
@click.option(
    "--batch-size",
    type=int,
    default=1000,
    help="Number of entities to process in each database batch (default: 1000)",
)
def dump_import_hierarchy(file, batch_size):
    """Import hierarchy trees for positions and locations from Wikidata dump."""

    # Get the latest dump and check its status
    with Session(get_engine()) as session:
        latest_dump = ensure_latest_dump(session, "extracted_at", allow_none=True)

        if latest_dump is not None and latest_dump.imported_hierarchy_at:
            click.echo(
                f"⚠️  Warning: Hierarchy for dump from {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already imported"
            )
            click.echo("Continuing anyway...")

    click.echo(f"⏳ Importing hierarchy trees from dump file: {file}")

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
        import_hierarchy_trees(file, batch_size=batch_size)

        # Mark as imported
        if latest_dump is not None:
            latest_dump.imported_hierarchy_at = datetime.now(timezone.utc)
            with Session(get_engine()) as session:
                session.merge(latest_dump)
                session.commit()

        click.echo("✅ Successfully imported hierarchy trees from dump")

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
    default=1000,
    help="Number of entities to process in each database batch (default: 1000)",
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

    click.echo(f"⏳ Importing supporting entities from dump file: {file}")

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
        import_entities(file, batch_size=batch_size)

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

        click.echo("✅ Successfully imported supporting entities from dump")

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
    default=1000,
    help="Number of entities to process in each database batch (default: 1000)",
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

    click.echo(f"⏳ Importing politicians from dump file: {file}")

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
        import_politicians(file, batch_size=batch_size)

        # Mark as imported
        if latest_dump is not None:
            latest_dump.imported_politicians_at = datetime.now(timezone.utc)
            with Session(get_engine()) as session:
                session.merge(latest_dump)
                session.commit()

        click.echo("✅ Successfully imported politicians from dump")

        # Suggest next steps
        click.echo()
        click.echo("💡 Next steps:")
        click.echo(
            "  • Run 'poliloom enrich-wikipedia --limit <amount>' to enrich politician data"
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


@main.command("garbage-collect")
def garbage_collect():
    """Garbage collect using two-dump validation strategy to safely soft-delete entities and statements."""

    click.echo("🗑️  Starting garbage collection with two-dump validation...")

    with Session(get_engine()) as session:
        try:
            # Get the latest 2 dumps for two-dump validation
            dumps = (
                session.query(WikidataDump)
                .order_by(WikidataDump.last_modified.desc())
                .limit(2)
                .all()
            )

            if not dumps:
                click.echo(
                    "❌ No dump found. Please import a dump before running garbage collection."
                )
                raise SystemExit(1)

            latest_dump = dumps[0]
            click.echo(
                f"📅 Latest dump timestamp: {latest_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )

            if len(dumps) < 2:
                click.echo(
                    "ℹ️  Only one dump found - skipping deletion for safety (first import)"
                )
                click.echo("   Items will only be deleted after next dump import")
                click.echo(
                    "✅ Garbage collection completed (no deletions - first import)"
                )
                return

            previous_dump = dumps[1]
            click.echo(
                f"📋 Previous dump timestamp: {previous_dump.last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )

            # Clean up missing entities
            click.echo("⏳ Cleaning up entities using two-dump validation...")
            entity_counts = CurrentImportEntity.cleanup_missing(
                session, previous_dump.last_modified
            )
            click.echo(
                f"  • Soft-deleted {entity_counts['entities_marked_deleted']} entities"
            )

            # Clean up missing statements
            click.echo("⏳ Cleaning up statements using two-dump validation...")
            statement_counts = CurrentImportStatement.cleanup_missing(
                session, previous_dump.last_modified
            )
            click.echo(
                f"  • Soft-deleted {statement_counts['properties_marked_deleted']} properties"
            )
            click.echo(
                f"  • Soft-deleted {statement_counts['relations_marked_deleted']} relations"
            )

            total_deleted = (
                entity_counts["entities_marked_deleted"]
                + statement_counts["properties_marked_deleted"]
                + statement_counts["relations_marked_deleted"]
            )

            click.echo("✅ Garbage collection completed successfully")
            click.echo(f"  • Total items soft-deleted: {total_deleted}")

        except Exception as e:
            click.echo(f"❌ Error during garbage collection: {e}")
            raise SystemExit(1)
        finally:
            # Clear tracking tables regardless of success/failure/early return
            click.echo("⏳ Clearing tracking tables...")
            CurrentImportEntity.clear_tracking_table(session)
            CurrentImportStatement.clear_tracking_table(session)
            session.commit()
            click.echo("  • Tracking tables cleared")


@main.command("clean-entities")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without making changes",
)
def clean_entities(dry_run):
    """Clean positions and locations outside current hierarchy definition.

    This command removes entities that don't match the hierarchy rules defined in
    importer/entity.py. It's useful after changing hierarchy definitions to clean up
    existing data.

    The same hierarchy logic as import_entities() is used:
    - Positions: Uses position_root_ids and ignore_ids
    - Locations: Uses location_root_ids

    Steps performed:
    1. Identify entities outside current hierarchy
    2. Soft-delete properties referencing removed entities
    3. Hard-delete entity records from specialized tables
    4. Hard-delete wikidata_entities only referenced by removed entities
    """
    from poliloom.models import WikidataEntity
    from sqlalchemy import text

    if dry_run:
        click.echo("🔍 DRY RUN MODE - No changes will be made")
    else:
        click.echo(
            "⚠️  This will soft-delete properties and hard-delete entity records outside the current hierarchy"
        )
        if not click.confirm("Do you want to continue?"):
            click.echo("Aborted.")
            return

    with Session(get_engine()) as session:
        try:
            # Load hierarchy configuration from WikidataEntity model
            click.echo(
                "⏳ Loading hierarchy definitions from WikidataEntity.HIERARCHY_CONFIG..."
            )
            config = WikidataEntity.HIERARCHY_CONFIG

            position_root_ids = config["position"]["roots"]
            position_ignore_ids = config["position"]["ignore"]
            location_root_ids = config["location"]["roots"]

            click.echo(f"  • Position roots: {len(position_root_ids)} IDs")
            click.echo(f"  • Position ignore: {len(position_ignore_ids)} IDs")
            click.echo(f"  • Location roots: {len(location_root_ids)} IDs")

            # Build hierarchy sets
            click.echo("⏳ Building hierarchy trees from database...")
            position_classes = WikidataEntity.query_hierarchy_descendants(
                session, position_root_ids, position_ignore_ids
            )
            location_classes = WikidataEntity.query_hierarchy_descendants(
                session, location_root_ids
            )
            click.echo(f"  • Valid position classes: {len(position_classes)}")
            click.echo(f"  • Valid location classes: {len(location_classes)}")

            # Clean positions
            click.echo("\n⏳ Identifying positions outside hierarchy...")
            positions_to_remove = _identify_positions_to_remove(
                session, position_root_ids, position_ignore_ids
            )
            click.echo(f"  • Found {len(positions_to_remove)} positions to remove")

            if positions_to_remove:
                if dry_run:
                    click.echo("  • [DRY RUN] Would soft-delete properties")
                    click.echo("  • [DRY RUN] Would hard-delete position records")
                else:
                    click.echo("  • Soft-deleting properties...")
                    props_deleted = session.execute(
                        text("""
                            UPDATE properties
                            SET deleted_at = NOW()
                            WHERE entity_id = ANY(:ids)
                              AND type = 'POSITION'
                              AND deleted_at IS NULL
                            RETURNING id
                        """),
                        {"ids": list(positions_to_remove)},
                    ).rowcount
                    click.echo(f"    → Soft-deleted {props_deleted} properties")

                    click.echo("  • Hard-deleting position records...")
                    pos_deleted = session.execute(
                        text("""
                            DELETE FROM positions
                            WHERE wikidata_id = ANY(:ids)
                        """),
                        {"ids": list(positions_to_remove)},
                    ).rowcount
                    click.echo(f"    → Hard-deleted {pos_deleted} position records")

            # Clean locations
            click.echo("\n⏳ Identifying locations outside hierarchy...")
            locations_to_remove = _identify_locations_to_remove(
                session, location_root_ids
            )
            click.echo(f"  • Found {len(locations_to_remove)} locations to remove")

            if locations_to_remove:
                if dry_run:
                    click.echo("  • [DRY RUN] Would soft-delete properties")
                    click.echo("  • [DRY RUN] Would hard-delete location records")
                else:
                    click.echo("  • Soft-deleting properties...")
                    props_deleted = session.execute(
                        text("""
                            UPDATE properties
                            SET deleted_at = NOW()
                            WHERE entity_id = ANY(:ids)
                              AND type = 'BIRTHPLACE'
                              AND deleted_at IS NULL
                            RETURNING id
                        """),
                        {"ids": list(locations_to_remove)},
                    ).rowcount
                    click.echo(f"    → Soft-deleted {props_deleted} properties")

                    click.echo("  • Hard-deleting location records...")
                    loc_deleted = session.execute(
                        text("""
                            DELETE FROM locations
                            WHERE wikidata_id = ANY(:ids)
                        """),
                        {"ids": list(locations_to_remove)},
                    ).rowcount
                    click.echo(f"    → Hard-deleted {loc_deleted} location records")

            # Clean orphaned wikidata_entities
            if positions_to_remove or locations_to_remove:
                click.echo("\n⏳ Cleaning orphaned wikidata_entities...")
                if dry_run:
                    click.echo("  • [DRY RUN] Would hard-delete orphaned entities")
                else:
                    orphans_deleted = _cleanup_orphaned_entities(session)
                    click.echo(f"  • Hard-deleted {orphans_deleted} orphaned entities")

            if not dry_run:
                session.commit()
                click.echo("\n✅ Clean-up completed successfully")
            else:
                click.echo("\n✅ Dry run completed - no changes made")

        except Exception as e:
            session.rollback()
            click.echo(f"\n❌ Error during cleanup: {e}")
            raise SystemExit(1)


def _identify_positions_to_remove(
    session: Session, root_ids: list[str], ignore_ids: list[str]
) -> set[str]:
    """Identify positions outside the current hierarchy."""
    from sqlalchemy import text

    result = session.execute(
        text("""
            WITH RECURSIVE descendants AS (
                -- Base case: start with the new root entities
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities
                WHERE wikidata_id = ANY(:root_ids)
                UNION
                -- Recursive case: find all children
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
                WHERE sr.relation_type = 'SUBCLASS_OF'
            ),
            ignored_branches AS (
                -- Base case: start with ignored root entities
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities
                WHERE wikidata_id = ANY(:ignore_ids)
                UNION
                -- Recursive case: find all descendants of ignored branches
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN ignored_branches ib ON sr.parent_entity_id = ib.wikidata_id
                WHERE sr.relation_type = 'SUBCLASS_OF'
            )
            SELECT p.wikidata_id
            FROM positions p
            WHERE (
                -- Not in the valid hierarchy
                NOT EXISTS (
                    SELECT 1 FROM wikidata_relations wr
                    JOIN descendants d ON wr.parent_entity_id = d.wikidata_id
                    WHERE wr.child_entity_id = p.wikidata_id
                       AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
                )
                -- OR in the ignored branches
                OR EXISTS (
                    SELECT 1 FROM wikidata_relations wr
                    JOIN ignored_branches ib ON wr.parent_entity_id = ib.wikidata_id
                    WHERE wr.child_entity_id = p.wikidata_id
                       AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
                )
            )
        """),
        {"root_ids": root_ids, "ignore_ids": ignore_ids},
    )
    return {row[0] for row in result.fetchall()}


def _identify_locations_to_remove(session: Session, root_ids: list[str]) -> set[str]:
    """Identify locations outside the current hierarchy."""
    from sqlalchemy import text

    result = session.execute(
        text("""
            WITH RECURSIVE descendants AS (
                -- Base case: start with the new root entities
                SELECT CAST(wikidata_id AS VARCHAR) AS wikidata_id
                FROM wikidata_entities
                WHERE wikidata_id = ANY(:root_ids)
                UNION
                -- Recursive case: find all children
                SELECT sr.child_entity_id AS wikidata_id
                FROM wikidata_relations sr
                JOIN descendants d ON sr.parent_entity_id = d.wikidata_id
                WHERE sr.relation_type = 'SUBCLASS_OF'
            )
            SELECT l.wikidata_id
            FROM locations l
            WHERE NOT EXISTS (
                SELECT 1 FROM wikidata_relations wr
                JOIN descendants d ON wr.parent_entity_id = d.wikidata_id
                WHERE wr.child_entity_id = l.wikidata_id
                   AND wr.relation_type IN ('INSTANCE_OF', 'SUBCLASS_OF')
            )
        """),
        {"root_ids": root_ids},
    )
    return {row[0] for row in result.fetchall()}


def _cleanup_orphaned_entities(session: Session) -> int:
    """Hard-delete wikidata_entities that are only referenced by removed entities."""
    from sqlalchemy import text

    # Build temp table of entities to keep
    session.execute(text("CREATE TEMP TABLE entities_to_keep (wikidata_id VARCHAR)"))

    # Insert from each entity table
    session.execute(
        text("INSERT INTO entities_to_keep SELECT wikidata_id FROM politicians")
    )
    session.execute(
        text("INSERT INTO entities_to_keep SELECT wikidata_id FROM locations")
    )
    session.execute(
        text("INSERT INTO entities_to_keep SELECT wikidata_id FROM positions")
    )
    session.execute(
        text("INSERT INTO entities_to_keep SELECT wikidata_id FROM countries")
    )
    session.execute(
        text("INSERT INTO entities_to_keep SELECT wikidata_id FROM languages")
    )

    # Keep entities referenced by properties
    session.execute(
        text("""
        INSERT INTO entities_to_keep
        SELECT DISTINCT entity_id
        FROM properties
        WHERE entity_id IS NOT NULL
    """)
    )

    # Keep parent entities from relations
    session.execute(
        text("""
        INSERT INTO entities_to_keep
        SELECT DISTINCT parent_entity_id
        FROM wikidata_relations
        WHERE child_entity_id IN (
            SELECT wikidata_id FROM politicians
            UNION ALL
            SELECT wikidata_id FROM locations
            UNION ALL
            SELECT wikidata_id FROM positions
            UNION ALL
            SELECT wikidata_id FROM countries
            UNION ALL
            SELECT wikidata_id FROM languages
        )
    """)
    )

    # Create index
    session.execute(
        text("CREATE INDEX idx_temp_entities_to_keep ON entities_to_keep(wikidata_id)")
    )

    # Delete entities not in keep list
    result = session.execute(
        text("""
        DELETE FROM wikidata_entities
        WHERE NOT EXISTS (
            SELECT 1 FROM entities_to_keep
            WHERE entities_to_keep.wikidata_id = wikidata_entities.wikidata_id
        )
    """)
    )

    # Clean up temp table
    session.execute(text("DROP TABLE entities_to_keep"))

    return result.rowcount


if __name__ == "__main__":
    main()
