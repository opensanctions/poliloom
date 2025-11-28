# PoliLoom Backend

The Python backend for PoliLoom — processes Wikidata dumps, extracts politician data using AI, and serves the evaluation API.

## Requirements

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- PostgreSQL with pgvector extension
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
make download-wikidata-dump
make extract-wikidata-dump

# Import in order
uv run poliloom import-hierarchy      # Build entity relationship trees
uv run poliloom import-entities       # Import positions, locations, countries
uv run poliloom import-politicians    # Import politicians

# Generate embeddings for semantic search
uv run poliloom embed-entities
```

### Extract politician data

```bash
# Enrich 20 politicians from any country/language
poliloom enrich-wikipedia --count 20

# Enrich 10 politicians from the US (Q30) or Italy (Q38)
poliloom enrich-wikipedia --count 10 --countries Q30 --countries Q38

# Enrich 5 politicians with English (Q1860) or French (Q150) Wikipedia sources
poliloom enrich-wikipedia --count 5 --languages Q1860 --languages Q150
```

### Run the API server

```bash
uv run uvicorn poliloom.api:app --reload
```

API documentation available at http://localhost:8000/docs

## CLI Reference

| Command                       | Description                                           |
| ----------------------------- | ----------------------------------------------------- |
| `poliloom import-hierarchy`   | Build position/location hierarchy trees from Wikidata |
| `poliloom import-entities`    | Import positions, locations, and countries            |
| `poliloom import-politicians` | Import politicians linking to existing entities       |
| `poliloom embed-entities`     | Generate vector embeddings for semantic search        |
| `poliloom enrich-wikipedia`   | Extract politician data from Wikipedia using AI       |
| `poliloom garbage-collect`    | Remove entities deleted from Wikidata                 |

Use `--help` on any command for detailed options.

## Configuration

Key environment variables (see `.env.example`):

| Variable                                                     | Description                       |
| ------------------------------------------------------------ | --------------------------------- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`    | PostgreSQL connection             |
| `OPENAI_API_KEY`                                             | Required for Wikipedia enrichment |
| `MEDIAWIKI_OAUTH_CLIENT_ID`, `MEDIAWIKI_OAUTH_CLIENT_SECRET` | For user authentication           |

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
