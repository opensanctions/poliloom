# **PoliLoom API/CLI Project Specification**

This document outlines the requirements and design for the API and Command Line Interface (CLI) components of the PoliLoom project. The primary goal of this project is to extract metadata on politicians from Wikipedia and other web sources to enrich Wikidata, providing a usable proof of concept. This specification will guide the development of the backend services and data processing functionalities.

## **1\. Project Goals and Scope**

This API and CLI project is responsible for:

- Populating a local database with politician data from Wikidata and Wikipedia.
- Extracting new properties (e.g., date of birth, birthplace) and political positions from web sources using Large Language Models (LLMs).
- Providing an API for a separate GUI project to interact with the extracted data, specifically for confirmation workflows.
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
- **External APIs:** Wikidata API, MediaWiki OAuth

**important** use the `uv` tool for running python commands and managing dependencies

## **3\. Database Schema**

The database reproduces a subset of the Wikidata politician data model to store extracted information. 

**To view the current database schema, run:** `PGPASSWORD=postgres pg_dump -h localhost -p 5432 -U postgres -d poliloom --schema-only`

**Schema Considerations:**

- **Incomplete Dates:** The schema should accommodate incomplete birth dates and position held dates (e.g., '1962', 'JUN 1982'). Store these as strings.
- **Multilingual Names:** The Politician entity will store names as strings. Handling multilingual variations in names during extraction and matching will be crucial.
- **Citizenships:** Politician citizenships are stored as HasCitizenship records linking politicians to countries. Multiple citizenships are supported by creating multiple HasCitizenship records. Citizenships are only imported from Wikidata and do not require user confirmation.
- **Conflict Resolution:** conflict_resolved fields will be used to flag when discrepancies between extracted data and existing Wikidata values have been addressed.
- **Embedding Workflow:** Position and Location entities have optional embedding fields that are initially NULL during import. Embeddings are generated separately using dedicated CLI commands (`poliloom positions embed` and `poliloom locations embed`) that process all entities without embeddings in batch for optimal performance.

## **4\. Core Functionality**

### **4.1. Data Import / Database Population**

This module is responsible for initially populating the local database with politician data.

- **Wikidata Querying:**
  - Utilize SPARQL queries to fetch Politician entities from Wikidata, primarily by occupation (Q82955) and position held (Q39486).
  - Implement pagination for large queries.
  - Fetch associated properties and positions directly from Wikidata for initial comparison.
  - Identify and store Wikidata IDs and English/local language Wikipedia URLs.
- **Country Data Handling:**
  - Countries are created on-demand when referenced during politician import or data extraction.
  - Use pycountry library to resolve ISO codes to country names and validate country data.
- **Position Data Handling:**
  - During politician import, only link politicians to positions that already exist in the database.
  - Do not create new Position entities during politician import - positions should be imported separately or through dedicated position import functionality.
  - This ensures we only work with positions that have been explicitly imported and are known to the system.
- **Location Data Handling:**
  - During politician import, only link politicians to locations (birthplaces) that already exist in the database.
  - Do not create new Location entities during politician import - locations should be imported separately or through dedicated location import functionality.
  - This ensures we only work with locations that have been explicitly imported and are known to the system.
- **Wikipedia Linkage:**
  - Connect Wikidata entities to their corresponding English and local language Wikipedia articles.
  - Prioritize existing links from Wikidata.
  - Handle cases where Wikidata entities lack Wikipedia links or Wikipedia articles lack Wikidata entries.
- **Deceased People Filtering (Optional/Configurable):**
  - Provide a mechanism to filter out deceased politicians, possibly through Wikidata property (P570: date of death) or rule-based filtering on Wikipedia categories/keywords.

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

The API will expose endpoints for the GUI to manage confirmation workflows. Authentication will leverage MediaWiki OAuth.

- **Authentication:**
  - Integrate with MediaWiki OAuth 2.0 for user authentication and authorization.
  - Accept JWT tokens from MediaWiki OAuth 2.0 flow in Authorization header (Bearer format).
  - Verify JWT token signatures using MediaWiki's public keys or token introspection endpoint.
  - Ensure secure handling of user tokens and permissions.

- **OpenAPI Documentation**: The complete API specification is available at `http://localhost:8000/openapi.json` when the backend server is running. To fetch it using curl:

```bash
curl http://localhost:8000/openapi.json
```

### **4.4. CLI Commands**

- **poliloom politicians import --id \<wikidata_id\>**

  - Imports a single politician entity from Wikidata based on its Wikidata ID.

- **poliloom politicians enrich --id \<wikidata_id\>**

  - Enriches a single politician entity by extracting data from its linked Wikipedia articles using LLMs.

- **poliloom politicians show --id \<wikidata_id\>**

  - Display comprehensive information about a politician, distinguishing between imported and extracted data.

- **poliloom positions import**

  - Import all political positions from Wikidata to populate the local Position table.

- **poliloom positions import-csv --file \<csv_file\>**

  - Import political positions from a custom CSV file.

- **poliloom positions embed**

  - Generate embeddings for all positions that don't have embeddings yet. Uses GPU if available.

- **poliloom locations import**

  - Import all geographic locations from Wikidata to populate the local Location table.

- **poliloom locations embed**

  - Generate embeddings for all locations that don't have embeddings yet. Uses GPU if available.

- **poliloom serve [--host HOST] [--port PORT] [--reload]**
  - Start the FastAPI web server.

- **poliloom database truncate [--all] [--table TABLE] [--yes]**
  - Truncate database tables while preserving schema.

## **5\. External Integrations**

- **Wikidata API:** Used for initial database population, querying political positions and geographic locations, and potentially updating Wikidata (after user confirmation via the GUI).
- **MediaWiki OAuth 2.0:** For user authentication within the API using JWT tokens.
- **OpenAI API:** For all LLM-based data extraction from web content.

## **6\. Key Design Considerations**

- **Data Validation:** Implement robust data validation for all incoming data, especially from LLM extraction, before storing in the database.
- **Error Handling:** Implement comprehensive error handling and logging for all API calls and CLI operations.
- **Performance:** Optimize database queries and LLM interactions for performance, especially during bulk operations. Consider caching strategies where appropriate. Embedding generation is performed separately from import operations using dedicated commands that leverage GPU acceleration when available.
- **Scalability:** Design the API to be scalable for future increases in data volume and user load.
- **Conflicting Information:** Develop a clear strategy for handling conflicting data between sources. This might involve flagging conflicts for manual review or implementing a confidence scoring system.
- **Archiving Web Sources:** A decision needs to be made on whether to archive web sources (e.g., using a web archiving service or local storage) to ensure data provenance, or simply store URLs. For the initial proof of concept, storing URLs is sufficient.
- **Tool Run Frequency:** The design should support both infrequent, large-scale data imports and potentially more frequent, targeted enrichment runs.

## **7. Minimal Testing Implementation**

Implement essential testing using pytest with mocking for external APIs. Focus on the core data pipeline: import → extract → confirm.

### **7.0. Testing Scope**

**What We Test:**

- **Core Business Logic**: All service layer methods (import, extraction, enrichment)
- **Database Models**: Entity relationships, constraints, cascade behavior, data integrity
- **External API Integration**: Wikidata SPARQL queries and entity API calls (mocked)
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

- **Database Models**: Relationships, date handling, CRUD operations, Country model
- **Wikidata Import**: Mock SPARQL responses, entity creation, error handling
- **LLM Extraction**: Mock OpenAI responses, property/position extraction, conflict detection
- **API Endpoints**: Both endpoints with auth mocking, error responses, pagination

### **7.2. Key Fixtures (conftest.py)**

- PostgreSQL test database (using docker-compose for CI/CD)
- Sample politician and country data
- Mock Wikidata SPARQL responses (politicians)
- Mock OpenAI structured extraction responses
- Sample Wikipedia content

**Priority**: Test the main data flow thoroughly. Mock all external APIs (Wikidata, OpenAI, MediaWiki OAuth). Handle incomplete dates, conflicting data, and API failures.

### **7.3. Development Environment**

- **Docker Compose:** Used for running PostgreSQL locally during development
- **Database Setup:** Single PostgreSQL instance for both development and testing
- **Vector Extensions:** pgvector extension enabled for semantic similarity search
- **Simplified Architecture:** Removal of SQLite/PostgreSQL dual support reduces complexity and ensures consistent behavior across environments
