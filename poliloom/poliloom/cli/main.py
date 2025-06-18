"""Main CLI interface for PoliLoom."""

import click
import logging
import uvicorn
from ..services.import_service import ImportService
from ..services.enrichment_service import EnrichmentService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def main(verbose):
    """PoliLoom CLI - Extract politician metadata from Wikipedia and web sources."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@main.command('import-wikidata')
@click.option('--id', 'wikidata_id', required=True, help='Wikidata ID (e.g., Q123456)')
def import_wikidata(wikidata_id):
    """Import a single politician entity from Wikidata based on its ID."""
    click.echo(f"Importing politician from Wikidata ID: {wikidata_id}")
    
    import_service = ImportService()
    
    try:
        politician_id = import_service.import_politician_by_id(wikidata_id)
        
        if politician_id:
            click.echo(f"✅ Successfully imported politician with database ID: {politician_id}")
        else:
            click.echo("❌ Failed to import politician. Check the logs for details.")
            exit(1)
    
    except Exception as e:
        click.echo(f"❌ Error importing politician: {e}")
        exit(1)
    
    finally:
        import_service.close()



@main.command('import-positions')
def import_positions():
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


@main.command('import-positions-extra')
@click.option('--file', 'csv_file', required=True, help='Path to CSV file containing positions data')
def import_positions_extra(csv_file):
    """Import political positions from a custom CSV file."""
    click.echo(f"Importing political positions from CSV file: {csv_file}")
    
    import_service = ImportService()
    
    try:
        count = import_service.import_positions_from_csv(csv_file)
        
        if count > 0:
            click.echo(f"✅ Successfully imported {count} political positions from CSV")
        else:
            click.echo("❌ Failed to import positions from CSV. Check the logs for details.")
            exit(1)
    
    except Exception as e:
        click.echo(f"❌ Error importing positions from CSV: {e}")
        exit(1)
    
    finally:
        import_service.close()


@main.command('enrich-wikipedia')
@click.option('--id', 'wikidata_id', required=True, help='Wikidata ID of politician to enrich (e.g., Q123456)')
def enrich_wikipedia(wikidata_id):
    """Enrich a politician entity by extracting data from its linked Wikipedia articles."""
    click.echo(f"Enriching politician with Wikidata ID: {wikidata_id}")
    
    enrichment_service = EnrichmentService()
    
    try:
        success = enrichment_service.enrich_politician_from_wikipedia(wikidata_id)
        
        if success:
            click.echo("✅ Successfully enriched politician data from Wikipedia sources")
        else:
            click.echo("❌ Failed to enrich politician. Check the logs for details.")
            exit(1)
    
    except Exception as e:
        click.echo(f"❌ Error enriching politician: {e}")
        exit(1)
    
    finally:
        enrichment_service.close()


@main.command('serve')
@click.option('--host', default='0.0.0.0', help='Host to bind the server to')
@click.option('--port', default=8000, help='Port to bind the server to')
@click.option('--reload', is_flag=True, help='Enable auto-reload for development')
def serve(host, port, reload):
    """Start the FastAPI web server."""
    
    click.echo(f"Starting PoliLoom API server on http://{host}:{port}")
    if reload:
        click.echo("Auto-reload enabled for development")
    
    uvicorn.run(
        "poliloom.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == '__main__':
    main()