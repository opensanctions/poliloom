# PoliLoom

Open-source tool to build the world's largest open database of politicians. Extracts politician data from Wikipedia using AI, verifies it through community review, and submits to Wikidata.

## Project Structure

```
poliloom/                        # Backend project root (pyproject.toml, Dockerfile)
  poliloom/                      # Python package (source code lives here)
    api/                         # FastAPI endpoints
    models/                      # SQLAlchemy models
    importer/                    # Wikidata dump processing
    cli.py, enrichment.py, ...
  alembic/                       # DB migrations
  tests/
poliloom-gui/                    # Frontend project root
  src/
    app/                         # Next.js App Router pages
    components/                  # Reusable React components
    types/                       # TypeScript definitions
docker-compose.yml               # Services: postgres, api, gui
```

## Tech Stack

**Backend**: Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL (pgvector), OpenAI API, SentenceTransformers
**Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS, NextAuth.js
**Package Managers**: uv (Python), npm (Node.js)

## Development Environment

Dev servers for both backend (port 8000) and frontend (port 3000) are always running - no need to start them.

```bash
# Backend
cd poliloom
uv sync                          # Install deps
uv run alembic upgrade head      # Run migrations
uv run pytest                    # Run tests

# Frontend
cd poliloom-gui
npm install                      # Install deps
npm run test                     # Run tests
```

## Database

- Main: PostgreSQL 15 with pgvector (port 5432)
- Test: Separate instance (port 5433)
- Connection: `PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d poliloom`

## Key Backend Files

- `poliloom/poliloom/cli.py` - CLI commands (import, enrich, embed)
- `poliloom/poliloom/api/` - FastAPI endpoints
- `poliloom/poliloom/models/` - SQLAlchemy models (Politician, Property, Position, etc.)
- `poliloom/poliloom/importer/` - Wikidata dump processing
- `poliloom/poliloom/enrichment.py` - AI-powered data extraction

## Key Frontend Files

- `poliloom-gui/src/app/` - Next.js App Router pages
- `poliloom-gui/src/app/evaluate/` - Main evaluation interface
- `poliloom-gui/src/components/` - Reusable React components
- `poliloom-gui/src/types/` - TypeScript definitions

## Data Pipeline

1. Download Wikidata dump → Extract hierarchy (P279 relationships)
2. Import positions, locations, countries
3. Import politicians with entity links
4. Generate embeddings for similarity search
5. AI extraction from Wikipedia → Community verification → Wikidata submission

## Environment Variables

Backend (`.env`): DB_*, OPENAI_API_KEY, MEDIAWIKI_CONSUMER_*, GOOGLE_APPLICATION_CREDENTIALS
Frontend (`.env.local`): AUTH_SECRET, MEDIAWIKI_OAUTH_*, API_BASE_URL

## Code Style

- Backend: Ruff (linting/formatting)
- Frontend: ESLint + Prettier
- Pre-commit hooks configured
