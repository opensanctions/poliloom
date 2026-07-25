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
**Package Managers**: uv (Python), pnpm (Node.js)

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
pnpm install                     # Install deps
pnpm test                        # Run tests
```

## Database

- Main: PostgreSQL 15 with pgvector (port 5432)
- Test: Separate instance (port 5433)
- Connection: `PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres -d poliloom`

## Key Backend Files

- `poliloom/poliloom/cli.py` - CLI commands (dump download/extract, import, cleanup, Meilisearch indexing)
- `poliloom/poliloom/api/` - FastAPI endpoints (politicians, sources, events, stats, auth)
- `poliloom/poliloom/models/` - SQLAlchemy models (Politician, Source, Property, etc.)
- `poliloom/poliloom/importer/` - Wikidata dump processing
- `poliloom/poliloom/enrichment.py` - AI-powered data extraction from web sources
- `poliloom/poliloom/scheduling.py` - On-demand enrichment orchestration (floor-of-1 top-up)
- `poliloom/poliloom/review_queue.py` - Claim-based review serving: per-property claims (TTL) handed out under per-politician row locks
- `poliloom/poliloom/archiving.py` - Web page fetching and MHTML archiving via Playwright
- `poliloom/poliloom/sse.py` - Server-sent events bus for real-time updates

## Key Frontend Files

- `poliloom-gui/src/app/(app)/politician/[qid]/` - Single politician evaluation view
- `poliloom-gui/src/app/(app)/session/` - Session flow (enriching, unlocked, complete)
- `poliloom-gui/src/components/evaluation/` - Evaluation UI (property display, source viewer, forms)
- `poliloom-gui/src/components/entity/` - Entity components (MultiSelect filter picker, etc.)
- `poliloom-gui/src/components/ui/` - Generic UI components (entity search, date picker, etc.)
- `poliloom-gui/src/contexts/` - React contexts (EvaluationSession, EventStream, NextPolitician, etc.)
- `poliloom-gui/src/types/` - TypeScript definitions

## Data Pipeline

1. Download Wikidata dump → Extract hierarchy (P279 relationships)
2. Import positions, locations, countries → Index entities to Meilisearch
3. Import politicians with entity links
4. Archive web sources (Wikipedia, government portals) as MHTML via Playwright
5. Users always review in at least one language. `/next` claims the unevaluated properties it serves (per-property claims with `CLAIM_TTL_MINUTES` TTL, default 30), so users never see each other's property; users with disjoint languages review the same politician in parallel. When nothing serveable remains, background enrichment (two-stage: free-form extraction → Meilisearch entity mapping) tops up to a floor of 1 serveable politician per filter combo; (politician, Wikipedia project) snapshots are re-enriched after `ENRICHMENT_COOLDOWN_DAYS` (default 365)
6. Community evaluation → Wikidata submission

## Environment Variables

Backend (`.env`): DB_*, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_REASONING_EFFORT, MEDIAWIKI_CONSUMER_*, GOOGLE_APPLICATION_CREDENTIALS, MEILI_URL, MEILI_MASTER_KEY, POLILOOM_ARCHIVE_ROOT, WIKIDATA_API_ROOT, ENRICHMENT_COOLDOWN_DAYS, CLAIM_TTL_MINUTES
Frontend (`.env.local`): AUTH_SECRET, MEDIAWIKI_OAUTH_*, API_BASE_URL

## Code Style

- Backend: Ruff (linting/formatting)
- Frontend: ESLint + Prettier
- Pre-commit hooks configured
