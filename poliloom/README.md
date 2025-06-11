# PoliLoom

PoliLoom is a tool for extracting politician metadata from Wikipedia and other web sources to enrich Wikidata. It provides both a CLI interface and API for managing politician data extraction and confirmation workflows.

## Overview

This project helps identify and extract missing or incomplete information about politicians from various web sources, using Large Language Models (LLMs) for structured data extraction. The goal is to create a usable proof of concept for enriching Wikidata with verified politician information.

## Features

### Current Functionality

- **Wikidata Import**: Import politician data directly from Wikidata by ID
- **Data Storage**: Local database storage using SQLAlchemy with SQLite (dev) or PostgreSQL (prod)
- **Data Validation**: Automatic validation that entities are human and politician-related
- **Duplicate Handling**: Prevents duplicate imports of the same politician

### Planned Features

- **Wikipedia Enrichment**: Extract additional properties from Wikipedia articles
- **Web Source Processing**: Process random web pages for politician information
- **Confirmation Workflow**: API endpoints for human validation of extracted data
- **Wikidata Updates**: Push confirmed data back to Wikidata

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
# Clone the repository
git clone <repository-url>
cd poliloom

# Install dependencies
uv sync

# Set up the database
uv run alembic upgrade head
```

## Usage

### CLI Commands

#### Import from Wikidata

Import a politician's data from Wikidata using their entity ID:

```bash
# Import Joe Biden (Q6279)
uv run poliloom import-wikidata --id Q6279

# Import with verbose logging
uv run poliloom -v import-wikidata --id Q6279
```

The command will:
1. Fetch the politician's data from Wikidata
2. Validate they are a human and politician
3. Extract properties (birth date, birth place, etc.)
4. Extract political positions and their dates
5. Store everything in the local database
6. Link to Wikipedia sources

### Database Schema

The project uses a relational database with the following main entities:

- **Politician**: Core politician information (name, country, Wikidata ID)
- **Property**: Individual properties like birth date, birth place
- **Position**: Political positions (President, Senator, etc.)
- **HoldsPosition**: Relationship between politicians and positions with dates
- **Source**: Web sources where data was extracted from

## Development

### Database Migrations

Create a new migration after model changes:

```bash
uv run alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

### Code Quality

The project uses:
- **Black** for code formatting
- **Ruff** for linting

```bash
# Format code
uv run black .

# Lint code
uv run ruff check .
```

## Configuration

The project uses environment variables for configuration:

- `DATABASE_URL`: Database connection string (default: `sqlite:///./poliloom.db`)

## Architecture

- **CLI**: Click-based command-line interface
- **API**: FastAPI-based REST API (planned)
- **Database**: SQLAlchemy ORM with Alembic migrations
- **External APIs**: Wikidata API, OpenAI API (planned)
- **Authentication**: MediaWiki OAuth (planned)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure tests pass and code is properly formatted
5. Submit a pull request

## License

[License information to be added]