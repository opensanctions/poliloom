"""Main CLI interface for PoliLoom."""

import asyncio
import click
import logging
import os
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
from sqlalchemy import exists, func, select
from poliloom.models import (
    Country,
    CurrentImportEntity,
    CurrentImportStatement,
    DownloadAlreadyCompleteError,
    DownloadInProgressError,
    Evaluation,
    Language,
    Location,
    Position,
    Property,
    PropertyReference,
    WikidataDump,
    WikidataEntity,
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

        # Prepare dump record (handles stale detection, force mode, etc.)
        with Session(get_engine()) as session:
            try:
                new_dump = WikidataDump.prepare_for_download(
                    session, url, last_modified, force=force
                )
                session.commit()

                if force:
                    click.echo(
                        f"⚠️  Forcing new download for dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                    )
                else:
                    click.echo(
                        f"📝 New dump found from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC"
                    )

            except DownloadAlreadyCompleteError:
                click.echo(
                    f"❌ Dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already downloaded"
                )
                click.echo("No new dump available. Use --force to download anyway.")
                raise SystemExit(1)

            except DownloadInProgressError as e:
                click.echo(
                    f"❌ Download for dump from {last_modified.strftime('%Y-%m-%d %H:%M:%S')} UTC already in progress"
                )
                click.echo(
                    f"   Started {e.hours_elapsed:.1f}h ago. Use --force to start new download."
                )
                raise SystemExit(1)

        # Download the file
        click.echo(f"⏳ Downloading Wikidata dump to {output}...")
        click.echo(
            "This is a large file (~100GB compressed) and may take several hours."
        )

        try:
            StorageFactory.download_from_url(url, output)

            # Mark as downloaded
            with Session(get_engine()) as session:
                new_dump.mark_downloaded(session)
                session.commit()

            click.echo(f"✅ Successfully downloaded dump to {output}")

        except Exception as download_error:
            # Clean up the dump record on failure to allow retries
            click.echo(f"❌ Download failed: {download_error}")
            click.echo("   Cleaning up dump record to allow retry...")
            with Session(get_engine()) as session:
                new_dump.cleanup_failed_download(session)
                session.commit()
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"❌ Error: {e}")
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
    default=None,
    help="Number of politicians to enrich (default: ENRICHMENT_BATCH_SIZE env var, or 5)",
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
@click.option(
    "--stateless",
    is_flag=True,
    help="Only enrich politicians without citizenship data (for bias prevention)",
)
def enrich_wikipedia(
    count: int | None,
    languages: tuple[str, ...],
    countries: tuple[str, ...],
    stateless: bool,
) -> None:
    """Enrich a specified number of politicians from Wikipedia.

    This command enriches politicians by extracting data from their Wikipedia articles.

    The --stateless flag addresses a systematic bias where politicians without citizenship
    data are never enriched by normal user-driven filters (which filter by country/language).
    Use this flag for scheduled enrichment jobs to ensure coverage of all politicians.

    When using --stateless, enrichment only runs if the number of stateless politicians
    with unevaluated extracted citizenship is below MIN_UNEVALUATED_POLITICIANS threshold
    (default: 10). This prevents over-enrichment when reviewers haven't caught up.

    Examples:
    - poliloom enrich-wikipedia --count 20
    - poliloom enrich-wikipedia --count 10 --countries Q30 --countries Q38
    - poliloom enrich-wikipedia --count 5 --languages Q1860 --languages Q150
    - poliloom enrich-wikipedia --stateless
    """
    try:
        # Default count from env var
        if count is None:
            count = int(os.getenv("ENRICHMENT_BATCH_SIZE", "5"))
        # Convert tuples to lists (or None if empty)
        languages_list = list(languages) if languages else None
        countries_list = list(countries) if countries else None

        # Stateless mode is mutually exclusive with language/country filters
        if stateless and (languages_list or countries_list):
            click.echo(
                "❌ --stateless cannot be combined with --languages or --countries"
            )
            raise SystemExit(1)

        # For stateless mode, check if we already have enough unevaluated citizenship
        if stateless:
            min_threshold = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
            from poliloom.models import Politician

            with Session(get_engine()) as db:
                current_count = Politician.count_stateless_with_unevaluated_citizenship(
                    db
                )

            click.echo(
                f"   Stateless politicians with unevaluated citizenship: {current_count}"
            )
            if current_count >= min_threshold:
                click.echo(
                    f"✅ Buffer sufficient (>= {min_threshold}), skipping enrichment"
                )
                return

            click.echo(
                f"   Buffer below threshold ({min_threshold}), proceeding with enrichment"
            )

        click.echo(f"⏳ Enriching {count} politicians...")
        if stateless:
            click.echo("   Mode: stateless (politicians without citizenship data)")
        if languages_list:
            click.echo(f"   Filtering by languages: {', '.join(languages_list)}")
        if countries_list:
            click.echo(f"   Filtering by countries: {', '.join(countries_list)}")

        enriched_count = 0
        for i in range(count):
            politician_found = asyncio.run(
                enrich_politician_from_wikipedia(
                    languages=languages_list,
                    countries=countries_list,
                    stateless=stateless,
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

        # Import supporting entities with Meilisearch indexing
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

            # Clean up missing entities (also removes from search index)
            click.echo("⏳ Cleaning up entities using two-dump validation...")
            deleted_entity_count = CurrentImportEntity.cleanup_missing(
                session, previous_dump.last_modified
            )
            click.echo(f"  • Soft-deleted {deleted_entity_count} entities")

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
                deleted_entity_count
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


# Entity classes to clean, in order
_ENTITY_CLASSES = [Position, Location, Country, Language]


@main.command("clean-entities")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without making changes",
)
def clean_entities(dry_run):
    """Clean entities outside current hierarchy definition.

    This command removes positions, locations, countries, and languages that don't
    match the hierarchy rules defined in each entity class (_hierarchy_roots and
    _hierarchy_ignore). It's useful after changing hierarchy definitions to clean
    up existing data.

    Entity types cleaned:
    - Positions: Uses position roots and ignore lists
    - Locations: Uses location roots
    - Countries: Uses country roots and ignore lists
    - Languages: Uses language roots

    Steps performed:
    1. Identify entities outside current hierarchy
    2. Soft-delete properties referencing removed entities (POSITION, BIRTHPLACE, CITIZENSHIP)
    3. Hard-delete entity records from specialized tables
    4. Hard-delete wikidata_entities only referenced by removed entities
    """
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
            # Process each entity type
            any_removed = False
            for entity_cls in _ENTITY_CLASSES:
                name = entity_cls.__tablename__
                click.echo(f"⏳ Identifying {name} outside hierarchy...")

                stats = entity_cls.cleanup_outside_hierarchy(session, dry_run=dry_run)
                total = stats["total_entities"]
                removed = stats["entities_removed"]
                props = stats["properties_deleted"]
                props_total = stats["properties_total"]
                props_extracted = stats["properties_extracted"]
                props_evaluated = stats["properties_evaluated"]
                pct = (removed / total * 100) if total else 0

                click.echo(f"  • Found {removed}/{total} {name} to remove ({pct:.1f}%)")

                if removed > 0:
                    any_removed = True
                    if dry_run:
                        if props:
                            pct_props = (
                                (props / props_total * 100) if props_total else 0
                            )
                            click.echo(
                                f"  • [DRY RUN] Would soft-delete {props}/{props_total} properties ({pct_props:.1f}%) - {props_extracted} extracted, {props_evaluated} with evaluations"
                            )
                        click.echo(
                            f"  • [DRY RUN] Would hard-delete {removed} {name} records"
                        )
                    else:
                        if props:
                            click.echo(f"    → Soft-deleted {props} properties")
                        click.echo(f"    → Hard-deleted {removed} {name} records")

            # Clean orphaned wikidata_entities
            if any_removed:
                click.echo("⏳ Cleaning orphaned wikidata_entities...")
                if dry_run:
                    click.echo("  • [DRY RUN] Would clean orphaned wikidata_entities")
                else:
                    orphans_deleted = WikidataEntity.cleanup_orphaned(session)
                    click.echo(f"  • Hard-deleted {orphans_deleted} orphaned entities")

            if not dry_run:
                session.commit()
                click.echo("\n✅ Clean-up completed successfully")
                if any_removed:
                    click.echo(
                        "\n⚠️ Run 'poliloom dump build-trees' to rebuild the hierarchy."
                    )
            else:
                click.echo("\n✅ Dry run completed - no changes made")

        except Exception as e:
            session.rollback()
            click.echo(f"\n❌ Error during cleanup: {e}")
            raise SystemExit(1)


@main.command("clean-properties")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview what would be deleted without making changes",
)
def clean_properties(dry_run):
    """Delete all unevaluated extracted properties.

    This command removes properties that:
    - Were extracted from web sources (archived_page_id IS NOT NULL)
    - Have not been evaluated/pushed to Wikidata (statement_id IS NULL)
    - Are not already soft-deleted (deleted_at IS NULL)

    This is useful for clearing extracted data that needs to be re-extracted
    with different extraction parameters or when changing enrichment strategies.
    """
    if dry_run:
        click.echo("🔍 DRY RUN MODE - No changes will be made")
    else:
        click.echo(
            "⚠️  This will permanently delete all unevaluated extracted properties"
        )
        if not click.confirm("Do you want to continue?"):
            click.echo("Aborted.")
            return

    with Session(get_engine()) as session:
        try:
            # NOT EXISTS check for evaluations
            has_evaluation = exists().where(Evaluation.property_id == Property.id)

            # Count unevaluated extracted properties without evaluations
            count_query = (
                session.query(Property)
                .filter(
                    Property.id.in_(
                        select(PropertyReference.property_id).distinct()
                    ),  # Extracted from web source
                    Property.statement_id.is_(None),  # Not yet pushed to Wikidata
                    Property.deleted_at.is_(None),  # Not already deleted
                    ~has_evaluation,  # No evaluations attached
                )
                .count()
            )

            if count_query == 0:
                click.echo("✅ No unevaluated extracted properties found")
                return

            click.echo(f"Found {count_query} unevaluated extracted properties")

            if dry_run:
                click.echo(
                    f"  • [DRY RUN] Would delete {count_query} unevaluated extracted properties"
                )
                # Count affected politicians
                affected_politicians = (
                    session.query(Property.politician_id)
                    .filter(
                        Property.id.in_(
                            select(PropertyReference.property_id).distinct()
                        ),
                        Property.statement_id.is_(None),
                        Property.deleted_at.is_(None),
                        ~has_evaluation,
                    )
                    .distinct()
                    .count()
                )
                click.echo(
                    f"  • [DRY RUN] Would clear enriched_at for {affected_politicians} politicians"
                )
            else:
                from poliloom.models import Politician

                # Get affected politician IDs before deleting properties
                affected_politician_ids = [
                    row[0]
                    for row in session.query(Property.politician_id)
                    .filter(
                        Property.id.in_(
                            select(PropertyReference.property_id).distinct()
                        ),
                        Property.statement_id.is_(None),
                        Property.deleted_at.is_(None),
                        ~has_evaluation,
                    )
                    .distinct()
                    .all()
                ]

                # Delete properties without evaluations
                deleted_count = (
                    session.query(Property)
                    .filter(
                        Property.id.in_(
                            select(PropertyReference.property_id).distinct()
                        ),  # Extracted from web source
                        Property.statement_id.is_(None),  # Not yet pushed to Wikidata
                        Property.deleted_at.is_(None),  # Not already deleted
                        ~has_evaluation,  # No evaluations attached
                    )
                    .delete(synchronize_session=False)
                )

                # Clear enriched_at for affected politicians
                cleared_count = (
                    session.query(Politician)
                    .filter(Politician.id.in_(affected_politician_ids))
                    .update({Politician.enriched_at: None}, synchronize_session=False)
                )

                session.commit()
                click.echo(
                    f"✅ Successfully deleted {deleted_count} unevaluated extracted properties"
                )
                click.echo(f"✅ Cleared enriched_at for {cleared_count} politicians")

        except Exception as e:
            session.rollback()
            click.echo(f"❌ Error during cleanup: {e}")
            raise SystemExit(1)


@main.command("index-create")
def index_create():
    """Create the Meilisearch entities index.

    Creates a single index with type-based filtering for all searchable entities.
    Safe to run multiple times - Meilisearch handles existing indexes gracefully.
    """
    from poliloom.search import SearchService, INDEX_NAME

    click.echo("⏳ Creating Meilisearch index...")

    search_service = SearchService()

    try:
        search_service.create_index()
        click.echo(f"✅ Successfully created index '{INDEX_NAME}'")
    except Exception as e:
        if "index_already_exists" in str(e):
            click.echo(f"⚠️  Index '{INDEX_NAME}' already exists")
        else:
            click.echo(f"❌ Error creating index: {e}")
            raise SystemExit(1)


@main.command("index-delete")
@click.option(
    "--confirm",
    is_flag=True,
    help="Confirm deletion without prompting",
)
def index_delete(confirm):
    """Delete the Meilisearch entities index.

    Removes the single entities index containing all searchable data.
    Use --confirm to skip the confirmation prompt.
    """
    from poliloom.search import SearchService, INDEX_NAME

    if not confirm:
        click.echo("⚠️  This will delete the Meilisearch index!")
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Aborted.")
            return

    click.echo("⏳ Deleting Meilisearch index...")

    search_service = SearchService()
    search_service.delete_index()
    click.echo(f"✅ Successfully deleted index '{INDEX_NAME}'")


@main.command("index-build")
@click.option(
    "--batch-size",
    default=50000,
    help="Number of documents to index per batch (10k-50k recommended)",
)
@click.option(
    "--rebuild",
    is_flag=True,
    help="Delete and recreate index before indexing",
)
def index_build(batch_size, rebuild):
    """Build Meilisearch index from database.

    Indexes all searchable entities with aggregated types. Each entity appears
    once with all its types (e.g., an entity can be both Location and Country).

    Use --rebuild to delete and recreate the index from scratch.
    """
    from poliloom.search import INDEX_NAME, SearchDocument, SearchService

    search_service = SearchService()

    if rebuild:
        click.echo("⏳ Rebuilding Meilisearch index...")
        search_service.delete_index()
        search_service.create_index()
        click.echo(f"   Recreated index '{INDEX_NAME}'")
    else:
        click.echo("⏳ Building Meilisearch index...")
        if search_service.ensure_index():
            click.echo(f"   Created index '{INDEX_NAME}'")

    # Build query for search index documents
    query = WikidataEntity.search_index_query()

    total_indexed = 0
    task_uids = []

    with Session(get_engine()) as session:
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = session.execute(count_query).scalar()

        if total == 0:
            click.echo("   No entities to index")
            return

        click.echo(f"   Found {total:,} entities to index")

        # Process in batches
        offset_val = 0
        while offset_val < total:
            paginated_query = query.offset(offset_val).limit(batch_size)
            rows = session.execute(paginated_query).fetchall()

            if not rows:
                break

            # Build search documents
            documents = [
                SearchDocument(
                    id=row.wikidata_id, types=list(row.types), labels=list(row.labels)
                )
                for row in rows
            ]

            # Send batch without waiting (enables Meilisearch auto-batching)
            task_uid = search_service.index_documents(documents)
            if task_uid is not None:
                task_uids.append(task_uid)

            total_indexed += len(documents)
            offset_val += batch_size

            click.echo(f"   Sent: {total_indexed:,}/{total:,}")

    click.echo(
        f"✅ Sent {total_indexed:,} documents for indexing ({len(task_uids)} tasks)"
    )
    click.echo(
        "   Indexing continues in the background. Use 'poliloom index-stats' to check progress."
    )


@main.command("index-stats")
def index_stats():
    """Show Meilisearch index status and task progress.

    Displays document counts, indexing progress, and any failed tasks.
    Useful for monitoring background indexing after index-build.
    """

    from poliloom.search import INDEX_NAME, SearchService

    search_service = SearchService()

    # Check server health
    try:
        health = search_service.client.health()
        click.echo(f"🟢 Meilisearch: {health['status']}")
    except Exception as e:
        click.echo(f"🔴 Meilisearch: unavailable ({e})")
        return

    # Get index stats
    try:
        index = search_service.client.index(INDEX_NAME)
        stats = index.get_stats()
        click.echo(f"\n📊 Index '{INDEX_NAME}':")
        click.echo(f"   Documents: {stats.number_of_documents:,}")
        click.echo(f"   Indexing: {'yes' if stats.is_indexing else 'no'}")
    except Exception as e:
        click.echo(f"\n📊 Index '{INDEX_NAME}': not found or error ({e})")

    # Get batch counts by status
    click.echo("\n📋 Batches:")
    icons = {"succeeded": "✅", "processing": "⏳", "enqueued": "📥", "failed": "❌"}
    for status in ["processing", "enqueued", "succeeded", "failed"]:
        try:
            batches = search_service.client.get_batches(
                {"statuses": [status], "limit": 10}
            )
        except Exception:
            continue

        count = batches.total
        if count == 0 or count is None:
            continue

        click.echo(f"   {icons.get(status, '•')} {status}: {count}")

        # Show details for processing batch
        if status == "processing" and batches.results:
            batch = batches.results[0]
            progress = batch.progress or {}
            pct = progress.get("percentage", 0)
            details = batch.details or {}
            docs = details.get("receivedDocuments", 0)
            click.echo(
                f"      └─ Batch {batch.uid}: {docs:,} docs, {pct:.1f}% complete"
            )

            # Show current step
            steps = progress.get("steps", [])
            if steps:
                step = steps[-1]
                name = step.get("currentStep", "?")
                finished = step.get("finished", 0)
                total = step.get("total", 0)
                click.echo(f"      └─ {name}: {finished:,}/{total:,}")

            # Show embedder stats
            stats = batch.stats or {}
            embedder = stats.get("embedderRequests", {})
            if embedder and embedder.get("total", 0) > 0:
                click.echo(
                    f"      └─ Embedder: {embedder['total']:,} requests "
                    f"({embedder.get('failed', 0)} failed)"
                )

        # Show failed batch errors
        if status == "failed" and batches.results:
            for batch in batches.results[:3]:
                stats = batch.stats or {}
                types = list(stats.get("types", {}).keys())
                click.echo(
                    f"      └─ Batch {batch.uid}: {', '.join(types) or 'unknown'}"
                )


if __name__ == "__main__":
    main()
