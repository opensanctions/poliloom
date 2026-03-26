# **PoliLoom API/CLI Project Specification**

This document outlines the high-level architecture and strategy for the PoliLoom project - extracting politician metadata from Wikipedia and web sources to enrich Wikidata.

## **1. Project Overview**

**Core Goals:**

- Populate local database with politician data from Wikidata dumps
- Extract politician properties (birth dates, birthplaces, political positions) from web sources using LLMs
- Provide API for GUI evaluation workflows
- Offer CLI tools for data import and enrichment operations
- Integrate with external services (Wikidata, OpenAI, MediaWiki OAuth)

**Scope:** Backend services and data processing.

## **2. Technology Stack**

- **Language:** Python with `uv` for dependency management
- **CLI:** Click framework
- **API:** FastAPI with MediaWiki OAuth 2.0 authentication
- **Database:** PostgreSQL with SQLAlchemy ORM and Alembic migrations
- **LLM Integration:** OpenAI API for structured data extraction
- **Search:** Meilisearch with OpenAI embeddings for hybrid search (keyword + semantic)
- **Storage:** Google Cloud Storage (GCS) for dump processing (automatic gs:// path detection)

**Important:** Always use `uv` for running Python commands and managing dependencies.

## **3. Architecture & Strategy**

### **Entity-Oriented Design**

Each Wikidata entity type has a dedicated class (`Politician`, `Position`, `Location`, `Country`, all inheriting from `WikidataEntityMixin`) handling its complete lifecycle. Uses `WikidataEntityProcessor` for type detection and processing.

### **Dump Processing Strategy**

Three separate CLI commands, each reading the dump file independently:

1. **`import-hierarchy`:** Extract P279 (subclass of) relationships for positions and locations. Store in database for reuse.
2. **`import-entities`:** Use hierarchy trees to import positions, locations, countries before politicians reference them.
3. **`import-politicians`:** Link politicians to existing entities, preventing deadlock issues.

### **Two-Stage Extraction Strategy**

For entity-linked properties (OpenAI's 500 enum limit):

1. **Free-form Extraction:** LLM extracts natural language descriptions
2. **Entity Mapping:** Meilisearch hybrid search (keyword + semantic) → top 100 candidates → LLM maps to specific Wikidata entity or None

## **4. Core Functionality**

### **Data Import Pipeline**

- **Wikidata Dumps:** Process complete latest-all.json (~1TB uncompressed)
- **Wikipedia Links:** Extract from entity sitelinks for enrichment
- **Batch Processing:** Efficient database insertion with configurable batch sizes
- **GCS Support:** Seamless local/cloud storage with gs:// paths

### **Enrichment Pipeline**

- **Web Source Archiving:** Fetch and archive web pages (Wikipedia, government portals) as MHTML via Playwright (`archiving.py`)
- **LLM Extraction:** OpenAI structured data API for politician properties
- **Similarity Search:** Match unlinked entities using Meilisearch hybrid search
- **Real-time Updates:** SSE events broadcast enrichment progress and evaluation count changes (`sse.py`)

### **API Endpoints**

- **Politicians:** `GET /politicians/next` (next unevaluated), `GET /politicians/{qid}`, `GET /politicians/search`, `POST /politicians` (create), `PATCH /politicians/{qid}/properties` (submit evaluations), `POST /politicians/{qid}/sources` (add source)
- **Sources:** `GET /sources/{id}` (politicians for source), `GET /sources/{id}.html` (archived HTML), `PATCH /sources/{id}/properties` (evaluate from source view)
- **Events:** `GET /events` (SSE stream for real-time updates: evaluation counts, enrichment progress)
- **Authentication:** MediaWiki OAuth 2.0 JWT tokens

### **CLI Structure**

_Use `--help` for detailed command documentation._

## **5. Key Design Decisions**

### **QID-Based Hierarchy**

- `wikidata_entities` uses `wikidata_id` as primary key (String type)
- All foreign keys reference QIDs directly for optimal performance
- Eliminates UUID-to-QID mapping complexity

### **Evaluation System**

- Single Evaluation table for all property types
- Boolean `is_accepted` flag for user actions on data
- Actions: **Accept** new extracted data (submit to Wikidata), **Reject** incorrect extracted data (soft delete), **Deprecate** existing statements (mark as deprecated in Wikidata)
- Supports multiple users

### **Search & Similarity**

- All entities indexed to Meilisearch with labels during import
- Meilisearch uses OpenAI embeddings for hybrid search (keyword + semantic)
- Position entities use higher semantic ratio (0.8) for better matching

## **6. External Integrations**

- **Wikidata Dumps:** Primary data source (latest-all.json)
- **Google Cloud Storage:** Large file processing and storage
- **OpenAI API:** All LLM-based extraction
- **MediaWiki OAuth 2.0:** User authentication for API
- **Playwright:** Web page fetching and MHTML archiving

## **7. Common Commands**

### **Development Setup**

```bash
# Sync dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### **Testing**

```bash
# Run all tests
uv run pytest

# Run all model tests
uv run pytest tests/models/

# Run specific test file
uv run pytest tests/models/test_politician.py

# Run with verbose output
uv run pytest -v

# Run specific test method
uv run pytest tests/models/test_politician.py::TestPolitician -k test_name
```

### **Database Operations**

```bash
# View current schema
PGPASSWORD=postgres pg_dump -h localhost -p 5432 -U postgres -d poliloom --schema-only

# Run Alembic migrations
uv run alembic upgrade head
```

### **CLI Commands**

```bash
# Start development server
uv run uvicorn poliloom.api:app --reload

# Import data workflow
uv run poliloom dump-download --output ./dump.json.bz2
uv run poliloom dump-extract --input ./dump.json.bz2 --output ./dump.json
uv run poliloom import-hierarchy --file ./dump.json
uv run poliloom import-entities --file ./dump.json
uv run poliloom import-politicians --file ./dump.json

# Enrich politician data
uv run poliloom enrich-wikipedia --count 20
uv run poliloom enrich-wikipedia --count 10 --countries Q30

# Meilisearch index management
uv run poliloom index-create
uv run poliloom index-build
uv run poliloom index-stats

# Maintenance operations
uv run poliloom garbage-collect
uv run poliloom clean-entities
uv run poliloom clean-properties
```

## **8. Code Style & Development Practices**

### **Code Formatting**

- **Auto-formatting**: Ruff handles formatting and linting via pre-commit hooks
- **Line Length**: 88 characters (configured in `pyproject.toml`)
- **Python Version**: Requires Python 3.12+
- **Import Style**: Standard Python import conventions

### **Testing Standards**

- **Framework**: pytest with asyncio support
- **Database**: PostgreSQL test database (port 5433)
- **Mocking**: External APIs (OpenAI, Meilisearch) mocked in `conftest.py`
- **Coverage Focus**: Entity classes, database models, core data pipeline
- **Approach**: Minimal, behavior-focused testing. Test business logic and data transformations, not language mechanics (inheritance, type checking). Avoid over-engineering tests.

### **Key Patterns**

- **Entity-Oriented Architecture**: Each Wikidata entity type has dedicated class
- **Date Handling**: Store incomplete dates as strings ('1962', 'JUN 1982')
- **Search Indexing**: Entities indexed to Meilisearch during import, embeddings generated by Meilisearch
## **9. Important Notes**

- **Always use `uv`** for Python execution and dependency management
- **Web Crawling**: Uses Playwright directly for page fetching and MHTML capture
- **Test Database**: Uses port 5433 to avoid conflicts with main database (port 5432)
