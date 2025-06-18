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
    from ..models import Politician, Property, HoldsPosition, HasCitizenship
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
        click.echo(f"Wikidata Link: https://www.wikidata.org/wiki/{politician.wikidata_id}")
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
