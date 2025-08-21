# **PoliLoom API/CLI Project Specification**

This document outlines the requirements and design for the API and Command Line Interface (CLI) components of the PoliLoom project. The primary goal of this project is to extract metadata on politicians from Wikipedia and other web sources to enrich Wikidata, providing a usable proof of concept. This specification will guide the development of the backend services and data processing functionalities.

## **1\. Project Goals and Scope**

This API and CLI project is responsible for:

- Populating a local database with politician data from Wikidata and Wikipedia.
- Extracting new properties (e.g., date of birth, birthplace) and political positions from web sources using Large Language Models (LLMs).
- Providing an API for a separate GUI project to interact with the extracted data, specifically for evaluation workflows.
- Offering CLI tools for direct data import and enrichment operations.
- Integrating with external services like Wikidata and OpenAI.

## **2\. Technology Stack**

- **Programming Language:** Python
- **Environment management:** uv
- **CLI Framework:** Click
- **Web Framework:** FastAPI (for API endpoints)
- **Database ORM:** SQLAlchemy
- **Database Migrations:** Alembic
- **Database:** PostgreSQL (development and production)
- **LLM Integration:** OpenAI API (for structured data extraction)
- **Vector Search:** SentenceTransformers ('all-MiniLM-L6-v2') for embeddings, pgvector extension
- **Cloud Storage:** Google Cloud Storage (GCS) for dump file storage and processing
- **External APIs:** Wikidata API, MediaWiki OAuth

**important** use the `uv` tool for running python commands and managing dependencies

**PyTorch Installation:**

- Docker images use CPU-only PyTorch: `uv sync --extra cpu`
- Development environment can use GPU: `uv sync --extra cu128`
- The extras are mutually exclusive to prevent conflicts

**GCS Configuration:**

- Commands automatically detect GCS paths (gs://) vs local filesystem paths

## **Web Crawling Reference**

The repository includes `crawl4ai_custom_context.md` - a comprehensive reference for crawl4ai library usage patterns and best practices. This file contains detailed examples for:

- Browser configuration and session management
- Content extraction strategies (CSS selectors, XPath, regex)
- LLM integration patterns for structured data extraction
- Performance optimization and cost management
- Error handling and quality control

Use this reference for all web requests in the project, including Wikipedia content fetching and politician data enrichment from external web sources.

## **3\. Database Schema**

The database reproduces a subset of the Wikidata politician data model to store extracted information.

**To view the current database schema, run:** `PGPASSWORD=postgres pg_dump -h localhost -p 5432 -U postgres -d poliloom --schema-only`

**Schema Considerations:**

- **Incomplete Dates:** The schema should accommodate incomplete birth dates and position held dates (e.g., '1962', 'JUN 1982'). Store these as strings.
- **Multilingual Names:** The Politician entity will store names as strings. Handling multilingual variations in names during extraction and matching will be crucial.
- **Citizenships:** Politician citizenships are stored as HasCitizenship records linking politicians to countries. Multiple citizenships are supported by creating multiple HasCitizenship records. Citizenships are only imported from Wikidata and do not require user evaluation. Citizenship relationships are only created when the referenced country already exists in the database.
- **Conflict Resolution:** conflict_resolved fields will be used to flag when discrepancies between extracted data and existing Wikidata values have been addressed.
- **Embedding Workflow:** Position and Location entities have optional embedding fields that are initially NULL during import. Embeddings are generated separately in batch processing for all entities without embeddings to ensure optimal performance.
- **Evaluation System:** Instead of direct confirmation fields, the system uses separate evaluation tables (PropertyEvaluation, PositionEvaluation, BirthplaceEvaluation) that track user evaluations with boolean confirmed/rejected flags for Properties, HoldsPosition, and BornAt entities. This allows multiple users to evaluate the same extracted data and supports threshold-based confirmation workflows.

## **4\. Core Functionality**

### **4.0. Entity-Oriented Architecture**

The system uses an entity-oriented architecture where each Wikidata entity type is represented by a dedicated class that handles its complete lifecycle from raw data to database insertion. This approach provides cleaner separation of concerns and eliminates awkward parameter passing patterns.

**Entity Class Hierarchy:**

- **`WikidataEntity`** (Base class): Common functionality for all Wikidata entities including truthy claim filtering, date extraction, and name extraction
- **`WikidataPolitician`**: Handles politician identification, birth/death date extraction, citizenship extraction, position extraction, and Wikipedia link extraction
- **`WikidataPosition`**: Handles position identification using cached hierarchy trees
- **`WikidataLocation`**: Handles location identification using cached hierarchy trees
- **`WikidataCountry`**: Handles country identification and ISO code extraction

**Factory Pattern:**

- **`WikidataEntityFactory`**: Determines entity type from raw Wikidata JSON and creates appropriate entity class instances
- Single entry point for entity creation with automatic type detection
- Handles malformed data gracefully by returning None for unrecognized entities

**Key Benefits:**

- **Truthy Claim Filtering**: Centralized in base class using rank-based filtering logic (preferred → normal → deprecated)
- **Type Safety**: Each entity class owns its data extraction and validation logic
- **Testability**: Entity classes can be unit tested independently of dump processing
- **Maintainability**: Changes to entity handling are contained within respective classes

### **4.1. Data Import / Database Population**

This module is responsible for initially populating the local database with politician data using Wikidata dump processing instead of API calls.

- **Wikidata Dump Processing:**
  - Process the complete Wikidata dump file (latest-all.json) directly
  - **Three-Pass Processing Strategy:**
    - **Pass 1 - Build Hierarchy Trees:** Extract all P279 (subclass of) relationships to build complete descendant trees for positions (Q294414 - public office) and locations (Q2221906 - geographic location). Cache hierarchy to JSON files for reuse.
    - **Pass 2 - Import Supporting Entities:** Use cached trees to efficiently filter and extract positions, locations, and countries from the dump, ensuring all entities that politicians will reference are available in the database first
    - **Pass 3 - Import Politicians:** Extract politicians by filtering entities with occupation (Q82955) or position held (Q39486) properties, linking them to the previously imported entities
  - Process entities in batches for efficient database insertion
  - This three-pass approach prevents deadlock issues that occurred when trying to link politicians to entities that hadn't been imported yet
- **Entity Extraction Strategy:**
  - Identify politicians through occupation properties (P106) and position held properties (P39)
  - Extract basic politician data: name, birth date, birth place, political positions with dates
  - Handle incomplete dates and multilingual names from dump data
  - Extract Wikipedia article links (sitelinks) for subsequent enrichment
- **Country Data Handling:**
  - Countries are only linked to existing entities (no on-demand creation)
  - Citizenship relationships are only created when the referenced country already exists in the database
  - This aligns with the existing pattern for positions and locations that only link to existing entities
- **Position Data Handling:**
  - Use cached position hierarchy tree (descendants of Q294414) to identify all political positions during dump processing
  - Create Position entities directly from dump data during the supporting entities import pass
  - Embeddings are initially NULL and generated separately for optimal performance
- **Location Data Handling:**
  - Use cached location hierarchy tree (descendants of Q2221906) to identify all geographic locations during dump processing
  - Create Location entities directly from dump data during the supporting entities import pass
  - Embeddings are initially NULL and generated separately for optimal performance
- **Country Data Handling:**
  - Import countries during the supporting entities pass to ensure they are available for citizenship relationships
  - Countries are identified through their entity types in the dump data
- **Hierarchy Tree Caching:**
  - Store position and location descendant trees as JSON files after first pass
  - Tree structure: `{"subclass_of": {"Q1": ["Q2", ...], ...}}`
  - Trees are rebuilt for each new dump import (no dump date tracking needed)
  - Enables efficient O(1) entity type checking during extraction
  - Includes subclass (P279) relationships for comprehensive hierarchy coverage
- **Wikipedia Linkage:**
  - Extract Wikipedia article links directly from entity sitelinks in the dump
  - Prioritize English and local language versions
  - Store links for subsequent enrichment processing
- **Deceased People Filtering (Optional/Configurable):**
  - Filter out deceased politicians using date of death property (P570) from dump data
  - Support configurable filtering during dump processing

### **4.2. Data Extraction / Enrichment**

This module extracts new properties and positions from web sources using LLMs.

- **Source Types:**
  - **Linked Wikipedia Articles:** Fetch content from Wikipedia URLs stored during import. Prioritize English and local language versions.
  - **Random Web Sources:** Handle unlinked web pages.
    - **Index Pages:** Use LLMs to identify XPath/CSS selectors for detail page links and pagination controls.
    - **Detail Pages:** Extract Property and HoldsPosition data.
- **LLM Integration:**
  - Feed relevant page content to OpenAI's structured data API.
  - Define precise JSON schemas for Property and HoldsPosition extraction, ensuring alignment with the database schema.
  - **Two-Stage Position Extraction Strategy:** Due to OpenAI structured outputs API limitations (500 enum maximum) and countries having tens of thousands of positions (e.g., France: 78K+), use a refined two-stage approach:
    - **Stage 1 - Free-form Position Extraction:** Prompt the LLM to extract arbitrary political positions from Wikipedia content without constraints, allowing it to return natural language position descriptions
    - **Stage 2 - Wikidata Position Mapping:** For each extracted position:
      - Generate embeddings using SentenceTransformers ('all-MiniLM-L6-v2' model)
      - Perform vector similarity search to find the 100 most similar Wikidata positions
      - Use OpenAI structured data API to map the extracted position to the correct Wikidata position or None, with preference for country-specific positions over generic ones
      - This avoids the noise issues of full-article similarity search while respecting API limitations
  - **Two-Stage Birthplace Extraction Strategy:** Similar to positions, use a two-stage approach for birthplace extraction:
    - **Stage 1 - Free-form Birthplace Extraction:** Prompt the LLM to extract birthplace information from Wikipedia content without constraints, allowing it to return natural language location descriptions
    - **Stage 2 - Wikidata Location Mapping:** For each extracted birthplace:
      - Generate embeddings using SentenceTransformers ('all-MiniLM-L6-v2' model)
      - Perform vector similarity search to find the 100 most similar Wikidata locations
      - Use OpenAI structured data API to map the extracted birthplace to the correct Wikidata location or None
- **Similarity Search for Unlinked Entities:**
  - For random web pages, after extraction, perform a similarity search against existing Politician entities in the local database (e.g., based on name, country, birth date, birthplace) to find potential matches.
  - Establish a similarity score threshold to decide whether to propose an update or create a new entity.
- **Conflict Handling:**
  - Identify discrepancies between extracted data and existing Wikidata values.
  - Flag conflicting data for review in the GUI.

### **4.3. API Endpoints (FastAPI)**

The API will expose endpoints for the GUI to manage evaluation workflows. Authentication will leverage MediaWiki OAuth.

- **Authentication:**
  - Integrate with MediaWiki OAuth 2.0 for user authentication and authorization.
  - Accept JWT tokens from MediaWiki OAuth 2.0 flow in Authorization header (Bearer format).
  - Verify JWT token signatures using MediaWiki's public keys or token introspection endpoint.
  - Ensure secure handling of user tokens and permissions.
- **Routes:**

  - **GET /politicians**: Retrieve politicians that have unevaluated (is_extracted=True) properties, positions, or birthplaces
  - **POST /evaluate**: Evaluate extracted data (properties, positions, birthplaces) with boolean confirmed/rejected results

- **OpenAPI Documentation**: The complete API specification is available at `http://localhost:8000/openapi.json` when the backend server is running. To fetch it using curl:

```bash
curl http://localhost:8000/openapi.json
```

### **4.4. CLI Commands**

- **poliloom dump download --output PATH**

  - Download latest Wikidata dump from Wikidata to specified location
  - **--output**: Output path - local filesystem path or GCS path (gs://bucket/path)
  - No progress bars, comprehensive error handling
  - Downloads compressed dump (~100GB) for subsequent extraction

- **poliloom dump extract --input PATH --output PATH**

  - Extract compressed Wikidata dump to JSON format
  - **--input**: Input path to compressed dump - local filesystem path or GCS path (gs://bucket/path)
  - **--output**: Output path for extracted JSON - local filesystem path or GCS path (gs://bucket/path)
  - Parallel decompression for optimal performance (~1TB uncompressed output)
  - Comprehensive error handling without fallbacks

- **poliloom dump build-hierarchy --file PATH [--workers NUM]**

  - Build hierarchy trees for positions and locations from Wikidata dump
  - **--file**: Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)
  - **--workers**: Number of worker processes (default: CPU count)
  - Uses chunk-based parallel processing - splits file into byte ranges for true parallelism
  - Extracts all P279 (subclass of) relationships to build complete descendant trees
  - Saves complete hierarchy to `complete_hierarchy.json` (~200-500MB) containing subclass relationships
  - Provides position/location counts for verification but stores everything in the complete hierarchy
  - Must be run before `dump import` command
  - **Performance**: Scales linearly with CPU cores - near-linear speedup up to 32+ cores
  - **Scalability**: Each worker processes independent file chunks for optimal resource utilization

- **poliloom dump import-entities --file PATH [--batch-size SIZE]**

  - Import supporting entities (positions, locations, countries) from a Wikidata dump file
  - **--file**: Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)
  - **--batch-size**: Number of entities to process in each database batch (default: 100)
  - Requires hierarchy trees to be built first using `dump build-hierarchy`
  - Processes the dump line-by-line for memory efficiency
  - Must be run before `dump import-politicians`

- **poliloom dump import-politicians --file PATH [--batch-size SIZE]**

  - Import politicians from a Wikidata dump file, linking them to existing entities
  - **--file**: Path to extracted JSON dump file - local filesystem path or GCS path (gs://bucket/path)
  - **--batch-size**: Number of entities to process in each database batch (default: 100)
  - Requires supporting entities to be imported first using `dump import-entities`
  - Processes the dump line-by-line for memory efficiency
  - Links politicians to existing positions, locations, and countries to avoid deadlock issues

- **poliloom dump query-hierarchy --entity-id ENTITY_ID**

  - Query hierarchy descendants for a given Wikidata entity ID
  - **--entity-id**: Wikidata entity ID to get descendants for (e.g., Q2221906 for geographic locations, Q294414 for public offices)
  - Requires complete hierarchy to be built first using `dump build-hierarchy`
  - Outputs one descendant entity ID per line for the given entity
  - Useful for understanding hierarchy structure and debugging entity classification

- **poliloom politicians enrich --id \<wikidata_id\>**

  - Enriches a single politician entity by extracting data from its linked Wikipedia articles using LLMs.

- **poliloom politicians show --id \<wikidata_id\>**

  - Display comprehensive information about a politician, distinguishing between imported and extracted data.

- **poliloom positions embed**

  - Generate embeddings for all Position entities that don't have embeddings yet
  - Processes positions in batches for optimal performance

- **poliloom locations embed**

  - Generate embeddings for all Location entities that don't have embeddings yet
  - Processes locations in batches for optimal performance

- **poliloom positions import-csv**

  - CSV import functionality for positions data

- **poliloom serve [--host HOST] [--port PORT] [--reload]**
  - Start the FastAPI web server.

**Recommended Workflow:**

1. `poliloom dump download --output ./latest-all.json.bz2` - Download compressed dump (one-time, ~100GB compressed)
2. `poliloom dump extract --input ./latest-all.json.bz2 --output ./latest-all.json` - Extract to JSON (~1TB uncompressed)
3. `poliloom dump build-hierarchy --file ./latest-all.json` - Build hierarchy trees for positions and locations (one-time per dump)
4. `poliloom dump import-entities --file ./latest-all.json` - Import supporting entities (positions, locations, countries) to database
5. `poliloom dump import-politicians --file ./latest-all.json` - Import politicians and link to existing entities

**GCS Workflow Example:**

1. `poliloom dump download --output gs://my-bucket/dumps/latest-all.json.bz2` - Download to GCS
2. `poliloom dump extract --input gs://my-bucket/dumps/latest-all.json.bz2 --output gs://my-bucket/dumps/latest-all.json` - Extract in GCS
3. `poliloom dump build-hierarchy --file gs://my-bucket/dumps/latest-all.json` - Build hierarchy from GCS
4. `poliloom dump import-entities --file gs://my-bucket/dumps/latest-all.json` - Import from GCS
5. `poliloom dump import-politicians --file gs://my-bucket/dumps/latest-all.json` - Import politicians from GCS

## **5\. External Integrations**

- **Wikidata Dumps:** Primary data source via dump files (latest-all.json) for bulk entity extraction
- **Google Cloud Storage (GCS):** Storage and processing of large Wikidata dump files using gs:// paths
- **Wikidata API:** Minimal usage, only for updating Wikidata after user evaluation via GUI
- **MediaWiki OAuth 2.0:** For user authentication within the API using JWT tokens
- **OpenAI API:** For all LLM-based data extraction from web content
- **Wikipedia API:** For fetching article content during enrichment process

## **6\. Key Design Considerations**

- **Data Validation:** Implement robust data validation for all incoming data, especially from LLM extraction, before storing in the database.
- **Error Handling:** Implement comprehensive error handling and logging for all API calls and CLI operations.
- **Performance:** Optimize database queries and LLM interactions for performance, especially during bulk operations. Consider caching strategies where appropriate.
- **Scalability:** Design the API to be scalable for future increases in data volume and user load.
- **Conflicting Information:** Develop a clear strategy for handling conflicting data between sources. This might involve flagging conflicts for manual review or implementing a confidence scoring system.
- **Archiving Web Sources:** A decision needs to be made on whether to archive web sources (e.g., using a web archiving service or local storage) to ensure data provenance, or simply store URLs. For the initial proof of concept, storing URLs is sufficient.
- **Tool Run Frequency:** The design should support both infrequent, large-scale data imports and potentially more frequent, targeted enrichment runs.

## **7. Minimal Testing Implementation**

Implement essential testing using pytest with mocking for external APIs. Focus on the core data pipeline: import → extract → evaluate.

### **7.0. Testing Scope**

**What We Test:**

- **Entity Classes**: Entity identification, data extraction, truthy claim filtering, database dictionary generation
- **Factory Pattern**: Entity type detection, malformed data handling, proper entity instantiation
- **Database Models**: Entity relationships, constraints, cascade behavior, data integrity
- **External API Integration**: Wikidata dump processing and Wikipedia API calls (mocked)
- **Data Processing**: Property extraction, position handling, country import, date parsing
- **Error Handling**: Network failures, malformed data, database errors, edge cases

**What We Don't Test:**

- **CLI Interface**: Thin wrappers over service methods with minimal business logic
- **Database Migrations**: Alembic migrations are considered infrastructure
- **Logging and Metrics**: Non-critical for core functionality validation
- **Performance/Load Testing**: Beyond scope of minimal implementation
- **End-to-End Integration**: Real API calls to external services

This focused approach ensures robust testing of critical data pipeline components while maintaining development velocity.

### **7.1. Required Test Coverage**

- **Entity Classes**: WikidataPolitician, WikidataPosition, WikidataLocation, WikidataCountry classes with truthy filtering
- **Factory Pattern**: WikidataEntityFactory with various entity types and edge cases
- **Database Models**: Relationships, date handling, CRUD operations, Country model
- **Wikidata Dump Processing**: Mock dump file content, entity extraction, batch processing, error handling
- **LLM Extraction**: Mock OpenAI responses, property/position extraction, conflict detection
- **API Endpoints**: Both endpoints with auth mocking, error responses, pagination

### **7.2. Key Fixtures (conftest.py)**

- PostgreSQL test database (using docker-compose for CI/CD)
- Sample politician and country data
- Mock Wikidata dump file content (compressed JSON entities)
- Mock OpenAI structured extraction responses
- Sample Wikipedia content

**Priority**: Test the main data flow thoroughly. Mock dump file processing, OpenAI API, and MediaWiki OAuth. Handle incomplete dates, conflicting data, and processing failures.

### **7.3. Development Environment**

- **Docker Compose:** Used for running PostgreSQL locally during development
- **Database Setup:** Single PostgreSQL instance for both development and testing
- **Vector Extensions:** pgvector extension enabled for semantic similarity search
- **Simplified Architecture:** Removal of SQLite/PostgreSQL dual support reduces complexity and ensures consistent behavior across environments
