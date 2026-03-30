"""Simplified enrichment module for extracting politician data from Wikipedia using LLM."""

import os
import logging
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Literal, Type, Union, Any
from sqlalchemy.orm import Session, selectinload
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator, create_model
from dicttoxml import dicttoxml

from .models import (
    Politician,
    Property,
    PropertyReference,
    PropertyType,
    Position,
    Location,
    Country,
    Source,
    WikidataRelation,
    WikidataEntity,
)
from .search import SearchService
from .wikidata.date import WikidataDate
from . import prompts

logger = logging.getLogger(__name__)


def create_qualifiers_json_for_position(
    start_date: Optional[str] = None, end_date: Optional[str] = None
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
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            input=[
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=config.result_model,
            reasoning={"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")},
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
                .selectinload(
                    WikidataEntity.parent_relations.and_(
                        WikidataRelation.deleted_at.is_(None)
                    )
                )
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

        extracted_names = [r.name for r in free_form_results]
        logger.info(
            f"Stage 1: Extracted {len(free_form_results)} free-form {config.entity_class.MAPPING_ENTITY_NAME}s for {politician.name}: {extracted_names}"
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
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=DynamicMappingResult,
            reasoning={
                "effort": os.getenv("OPENAI_MAPPING_REASONING_EFFORT", "medium")
            },
        )

        if response.output_parsed is None:
            return None

        return getattr(response.output_parsed, field_name)

    except Exception as e:
        logger.error(f"Error mapping {entity_type} with LLM: {e}")
        return None


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


async def extract_and_store(
    db: Session,
    content: str,
    politician: Politician,
    source: Source,
) -> int:
    """Extract properties from text content and store them.

    This is the enrichment entry point called by the archiving pipeline.

    Args:
        db: Database session
        content: Plain text content extracted from the source
        politician: Politician to extract properties for
        source: Source to link references to

    Returns:
        Number of properties extracted.
    """
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        (
            date_properties,
            positions,
            birthplaces,
            citizenships,
        ) = await asyncio.gather(
            extract_properties_generic(
                openai_client,
                content,
                politician,
                DATES_CONFIG,
            ),
            extract_two_stage_generic(
                openai_client,
                db,
                content,
                politician,
                POSITIONS_CONFIG,
            ),
            extract_two_stage_generic(
                openai_client,
                db,
                content,
                politician,
                BIRTHPLACES_CONFIG,
            ),
            extract_two_stage_generic(
                openai_client,
                db,
                content,
                politician,
                CITIZENSHIPS_CONFIG,
            ),
        )
    finally:
        await openai_client.close()

    store_extracted_data(
        db,
        politician,
        source,
        date_properties,
        positions,
        birthplaces,
        citizenships,
    )

    return sum(
        len(items)
        for items in (date_properties, positions, birthplaces, citizenships)
        if items
    )


def store_extracted_data(
    db: Session,
    politician: Politician,
    source: Source,
    properties: Optional[List[ExtractedProperty]],
    positions: Optional[List[ExtractedPosition]],
    birthplaces: Optional[List[ExtractedBirthplace]],
    citizenships: Optional[List[ExtractedCitizenship]],
) -> bool:
    """Store extracted data in the database."""
    try:
        # Build (property_kwargs, find_kwargs, quotes, label) for each extracted item
        items = []

        for p in properties or []:
            wd = WikidataDate.from_date_string(p.value)
            kwargs = dict(
                type=p.type,
                value=wd.time_string,
                value_precision=wd.precision,
            )
            items.append((kwargs, p.supporting_quotes, f"{p.type} = '{p.value}'"))

        for pos in positions or []:
            qualifiers_json = create_qualifiers_json_for_position(
                pos.start_date, pos.end_date
            )
            kwargs = dict(
                type=PropertyType.POSITION,
                entity_id=pos.wikidata_id,
                qualifiers_json=qualifiers_json,
            )
            items.append((kwargs, pos.supporting_quotes, f"position {pos.wikidata_id}"))

        for bp in birthplaces or []:
            kwargs = dict(type=PropertyType.BIRTHPLACE, entity_id=bp.wikidata_id)
            items.append((kwargs, bp.supporting_quotes, f"birthplace {bp.wikidata_id}"))

        for cit in citizenships or []:
            kwargs = dict(type=PropertyType.CITIZENSHIP, entity_id=cit.wikidata_id)
            items.append(
                (kwargs, cit.supporting_quotes, f"citizenship {cit.wikidata_id}")
            )

        for kwargs, quotes, label in items:
            # Query existing properties once for both matching and subsumption
            property_type = kwargs["type"]
            query = db.query(Property).filter(
                Property.politician_id == politician.id,
                Property.type == property_type,
                Property.deleted_at.is_(None),
            )
            if property_type not in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
                query = query.filter(Property.entity_id == kwargs.get("entity_id"))
            existing_properties = query.all()

            prop = Property.find_matching(
                existing_properties,
                property_type=property_type,
                politician_id=politician.id,
                **{k: v for k, v in kwargs.items() if k != "type"},
            )
            if prop:
                logger.info(
                    f"Added reference to existing {label} for {politician.name}"
                )
            elif (
                property_type == PropertyType.POSITION
                and kwargs.get("entity_id")
                and Property.is_timeframe_subsumed(
                    existing_properties,
                    kwargs.get("qualifiers_json"),
                )
            ):
                logger.info(f"Skipping subsumed {label} for {politician.name}")
                continue
            else:
                prop = Property(politician_id=politician.id, **kwargs)
                db.add(prop)
                db.flush()
                logger.info(f"Added new {label} for {politician.name}")

            existing_ref = (
                db.query(PropertyReference)
                .filter_by(property_id=prop.id, source_id=source.id)
                .first()
            )
            if existing_ref:
                existing_ref.supporting_quotes = list(
                    set((existing_ref.supporting_quotes or []) + quotes)
                )
            else:
                db.add(
                    PropertyReference(
                        property=prop, source=source, supporting_quotes=quotes
                    )
                )

        return True

    except Exception as e:
        logger.error(f"Error storing extracted data: {e}")
        return False
