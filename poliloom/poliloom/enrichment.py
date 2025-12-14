"""Simplified enrichment module for extracting politician data from Wikipedia using LLM."""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Literal, Type, Union, Any
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator, create_model
from bs4 import BeautifulSoup
from dicttoxml import dicttoxml
from dataclasses import dataclass

from .page_fetcher import fetch_page


from .models import (
    Politician,
    Property,
    PropertyType,
    Position,
    Location,
    Country,
    ArchivedPage,
    WikidataRelation,
    WikidataEntity,
)
from . import archive
from .database import get_engine
from .search import SearchService
from .wikidata_date import WikidataDate
from . import prompts

logger = logging.getLogger(__name__)


def create_qualifiers_json_for_position(
    start_date: Optional[str], end_date: Optional[str]
) -> Optional[dict]:
    """Create qualifiers_json for a position with start and end dates using WikidataDate."""
    if not start_date and not end_date:
        return None

    qualifiers_json = {}

    # Add start date (P580)
    if start_date:
        wikidata_date = WikidataDate.from_date_string(start_date)
        if wikidata_date:
            qualifiers_json["P580"] = [wikidata_date.to_wikidata_qualifier()]

    # Add end date (P582)
    if end_date:
        wikidata_date = WikidataDate.from_date_string(end_date)
        if wikidata_date:
            qualifiers_json["P582"] = [wikidata_date.to_wikidata_qualifier()]

    return qualifiers_json if qualifiers_json else None


class ExtractedProperty(BaseModel):
    """Schema for extracted property data."""

    type: PropertyType
    value: str
    supporting_quotes: List[str]

    @field_validator("value")
    @classmethod
    def validate_date_value(cls, v: str) -> str:
        return WikidataDate.validate_date_format(v)


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""

    wikidata_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    supporting_quotes: List[str]

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return WikidataDate.validate_date_format(v)


class ExtractedBirthplace(BaseModel):
    """Schema for extracted birthplace data."""

    wikidata_id: str
    supporting_quotes: List[str]


class PropertyExtractionResult(BaseModel):
    """Response model for property extraction."""

    properties: Optional[List[ExtractedProperty]]


class FreeFormPosition(BaseModel):
    """Free-form position extracted before mapping to Wikidata."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    supporting_quotes: List[str]

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return WikidataDate.validate_date_format(v)


class FreeFormPositionResult(BaseModel):
    """Response model for free-form position extraction."""

    positions: Optional[List[FreeFormPosition]]


class FreeFormBirthplace(BaseModel):
    """Free-form birthplace extracted before mapping to Wikidata."""

    name: str
    supporting_quotes: List[str]


class FreeFormBirthplaceResult(BaseModel):
    """Response model for free-form birthplace extraction."""

    birthplaces: Optional[List[FreeFormBirthplace]]


class FreeFormCitizenship(BaseModel):
    """Free-form citizenship extracted before mapping to Wikidata."""

    name: str
    supporting_quotes: List[str]


class FreeFormCitizenshipResult(BaseModel):
    """Response model for free-form citizenship extraction."""

    citizenships: Optional[List[FreeFormCitizenship]]


class ExtractedCitizenship(BaseModel):
    """Schema for extracted citizenship data."""

    wikidata_id: str
    supporting_quotes: List[str]


@dataclass
class ExtractionConfig:
    """Base configuration for property extraction."""

    property_types: List[PropertyType]
    system_prompt: str
    result_model: Type[BaseModel]
    user_prompt_template: str
    analysis_focus_template: str
    result_field_name: str = "properties"  # Field name in result model


@dataclass
class TwoStageExtractionConfig(ExtractionConfig):
    """Configuration for two-stage extraction (free-form -> mapping)."""

    entity_class: Type[Union[Position, Location, Country]] = None
    mapping_system_prompt: str = ""  # System prompt for mapping stage
    final_model: Type[BaseModel] = None
    search_limit: int = 100  # Number of candidates to retrieve for mapping


async def extract_properties_generic(
    openai_client: AsyncOpenAI,
    content: str,
    politician: Politician,
    config: ExtractionConfig,
) -> Optional[List[Any]]:
    """Generic property extraction using provided configuration."""
    try:
        # Build comprehensive politician context
        politician_context = politician.to_xml_context(
            focus_property_types=config.property_types,
        )

        # Build analysis focus if politician has existing properties
        analysis_focus = ""
        existing_properties = politician.get_properties_by_types(config.property_types)

        if existing_properties:
            analysis_focus = config.analysis_focus_template

        user_prompt = config.user_prompt_template.format(
            politician_name=politician.name,
            politician_context=politician_context,
            analysis_focus=analysis_focus,
            content=content,
        )

        logger.debug(f"Extracting {config.property_types} for {politician.name}")

        response = await openai_client.responses.parse(
            model="gpt-5",
            input=[
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=config.result_model,
            reasoning={"effort": "minimal"},
        )

        if response.output_parsed is None:
            logger.error(f"OpenAI extraction returned None for {config.property_types}")
            return None

        return getattr(response.output_parsed, config.result_field_name)

    except Exception as e:
        logger.error(f"Error extracting {config.property_types} with LLM: {e}")
        return None


async def _map_single_item(
    openai_client: AsyncOpenAI,
    db: Session,
    free_item: Any,
    politician: Politician,
    config: TwoStageExtractionConfig,
    search_service: SearchService,
) -> Optional[Any]:
    """Helper function to map a single free-form item to Wikidata entity.

    Args:
        openai_client: Async OpenAI client
        db: Database session
        free_item: Free-form extracted item
        politician: Politician being enriched
        config: Extraction configuration
        search_service: SearchService for entity lookup
    """
    try:
        # Entity class handles routing to appropriate backend via find_similar
        entity_ids = config.entity_class.find_similar(
            free_item.name, search_service, limit=config.search_limit
        )

        if not entity_ids:
            logger.debug(
                f"No similar {config.entity_class.MAPPING_ENTITY_NAME}s found for '{free_item.name}'"
            )
            return None

        # Query the entities with full data
        similar_entities = (
            db.query(config.entity_class)
            .join(
                WikidataEntity,
                config.entity_class.wikidata_id == WikidataEntity.wikidata_id,
            )
            .filter(config.entity_class.wikidata_id.in_(entity_ids))
            .filter(WikidataEntity.deleted_at.is_(None))
            .options(
                selectinload(config.entity_class.wikidata_entity)
                .selectinload(WikidataEntity.parent_relations)
                .selectinload(WikidataRelation.parent_entity)
            )
            .all()
        )

        if not similar_entities:
            logger.debug(
                f"No similar {config.entity_class.MAPPING_ENTITY_NAME}s found for '{free_item.name}'"
            )
            return None

        # Use LLM to map to correct entity
        candidate_entities = [
            {
                "qid": entity.wikidata_id,
                "name": entity.name,
                "description": entity.description,
            }
            for entity in similar_entities
        ]

        mapped_qid = await map_to_wikidata_entity(
            openai_client,
            free_item.name,
            free_item.supporting_quotes,
            candidate_entities,
            politician,
            config.entity_class.MAPPING_ENTITY_NAME,
            config.mapping_system_prompt,
        )

        if not mapped_qid:
            return None

        # Verify entity exists in database
        entity = db.query(config.entity_class).filter_by(wikidata_id=mapped_qid).first()
        if not entity:
            return None

        # Create result based on entity type
        if config.entity_class.MAPPING_ENTITY_NAME == "position":
            result = ExtractedPosition(
                wikidata_id=entity.wikidata_id,
                start_date=getattr(free_item, "start_date", None),
                end_date=getattr(free_item, "end_date", None),
                supporting_quotes=free_item.supporting_quotes,
            )
        elif config.entity_class.MAPPING_ENTITY_NAME == "location":
            result = ExtractedBirthplace(
                wikidata_id=entity.wikidata_id,
                supporting_quotes=free_item.supporting_quotes,
            )
        else:  # country
            result = ExtractedCitizenship(
                wikidata_id=entity.wikidata_id,
                supporting_quotes=free_item.supporting_quotes,
            )

        logger.debug(f"Mapped '{free_item.name}' -> '{entity.name}' ({mapped_qid})")
        return result

    except Exception as e:
        logger.error(
            f"Error mapping single {config.entity_class.MAPPING_ENTITY_NAME}: {e}"
        )
        return None


async def extract_two_stage_generic(
    openai_client: AsyncOpenAI,
    db: Session,
    content: str,
    politician: Politician,
    config: TwoStageExtractionConfig,
) -> Optional[List[Any]]:
    """Generic two-stage extraction (free-form -> mapping).

    Args:
        openai_client: Async OpenAI client
        db: Database session
        content: Text content to extract from
        politician: Politician being enriched
        config: Extraction configuration
    """
    search_service = SearchService()

    try:
        # Stage 1: Free-form extraction
        free_form_results = await extract_properties_generic(
            openai_client, content, politician, config
        )

        if not free_form_results:
            logger.info(
                f"No {config.entity_class.MAPPING_ENTITY_NAME}s extracted for {politician.name}"
            )
            return []

        logger.info(
            f"Stage 1: Extracted {len(free_form_results)} free-form {config.entity_class.MAPPING_ENTITY_NAME}s for {politician.name}"
        )

        # Stage 2: Map to Wikidata entities in parallel
        mapping_tasks = [
            _map_single_item(
                openai_client,
                db,
                free_item,
                politician,
                config,
                search_service,
            )
            for free_item in free_form_results
        ]

        mapping_results = await asyncio.gather(*mapping_tasks)

        # Filter out None results
        mapped_results = [result for result in mapping_results if result is not None]

        logger.info(
            f"Stage 2: Mapped {len(mapped_results)} of {len(free_form_results)} {config.entity_class.MAPPING_ENTITY_NAME}s for {politician.name}"
        )
        return mapped_results

    except Exception as e:
        logger.error(
            f"Error extracting {config.entity_class.MAPPING_ENTITY_NAME}s: {e}"
        )
        return None


async def map_to_wikidata_entity(
    openai_client: AsyncOpenAI,
    extracted_name: str,
    supporting_quotes: List[str],
    candidate_entities: List[dict],
    politician: Politician,
    entity_type: str,
    system_prompt: str,
) -> Optional[str]:
    """Generic mapping function for positions and locations."""
    try:
        # Create dynamic model with candidate entity QIDs
        entity_qids = [
            entity["qid"] for entity in candidate_entities if entity.get("qid")
        ]
        EntityQidType = Optional[Literal[tuple(entity_qids)]]

        field_name = f"wikidata_{entity_type}_qid"
        DynamicMappingResult = create_model(
            f"{entity_type.title()}MappingResult", **{field_name: (EntityQidType, None)}
        )

        # Format candidates with XML structure and rich descriptions
        candidates_xml = dicttoxml(
            candidate_entities,
            custom_root="candidates",
            item_func=lambda x: "entity",
            attr_type=False,
            xml_declaration=False,
        )
        candidates_text = candidates_xml.decode("utf-8")

        # Build politician context for stage 2 mapping
        politician_context = politician.to_xml_context()

        # Format supporting quotes as bulleted list
        quotes_text = "\n".join(f'- "{quote}"' for quote in supporting_quotes)

        user_prompt = f"""Map this extracted {entity_type} to the correct Wikidata {entity_type}:

{politician_context}

Extracted {entity_type.title()}: "{extracted_name}"
Supporting Evidence:
{quotes_text}

Candidate Wikidata {entity_type.title()}s:
{candidates_text}

Select the best matching QID or None if no good match exists."""

        response = await openai_client.responses.parse(
            model="gpt-5",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=DynamicMappingResult,
            reasoning={"effort": "minimal"},
        )

        if response.output_parsed is None:
            return None

        return getattr(response.output_parsed, field_name)

    except Exception as e:
        logger.error(f"Error mapping {entity_type} with LLM: {e}")
        return None


def extract_permanent_url(html_content: str) -> Optional[str]:
    """Extract Wikipedia permanent URL with oldid from HTML content.

    Uses the Wikipedia sidebar's permanent link element (id="t-permalink") to extract
    the canonical permanent URL. This handles redirects correctly since the permanent
    link always points to the actual page revision being viewed.

    Args:
        html_content: The HTML content to search

    Returns:
        The permanent URL with oldid (e.g., "https://en.wikipedia.org/w/index.php?title=Page&oldid=123456789"),
        or None if not found
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        permalink_element = soup.find(id="t-permalink")

        if not permalink_element:
            logger.debug("No t-permalink element found in HTML")
            return None

        anchor = permalink_element.find("a")
        if not anchor or not anchor.get("href"):
            logger.debug("No anchor with href found in t-permalink element")
            return None

        permanent_url = anchor["href"]
        logger.debug(f"Found permanent URL via t-permalink: {permanent_url}")
        return permanent_url

    except Exception as e:
        logger.warning(f"Error extracting permanent URL: {e}")
        return None


async def fetch_and_archive_page(
    url: str,
    db: Session,
    wikipedia_project_id: Optional[str] = None,
) -> ArchivedPage:
    """Fetch web page content and archive it.

    Stores HTML and MHTML content. When a Wikipedia project ID is provided,
    also extracts the permanent URL with oldid and links languages from the project.

    Args:
        url: The URL to fetch and archive
        db: Database session
        wikipedia_project_id: Optional Wikipedia project Wikidata ID. When provided,
            extracts the permanent URL with oldid and links languages from the project.

    Returns:
        ArchivedPage with archived content (HTML, MHTML)

    Raises:
        PageFetchError: If the page cannot be fetched (timeout, network error, HTTP error)
    """
    now = datetime.now(timezone.utc)

    # Fetch the page content
    fetched = await fetch_page(url)

    # Extract permanent URL for Wikipedia pages (used in references)
    permanent_url = None
    if wikipedia_project_id and fetched.html:
        permanent_url = extract_permanent_url(fetched.html)
        if permanent_url:
            logger.info(f"Extracted permanent URL: {permanent_url}")

    # Create ArchivedPage record with original URL for display
    archived_page = ArchivedPage(
        url=url,
        permanent_url=permanent_url,
        fetch_timestamp=now,
        wikipedia_project_id=wikipedia_project_id,
    )
    db.add(archived_page)
    db.flush()

    # Link languages from Wikipedia project
    archived_page.link_languages_from_project(db)
    db.flush()

    # Save all content files
    archived_page.save_archived_files(fetched.mhtml, fetched.html)

    return archived_page


# Configuration instances for different extraction types
DATES_CONFIG = ExtractionConfig(
    property_types=[PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE],
    system_prompt=prompts.DATES_EXTRACTION_SYSTEM_PROMPT,
    result_model=PropertyExtractionResult,
    user_prompt_template=prompts.EXTRACTION_USER_PROMPT_TEMPLATE,
    analysis_focus_template=prompts.DATES_ANALYSIS_FOCUS_TEMPLATE,
)

POSITIONS_CONFIG = TwoStageExtractionConfig(
    property_types=[PropertyType.POSITION],
    system_prompt=prompts.POSITIONS_EXTRACTION_SYSTEM_PROMPT,
    result_model=FreeFormPositionResult,
    user_prompt_template=prompts.POSITIONS_USER_PROMPT_TEMPLATE,
    analysis_focus_template=prompts.POSITIONS_ANALYSIS_FOCUS_TEMPLATE,
    result_field_name="positions",
    entity_class=Position,
    mapping_system_prompt=prompts.POSITION_MAPPING_SYSTEM_PROMPT,
    final_model=ExtractedPosition,
    search_limit=100,
)

BIRTHPLACES_CONFIG = TwoStageExtractionConfig(
    property_types=[PropertyType.BIRTHPLACE],
    system_prompt=prompts.BIRTHPLACES_EXTRACTION_SYSTEM_PROMPT,
    result_model=FreeFormBirthplaceResult,
    user_prompt_template=prompts.BIRTHPLACES_USER_PROMPT_TEMPLATE,
    analysis_focus_template=prompts.BIRTHPLACES_ANALYSIS_FOCUS_TEMPLATE,
    result_field_name="birthplaces",
    entity_class=Location,
    mapping_system_prompt=prompts.LOCATION_MAPPING_SYSTEM_PROMPT,
    final_model=ExtractedBirthplace,
    search_limit=100,
)

CITIZENSHIPS_CONFIG = TwoStageExtractionConfig(
    property_types=[PropertyType.CITIZENSHIP],
    system_prompt=prompts.CITIZENSHIPS_EXTRACTION_SYSTEM_PROMPT,
    result_model=FreeFormCitizenshipResult,
    user_prompt_template=prompts.CITIZENSHIPS_USER_PROMPT_TEMPLATE,
    analysis_focus_template=prompts.CITIZENSHIPS_ANALYSIS_FOCUS_TEMPLATE,
    result_field_name="citizenships",
    entity_class=Country,
    mapping_system_prompt=prompts.COUNTRY_MAPPING_SYSTEM_PROMPT,
    final_model=ExtractedCitizenship,
    search_limit=25,
)


def count_politicians_with_unevaluated(
    db: Session,
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
) -> int:
    """
    Count politicians that have unevaluated extracted properties.

    Args:
        db: Database session
        languages: Optional list of language QIDs to filter by
        countries: Optional list of country QIDs to filter by

    Returns:
        Number of politicians with unevaluated properties matching filters
    """
    # Build composable query using filter methods
    politician_ids_query = Politician.query_base()

    politician_ids_query = Politician.filter_by_unevaluated_properties(
        politician_ids_query, languages=languages
    )

    if countries:
        politician_ids_query = Politician.filter_by_countries(
            politician_ids_query, countries
        )

    # Count the results
    count_query = select(func.count()).select_from(politician_ids_query.subquery())
    result = db.execute(count_query).scalar()
    return result or 0


def has_enrichable_politicians(
    db: Session,
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
) -> bool:
    """
    Check if there are politicians available to enrich.

    Uses the same query logic as enrich_politician_from_wikipedia to determine
    if any politicians can be enriched (not enriched within last 6 months).

    Args:
        db: Database session
        languages: Optional list of language QIDs to filter by
        countries: Optional list of country QIDs to filter by
        stateless: If True, check for politicians without citizenship data

    Returns:
        True if there are politicians available to enrich, False otherwise
    """
    query = Politician.query_for_enrichment(
        languages=languages,
        countries=countries,
        stateless=stateless,
    ).limit(1)

    result = db.execute(query).first()
    return result is not None


def enrich_batch(
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
) -> int:
    """
    Enrich a batch of politicians based on ENRICHMENT_BATCH_SIZE env var.

    This function is synchronous and uses asyncio.run() to call async enrichment functions.
    It's designed to be run in a ThreadPoolExecutor to avoid blocking API workers.

    Args:
        languages: Optional list of language QIDs to filter by
        countries: Optional list of country QIDs to filter by
        stateless: If True, only enrich politicians without citizenship data

    Returns:
        Number of politicians successfully enriched during this run
    """
    batch_size = int(os.getenv("ENRICHMENT_BATCH_SIZE", "5"))
    enriched_count = 0

    logger.info(f"Starting enrichment batch of {batch_size} politicians")

    for i in range(batch_size):
        # Enrich one politician - run async function in new event loop
        politician_found = asyncio.run(
            enrich_politician_from_wikipedia(
                languages=languages, countries=countries, stateless=stateless
            )
        )

        if not politician_found:
            # No more politicians to enrich
            logger.info("No more politicians available to enrich")
            break

        enriched_count += 1

    logger.info(
        f"Enrichment batch complete: {enriched_count}/{batch_size} politicians enriched"
    )
    return enriched_count


async def _fetch_and_extract_from_page(
    openai_client: AsyncOpenAI,
    db: Session,
    politician: Politician,
    url: str,
    wikipedia_project_id: str,
) -> tuple[bool, int, int, int, int]:
    """
    Fetch a web page, archive it, and extract politician data from it.

    Args:
        openai_client: OpenAI async client
        db: Database session
        politician: Politician to enrich
        url: Web page URL
        wikipedia_project_id: Wikipedia project Wikidata ID for language linking

    Returns:
        Tuple of (success, date_count, position_count, birthplace_count, citizenship_count)
    """
    try:
        logger.info(f"Processing source: {url}")

        # Fetch and archive the page
        archived_page = await fetch_and_archive_page(url, db, wikipedia_project_id)

        # Read content from archived page
        html_content = archive.read_archived_content(archived_page.path_root, "html")

        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text()
        content = " ".join(text.split())

        # Extract data from this specific source in parallel
        (
            date_properties,
            positions,
            birthplaces,
            citizenships,
        ) = await asyncio.gather(
            extract_properties_generic(
                openai_client, content, politician, DATES_CONFIG
            ),
            extract_two_stage_generic(
                openai_client, db, content, politician, POSITIONS_CONFIG
            ),
            extract_two_stage_generic(
                openai_client, db, content, politician, BIRTHPLACES_CONFIG
            ),
            extract_two_stage_generic(
                openai_client, db, content, politician, CITIZENSHIPS_CONFIG
            ),
        )

        # Store extracted data for this specific source
        success = store_extracted_data(
            db,
            politician,
            archived_page,
            date_properties,
            positions,
            birthplaces,
            citizenships,
        )

        if success:
            # Count what was extracted from this source
            date_count = len(date_properties) if date_properties else 0
            position_count = len(positions) if positions else 0
            birthplace_count = len(birthplaces) if birthplaces else 0
            citizenship_count = len(citizenships) if citizenships else 0

            source_total = (
                date_count + position_count + birthplace_count + citizenship_count
            )
            logger.info(
                f"Extracted {source_total} items from {url} "
                f"({date_count} dates, {position_count} positions, {birthplace_count} birthplaces, {citizenship_count} citizenships)"
            )
            return True, date_count, position_count, birthplace_count, citizenship_count
        else:
            logger.warning(
                f"Failed to store extracted data from {url} for {politician.name}"
            )
            return False, 0, 0, 0, 0

    except Exception as e:
        logger.error(f"Error processing page {url}: {e}")
        return False, 0, 0, 0, 0


async def enrich_politician_from_wikipedia(
    languages: Optional[List[str]] = None,
    countries: Optional[List[str]] = None,
    stateless: bool = False,
) -> bool:
    """
    Enrich a single politician's data by extracting information from their Wikipedia sources.

    Processes multiple Wikipedia articles concurrently based on politician's
    citizenship and official languages of their countries, prioritized by Wikipedia
    link popularity.

    Uses FOR UPDATE SKIP LOCKED to prevent concurrent processes from enriching
    the same politician.

    Args:
        languages: Optional list of language QIDs to filter by
        countries: Optional list of country QIDs to filter by
        stateless: If True, only enrich politicians without citizenship data

    Returns:
        True if a politician was found and enriched (successfully or not), False if no politician available
    """

    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with Session(get_engine()) as db:
        # Build query for enrichment candidates
        # All filters (including enriched_at) are in the same query that gets the lock,
        # preventing race conditions where a politician is selected after being enriched
        # by another concurrent process.
        #
        # Ordering strategy:
        # 1. NULL enriched_at first (never enriched)
        # 2. Among NULL, higher QID numbers first (newer politicians)
        # 3. Then by enriched_at ascending (oldest enrichment first)
        # This ensures we enrich all politicians once before re-enriching any
        #
        # Use FOR UPDATE SKIP LOCKED to prevent concurrent processes from
        # selecting the same politician
        query = (
            Politician.query_for_enrichment(
                languages=languages,
                countries=countries,
                stateless=stateless,
            )
            .options(
                # Load the politician's wikidata entity
                selectinload(Politician.wikidata_entity),
                # Load all properties with their related entities and relations
                selectinload(Politician.properties)
                .selectinload(Property.entity)
                .selectinload(WikidataEntity.parent_relations)
                .selectinload(WikidataRelation.parent_entity),
                # Load Wikipedia links
                selectinload(Politician.wikipedia_links),
            )
            .order_by(
                Politician.enriched_at.asc().nullsfirst(),
                Politician.wikidata_id_numeric.desc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        politician = db.scalars(query).first()

        if not politician:
            return False

        try:
            # Get priority Wikipedia links based on citizenship and language popularity
            priority_links = politician.get_priority_wikipedia_links(db)

            if not priority_links:
                raise ValueError(
                    f"No suitable Wikipedia links found for politician {politician.name}"
                )

            logger.info(
                f"Processing {len(priority_links)} Wikipedia sources for {politician.name}: "
                f"{[f'{wikipedia_project_id} ({url})' for url, wikipedia_project_id in priority_links]}"
            )

            # Process all pages concurrently
            page_tasks = [
                _fetch_and_extract_from_page(
                    openai_client, db, politician, url, wikipedia_project_id
                )
                for url, wikipedia_project_id in priority_links
            ]

            page_results = await asyncio.gather(*page_tasks)

            # Aggregate results from all pages
            total_dates = 0
            total_positions = 0
            total_birthplaces = 0
            total_citizenships = 0
            processed_sources = 0

            for (
                success,
                date_count,
                position_count,
                birthplace_count,
                citizenship_count,
            ) in page_results:
                if success:
                    total_dates += date_count
                    total_positions += position_count
                    total_birthplaces += birthplace_count
                    total_citizenships += citizenship_count
                    processed_sources += 1

            # Final summary
            grand_total = (
                total_dates + total_positions + total_birthplaces + total_citizenships
            )
            logger.info(
                f"Successfully enriched {politician.name} ({politician.wikidata_id}) from {processed_sources}/{len(priority_links)} sources: "
                f"{grand_total} total items ({total_dates} dates, {total_positions} positions, {total_birthplaces} birthplaces, {total_citizenships} citizenships)"
            )

            # Update enriched_at and commit all changes atomically
            # This includes: ArchivedPages, Properties, and enriched_at timestamp
            # The FOR UPDATE lock is held until this commit
            politician.enriched_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            logger.error(f"Error enriching politician {politician.wikidata_id}: {e}")
            # Rollback failed enrichment, then set enriched_at to prevent infinite retries
            db.rollback()
            politician.enriched_at = datetime.now(timezone.utc)
            db.commit()

        finally:
            # Close the OpenAI client to prevent event loop cleanup errors
            await openai_client.close()

        return True


def store_extracted_data(
    db: Session,
    politician: Politician,
    archived_page: ArchivedPage,
    properties: Optional[List[ExtractedProperty]],
    positions: Optional[List[ExtractedPosition]],
    birthplaces: Optional[List[ExtractedBirthplace]],
    citizenships: Optional[List[ExtractedCitizenship]],
) -> bool:
    """Store extracted data in the database."""
    try:
        # Store value properties (dates)
        if properties:
            for property_data in properties:
                # Convert date string to WikidataDate and store the time_string
                wikidata_date = WikidataDate.from_date_string(property_data.value)

                new_property = Property(
                    politician_id=politician.id,
                    type=property_data.type,
                    value=wikidata_date.time_string,
                    value_precision=wikidata_date.precision,
                    qualifiers_json=None,  # For extracted dates, no qualifiers initially
                    references_json=archived_page.create_references_json(),
                    archived_page_id=archived_page.id,
                    supporting_quotes=property_data.supporting_quotes,
                )

                if new_property.should_store(db):
                    db.add(new_property)
                    db.flush()
                    logger.info(
                        f"Added new property: {property_data.type} = '{property_data.value}' for {politician.name}"
                    )

        # Store entity-linked properties
        entity_configs = [
            (positions, PropertyType.POSITION, Position, "position"),
            (birthplaces, PropertyType.BIRTHPLACE, Location, "birthplace"),
            (citizenships, PropertyType.CITIZENSHIP, Country, "citizenship"),
        ]

        for extracted_data, property_type, entity_class, entity_name in entity_configs:
            if extracted_data:
                for item_data in extracted_data:
                    if item_data.wikidata_id:
                        entity = (
                            db.query(entity_class)
                            .filter_by(wikidata_id=item_data.wikidata_id)
                            .first()
                        )

                        # Create qualifiers for positions with dates
                        qualifiers_json = None
                        if property_type == PropertyType.POSITION:
                            qualifiers_json = create_qualifiers_json_for_position(
                                getattr(item_data, "start_date", None),
                                getattr(item_data, "end_date", None),
                            )

                        new_property = Property(
                            politician_id=politician.id,
                            type=property_type,
                            entity_id=entity.wikidata_id,
                            qualifiers_json=qualifiers_json,
                            references_json=archived_page.create_references_json(),
                            archived_page_id=archived_page.id,
                            supporting_quotes=item_data.supporting_quotes,
                        )

                        if new_property.should_store(db):
                            db.add(new_property)
                            db.flush()
                            logger.info(
                                f"Added new {entity_name}: '{entity.name}' ({entity.wikidata_id}) for {politician.name}"
                            )

        return True

    except Exception as e:
        logger.error(f"Error storing extracted data: {e}")
        return False
