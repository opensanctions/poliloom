# PoliLoom GUI - Project Specification

## Project Purpose

The PoliLoom GUI is a web application for reviewing and validating politician metadata automatically extracted by the PoliLoom project. Users evaluate properties (birth dates, birthplaces, positions, citizenship) extracted by LLMs from web sources (Wikipedia, government portals, etc.) before the data is submitted to Wikidata.

## Technical Requirements

- Next.js with App Router, React, TypeScript
- Tailwind CSS for styling
- MediaWiki OAuth for authentication
- RESTful API integration with the PoliLoom backend (proxied via Next.js API routes)
- Vitest + React Testing Library for testing

## Core Features

### Authentication

- MediaWiki OAuth login, session management, protected routes

### Evaluation Interface

- **Politician view** (`/politician/[qid]`): Single politician with all extracted properties, grouped by type. Accept/reject individual properties.
- **Source view** (`/sources/[id]`): Evaluate properties from a specific source's perspective. Archived HTML displayed in iframe with CSS Custom Highlight API for proof text.
- **Session flow** (`/session/enriching`, `/session/unlocked`, `/session/complete`): Guides users through the evaluation session lifecycle.
- **OmniBox**: Search/navigate to politicians, with option to create new entries.

### Real-time Updates

- Server-sent events (EventStreamContext) for live evaluation count updates and enrichment progress notifications.

### User-Added Data

- Users can add new properties (dates, entities, positions) and sources via dedicated forms.

## Data Model

**Politicians**: ID, name, Wikidata QID, unified `properties` array of extracted data.

**Properties**: Each has a `type` (P569 birth date, P570 death date, P19 birthplace, P39 position, P27 citizenship), optional qualifiers (start/end dates), supporting quotes, and source references.

**Sources**: Archived web pages (MHTML) linked to politicians. Displayed in iframe with highlighted proof text.

**Evaluations**: Accept/reject individual properties, submitted in batches via `PATCH /politicians/{qid}/properties`.

## Key Architecture

- **Contexts**: `EvaluationSessionContext` (batch evaluation state), `EventStreamContext` (SSE), `NextPoliticianContext` (prefetch next politician), `UserPreferencesContext` (advanced mode, filters)
- **API proxy**: Next.js API routes in `src/app/api/` proxy to backend, attaching auth tokens
- **Route groups**: `(app)/` for authenticated routes, `(public)/` for login

## Testing

**Framework**: Vitest + React Testing Library

**Approach**: Minimal, behavior-focused. Test user-facing behavior, not implementation details.

**Priorities**: Auth flow, core evaluation workflow, politician display/navigation, API integration, error handling.
