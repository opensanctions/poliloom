# PoliLoom

PoliLoom extracts politician data from web sources, has people review it, and submits accepted data to Wikidata.

## Repository Scope

- `poliloom/` contains the Python API, CLI, import, and enrichment backend.
- `poliloom-gui/` contains the Next.js review interface.
- Follow the nested `AGENTS.md` in the package you change. For cross-package work, follow both.

## Agent Environment

In the configured agent development environment, the backend and frontend dev servers are already running on ports 8000 and 3000. Do not start replacement servers unless the user asks.

Use `uv` for Python work and `pnpm` for frontend work. Run commands from the relevant package directory unless a command explicitly targets the repository root.

## Cross-Package Changes

The frontend mirrors backend API contracts manually. When an API schema or route changes, check the corresponding routes under `poliloom-gui/src/app/api/`, types in `poliloom-gui/src/types/`, callers, and tests.

## Safety

Do not run expensive or destructive data operations unless explicitly requested. This includes Wikidata dump download/import commands, cleanup or garbage-collection commands, Meilisearch index deletion/rebuilds, `make db-truncate`, and `make db-restore`.

## Validation

Start with focused checks for the code changed, then run the package-level checks in the relevant nested `AGENTS.md`. Do not treat an already-running dev server as a substitute for tests, linting, or type checking.
