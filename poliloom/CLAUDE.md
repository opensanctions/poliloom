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
- **Development Database:** SQLite
- **Production Database:** PostgreSQL
- **LLM Integration:** OpenAI API (for structured data extraction)
- **External APIs:** Wikidata API, MediaWiki OAuth

**important** use the `uv` tool for running python commands and managing dependencies

## **3\. Database Schema**

The database will reproduce a subset of the Wikidata politician data model to store extracted information. The core entities and their relationships are as follows:

- **Politician**
  - id (Primary Key, e.g., Wikidata ID, internal UUID)
  - name (String)
  - wikidata_id (String, Wikidata QID)
  - is_deceased (Boolean, consideration for filtering)
- **Source**
  - id (Primary Key, e.g., URL hash, internal UUID)
  - url (String, URL of the source page)
  - extracted_at (Datetime)
- **Property**
  - id (Primary Key, internal UUID)
  - politician_id (Foreign Key to Politician.id)
  - type (String, e.g., 'BirthDate', 'BirthPlace', 'Citizenship')
  - value (String, for the extracted property value)
  - is_extracted (Boolean, True if newly extracted and unconfirmed)
  - confirmed_by (String, ID of user who confirmed, Null if unconfirmed)
  - confirmed_at (Datetime, Null if unconfirmed)
- **Position**
  - id (Primary Key, e.g., Wikidata QID, internal UUID)
  - name (String, name of the position)
  - country (String, ISO 3166-1 alpha-2 code where possible)
  - wikidata_id (String, Wikidata QID for the position)
- **HoldsPosition** (Many-to-many relationship entity)
  - id (Primary Key, internal UUID)
  - politician_id (Foreign Key to Politician.id)
  - position_id (Foreign Key to Position.id)
  - start_date (String, e.g., 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', allowing for incomplete dates)
  - end_date (String, e.g., 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', allowing for incomplete dates)
  - is_extracted (Boolean, True if newly extracted and unconfirmed)
  - confirmed_by (String, ID of user who confirmed, Null if unconfirmed)
  - confirmed_at (Datetime, Null if unconfirmed)
- **Association Tables:**
  - politician_source (for Politician to Source many-to-many)
  - property_source (for Property to Source many-to-many)
  - holdsposition_source (for HoldsPosition to Source many-to-many)

**Schema Considerations:**

- **Incomplete Dates:** The schema should accommodate incomplete birth dates and position held dates (e.g., '1962', 'JUN 1982'). Store these as strings.
- **Multilingual Names:** The Politician entity will store names as strings. Handling multilingual variations in names during extraction and matching will be crucial.
- **Citizenships:** Politician citizenships are stored as Property records with type='Citizenship'. Multiple citizenships are supported by creating multiple Property records.
- **Conflict Resolution:** conflict_resolved fields will be used to flag when discrepancies between extracted data and existing Wikidata values have been addressed.

## **4\. Core Functionality**

### **4.1. Data Import / Database Population**

This module is responsible for initially populating the local database with politician data.

- **Wikidata Querying:**
  - Utilize SPARQL queries to fetch Politician entities from Wikidata, primarily by occupation (Q82955) and position held (Q39486).
  - Implement pagination for large queries.
  - Fetch associated properties and positions directly from Wikidata for initial comparison.
  - Identify and store Wikidata IDs and English/local language Wikipedia URLs.
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
  - **Position Extraction Enhancement:** Before extracting positions, query Wikidata for political positions relevant to the politician's country to reduce LLM token usage and improve accuracy.
- **Similarity Search for Unlinked Entities:**
  - For random web pages, after extraction, perform a similarity search against existing Politician entities in the local database (e.g., based on name, country, birth date, birthplace) to find potential matches.
  - Establish a similarity score threshold to decide whether to propose an update or create a new entity.
- **Conflict Handling:**
  - Identify discrepancies between extracted data and existing Wikidata values.
  - Flag conflicting data for review in the GUI.

### **4.3. API Endpoints (FastAPI)**

The API will expose endpoints for the GUI to manage confirmation workflows. Authentication will leverage MediaWiki OAuth.

- **Authentication:**
  - Integrate with MediaWiki OAuth for user authentication and authorization.
  - Ensure secure handling of user tokens and permissions.
- **Routes:**

  - GET /politicians/unconfirmed

    - **Description:** Retrieves a list of Politician entities that have Property or HoldsPosition records marked as is_new=True (i.e., unconfirmed by a user).
    - **Parameters:**
      - limit (Optional, Integer): Maximum number of politicians to return.
      - offset (Optional, Integer): Offset for pagination.
    - **Response:** JSON array of Politician objects, each including their unconfirmed Property and HoldsPosition data.
    - **Example Response (Simplified):**  
      \[  
       {  
       "id": "politician_id_123",  
       "name": "John Doe",  
       "country": "US",  
       "unconfirmed_properties": \[  
       {"type": "BirthDate", "value": "1970-01-15", "source_url": "http://example.com/source1"},  
       {"type": "BirthPlace", "value": "New York, USA", "source_url": "http://example.com/source1"}  
       \],  
       "unconfirmed_positions": \[  
       {"position_name": "Mayor", "start_date": "2020", "end_date": "2024", "source_url": "http://example.com/source2"}  
       \]  
       },  
       ...  
      \]

  - POST /politicians/{politician_id}/confirm
    - **Description:** Allows a user to confirm the correctness of extracted properties and positions for a given politician. It also handles discarding specific properties/positions.
    - **Parameters:**
      - politician_id (Path Parameter, String): The ID of the politician being confirmed.
    - **Request Body (JSON):**
      - confirmed_properties (Array of Strings): List of Property.ids that the user confirms as correct.
      - discarded_properties (Array of Strings): List of Property.ids that the user marks as incorrect/to be discarded.
      - confirmed_positions (Array of Strings): List of HoldsPosition.ids that the user confirms as correct.
      - discarded_positions (Array of Strings): List of HoldsPosition.ids that the user marks as incorrect/to be discarded.
    - **Logic:**
      - For confirmed IDs: Update is_new to False, set confirmed_by and confirmed_at. Trigger an update to Wikidata if applicable.
      - For discarded IDs: Mark as discarded (e.g., set is_new to False and add a status field like discarded or soft-delete).
    - **Response:** JSON object indicating success or failure.
    - **Example Request Body:**  
      {  
       "confirmed_properties": \["prop_id_1", "prop_id_2"\],  
       "discarded_properties": \["prop_id_3"\],  
       "confirmed_positions": \["pos_id_1"\],  
       "discarded_positions": \[\]  
      }

### **4.4. CLI Commands**

The CLI will provide direct interaction for data management and enrichment tasks.

- poliloom import-wikidata \--id \<wikidata_id\>
  - **Description:** Imports a single politician entity from Wikidata based on its Wikidata ID.
  - **Functionality:** Queries Wikidata for the specified ID, extracts available properties and positions, and populates the local database. Fetches associated Wikipedia links.
- poliloom enrich-wikipedia \--id \<wikidata_id\>
  - **Description:** Enriches a single politician entity in the local database by extracting data from its linked Wikipedia articles.
  - **Functionality:** Fetches the Wikipedia content for the politician with the specified Wikidata ID, feeds it to the LLM for property and position extraction, and stores the new is_extracted=True data in the database.

## **5\. External Integrations**

- **Wikidata API:** Used for initial database population, querying political positions, and potentially updating Wikidata (after user confirmation via the GUI).
- **MediaWiki OAuth:** For user authentication within the API.
- **OpenAI API:** For all LLM-based data extraction from web content.

## **6\. Key Design Considerations**

- **Data Validation:** Implement robust data validation for all incoming data, especially from LLM extraction, before storing in the database.
- **Error Handling:** Implement comprehensive error handling and logging for all API calls and CLI operations.
- **Performance:** Optimize database queries and LLM interactions for performance, especially during bulk operations. Consider caching strategies where appropriate.
- **Scalability:** Design the API to be scalable for future increases in data volume and user load.
- **Conflicting Information:** Develop a clear strategy for handling conflicting data between sources. This might involve flagging conflicts for manual review or implementing a confidence scoring system.
- **Archiving Web Sources:** A decision needs to be made on whether to archive web sources (e.g., using a web archiving service or local storage) to ensure data provenance, or simply store URLs. For the initial proof of concept, storing URLs is sufficient.
- **Tool Run Frequency:** The design should support both infrequent, large-scale data imports and potentially more frequent, targeted enrichment runs.

## **7. Minimal Testing Implementation**

Implement essential testing using pytest with mocking for external APIs. Focus on the core data pipeline: import → extract → confirm.

### **7.1. Test Structure**

```
tests/
├── conftest.py              # Fixtures and test DB setup
├── test_models.py           # Database models and relationships
├── test_import.py           # Wikidata import with mocked responses
├── test_extraction.py       # LLM extraction with mocked OpenAI
├── test_api.py              # FastAPI endpoints
└── test_cli.py              # CLI commands
```

Keep fixtures in `tests/fixtures/`

### **7.2. Required Test Coverage**

- **Database Models**: Relationships, date handling, CRUD operations
- **Wikidata Import**: Mock SPARQL responses, entity creation, error handling
- **LLM Extraction**: Mock OpenAI responses, property/position extraction, conflict detection
- **API Endpoints**: Both endpoints with auth mocking, error responses, pagination
- **CLI Commands**: Both commands with success/failure cases

### **7.3. Key Fixtures (conftest.py)**

- In-memory SQLite test database
- Sample politician data
- Mock Wikidata SPARQL responses
- Mock OpenAI structured extraction responses
- Sample Wikipedia content

### **7.4. Testing Commands**

```bash
pytest --cov=poliloom --cov-fail-under=70
```

**Priority**: Test the main data flow thoroughly. Mock all external APIs (Wikidata, OpenAI, MediaWiki OAuth). Handle incomplete dates, conflicting data, and API failures.
