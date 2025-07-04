"""Main CLI interface for PoliLoom."""

import click
import logging
import uvicorn
import httpx
from pathlib import Path
from tqdm import tqdm
from ..services.import_service import ImportService
from ..services.enrichment_service import EnrichmentService

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
def database():
    """Commands for database operations."""
    pass


@database.command("truncate")
@click.option("--all", is_flag=True, help="Truncate all tables")
@click.option("--table", multiple=True, help="Specific table(s) to truncate")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
def database_truncate(all, table, yes):
    """Truncate database tables while preserving schema."""
    from ..database import SessionLocal, engine
    from ..models import Base
    from sqlalchemy import text

    # Get all table names from metadata
    all_tables = [t.name for t in Base.metadata.sorted_tables]

    # Determine which tables to truncate
    if all:
        tables_to_truncate = all_tables
    elif table:
        # Validate table names
        invalid_tables = [t for t in table if t not in all_tables]
        if invalid_tables:
            click.echo(f"❌ Invalid table names: {', '.join(invalid_tables)}")
            click.echo(f"Available tables: {', '.join(all_tables)}")
            exit(1)
        tables_to_truncate = list(table)
    else:
        click.echo("❌ Please specify --all or --table <name> to truncate")
        click.echo(f"Available tables: {', '.join(all_tables)}")
        exit(1)

    # Show what will be truncated
    click.echo("⚠️  WARNING: This will DELETE ALL DATA from the following tables:")
    for t in tables_to_truncate:
        click.echo(f"  • {t}")

    # Confirm unless --yes was provided
    if not yes:
        if not click.confirm("\nAre you sure you want to proceed?"):
            click.echo("❌ Truncate operation cancelled")
            exit(0)

    session = None
    try:
        session = SessionLocal()

        # Disable foreign key checks temporarily
        with engine.connect() as conn:
            conn.execute(text("SET session_replication_role = 'replica';"))
            conn.commit()

            # Truncate tables in reverse dependency order
            for table_name in reversed(tables_to_truncate):
                click.echo(f"Truncating {table_name}...")
                conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE;"))
                conn.commit()

            # Re-enable foreign key checks
            conn.execute(text("SET session_replication_role = 'origin';"))
            conn.commit()

        click.echo("✅ Successfully truncated all specified tables")

    except Exception as e:
        click.echo(f"❌ Error truncating tables: {e}")
        exit(1)
    finally:
        if session:
            session.close()


@main.group()
def dump():
    """Commands for managing Wikidata dumps."""
    pass


@dump.command("download")
@click.option(
    "--output",
    default="./latest-all.json.gz",
    help="Local path to save the dump file (default: ./latest-all.json.gz)",
)
@click.option(
    "--url",
    default="https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.gz",
    help="Custom dump URL (default: https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.gz)",
)
def dump_download(output, url):
    """Download the latest Wikidata dump to disk for offline processing."""
    click.echo(f"Downloading Wikidata dump from: {url}")
    click.echo(f"Output path: {output}")
    
    # Create output directory if it doesn't exist
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Check if file already exists
        if output_path.exists():
            if not click.confirm(f"File {output} already exists. Overwrite?"):
                click.echo("Download cancelled.")
                return
        
        # Simple download with httpx and tqdm for progress tracking
        click.echo("Starting download...")
        
        with httpx.stream("GET", url, timeout=300) as response:
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            if total_size > 0:
                click.echo(f"Total file size: {total_size / (1024**3):.2f} GB")
            
            with open(output_path, 'wb') as f:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc="Downloading"
                ) as pbar:
                    for chunk in response.iter_bytes(chunk_size=1024*1024):  # 1MB chunks
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        # Verify file was downloaded successfully
        if output_path.exists() and output_path.stat().st_size > 0:
            file_size = output_path.stat().st_size
            click.echo(f"✅ Successfully downloaded {file_size / (1024**3):.2f} GB to {output}")
        else:
            click.echo("❌ Download failed - file is empty or missing")
            if output_path.exists():
                output_path.unlink()  # Remove empty file
            exit(1)
            
    except httpx.RequestError as e:
        click.echo(f"❌ Download failed: {e}")
        if output_path.exists():
            output_path.unlink()  # Remove partial file
        exit(1)
    except KeyboardInterrupt:
        click.echo("\n❌ Download cancelled by user")
        if output_path.exists():
            output_path.unlink()  # Remove partial file
        exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}")
        if output_path.exists():
            output_path.unlink()  # Remove partial file
        exit(1)


@politicians.command("import")
@click.option("--id", "wikidata_id", required=True, help="Wikidata ID (e.g., Q123456)")
def politicians_import(wikidata_id):
    """Import a single politician entity from Wikidata based on its ID."""
    click.echo(f"Importing politician from Wikidata ID: {wikidata_id}")

    import_service = ImportService()

    try:
        politician_id = import_service.import_politician_by_id(wikidata_id)

        if politician_id:
            click.echo(
                f"✅ Successfully imported politician with database ID: {politician_id}"
            )
        else:
            click.echo("❌ Failed to import politician. Check the logs for details.")
            exit(1)

    except Exception as e:
        click.echo(f"❌ Error importing politician: {e}")
        exit(1)

    finally:
        import_service.close()


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
        success = enrichment_service.enrich_politician_from_wikipedia(wikidata_id)

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

    from ..database import SessionLocal
    from ..models import Politician, Property, HoldsPosition, HasCitizenship, BornAt
    from sqlalchemy.orm import joinedload

    session = None
    try:
        session = SessionLocal()
        # Query politician with all related data
        politician = (
            session.query(Politician)
            .filter(Politician.wikidata_id == wikidata_id)
            .options(
                joinedload(Politician.properties).joinedload(Property.sources),
                joinedload(Politician.positions_held).joinedload(
                    HoldsPosition.position
                ),
                joinedload(Politician.positions_held).joinedload(HoldsPosition.sources),
                joinedload(Politician.citizenships).joinedload(HasCitizenship.country),
                joinedload(Politician.birthplaces).joinedload(BornAt.location),
                joinedload(Politician.birthplaces).joinedload(BornAt.sources),
                joinedload(Politician.sources),
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
                    status = "✅ CONFIRMED" if prop.confirmed_by else "⏳ PENDING"
                    if prop.confirmed_by:
                        status += f" by {prop.confirmed_by} on {prop.confirmed_at.strftime('%Y-%m-%d')}"

                    click.echo(f"    • {prop.type}: {prop.value} [{status}]")

                    # Show sources
                    if prop.sources:
                        for source in prop.sources:
                            click.echo(f"      📖 Source: {source.url}")

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
                    status = "✅ CONFIRMED" if birthplace.confirmed_by else "⏳ PENDING"
                    if birthplace.confirmed_by:
                        status += f" by {birthplace.confirmed_by} on {birthplace.confirmed_at.strftime('%Y-%m-%d')}"

                    location_info = f"{birthplace.location.name}"
                    if birthplace.location.wikidata_id:
                        location_info += f" [{birthplace.location.wikidata_id}]"

                    click.echo(f"    • {location_info} [{status}]")

                    # Show sources
                    if birthplace.sources:
                        for source in birthplace.sources:
                            click.echo(f"      📖 Source: {source.url}")

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
                    status = "✅ CONFIRMED" if pos.confirmed_by else "⏳ PENDING"
                    if pos.confirmed_by:
                        status += f" by {pos.confirmed_by} on {pos.confirmed_at.strftime('%Y-%m-%d')}"

                    date_info = ""
                    if pos.start_date or pos.end_date:
                        start = pos.start_date or "?"
                        end = pos.end_date or "present"
                        date_info = f" ({start} - {end})"

                    position_info = f"{pos.position.name}{date_info}"
                    if pos.position.wikidata_id:
                        position_info += f" [{pos.position.wikidata_id}]"

                    click.echo(f"    • {position_info} [{status}]")

                    # Show sources
                    if pos.sources:
                        for source in pos.sources:
                            click.echo(f"      📖 Source: {source.url}")

        click.echo()
        click.echo("=" * 80)

    except Exception as e:
        click.echo(f"❌ Error showing politician information: {e}")
        exit(1)
    finally:
        if session:
            session.close()


@positions.command("import")
def positions_import():
    """Import all political positions from Wikidata to populate the local Position table."""
    click.echo("Importing all political positions from Wikidata...")

    import_service = ImportService()

    try:
        count = import_service.import_all_positions()

        if count > 0:
            click.echo(f"✅ Successfully imported {count} political positions")
        else:
            click.echo("❌ Failed to import positions. Check the logs for details.")
            exit(1)

    except Exception as e:
        click.echo(f"❌ Error importing positions: {e}")
        exit(1)

    finally:
        import_service.close()


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


@positions.command("embed")
def positions_embed():
    """Generate embeddings for all positions that don't have embeddings yet."""
    click.echo("Generating embeddings for positions without embeddings...")

    from ..database import SessionLocal
    from ..models import Position
    from ..embeddings import generate_embeddings

    session = None
    try:
        session = SessionLocal()

        # Get all positions without embeddings
        positions_without_embeddings = (
            session.query(Position).filter(Position.embedding.is_(None)).all()
        )

        if not positions_without_embeddings:
            click.echo("✅ All positions already have embeddings")
            return

        count = len(positions_without_embeddings)
        click.echo(f"Found {count} positions without embeddings")

        # Extract names for batch processing
        names = [pos.name for pos in positions_without_embeddings]

        # Generate embeddings
        click.echo("Generating embeddings...")
        embeddings = generate_embeddings(names)

        # Update positions with embeddings
        for position, embedding in zip(positions_without_embeddings, embeddings):
            position.embedding = embedding

        session.commit()
        click.echo(f"✅ Successfully generated embeddings for {count} positions")

    except Exception as e:
        if session:
            session.rollback()
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)
    finally:
        if session:
            session.close()


@locations.command("import")
def locations_import():
    """Import all geographic locations from Wikidata to populate the local Location table."""
    click.echo("Importing all geographic locations from Wikidata...")

    import_service = ImportService()

    try:
        count = import_service.import_all_locations()

        if count > 0:
            click.echo(f"✅ Successfully imported {count} geographic locations")
        else:
            click.echo("❌ Failed to import locations. Check the logs for details.")
            exit(1)

    except Exception as e:
        click.echo(f"❌ Error importing locations: {e}")
        exit(1)

    finally:
        import_service.close()


@locations.command("embed")
def locations_embed():
    """Generate embeddings for all locations that don't have embeddings yet."""
    click.echo("Generating embeddings for locations without embeddings...")

    from ..database import SessionLocal
    from ..models import Location
    from ..embeddings import generate_embeddings

    session = None
    try:
        session = SessionLocal()

        # Get all locations without embeddings
        locations_without_embeddings = (
            session.query(Location).filter(Location.embedding.is_(None)).all()
        )

        if not locations_without_embeddings:
            click.echo("✅ All locations already have embeddings")
            return

        count = len(locations_without_embeddings)
        click.echo(f"Found {count} locations without embeddings")

        # Extract names for batch processing
        names = [loc.name for loc in locations_without_embeddings]

        # Generate embeddings
        click.echo("Generating embeddings...")
        embeddings = generate_embeddings(names)

        # Update locations with embeddings
        for location, embedding in zip(locations_without_embeddings, embeddings):
            location.embedding = embedding

        session.commit()
        click.echo(f"✅ Successfully generated embeddings for {count} locations")

    except Exception as e:
        if session:
            session.rollback()
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)
    finally:
        if session:
            session.close()


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
