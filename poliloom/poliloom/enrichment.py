"""Simplified enrichment module for extracting politician data from Wikipedia using LLM."""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Literal, Type, Union, Any
from sqlalchemy.orm import Session, selectinload
from openai import OpenAI
from pydantic import BaseModel, field_validator, create_model
from unmhtml import MHTMLConverter
from bs4 import BeautifulSoup
from dicttoxml import dicttoxml
from dataclasses import dataclass


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
from .embeddings import generate_embedding
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
    proof: str

    @field_validator("value")
    @classmethod
    def validate_date_value(cls, v: str) -> str:
        return WikidataDate.validate_date_format(v)


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""

    wikidata_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return WikidataDate.validate_date_format(v)


class ExtractedBirthplace(BaseModel):
    """Schema for extracted birthplace data."""

    wikidata_id: str
    proof: str


class PropertyExtractionResult(BaseModel):
    """Response model for property extraction."""

    properties: Optional[List[ExtractedProperty]]


class FreeFormPosition(BaseModel):
    """Free-form position extracted before mapping to Wikidata."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str

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
    proof: str


class FreeFormBirthplaceResult(BaseModel):
    """Response model for free-form birthplace extraction."""

    birthplaces: Optional[List[FreeFormBirthplace]]


class FreeFormCitizenship(BaseModel):
    """Free-form citizenship extracted before mapping to Wikidata."""

    name: str
    proof: str


class FreeFormCitizenshipResult(BaseModel):
    """Response model for free-form citizenship extraction."""

    citizenships: Optional[List[FreeFormCitizenship]]


class ExtractedCitizenship(BaseModel):
    """Schema for extracted citizenship data."""

    wikidata_id: str
    proof: str


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
    mapping_entity_name: str = ""  # "position", "location", or "country"
    mapping_system_prompt: str = ""  # System prompt for mapping stage
    final_model: Type[BaseModel] = None


def extract_properties_generic(
    openai_client: OpenAI,
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

        response = openai_client.responses.parse(
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


def extract_two_stage_generic(
    openai_client: OpenAI,
    db: Session,
    content: str,
    politician: Politician,
    config: TwoStageExtractionConfig,
) -> Optional[List[Any]]:
    """Generic two-stage extraction (free-form -> mapping)."""
    try:
        # Stage 1: Free-form extraction
        free_form_results = extract_properties_generic(
            openai_client, content, politician, config
        )

        if not free_form_results:
            logger.info(
                f"No {config.mapping_entity_name}s extracted for {politician.name}"
            )
            return []

        logger.info(
            f"Stage 1: Extracted {len(free_form_results)} free-form {config.mapping_entity_name}s for {politician.name}"
        )

        # Stage 2: Map to Wikidata entities
        mapped_results = []
        for free_item in free_form_results:
            # Find similar entities using embeddings
            query_embedding = generate_embedding(free_item.name)

            similar_entities = (
                db.query(config.entity_class)
                .options(
                    selectinload(getattr(config.entity_class, "wikidata_entity"))
                    .selectinload(WikidataEntity.parent_relations)
                    .selectinload(WikidataRelation.parent_entity)
                )
                .filter(getattr(config.entity_class, "embedding").isnot(None))
                .order_by(
                    getattr(config.entity_class, "embedding").cosine_distance(
                        query_embedding
                    )
                )
                .limit(100)
                .all()
            )

            if not similar_entities:
                logger.debug(
                    f"No similar {config.mapping_entity_name}s found for '{free_item.name}'"
                )
                continue

            # Use LLM to map to correct entity
            candidate_entities = [
                {
                    "qid": entity.wikidata_id,
                    "name": entity.name,
                    "description": entity.description,
                }
                for entity in similar_entities
            ]

            mapped_qid = map_to_wikidata_entity(
                openai_client,
                free_item.name,
                free_item.proof,
                candidate_entities,
                politician,
                config.mapping_entity_name,
                config.mapping_system_prompt,
            )

            if mapped_qid:
                # Verify entity exists in database
                entity = (
                    db.query(config.entity_class)
                    .filter_by(wikidata_id=mapped_qid)
                    .first()
                )
                if entity:
                    # Create result based on entity type
                    if config.mapping_entity_name == "position":
                        mapped_results.append(
                            ExtractedPosition(
                                wikidata_id=entity.wikidata_id,
                                start_date=getattr(free_item, "start_date", None),
                                end_date=getattr(free_item, "end_date", None),
                                proof=free_item.proof,
                            )
                        )
                    elif config.mapping_entity_name == "location":
                        mapped_results.append(
                            ExtractedBirthplace(
                                wikidata_id=entity.wikidata_id,
                                proof=free_item.proof,
                            )
                        )
                    else:  # country
                        mapped_results.append(
                            ExtractedCitizenship(
                                wikidata_id=entity.wikidata_id,
                                proof=free_item.proof,
                            )
                        )
                    logger.debug(
                        f"Mapped '{free_item.name}' -> '{entity.name}' ({mapped_qid})"
                    )

        logger.info(
            f"Stage 2: Mapped {len(mapped_results)} of {len(free_form_results)} {config.mapping_entity_name}s for {politician.name}"
        )
        return mapped_results

    except Exception as e:
        logger.error(f"Error extracting {config.mapping_entity_name}s: {e}")
        return None


def map_to_wikidata_entity(
    openai_client: OpenAI,
    extracted_name: str,
    proof_text: str,
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

        entity_label = "position" if entity_type == "position" else "birthplace"
        user_prompt = f"""Map this extracted {entity_label} to the correct Wikidata {entity_type}:

{politician_context}

Extracted {entity_label.title()}: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata {entity_type.title()}s:
{candidates_text}

Select the best matching QID or None if no good match exists."""

        response = openai_client.responses.parse(
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


async def fetch_and_archive_page(
    url: str, db: Session, iso1_code: str = None, iso3_code: str = None
) -> ArchivedPage:
    """Fetch web page content and archive it."""
    # Create and insert ArchivedPage first
    now = datetime.now(timezone.utc)
    archived_page = ArchivedPage(
        url=url, fetch_timestamp=now, iso1_code=iso1_code, iso3_code=iso3_code
    )
    db.add(archived_page)
    db.flush()

    # Lazy import crawl4ai
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

    config = CrawlerRunConfig(
        capture_mhtml=True,
        verbose=True,
        word_count_threshold=0,
        only_text=True,
    )

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url, config=config)

        if not result.success:
            db.rollback()
            raise RuntimeError(f"Failed to crawl page: {url}")

        # Save MHTML archive
        if result.mhtml:
            mhtml_path = archive.save_archived_content(
                archived_page.path_root, "mhtml", result.mhtml
            )
            logger.info(f"Saved MHTML archive: {mhtml_path}")

            # Generate HTML from MHTML
            try:
                # Read MHTML content from storage (works with both local and GCS paths)
                mhtml_content = archive.read_archived_content(
                    archived_page.path_root, "mhtml"
                )
                converter = MHTMLConverter()
                html_content = converter.convert(mhtml_content)
                html_path = archive.save_archived_content(
                    archived_page.path_root, "html", html_content
                )
                logger.info(f"Generated HTML from MHTML: {html_path}")
            except Exception as e:
                logger.warning(f"Failed to generate HTML from MHTML: {e}")

        # Save markdown content
        markdown_content = result.markdown
        if markdown_content:
            markdown_path = archive.save_archived_content(
                archived_page.path_root, "md", markdown_content
            )
            logger.info(f"Saved markdown content: {markdown_path}")

        db.commit()
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
    mapping_entity_name="position",
    mapping_system_prompt=prompts.POSITION_MAPPING_SYSTEM_PROMPT,
    final_model=ExtractedPosition,
)

BIRTHPLACES_CONFIG = TwoStageExtractionConfig(
    property_types=[PropertyType.BIRTHPLACE],
    system_prompt=prompts.BIRTHPLACES_EXTRACTION_SYSTEM_PROMPT,
    result_model=FreeFormBirthplaceResult,
    user_prompt_template=prompts.BIRTHPLACES_USER_PROMPT_TEMPLATE,
    analysis_focus_template=prompts.BIRTHPLACES_ANALYSIS_FOCUS_TEMPLATE,
    result_field_name="birthplaces",
    entity_class=Location,
    mapping_entity_name="location",
    mapping_system_prompt=prompts.LOCATION_MAPPING_SYSTEM_PROMPT,
    final_model=ExtractedBirthplace,
)

CITIZENSHIPS_CONFIG = TwoStageExtractionConfig(
    property_types=[PropertyType.CITIZENSHIP],
    system_prompt=prompts.CITIZENSHIPS_EXTRACTION_SYSTEM_PROMPT,
    result_model=FreeFormCitizenshipResult,
    user_prompt_template=prompts.CITIZENSHIPS_USER_PROMPT_TEMPLATE,
    analysis_focus_template=prompts.CITIZENSHIPS_ANALYSIS_FOCUS_TEMPLATE,
    result_field_name="citizenships",
    entity_class=Country,
    mapping_entity_name="country",
    mapping_system_prompt=prompts.COUNTRY_MAPPING_SYSTEM_PROMPT,
    final_model=ExtractedCitizenship,
)


async def enrich_politicians_from_wikipedia(
    limit: Optional[int] = None,
) -> tuple[int, int]:
    """
    Enrich politicians' data by extracting information from their Wikipedia sources.

    Now processes multiple Wikipedia articles based on politician's citizenship and
    official languages of their countries, prioritized by Wikipedia link popularity.

    Args:
        limit: Optional limit on number of politicians to enrich. If None, enriches all.

    Returns:
        Tuple of (success_count, total_count)
    """

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with Session(get_engine()) as db:
        # Query politicians that need enrichment
        query = (
            db.query(Politician)
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
            .filter(Politician.wikipedia_links.any())
            .order_by(Politician.enriched_at.asc().nullsfirst())
        )

        if limit:
            politicians = query.limit(limit).all()
        else:
            politicians = query.all()

        if not politicians:
            return 0, 0

        success_count = 0

        for politician in politicians:
            try:
                # Get priority Wikipedia links based on citizenship and language popularity
                priority_links = politician.get_priority_wikipedia_links(db)

                if not priority_links:
                    raise ValueError(
                        f"No suitable Wikipedia links found for politician {politician.name}"
                    )

                logger.info(
                    f"Processing {len(priority_links)} Wikipedia sources for {politician.name}: "
                    f"{[f'{iso1_code} ({url})' for url, iso1_code, _ in priority_links]}"
                )

                # Track totals across all sources
                total_dates = 0
                total_positions = 0
                total_birthplaces = 0
                total_citizenships = 0
                processed_sources = 0

                # Process each priority Wikipedia link individually
                for url, iso1_code, iso3_code in priority_links:
                    logger.info(f"Processing Wikipedia source: {url}")

                    # Check if we already have this page archived
                    existing_page = (
                        db.query(ArchivedPage).filter(ArchivedPage.url == url).first()
                    )

                    if existing_page:
                        logger.info(f"Using existing archived page for {url}")
                        archived_page = existing_page
                        # Update language codes if missing
                        if not archived_page.iso1_code or not archived_page.iso3_code:
                            archived_page.iso1_code = iso1_code
                            archived_page.iso3_code = iso3_code
                            db.flush()
                    else:
                        # Fetch and archive the page with language codes
                        archived_page = await fetch_and_archive_page(
                            url, db, iso1_code, iso3_code
                        )

                    # Read content from archived page
                    html_content = archive.read_archived_content(
                        archived_page.path_root, "html"
                    )

                    soup = BeautifulSoup(html_content, "html.parser")
                    text = soup.get_text()
                    content = " ".join(text.split())

                    # Extract data from this specific source
                    date_properties = extract_properties_generic(
                        openai_client, content, politician, DATES_CONFIG
                    )

                    positions = extract_two_stage_generic(
                        openai_client, db, content, politician, POSITIONS_CONFIG
                    )

                    birthplaces = extract_two_stage_generic(
                        openai_client, db, content, politician, BIRTHPLACES_CONFIG
                    )

                    citizenships = extract_two_stage_generic(
                        openai_client, db, content, politician, CITIZENSHIPS_CONFIG
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

                        total_dates += date_count
                        total_positions += position_count
                        total_birthplaces += birthplace_count
                        total_citizenships += citizenship_count
                        processed_sources += 1

                        source_total = (
                            date_count
                            + position_count
                            + birthplace_count
                            + citizenship_count
                        )
                        logger.info(
                            f"Extracted {source_total} items from {url} "
                            f"({date_count} dates, {position_count} positions, {birthplace_count} birthplaces, {citizenship_count} citizenships)"
                        )
                    else:
                        logger.warning(
                            f"Failed to store extracted data from {url} for {politician.name}"
                        )

                # Commit all changes
                db.commit()

                # Final summary
                grand_total = (
                    total_dates
                    + total_positions
                    + total_birthplaces
                    + total_citizenships
                )
                logger.info(
                    f"Successfully enriched {politician.name} ({politician.wikidata_id}) from {processed_sources}/{len(priority_links)} sources: "
                    f"{grand_total} total items ({total_dates} dates, {total_positions} positions, {total_birthplaces} birthplaces, {total_citizenships} citizenships)"
                )
                success_count += 1

            except Exception as e:
                logger.error(
                    f"Error enriching politician {politician.wikidata_id}: {e}"
                )
                # Don't raise, continue with next politician

            finally:
                # Always update enriched_at timestamp regardless of success/failure
                politician.enriched_at = datetime.now(timezone.utc)
                db.commit()

        return success_count, len(politicians)


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
        # Store properties
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
                    proof_line=property_data.proof,
                )
                db.add(new_property)
                db.flush()
                logger.info(
                    f"Added new property: {property_data.type} = '{property_data.value}' for {politician.name}"
                )

        # Store positions - only link to existing positions
        if positions:
            for position_data in positions:
                if position_data.wikidata_id:
                    # Only find existing positions, don't create new ones
                    position = (
                        db.query(Position)
                        .filter_by(wikidata_id=position_data.wikidata_id)
                        .first()
                    )

                    if not position:
                        logger.warning(
                            f"Position '{position_data.wikidata_id}' not found in database for {politician.name} - skipping"
                        )
                        continue

                    # Create qualifiers_json with dates
                    qualifiers_json = create_qualifiers_json_for_position(
                        position_data.start_date, position_data.end_date
                    )

                    # Always add as new record
                    position_property = Property(
                        politician_id=politician.id,
                        type=PropertyType.POSITION,
                        entity_id=position.wikidata_id,
                        qualifiers_json=qualifiers_json,
                        references_json=archived_page.create_references_json(),
                        archived_page_id=archived_page.id,
                        proof_line=position_data.proof,
                    )
                    db.add(position_property)
                    db.flush()

                    date_range = ""
                    if position_data.start_date:
                        date_range = f" ({position_data.start_date}"
                        if position_data.end_date:
                            date_range += f" - {position_data.end_date})"
                        else:
                            date_range += " - present)"
                    elif position_data.end_date:
                        date_range = f" (until {position_data.end_date})"

                    logger.info(
                        f"Added new position: '{position.name}' ({position.wikidata_id}){date_range} for {politician.name}"
                    )

        # Store birthplaces - only link to existing locations
        if birthplaces:
            for birthplace_data in birthplaces:
                if birthplace_data.wikidata_id:
                    # Only find existing locations, don't create new ones
                    location = (
                        db.query(Location)
                        .filter_by(wikidata_id=birthplace_data.wikidata_id)
                        .first()
                    )

                    if not location:
                        logger.warning(
                            f"Location '{birthplace_data.wikidata_id}' not found in database for {politician.name} - skipping"
                        )
                        continue

                    # Check if this birthplace relationship already exists
                    existing_birth = (
                        db.query(Property)
                        .filter_by(
                            politician_id=politician.id,
                            type=PropertyType.BIRTHPLACE,
                            entity_id=location.wikidata_id,
                        )
                        .first()
                    )

                    if not existing_birth:
                        birthplace_property = Property(
                            politician_id=politician.id,
                            type=PropertyType.BIRTHPLACE,
                            entity_id=location.wikidata_id,
                            references_json=archived_page.create_references_json(),
                            archived_page_id=archived_page.id,
                            proof_line=birthplace_data.proof,
                        )
                        db.add(birthplace_property)
                        db.flush()
                        logger.info(
                            f"Added new birthplace: '{location.name}' ({location.wikidata_id}) for {politician.name}"
                        )

        # Store citizenships - only link to existing countries
        if citizenships:
            for citizenship_data in citizenships:
                if citizenship_data.wikidata_id:
                    # Only find existing countries, don't create new ones
                    country = (
                        db.query(Country)
                        .filter_by(wikidata_id=citizenship_data.wikidata_id)
                        .first()
                    )

                    if not country:
                        logger.warning(
                            f"Country '{citizenship_data.wikidata_id}' not found in database for {politician.name} - skipping"
                        )
                        continue

                    # Check if this citizenship relationship already exists
                    existing_citizenship = (
                        db.query(Property)
                        .filter_by(
                            politician_id=politician.id,
                            type=PropertyType.CITIZENSHIP,
                            entity_id=country.wikidata_id,
                        )
                        .first()
                    )

                    if not existing_citizenship:
                        citizenship_property = Property(
                            politician_id=politician.id,
                            type=PropertyType.CITIZENSHIP,
                            entity_id=country.wikidata_id,
                            references_json=archived_page.create_references_json(),
                            archived_page_id=archived_page.id,
                            proof_line=citizenship_data.proof,
                        )
                        db.add(citizenship_property)
                        db.flush()
                        logger.info(
                            f"Added new citizenship: '{country.name}' ({country.wikidata_id}) for {politician.name}"
                        )

        return True

    except Exception as e:
        logger.error(f"Error storing extracted data: {e}")
        return False
