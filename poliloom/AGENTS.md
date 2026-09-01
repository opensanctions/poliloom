# PoliLoom Backend

Instructions for work under `poliloom/`. Repository-wide instructions in `../AGENTS.md` also apply.

## Commands

Always use `uv`. Run commands from this directory.

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Run focused tests while developing, for example `uv run pytest tests/test_review_queue.py`, then run the full suite. Use `uv run poliloom <command> --help` for CLI usage rather than relying on a maintained command catalogue.

## Database and Migration Safety

- Tests use the `poliloom_test` PostgreSQL database configured in `pyproject.toml`.
- The test fixtures create all tables at session start and drop them at session end. Never point tests at the `poliloom` application database or override the test database settings with application credentials.
- Model or schema changes require an Alembic migration. Do not use a local schema change as a substitute for a committed migration.
- PostgreSQL behavior is exercised for real in tests. Meilisearch and other external integrations should be mocked unless a test is explicitly an integration test.

## Behavioral Invariants

Preserve these unless the task explicitly changes them:

- Review work is claimed per property with a TTL, not per politician. Users with disjoint language selections may review different properties of the same politician concurrently.
- Candidate selection and claim creation must remain atomic. The queue uses per-politician row locking to prevent overlapping claims.
- Language filtering applies to property references; unreferenced properties and references with unknown language remain reviewable according to `review_queue.py`.
- On-demand enrichment maintains a floor of one serveable politician for each language/country filter combination.
- Enrichment freshness is tracked per politician and Wikipedia project and is governed by `ENRICHMENT_COOLDOWN_DAYS`.
- Entity-linked extraction is intentionally two-stage: extract free-form text, search Meilisearch for candidates, then ask the model to map to a Wikidata entity. This avoids passing unbounded entity enums to the model.
- Wikidata dump import order is hierarchy, supporting entities, then politicians. Politicians link to entities imported by the earlier passes.
- Wikidata entity relationships use QIDs directly. Do not introduce a surrogate QID translation layer without an explicit design change.
- Date properties use Wikidata time strings together with explicit `value_precision`. Use `poliloom.wikidata.date.WikidataDate` rather than introducing ad-hoc date formats.

## Testing

Write minimal, behavior-focused tests. Test business rules and data transformations rather than Python mechanics or private implementation details. Add regression coverage when changing queueing, enrichment, import, API, or Wikidata statement behavior.
