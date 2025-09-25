# **PoliLoom API/CLI Project Specification**

This document outlines the high-level architecture and strategy for the PoliLoom project - a proof of concept for extracting politician metadata from Wikipedia and web sources to enrich Wikidata.

## **1. Project Overview**

**Core Goals:**

- Populate local database with politician data from Wikidata dumps
- Extract politician properties (birth dates, birthplaces, political positions) from web sources using LLMs
- Provide API for GUI evaluation workflows
- Offer CLI tools for data import and enrichment operations
- Integrate with external services (Wikidata, OpenAI, MediaWiki OAuth)

**Scope:** Backend services and data processing for a usable proof of concept.

## **2. Technology Stack**

- **Language:** Python with `uv` for dependency management
- **CLI:** Click framework
- **API:** FastAPI with MediaWiki OAuth 2.0 authentication
- **Database:** PostgreSQL with SQLAlchemy ORM and Alembic migrations
- **LLM Integration:** OpenAI API for structured data extraction
- **Vector Search:** SentenceTransformers ('paraphrase-multilingual-MiniLM-L12-v2') + pgvector extension
- **Storage:** Google Cloud Storage (GCS) for dump processing (automatic gs:// path detection)
- **PyTorch:** CPU-only in Docker (`uv sync --extra cpu`), GPU for development (`uv sync --extra cu128`)

**Important:** Always use `uv` for running Python commands and managing dependencies.

## **3. Architecture & Strategy**

### **Entity-Oriented Design**

Each Wikidata entity type has a dedicated class (`WikidataPolitician`, `WikidataPosition`, `WikidataLocation`, `WikidataCountry`) handling its complete lifecycle. Uses `WikidataEntityFactory` for type detection and creation.

### **Three-Pass Dump Processing Strategy**

1. **Pass 1 - Build Hierarchy Trees:** Extract P279 (subclass of) relationships for positions (Q294414) and locations (Q2221906). Store in database for reuse.
2. **Pass 2 - Import Supporting Entities:** Use hierarchy trees to import positions, locations, countries before politicians reference them.
3. **Pass 3 - Import Politicians:** Link politicians to existing entities, preventing deadlock issues.

### **Two-Stage Extraction Strategy**

For entity-linked properties (OpenAI's 500 enum limit):

1. **Free-form Extraction:** LLM extracts natural language descriptions
2. **Vector Mapping:** Generate embeddings → similarity search top 100 → LLM maps to specific Wikidata entity or None

## **4. Core Functionality**

### **Data Import Pipeline**

- **Wikidata Dumps:** Process complete latest-all.json (~1TB uncompressed)
- **Wikipedia Links:** Extract from entity sitelinks for enrichment
- **Batch Processing:** Efficient database insertion with configurable batch sizes
- **GCS Support:** Seamless local/cloud storage with gs:// paths

### **Enrichment Pipeline**

- **Wikipedia Content:** Fetch and process linked articles
- **LLM Extraction:** OpenAI structured data API for politician properties
- **Conflict Detection:** Flag discrepancies between extracted and existing Wikidata values
- **Similarity Search:** Match unlinked entities using embeddings

### **API Endpoints**

- **GET /politicians:** Retrieve politicians with unevaluated extractions
- **POST /evaluate:** Submit evaluation results (confirmed/rejected)
- **Authentication:** MediaWiki OAuth 2.0 JWT tokens

### **CLI Structure**

_Use `--help` for detailed command documentation._

## **5. Key Design Decisions**

### **QID-Based Hierarchy**

- `wikidata_classes` uses `wikidata_id` as primary key (String type)
- All foreign keys reference QIDs directly for optimal performance
- Eliminates UUID-to-QID mapping complexity

### **Evaluation System**

- Single Evaluation table for all property types
- Boolean confirmed/rejected flags instead of direct entity confirmation
- Supports multiple users and threshold-based workflows

### **Embedding Workflow**

- Position/Location embeddings initially NULL during import
- Generated separately in batch processing for optimal performance
- Used for similarity search in two-stage extraction

### **Conflict Handling**

- `conflict_resolved` fields flag when discrepancies are addressed
- Extract-then-evaluate workflow prevents data corruption

## **6. External Integrations**

- **Wikidata Dumps:** Primary data source (latest-all.json)
- **Google Cloud Storage:** Large file processing and storage
- **OpenAI API:** All LLM-based extraction
- **MediaWiki OAuth 2.0:** User authentication for API
- **Wikipedia API:** Article content fetching

## **7. Common Commands**

### **Development Setup**

```bash
# Sync dependencies (CPU-only for Docker)
uv sync --extra cpu

# Sync for GPU development
uv sync --extra cu128

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
uv run pytest tests/test_entity_classes.py::TestWikidataPolitician::test_politician_creation
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

# Generate embeddings
uv run poliloom embed-entities

# Enrich politician data
uv run poliloom enrich-wikipedia --id Q6279
uv run poliloom enrich-wikipedia --limit 100

# Show politician information
uv run poliloom show-politician --id Q6279
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
- **Mocking**: External APIs (OpenAI, sentence-transformers) mocked in `conftest.py`
- **Coverage Focus**: Entity classes, database models, core data pipeline

### **Key Patterns**

- **Entity-Oriented Architecture**: Each Wikidata entity type has dedicated class
- **Date Handling**: Store incomplete dates as strings ('1962', 'JUN 1982')
- **Embedding Strategy**: NULL during import, batch-generated separately
- **Error Handling**: Comprehensive logging and graceful degradation

### **Pre-commit Configuration**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
```

## **9. Important Notes**

- **Always use `uv`** for Python execution and dependency management
- **Web Crawling**: Reference `crawl4ai_custom_context.md` for all web requests
- **PyTorch Extras**: cpu/cu128 extras are mutually exclusive (configured in pyproject.toml)
- **Test Database**: Uses port 5433 to avoid conflicts with main database (port 5432)
