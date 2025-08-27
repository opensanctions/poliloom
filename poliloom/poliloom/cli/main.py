"""Main CLI interface for PoliLoom."""

import asyncio
import subprocess
import click
import logging
import uvicorn
from sqlalchemy.orm import joinedload

from ..services.import_service import ImportService
from ..services.enrichment_service import EnrichmentService
from ..services.storage import StorageFactory
from ..services.dump_processor import WikidataDumpProcessor
from ..services.hierarchy_builder import HierarchyBuilder
from ..database import get_db_session, get_db_session_no_commit
from ..models import (
    Politician,
    HoldsPosition,
    HasCitizenship,
    BornAt,
    Position,
    Location,
    SubclassRelation,
)
from ..embeddings import generate_embeddings_for_entities

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(verbose):
    """PoliLoom CLI - Extract politician metadata from Wikipedia and web sources."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@main.group()
def politicians():
    """Commands for managing politicians."""
    pass


@main.group()
def positions():
    """Commands for managing political positions."""
    pass


@main.group()
def locations():
    """Commands for managing geographic locations."""
    pass


@main.group()
def dump():
    """Commands for Wikidata dump processing."""
    pass


@dump.command("download")
@click.option(
    "--output",
    required=True,
    help="Output path - local filesystem path or GCS path (gs://bucket/path)",
)
def dump_download(output):
    """Download latest Wikidata dump from Wikidata to specified location."""
    url = "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"

    click.echo(f"Downloading Wikidata dump from {url} to {output}...")
    click.echo("This is a large file (~100GB compressed) and may take several hours.")

    try:
        StorageFactory.download_from_url(url, output)
        click.echo(f"✅ Successfully downloaded dump to {output}")
    except Exception as e:
        click.echo(f"❌ Download failed: {e}")
        raise SystemExit(1)


@dump.command("extract")
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
    click.echo(f"Extracting {input} to {output}...")

    # Check if source exists
    backend = StorageFactory.get_backend(input)
    if not backend.exists(input):
        click.echo(f"❌ Source file not found: {input}")
        click.echo("Run 'poliloom dump download' first")
        raise SystemExit(1)

    # Check for lbzip2 (required for parallel decompression)
    if subprocess.run(["which", "lbzip2"], capture_output=True).returncode != 0:
        click.echo("❌ lbzip2 not found. Please install lbzip2:")
        click.echo("  On Ubuntu/Debian: sudo apt-get install lbzip2")
        click.echo("  On macOS: brew install lbzip2")
        raise SystemExit(1)

    try:
        click.echo("⏳ Extracting dump file...")
        click.echo("This will produce a file ~10x larger than the compressed version.")

        StorageFactory.extract_bz2(input, output, use_parallel=True)
        click.echo(f"✅ Successfully extracted dump to {output}")
    except Exception as e:
        click.echo(f"❌ Extraction failed: {e}")
        raise SystemExit(1)


@politicians.command("enrich")
@click.option(
    "--id",
    "wikidata_id",
    required=True,
    help="Wikidata ID of politician to enrich (e.g., Q123456)",
)
def politicians_enrich(wikidata_id):
    """Enrich a politician entity by extracting data from its linked Wikipedia articles."""
    click.echo(f"Enriching politician with Wikidata ID: {wikidata_id}")

    enrichment_service = EnrichmentService()

    try:
        success = asyncio.run(
            enrichment_service.enrich_politician_from_wikipedia(wikidata_id)
        )

        if success:
            click.echo(
                "✅ Successfully enriched politician data from Wikipedia sources"
            )
        else:
            click.echo("❌ Failed to enrich politician. Check the logs for details.")
            exit(1)

    except Exception as e:
        click.echo(f"❌ Error enriching politician: {e}")
        exit(1)

    finally:
        enrichment_service.close()


@politicians.command("show")
@click.option(
    "--id",
    "wikidata_id",
    required=True,
    help="Wikidata ID of politician to show (e.g., Q123456)",
)
def politicians_show(wikidata_id):
    """Display comprehensive information about a politician, distinguishing between imported and generated data."""
    click.echo(f"Showing information for politician with Wikidata ID: {wikidata_id}")

    try:
        with get_db_session_no_commit() as session:
            # Query politician with all related data
            politician = (
                session.query(Politician)
                .filter(Politician.wikidata_id == wikidata_id)
                .options(
                    joinedload(Politician.properties),
                    joinedload(Politician.positions_held).joinedload(
                        HoldsPosition.position
                    ),
                    joinedload(Politician.citizenships).joinedload(
                        HasCitizenship.country
                    ),
                    joinedload(Politician.birthplaces).joinedload(BornAt.location),
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


@positions.command("embed")
@click.option(
    "--batch-size", default=100000, help="Number of positions to process in each batch"
)
def positions_embed(batch_size):
    """Generate embeddings for all positions that don't have embeddings yet."""
    click.echo("Generating embeddings for positions without embeddings...")

    try:
        with get_db_session() as session:
            generate_embeddings_for_entities(
                session=session,
                model_class=Position,
                entity_name="positions",
                batch_size=batch_size,
                progress_callback=click.echo,
            )

    except Exception as e:
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)


@positions.command("import-csv")
@click.option(
    "--file",
    "csv_file",
    required=True,
    help="Path to CSV file containing positions data",
)
def positions_import_csv(csv_file):
    """Import political positions from a custom CSV file."""
    click.echo(f"Importing political positions from CSV file: {csv_file}")

    import_service = ImportService()

    try:
        count = import_service.import_positions_from_csv(csv_file)

        if count > 0:
            click.echo(f"✅ Successfully imported {count} political positions from CSV")
        else:
            click.echo(
                "❌ Failed to import positions from CSV. Check the logs for details."
            )
            exit(1)

    except Exception as e:
        click.echo(f"❌ Error importing positions from CSV: {e}")
        exit(1)

    finally:
        import_service.close()


@locations.command("embed")
@click.option(
    "--batch-size", default=100000, help="Number of locations to process in each batch"
)
def locations_embed(batch_size):
    """Generate embeddings for all locations that don't have embeddings yet."""
    click.echo("Generating embeddings for locations without embeddings...")

    try:
        with get_db_session() as session:
            generate_embeddings_for_entities(
                session=session,
                model_class=Location,
                entity_name="locations",
                batch_size=batch_size,
                progress_callback=click.echo,
            )

    except Exception as e:
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)


@dump.command("build-hierarchy")
@click.option(
    "--file",
    required=True,
    help="Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)",
)
def dump_build_hierarchy(file):
    """Build hierarchy trees for positions and locations from Wikidata dump."""
    click.echo(f"Building hierarchy trees from dump file: {file}")

    # Check if dump file exists using storage backend
    backend = StorageFactory.get_backend(file)
    if not backend.exists(file):
        click.echo(f"❌ Dump file not found: {file}")
        click.echo(
            "Please run 'poliloom dump download' and 'poliloom dump extract' first"
        )
        raise SystemExit(1)

    processor = WikidataDumpProcessor()

    try:
        click.echo("⏳ Extracting P279 (subclass of) relationships...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Build the trees (always parallel)
        trees = processor.build_hierarchy_trees(file)

        click.echo("✅ Successfully built hierarchy trees:")
        click.echo(
            f"  • Positions: {len(trees['positions'])} descendants of Q294414 (public office)"
        )
        click.echo(
            f"  • Locations: {len(trees['locations'])} descendants of Q2221906 (geographic location)"
        )
        click.echo("Complete hierarchy saved to database")
    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user. Cleaning up...")
        click.echo("❌ Hierarchy tree building was cancelled.")
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error building hierarchy trees: {e}")
        raise SystemExit(1)


@dump.command("import-entities")
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
    click.echo(f"Importing supporting entities from dump file: {file}")
    click.echo(f"Using batch size: {batch_size}")

    # Check if dump file exists using storage backend
    backend = StorageFactory.get_backend(file)
    if not backend.exists(file):
        click.echo(f"❌ Dump file not found: {file}")
        click.echo(
            "Please run 'poliloom dump download' and 'poliloom dump extract' first"
        )
        raise SystemExit(1)

    # Check if hierarchy data exists in database
    try:
        with get_db_session_no_commit() as session:
            hierarchy_builder = HierarchyBuilder()
            subclass_relations = hierarchy_builder.load_complete_hierarchy(session)
            if subclass_relations is None:
                click.echo("❌ Complete hierarchy not found in database!")
                click.echo(
                    "Run 'poliloom dump build-hierarchy' first to generate the hierarchy trees."
                )
                raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error checking hierarchy data: {e}")
        raise SystemExit(1)

    processor = WikidataDumpProcessor()

    try:
        click.echo("⏳ Extracting supporting entities from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Extract supporting entities only
        counts = processor.extract_entities_from_dump(file, batch_size=batch_size)

        click.echo("✅ Successfully imported supporting entities from dump:")
        click.echo(f"  • Positions: {counts['positions']}")
        click.echo(f"  • Locations: {counts['locations']}")
        click.echo(f"  • Countries: {counts['countries']}")
        click.echo(f"  • Total: {sum(counts.values())}")

        # Suggest next steps
        click.echo()
        click.echo("💡 Next steps:")
        click.echo("  • Run 'poliloom dump import-politicians' to import politicians")
        click.echo("  • Run 'poliloom positions embed' to generate position embeddings")
        click.echo("  • Run 'poliloom locations embed' to generate location embeddings")
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


@dump.command("import-politicians")
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
    click.echo(f"Importing politicians from dump file: {file}")
    click.echo(f"Using batch size: {batch_size}")

    # Check if dump file exists using storage backend
    backend = StorageFactory.get_backend(file)
    if not backend.exists(file):
        click.echo(f"❌ Dump file not found: {file}")
        click.echo(
            "Please run 'poliloom dump download' and 'poliloom dump extract' first"
        )
        raise SystemExit(1)

    processor = WikidataDumpProcessor()

    try:
        click.echo("⏳ Extracting politicians from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Extract politicians only
        counts = processor.extract_politicians_from_dump(file, batch_size=batch_size)

        click.echo("✅ Successfully imported politicians from dump:")
        click.echo(f"  • Politicians: {counts['politicians']}")

        # Suggest next steps
        click.echo()
        click.echo("💡 Next steps:")
        click.echo(
            "  • Run 'poliloom politicians enrich --id <wikidata_id>' to enrich politician data"
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


@dump.command("query-hierarchy")
@click.option(
    "--entity-id",
    required=True,
    help="Wikidata entity ID to get descendants for (e.g., Q2221906)",
)
def dump_query_hierarchy(entity_id):
    """Query hierarchy descendants for a given entity ID."""

    try:
        # Check if hierarchy data exists in database and query descendants directly
        with get_db_session_no_commit() as session:
            hierarchy_builder = HierarchyBuilder()

            # Check if hierarchy data exists (efficient count check)
            relation_count = session.query(SubclassRelation).count()

            if relation_count == 0:
                click.echo("❌ No hierarchy data found in database!")
                click.echo(
                    "Run 'poliloom dump build-hierarchy' first to generate the hierarchy."
                )
                exit(1)

            # Get all descendants of the given entity using direct database query
            descendants = hierarchy_builder.query_descendants(entity_id, session)

            # Output one entity ID per line
            for descendant in sorted(descendants):
                click.echo(descendant)

    except Exception as e:
        click.echo(f"❌ Error querying hierarchy: {e}")
        exit(1)


@main.command("serve")
@click.option("--host", default="0.0.0.0", help="Host to bind the server to")
@click.option("--port", default=8000, help="Port to bind the server to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host, port, reload):
    """Start the FastAPI web server."""

    click.echo(f"Starting PoliLoom API server on http://{host}:{port}")
    if reload:
        click.echo("Auto-reload enabled for development")

    uvicorn.run(
        "poliloom.api.app:app", host=host, port=port, reload=reload, log_level="info"
    )


if __name__ == "__main__":
    main()
