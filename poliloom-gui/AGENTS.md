# PoliLoom GUI

Instructions for work under `poliloom-gui/`. Repository-wide instructions in `../AGENTS.md` also apply.

## Commands

Use `pnpm`. Run commands from this directory.

```bash
pnpm lint
pnpm typecheck
pnpm exec prettier --check .
pnpm exec vitest run
```

Run a focused test file while developing, for example `pnpm exec vitest run src/contexts/NextPoliticianContext.test.tsx`, then run the full suite. Run `pnpm build` for changes to routing, rendering boundaries, Next.js configuration, or production-only behavior.

## Application Boundaries

- Browser-facing backend requests go through same-origin routes in `src/app/api/`. These routes proxy to the backend and attach authentication; do not call `API_BASE_URL` directly from client components.
- Backend response and request schemas are mirrored manually in `src/types/index.ts`. When the backend contract changes, update the types, proxy route where necessary, callers, and tests together.
- Filters are persisted in cookies. Preserve URL-to-cookie handling in `src/proxy.ts` and the behavior of `FilterContext` when changing filter flow.
- User settings are persisted through the backend settings endpoint. Do not turn them into client-only React state.
- Real-time evaluation and enrichment updates arrive through the shared SSE connection in `EventStreamContext`; avoid creating independent event streams in feature components.

## Testing

Use Vitest and React Testing Library. Prefer user-visible behavior and accessible queries over component internals. Add regression coverage for authentication, proxy behavior, evaluation submission, filtering, session navigation, and error handling when those areas change.

Keep tests deterministic: mock network, navigation, and browser-only APIs through the existing test setup rather than depending on the running development servers.
