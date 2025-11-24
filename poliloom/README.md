# PoliLoom

PoliLoom is a Python API and CLI tool for extracting politician metadata from Wikipedia and other web sources to enrich Wikidata. It processes Wikidata dumps to build a local database and uses Large Language Models to extract missing politician information.

## Technology Stack

- **Python** with **uv** for dependency management
- **Click** CLI framework and **FastAPI** web framework
- **SQLAlchemy** ORM with **PostgreSQL** database
- **OpenAI API** for structured data extraction
- **SentenceTransformers** with **pgvector** for vector search
- **MediaWiki OAuth 2.0** for authentication

## Platform Requirements

**This project requires Linux or macOS. Windows is not supported.**

The dump processing pipeline relies on Unix-style multiprocessing with copy-on-write memory sharing. When processing the Wikidata dump, we share large frozensets across worker processes. On Unix systems, these are efficiently shared via fork() without duplication. Windows would duplicate this data for each worker, making the memory requirements impractical.

## Installation

```bash
# Clone and set up the project
git clone <repository-url>
cd poliloom
uv sync

# Start PostgreSQL
cd .. && docker compose up -d postgres

# Set up database
uv run alembic upgrade head
```

## Quick Start

PoliLoom uses a three-pass strategy to process Wikidata dumps:

```bash
# 1. Download and extract Wikidata dump (one-time setup)
make download-wikidata-dump  # Downloads ~100GB compressed dump
make extract-wikidata-dump   # Extracts to ~1TB JSON file

# 2. Import hierarchy trees (required once per dump)
uv run poliloom import-hierarchy

# 3. Import entities in order
uv run poliloom import-entities     # Import positions, locations, countries
uv run poliloom import-politicians  # Import politicians linking to entities

# 4. Generate embeddings for vector search
uv run poliloom embed-entities

# 5. Enrich politician data using LLMs
uv run poliloom enrich-wikipedia --id Q6279

# 6. Start API server
uv run uvicorn poliloom.api:app --reload
```

## CLI Commands

### Dump Processing

- `poliloom import-hierarchy [--file FILE]` - Import position/location hierarchy trees
- `poliloom import-entities [--file FILE] [--batch-size SIZE]` - Import supporting entities
- `poliloom import-politicians [--file FILE] [--batch-size SIZE]` - Import politicians

### Data Management

- `poliloom enrich-wikipedia --id <wikidata_id>` - Enrich politician using LLMs
- `poliloom enrich-wikipedia --limit <N>` - Enrich politicians until N have unevaluated statements
- `poliloom embed-entities` - Generate embeddings for all positions and locations
- `poliloom garbage-collect` - Clean up entities missing from latest dumps using two-dump validation

### Server

- `uvicorn poliloom.api:app --reload` - Start FastAPI server with auto-reload

## Core Features

### Three-Pass Dump Processing

1. **Import Hierarchy Trees** - Extract entity relationships for efficient filtering
2. **Import Supporting Entities** - Import positions, locations, and countries first
3. **Import Politicians** - Link politicians to existing entities to prevent deadlocks

### LLM-Based Data Extraction

- **Two-stage extraction** for entity-linked properties to handle large datasets
- **Stage 1**: Free-form extraction from Wikipedia content
- **Stage 2**: Vector similarity search + OpenAI mapping to Wikidata entities

### Vector Search

- **SentenceTransformers** with 'paraphrase-multilingual-MiniLM-L12-v2' model for embeddings
- **pgvector** extension for efficient similarity search
- Supports mapping extracted text to existing Wikidata entities

## API Endpoints

The FastAPI server provides endpoints for evaluation workflows:

- `GET /politicians` - Get politicians with unevaluated data
- `POST /evaluate` - Evaluate extracted data (accept/reject/deprecate)

Access API documentation at `http://localhost:8000/docs` when server is running.

## Configuration

Copy `.env.example` to `.env` and set the required environment variables:

```bash
cp .env.example .env
```

Key configuration variables:

**Database (Local Development):**

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=poliloom
DB_USER=postgres
DB_PASSWORD=postgres
```

**Database (Google Cloud SQL):**

```bash
INSTANCE_CONNECTION_NAME=project:region:instance
DB_IAM_USER=your-iam-user
DB_NAME=poliloom
```

**External Services:**

```bash
OPENAI_API_KEY=your_openai_api_key
MEDIAWIKI_OAUTH_CLIENT_ID=your-client-id
MEDIAWIKI_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

## Development

### Testing

```bash
# Start test database
cd .. && docker compose up -d postgres_test

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

**Database Schema**: Stores politicians with unified property model for all metadata (positions, birthplaces, citizenship). Properties are distinguished by type enum and support both entity relationships and string values. Includes embeddings for similarity search and evaluation workflows.

**External Integrations**: Wikidata dumps, OpenAI API, Wikipedia API, MediaWiki OAuth

For detailed specifications, see [CLAUDE.md](./CLAUDE.md).
