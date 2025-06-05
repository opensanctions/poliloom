"""Command-line interface for the wp-wd-sync tool."""

import click
from typing import Optional
from wp_wd_sync.wikidata import Item
from wp_wd_sync.wikipedia import Page
from wp_wd_sync.parse import parse_page


@click.command()
@click.option(
    "--wikidata-id",
    required=True,
    help="Wikidata item ID (e.g., Q12345)",
    type=str,
)
@click.option(
    "--output",
    "-o",
    help="Output file path (default: stdout)",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
)
def main(wikidata_id: str, output: Optional[str]) -> None:
    """Extract birth information from Wikipedia pages linked to a Wikidata item."""
    if not wikidata_id.startswith("Q"):
        raise click.BadParameter("Wikidata ID must start with 'Q'")
    
    click.echo(f"Fetching data for Wikidata item: {wikidata_id}")
    item = Item.fetch(wikidata_id)
    
    click.echo("\nWikipedia pages:")
    for sitelink in item.sitelinks.values():
        # click.echo(f"\nFetching {sitelink.site}: {sitelink.title}")
        try:
            page = Page.fetch(sitelink.title, site=sitelink.site)
            if page is None:
                # click.echo(f"Skipping site: {sitelink.site}")
                continue
                
            click.echo(f"Page ID: {page.pageid}")
            click.echo(f"Page URL: {page.get_url()}")
            
            # Parse the page content
            parsed_data = parse_page(page.get_content())
            if parsed_data:
                if 'birth_date' in parsed_data:
                    click.echo(f"Birth Date: {parsed_data['birth_date']}")
                if 'birth_place' in parsed_data:
                    click.echo(f"Birth Place: {parsed_data['birth_place']}")
            else:
                click.echo("No birth information found in infobox")
                
            click.echo(f"Summary: {page.get_summary()[:200]}...")
            
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)


if __name__ == "__main__":
    main() 