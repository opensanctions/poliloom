# PoliLoom

PoliLoom is a tool for extracting politician metadata from Wikipedia and other web sources to enrich Wikidata. It provides both a CLI interface and API for managing politician data extraction and confirmation workflows.

## Overview

This project helps identify and extract missing or incomplete information about politicians from various web sources, using Large Language Models (LLMs) for structured data extraction. The goal is to create a usable proof of concept for enriching Wikidata with verified politician information.

## Features

### Current Functionality

- **Wikidata Import**: Import politician data directly from Wikidata by ID
- **Political Positions**: Import and manage political positions from Wikidata or CSV files
- **Data Enrichment**: Extract additional properties from Wikipedia articles using LLMs with two-stage extraction strategy
- **Vector Search**: Semantic similarity search for positions and locations using SentenceTransformers with pgvector
- **GPU Acceleration**: Embedding generation leverages GPU when available for improved performance
- **Data Storage**: Local database storage using SQLAlchemy with PostgreSQL
- **Data Validation**: Automatic validation that entities are human and politician-related
- **Duplicate Handling**: Prevents duplicate imports of the same politician
- **FastAPI Server**: Web server with API endpoints for confirmation workflows
- **MediaWiki OAuth**: Authentication system for user validation

### Planned Features

- **Web Source Processing**: Process random web pages for politician information
- **Wikidata Updates**: Push confirmed data back to Wikidata

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
# Clone the repository
git clone <repository-url>
cd poliloom

# Install system dependencies
# For parallel bzip2 decompression (required for Wikidata dump processing):
# On Ubuntu/Debian: sudo apt-get install lbzip2
# On macOS: brew install lbzip2

# Install dependencies
uv sync

# Start PostgreSQL using Docker Compose
docker-compose up -d postgres

# Set up the database
uv run alembic upgrade head
```

## Usage

### CLI Commands

#### Politicians Commands

**Import from Wikidata**

Import a politician's data from Wikidata using their entity ID:

```bash
# Import Joe Biden (Q6279)
uv run poliloom politicians import --id Q6279

# Import with verbose logging
uv run poliloom -v politicians import --id Q6279
```

**Enrich politician data**

Extract additional data from Wikipedia using LLMs:

```bash
# Enrich Joe Biden's data from Wikipedia
uv run poliloom politicians enrich --id Q6279
```

**Display politician information**

Show comprehensive information about a politician:

```bash
# Show all data for Joe Biden
uv run poliloom politicians show --id Q6279
```

#### Positions Commands

**Import political positions from Wikidata**

```bash
# Import all political positions from Wikidata
uv run poliloom positions import
```

**Import positions from CSV**

```bash
# Import positions from a custom CSV file
uv run poliloom positions import-csv --file positions.csv
```

**Generate embeddings for positions**

```bash
# Generate embeddings for all positions without embeddings (uses GPU if available)
uv run poliloom positions embed
```

#### Locations Commands

**Import geographic locations from Wikidata**

```bash
# Import all geographic locations from Wikidata
uv run poliloom locations import
```

**Generate embeddings for locations**

```bash
# Generate embeddings for all locations without embeddings (uses GPU if available)
uv run poliloom locations embed
```

#### Database Commands

**Truncate database tables**

```bash
# Truncate all tables (with confirmation)
uv run poliloom database truncate --all

# Truncate specific table
uv run poliloom database truncate --table politicians

# Skip confirmation prompt
uv run poliloom database truncate --all --yes
```

#### Server Commands

**Start the FastAPI web server**

```bash
# Start server on default host/port
uv run poliloom serve

# Start with custom host and port
uv run poliloom serve --host 0.0.0.0 --port 8080

# Start in development mode with auto-reload
uv run poliloom serve --reload
```

### Database Schema

The project uses a relational database with the following main entities:

- **Politician**: Core politician information (name, Wikidata ID)
- **Property**: Individual properties like birth date, birth place with confirmation status
- **Position**: Political positions (President, Senator, etc.) with embeddings for similarity search
- **Location**: Geographic locations (cities, regions, countries) with embeddings for similarity search
- **HoldsPosition**: Relationship between politicians and positions with dates and confirmation status
- **Country**: Countries with ISO codes and Wikidata IDs
- **HasCitizenship**: Many-to-many relationship between politicians and countries
- **PositionCountry**: Many-to-many relationship between positions and countries
- **Source**: Web sources where data was extracted from

The schema supports:
- Incomplete dates (stored as strings)
- Multilingual names
- Multiple citizenships
- Confirmation workflows with user tracking
- Vector embeddings for semantic search (generated separately from import using dedicated commands)
- Two-stage extraction strategy for positions and birthplaces to handle large datasets efficiently

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

The project uses **Ruff** for both linting and code formatting with pre-commit hooks:

```bash
# Lint and format code (runs automatically via pre-commit)
uv run ruff check --fix .
uv run ruff format .

# Install pre-commit hooks (runs ruff automatically on commit)
uv run pre-commit install
```

## Configuration

The project uses environment variables for configuration:

- `DATABASE_URL`: Database connection string (default: `postgresql://postgres:postgres@localhost:5432/poliloom`)
- `OPENAI_API_KEY`: OpenAI API key for LLM-based data extraction
- MediaWiki OAuth settings for authentication (see CLAUDE.md for details)

### API Endpoints

The FastAPI server provides the following endpoints:

- **GET /politicians/unconfirmed**: Retrieve politicians with unconfirmed extracted data
- **POST /politicians/{politician_id}/confirm**: Confirm or discard extracted properties and positions

### Testing

The project includes comprehensive testing using pytest with PostgreSQL:

```bash
# Start test database
docker-compose up -d postgres_test

# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=poliloom
```

Tests cover:
- Database models and relationships
- Wikidata import functionality (with mocked API calls)
- LLM extraction (with mocked OpenAI responses)
- API endpoints with authentication
- Error handling and edge cases

## Architecture

- **CLI**: Click-based command-line interface with structured subcommands
- **API**: FastAPI-based REST API with MediaWiki OAuth authentication
- **Database**: SQLAlchemy ORM with Alembic migrations
- **Vector Search**: SentenceTransformers with 'all-MiniLM-L6-v2' model and pgvector for position similarity
- **External APIs**: Wikidata API, OpenAI API for structured data extraction
- **Authentication**: MediaWiki OAuth for user validation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Ensure tests pass and code is properly formatted
5. Submit a pull request
