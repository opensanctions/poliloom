# PoliLoom

Open-source tool to build the world's largest open database of politicians. Extracts politician data from web sources (Wikipedia, government portals, etc.) using AI, verifies it through community review, and submits to Wikidata.

## Project Structure

```
poliloom/                        # Backend (Python package, pyproject.toml, Dockerfile)
poliloom-gui/                    # Frontend (Next.js, package.json)
docker-compose.yml               # Services: postgres, api, gui
```

## Tech Stack

**Backend**: Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL (pgvector), OpenAI API, Meilisearch (hybrid search with OpenAI embeddings)
**Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS, NextAuth.js
**Infrastructure**: Meilisearch (entity search + semantic similarity), Playwright (web page archiving)
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
- `poliloom/poliloom/api/` - FastAPI endpoints (politicians, sources, events, stats, auth)
- `poliloom/poliloom/models/` - SQLAlchemy models (Politician, Source, Property, etc.)
- `poliloom/poliloom/importer/` - Wikidata dump processing
- `poliloom/poliloom/enrichment.py` - AI-powered data extraction from web sources
- `poliloom/poliloom/archiving.py` - Web page fetching and MHTML archiving via Playwright
- `poliloom/poliloom/sse.py` - Server-sent events bus for real-time updates

## Key Frontend Files

- `poliloom-gui/src/app/(app)/politician/[qid]/` - Single politician evaluation view
- `poliloom-gui/src/app/(app)/sources/[id]/` - Source evaluation view
- `poliloom-gui/src/app/(app)/session/` - Session flow (enriching, unlocked, complete)
- `poliloom-gui/src/components/evaluation/` - Evaluation UI (property display, source viewer, forms)
- `poliloom-gui/src/components/ui/` - Generic UI components (entity search, date picker, etc.)
- `poliloom-gui/src/contexts/` - React contexts (EvaluationSession, EventStream, NextPolitician, etc.)
- `poliloom-gui/src/types/` - TypeScript definitions

## Data Pipeline

1. Download Wikidata dump → Extract hierarchy (P279 relationships)
2. Import positions, locations, countries → Index entities to Meilisearch
3. Import politicians with entity links
4. Archive web sources (Wikipedia, government portals) as MHTML via Playwright
5. AI extraction from web sources (two-stage: free-form extraction → Meilisearch entity mapping)
6. Community evaluation → Wikidata submission

## Environment Variables

Backend (`.env`): DB_*, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_REASONING_EFFORT, MEDIAWIKI_CONSUMER_*, GOOGLE_APPLICATION_CREDENTIALS, MEILI_URL, MEILI_MASTER_KEY, POLILOOM_ARCHIVE_ROOT, WIKIDATA_API_ROOT, MIN_UNEVALUATED_POLITICIANS
Frontend (`.env.local`): AUTH_SECRET, MEDIAWIKI_OAUTH_*, API_BASE_URL

## Code Style

- Backend: Ruff (linting/formatting)
- Frontend: ESLint + Prettier
- Pre-commit hooks configured
