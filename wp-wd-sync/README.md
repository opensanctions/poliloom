# WP-WD-Sync

A Python tool that extracts birth information from Wikipedia pages linked to Wikidata items.

## Features

- Fetches Wikipedia pages linked to a Wikidata item
- Parses Wikipedia page content using mwparserfromhell
- Extracts birth date and place information from infoboxes
- Returns structured data about the person's birth information

## Installation

```bash
pip install wp-wd-sync
```

## Usage

```bash
wp-wd-sync --wikidata-id Q12345
```

## Development

This project uses Hatch for development. To set up the development environment:

```bash
pip install hatch
hatch shell
```

## License

MIT 