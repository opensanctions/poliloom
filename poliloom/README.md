# PoliLoom

PoliLoom is a Python API and CLI tool for extracting politician metadata from Wikipedia and other web sources to enrich Wikidata. It processes Wikidata dumps to build a local database and uses Large Language Models to extract missing politician information.

## Technology Stack

- **Python** with **uv** for dependency management
- **Click** CLI framework and **FastAPI** web framework
- **SQLAlchemy** ORM with **PostgreSQL** database
- **OpenAI API** for structured data extraction
- **SentenceTransformers** with **pgvector** for vector search
- **MediaWiki OAuth 2.0** for authentication

## Installation

```bash
# Clone and set up the project
git clone <repository-url>
cd poliloom
uv sync

# Start PostgreSQL
docker-compose up -d postgres

# Set up database
uv run alembic upgrade head

# Install system dependencies for dump processing
# Ubuntu/Debian: sudo apt-get install lbzip2
# macOS: brew install lbzip2
```

## Quick Start

PoliLoom uses a three-pass strategy to process Wikidata dumps:

```bash
# 1. Download and extract Wikidata dump (one-time setup)
make download-wikidata-dump  # Downloads ~100GB compressed dump
make extract-wikidata-dump   # Extracts to ~1TB JSON file

# 2. Build hierarchy trees (required once per dump)
uv run poliloom dump build-hierarchy

# 3. Import entities in order
uv run poliloom dump import-entities     # Import positions, locations, countries
uv run poliloom dump import-politicians  # Import politicians linking to entities

# 4. Generate embeddings for vector search
uv run poliloom positions embed
uv run poliloom locations embed

# 5. Enrich politician data using LLMs
uv run poliloom politicians enrich --id Q6279

# 6. Start API server
uv run poliloom serve
```

## CLI Commands

### Dump Processing

- `poliloom dump build-hierarchy [--file FILE] [--workers NUM]` - Build position/location hierarchy trees
- `poliloom dump import-entities [--file FILE] [--batch-size SIZE]` - Import supporting entities
- `poliloom dump import-politicians [--file FILE] [--batch-size SIZE]` - Import politicians

### Data Management

- `poliloom politicians enrich --id <wikidata_id>` - Enrich politician using LLMs
- `poliloom politicians show --id <wikidata_id>` - Display politician information
- `poliloom positions embed` - Generate position embeddings
- `poliloom locations embed` - Generate location embeddings
- `poliloom positions import-csv` - Import positions from CSV

### Server

- `poliloom serve [--host HOST] [--port PORT] [--reload]` - Start FastAPI server

## Core Features

### Three-Pass Dump Processing
1. **Build Hierarchy Trees** - Extract entity relationships for efficient filtering
2. **Import Supporting Entities** - Import positions, locations, and countries first
3. **Import Politicians** - Link politicians to existing entities to prevent deadlocks

### LLM-Based Data Extraction
- **Two-stage extraction** for positions and birthplaces to handle large datasets
- **Stage 1**: Free-form extraction from Wikipedia content
- **Stage 2**: Vector similarity search + OpenAI mapping to Wikidata entities

### Vector Search
- **SentenceTransformers** with 'all-MiniLM-L6-v2' model for embeddings
- **pgvector** extension for efficient similarity search
- Supports mapping extracted text to existing Wikidata entities

## API Endpoints

The FastAPI server provides endpoints for evaluation workflows:

- `GET /politicians` - Get politicians with unevaluated data
- `POST /evaluate` - Evaluate extracted data (confirm/discard)

Access API documentation at `http://localhost:8000/docs` when server is running.

## Configuration

Set environment variables in `.env`:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/poliloom
OPENAI_API_KEY=your_openai_api_key
WIKIDATA_DUMP_BZ2_PATH=./latest-all.json.bz2
WIKIDATA_DUMP_JSON_PATH=./latest-all.json
```

## Development

### Testing

```bash
# Start test database
docker-compose up -d postgres_test

# Run tests with coverage
uv run pytest --cov=poliloom
```

### Code Quality

```bash
# Format and lint (runs automatically via pre-commit)
uv run ruff check --fix .
uv run ruff format .

# Install pre-commit hooks
uv run pre-commit install
```

### Database Migrations

```bash
# Create migration after model changes
uv run alembic revision --autogenerate -m "Description"

# Apply migrations
uv run alembic upgrade head
```

## Architecture

**Data Pipeline**: Wikidata dump → Local database → LLM enrichment → Evaluation GUI

**Database Schema**: Stores politicians, positions, locations with relationships and embeddings. Supports incomplete dates, multiple citizenships, and evaluation workflows.

**External Integrations**: Wikidata dumps, OpenAI API, Wikipedia API, MediaWiki OAuth

For detailed specifications, see [CLAUDE.md](./CLAUDE.md).