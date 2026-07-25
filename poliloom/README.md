# PoliLoom Backend

The Python backend for PoliLoom — processes Wikidata dumps, extracts politician data using AI, and serves the evaluation API.

## Requirements

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- Meilisearch
- Linux or macOS (Windows not supported due to multiprocessing requirements)
- OpenAI API key

## Setup

```bash
# Install dependencies
uv sync

# Start PostgreSQL (from project root)
cd .. && docker compose up -d postgres

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Run database migrations
uv run alembic upgrade head
```

## Usage

### Import Wikidata

PoliLoom uses a three-pass strategy to process the Wikidata dump:

```bash
# Download and extract (one-time, ~100GB download → ~2TB extracted)
uv run poliloom dump-download --output ./dump.json.bz2
uv run poliloom dump-extract --input ./dump.json.bz2 --output ./dump.json

# Import in order
uv run poliloom import-hierarchy      # Build entity relationship trees
uv run poliloom import-entities       # Import positions, locations, countries
uv run poliloom import-politicians    # Import politicians
```

### Extract politician data

Enrichment is demand-driven: `/politicians/next` claims and serves unevaluated
properties in the user's selected languages, and background enrichment tops up
to one serveable politician per filter combo when the pool runs dry. Each
(politician, Wikipedia project) gets a fresh snapshot after
`ENRICHMENT_COOLDOWN_DAYS` (default 365).

### Run the API server

```bash
uv run uvicorn poliloom.api:app --reload
```

API documentation available at http://localhost:8000/docs

All CLI commands support `--help` for detailed options. See `.env.example` for configuration.

## Development

```bash
# Run tests
uv run pytest

# Format and lint
uv run ruff check --fix .
uv run ruff format .

# Create database migration
uv run alembic revision --autogenerate -m "Description"
```

## Architecture

**Data flow**: Wikidata dump → PostgreSQL → AI enrichment → Evaluation API → GUI

**Key components**:

- `importer/` — Wikidata dump processing
- `enrichment.py` — AI-powered data extraction
- `api/` — FastAPI endpoints for the evaluation interface
- `models/` — SQLAlchemy database models

See [CLAUDE.md](./CLAUDE.md) for detailed specifications.
