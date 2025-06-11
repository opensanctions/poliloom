"""Main CLI interface for PoliLoom."""

import click
import logging
from ..services.import_service import ImportService

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


if __name__ == '__main__':
    main()