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
    from ..models import Politician, HoldsPosition, HasCitizenship, BornAt
    from sqlalchemy.orm import joinedload

    session = None
    try:
        session = SessionLocal()
        # Query politician with all related data
        politician = (
            session.query(Politician)
            .filter(Politician.wikidata_id == wikidata_id)
            .options(
                joinedload(Politician.properties),
                joinedload(Politician.positions_held).joinedload(
                    HoldsPosition.position
                ),
                joinedload(Politician.citizenships).joinedload(HasCitizenship.country),
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
                    status = "✅ CONFIRMED" if prop.confirmed_by else "⏳ PENDING"
                    if prop.confirmed_by:
                        status += f" by {prop.confirmed_by} on {prop.confirmed_at.strftime('%Y-%m-%d')}"

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
                    status = "✅ CONFIRMED" if birthplace.confirmed_by else "⏳ PENDING"
                    if birthplace.confirmed_by:
                        status += f" by {birthplace.confirmed_by} on {birthplace.confirmed_at.strftime('%Y-%m-%d')}"

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

        click.echo()
        click.echo("=" * 80)

    except Exception as e:
        click.echo(f"❌ Error showing politician information: {e}")
        exit(1)
    finally:
        if session:
            session.close()


@positions.command("embed")
@click.option(
    "--batch-size", default=100000, help="Number of positions to process in each batch"
)
def positions_embed(batch_size):
    """Generate embeddings for all positions that don't have embeddings yet."""
    click.echo("Generating embeddings for positions without embeddings...")

    from ..database import SessionLocal
    from ..models import Position
    from ..embeddings import generate_embeddings_for_entities

    session = None
    try:
        session = SessionLocal()
        generate_embeddings_for_entities(
            session=session,
            model_class=Position,
            entity_name="positions",
            batch_size=batch_size,
            progress_callback=click.echo,
        )

    except Exception as e:
        if session:
            session.rollback()
        click.echo(f"❌ Error generating embeddings: {e}")
        exit(1)
    finally:
        if session:
            session.close()


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

    from ..database import SessionLocal
    from ..models import Location
    from ..embeddings import generate_embeddings_for_entities

    session = None
    try:
        session = SessionLocal()
        generate_embeddings_for_entities(
            session=session,
            model_class=Location,
            entity_name="locations",
            batch_size=batch_size,
            progress_callback=click.echo,
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


@dump.command("import-entities")
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
def dump_import_entities(dump_file, batch_size, num_workers):
    """Import supporting entities (positions, locations, countries) from a Wikidata dump file."""
    click.echo(f"Importing supporting entities from dump file: {dump_file}")
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
        click.echo("⏳ Extracting supporting entities from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Extract supporting entities only
        counts = processor.extract_entities_from_dump(
            dump_file, batch_size=batch_size, num_workers=num_workers
        )

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
        exit(1)
    except Exception as e:
        click.echo(f"❌ Error importing supporting entities: {e}")
        exit(1)


@dump.command("import-politicians")
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
def dump_import_politicians(dump_file, batch_size, num_workers):
    """Import politicians from a Wikidata dump file, linking them to existing entities."""
    click.echo(f"Importing politicians from dump file: {dump_file}")
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
        click.echo("⏳ Extracting politicians from dump...")
        click.echo("This may take a while for the full dump...")
        click.echo("Press Ctrl+C to interrupt...")

        # Extract politicians only
        counts = processor.extract_politicians_from_dump(
            dump_file, batch_size=batch_size, num_workers=num_workers
        )

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
        exit(1)
    except Exception as e:
        click.echo(f"❌ Error importing politicians: {e}")
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
