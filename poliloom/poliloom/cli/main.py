"""Main CLI interface for PoliLoom."""

import click
import logging
import uvicorn
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
def dump():
    """Commands for Wikidata dump processing."""
    pass


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
@click.option(
    "--batch-size", default=100000, help="Number of positions to process in each batch"
)
def positions_embed(batch_size):
    """Generate embeddings for all positions that don't have embeddings yet."""
    click.echo("Generating embeddings for positions without embeddings...")

    from ..database import SessionLocal
    from ..models import Position
    from ..embeddings import generate_embeddings

    session = None
    try:
        session = SessionLocal()

        # Get total count of positions without embeddings
        total_count = (
            session.query(Position).filter(Position.embedding.is_(None)).count()
        )

        if total_count == 0:
            click.echo("✅ All positions already have embeddings")
            return

        click.echo(f"Found {total_count} positions without embeddings")
        click.echo(f"Processing in batches of {batch_size}")

        processed_count = 0
        offset = 0

        while offset < total_count:
            # Load batch of positions
            batch_positions = (
                session.query(Position)
                .filter(Position.embedding.is_(None))
                .offset(offset)
                .limit(batch_size)
                .all()
            )

            if not batch_positions:
                break

            # Extract names for this batch
            names = [pos.name for pos in batch_positions]

            # Generate embeddings for this batch
            embeddings = generate_embeddings(names)

            # Update positions with embeddings
            for position, embedding in zip(batch_positions, embeddings):
                position.embedding = embedding

            # Commit this batch
            session.commit()

            # Update progress
            batch_size_actual = len(batch_positions)
            processed_count += batch_size_actual
            offset += batch_size
            click.echo(f"Processed {processed_count}/{total_count} positions")

        click.echo(
            f"✅ Successfully generated embeddings for {processed_count} positions"
        )

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
@click.option(
    "--batch-size", default=100000, help="Number of locations to process in each batch"
)
def locations_embed(batch_size):
    """Generate embeddings for all locations that don't have embeddings yet."""
    click.echo("Generating embeddings for locations without embeddings...")

    from ..database import SessionLocal
    from ..models import Location
    from ..embeddings import generate_embeddings

    session = None
    try:
        session = SessionLocal()

        # Get total count of locations without embeddings
        total_count = (
            session.query(Location).filter(Location.embedding.is_(None)).count()
        )

        if total_count == 0:
            click.echo("✅ All locations already have embeddings")
            return

        click.echo(f"Found {total_count} locations without embeddings")
        click.echo(f"Processing in batches of {batch_size}")

        processed_count = 0
        offset = 0

        while offset < total_count:
            # Load batch of locations
            batch_locations = (
                session.query(Location)
                .filter(Location.embedding.is_(None))
                .offset(offset)
                .limit(batch_size)
                .all()
            )

            if not batch_locations:
                break

            # Extract names for this batch
            names = [loc.name for loc in batch_locations]

            # Generate embeddings for this batch
            embeddings = generate_embeddings(names)

            # Update locations with embeddings
            for location, embedding in zip(batch_locations, embeddings):
                location.embedding = embedding

            # Commit this batch
            session.commit()

            # Update progress
            batch_size_actual = len(batch_locations)
            processed_count += batch_size_actual
            offset += batch_size
            click.echo(f"Processed {processed_count}/{total_count} locations")

        click.echo(
            f"✅ Successfully generated embeddings for {processed_count} locations"
        )

    except Exception as e:
        if session:
            session.rollback()
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)
    finally:
        if session:
            session.close()


@dump.command("build-hierarchy")
@click.option(
    "--file",
    "dump_file",
    help="Path to the extracted JSON dump file",
    envvar="WIKIDATA_DUMP_JSON_PATH",
    default="./latest-all.json",
)
@click.option(
    "--workers",
    "num_workers",
    type=int,
    help="Number of worker processes (default: CPU count)",
)
def dump_build_hierarchy(dump_file, num_workers):
    """Build hierarchy trees for positions and locations from Wikidata dump."""
    click.echo(f"Building hierarchy trees from dump file: {dump_file}")

    import os
    from ..services.dump_processor import WikidataDumpProcessor

    # Check if dump file exists
    if not os.path.exists(dump_file):
        click.echo(f"❌ Dump file not found: {dump_file}")
        click.echo(
            "Please run 'make download-wikidata-dump' and 'make extract-wikidata-dump' first"
        )
        exit(1)

    processor = WikidataDumpProcessor()

    try:
        click.echo("⏳ Extracting P279 (subclass of) relationships...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Build the trees (always parallel)
        trees = processor.build_hierarchy_trees(dump_file, num_workers=num_workers)

        click.echo("✅ Successfully built hierarchy trees:")
        click.echo(
            f"  • Positions: {len(trees['positions'])} descendants of Q294414 (public office)"
        )
        click.echo(
            f"  • Locations: {len(trees['locations'])} descendants of Q2221906 (geographic location)"
        )
        click.echo("Complete hierarchy saved to complete_hierarchy.json")

    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user. Cleaning up...")
        click.echo("❌ Hierarchy tree building was cancelled.")
        exit(1)
    except Exception as e:
        click.echo(f"❌ Error building hierarchy trees: {e}")
        exit(1)


@dump.command("import")
@click.option(
    "--file",
    "dump_file",
    help="Path to the extracted JSON dump file",
    envvar="WIKIDATA_DUMP_JSON_PATH",
    default="./latest-all.json",
)
@click.option(
    "--batch-size",
    "batch_size",
    type=int,
    default=1000,
    help="Number of entities to process in each database batch (default: 1000)",
)
@click.option(
    "--workers",
    "num_workers",
    type=int,
    help="Number of worker processes (default: CPU count)",
)
def dump_import(dump_file, batch_size, num_workers):
    """Import positions, locations, countries, and politicians from a Wikidata dump file."""
    click.echo(f"Importing entities from dump file: {dump_file}")
    click.echo(f"Using batch size: {batch_size}")

    import os
    from ..services.dump_processor import WikidataDumpProcessor

    # Check if dump file exists
    if not os.path.exists(dump_file):
        click.echo(f"❌ Dump file not found: {dump_file}")
        click.echo(
            "Please run 'make download-wikidata-dump' and 'make extract-wikidata-dump' first"
        )
        exit(1)

    # Check if hierarchy trees exist
    if not os.path.exists("complete_hierarchy.json"):
        click.echo("❌ Complete hierarchy not found!")
        click.echo(
            "Run 'poliloom dump build-hierarchy' first to generate the hierarchy trees."
        )
        exit(1)

    processor = WikidataDumpProcessor()

    try:
        click.echo("⏳ Extracting entities from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Extract entities
        counts = processor.extract_entities_from_dump(
            dump_file, batch_size=batch_size, num_workers=num_workers
        )

        click.echo("✅ Successfully imported entities from dump:")
        click.echo(f"  • Positions: {counts['positions']}")
        click.echo(f"  • Locations: {counts['locations']}")
        click.echo(f"  • Countries: {counts['countries']}")
        click.echo(f"  • Politicians: {counts['politicians']}")
        click.echo(f"  • Total: {sum(counts.values())}")

        # Suggest next steps
        click.echo()
        click.echo("💡 Next steps:")
        click.echo("  • Run 'poliloom positions embed' to generate position embeddings")
        click.echo("  • Run 'poliloom locations embed' to generate location embeddings")

    except KeyboardInterrupt:
        click.echo("\n⚠️  Process interrupted by user. Cleaning up...")
        click.echo("❌ Entity import was cancelled.")
        click.echo(
            "⚠️  Note: Some entities may have been partially imported to the database."
        )
        exit(1)
    except Exception as e:
        click.echo(f"❌ Error importing entities: {e}")
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
