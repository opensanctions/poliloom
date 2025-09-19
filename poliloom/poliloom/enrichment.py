"""Simplified enrichment module for extracting politician data from Wikipedia using LLM."""

import os
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional, Literal
from sqlalchemy.orm import Session, selectinload
from openai import OpenAI
from pydantic import BaseModel, field_validator, create_model
from unmhtml import MHTMLConverter
from bs4 import BeautifulSoup

from .models import (
    Politician,
    Property,
    PropertyType,
    Position,
    HoldsPosition,
    Location,
    BornAt,
    ArchivedPage,
    WikidataRelation,
    WikidataEntity,
    RelationType,
)
from . import archive
from .database import get_engine
from .wikidata_date import WikidataDate

logger = logging.getLogger(__name__)

# Global cached embedding model
_embedding_model = None


def get_embedding_model():
    """Get or create the cached SentenceTransformer model."""
    import torch
    from sentence_transformers import SentenceTransformer

    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading SentenceTransformer model...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        logger.info("SentenceTransformer model loaded and cached successfully")
    return _embedding_model


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text string."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist()


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

    properties: List[ExtractedProperty]


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

    positions: List[FreeFormPosition]


class FreeFormBirthplace(BaseModel):
    """Free-form birthplace extracted before mapping to Wikidata."""

    location_name: str
    proof: str


class FreeFormBirthplaceResult(BaseModel):
    """Response model for free-form birthplace extraction."""

    birthplaces: List[FreeFormBirthplace]


async def fetch_and_archive_page(url: str, db: Session) -> ArchivedPage:
    """Fetch web page content and archive it."""
    # Create and insert ArchivedPage first
    now = datetime.now(timezone.utc)
    archived_page = ArchivedPage(url=url, fetch_timestamp=now)
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


def extract_properties(
    openai_client: OpenAI,
    content: str,
    politician: Politician,
) -> Optional[List[ExtractedProperty]]:
    """Extract birth and death dates from content using OpenAI."""
    try:
        # Build comprehensive politician context
        politician_context = build_politician_context_xml(
            politician,
            existing_properties=politician.properties,
        )

        validation_focus = ""
        if politician.properties:
            validation_focus = """
<validation_focus>
Use this information to:
- Focus on finding additional or conflicting dates not already in Wikidata
- Validate or provide more precise versions of existing dates
- Identify any discrepancies between the article and Wikidata
</validation_focus>
"""

        system_prompt = """You are a data extraction assistant for Wikipedia biographical data.

<extraction_scope>
Extract ONLY these two property types:
- birth_date: Use format YYYY-MM-DD, or YYYY-MM, YYYY for incomplete dates
- death_date: Use format YYYY-MM-DD, or YYYY-MM, YYYY for incomplete dates
</extraction_scope>

<extraction_rules>
- Only extract information explicitly stated in the text
- Extract only birth_date and death_date - ignore all other personal information
- Use partial dates if full dates aren't available
</extraction_rules>

<proof_requirements>
- Each property must include one exact verbatim quote from the source content that mentions this property
- The quote must be copied exactly as it appears in the source, word-for-word
- When multiple sentences support the claim, choose the most important and relevant single quote
- The quote must actually exist in the provided content
</proof_requirements>"""

        user_prompt = f"""Extract personal properties of {politician.name} from this Wikipedia article text:

{politician_context}
{validation_focus}

<article_content>
{content}
</article_content>"""

        logger.debug(f"Extracting properties for {politician.name}")

        response = openai_client.responses.parse(
            model="gpt-5",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=PropertyExtractionResult,
            reasoning={"effort": "minimal"},
        )

        if response.output_parsed is None:
            logger.error("OpenAI property extraction returned None for parsed data")
            return None

        return response.output_parsed.properties

    except Exception as e:
        logger.error(f"Error extracting properties with LLM: {e}")
        return None


def extract_positions(
    openai_client: OpenAI,
    db: Session,
    content: str,
    politician: Politician,
) -> Optional[List[ExtractedPosition]]:
    """Extract political positions from content using two-stage approach."""
    try:
        # Build comprehensive politician context
        politician_context = build_politician_context_xml(
            politician,
            existing_positions=politician.wikidata_positions,
        )

        position_analysis_focus = ""
        if politician.wikidata_positions:
            position_analysis_focus = """
<position_analysis_focus>
Use this information to:
- Identify mentions of these positions in the text (they may appear with different wordings)
- Find additional positions not already in Wikidata
- Discover more specific date ranges for known positions
- Identify more specific variants of generic positions (e.g., specific committee memberships)
</position_analysis_focus>
"""

        # Stage 1: Free-form extraction
        system_prompt = """You are a political data analyst specializing in extracting structured information from Wikipedia articles and official government websites.

<extraction_scope>
Extract all political positions from the provided content following these rules:
- Extract any political offices, government roles, elected positions, or political appointments
- When the article clearly indicates the country/jurisdiction context, enhance position names with that context in parentheses (e.g., "Minister of Defence (Myanmar)")
- Only add jurisdictional context when you have high confidence from the article content
- Preserve the original position name without additions when jurisdiction is uncertain
- Return an empty list if no political positions are found in the content
</extraction_scope>

<date_formatting_rules>
- Use format YYYY-MM-DD
- Use YYYY-MM, or YYYY for incomplete dates
- Leave end_date null if position is current or unknown
</date_formatting_rules>

<proof_requirements>
- Each position must include one exact verbatim quote from the source content that mentions this position
- The quote must be copied exactly as it appears in the source, word-for-word
- When multiple sentences support the claim, choose the most important and relevant single quote
- The quote must actually exist in the provided content
</proof_requirements>"""

        user_prompt = f"""Extract all political positions held by {politician.name} from the content below.

{politician_context}
{position_analysis_focus}

<article_content>
{content}
</article_content>"""

        logger.debug(f"Stage 1: Extracting positions for {politician.name}")

        response = openai_client.responses.parse(
            model="gpt-5",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=FreeFormPositionResult,
            reasoning={"effort": "minimal"},
        )

        if response.output_parsed is None:
            logger.error("OpenAI position extraction returned None")
            return None

        free_form_positions = response.output_parsed.positions
        if not free_form_positions:
            logger.info(f"No positions extracted for {politician.name}")
            return []

        logger.info(
            f"Stage 1: Extracted {len(free_form_positions)} free-form positions for {politician.name}"
        )

        # Stage 2: Map to Wikidata positions
        mapped_positions = []
        for free_position in free_form_positions:
            # Find similar positions using embeddings
            query_embedding = generate_embedding(free_position.name)

            similar_positions = (
                db.query(Position)
                .options(
                    selectinload(Position.wikidata_entity)
                    .selectinload(WikidataEntity.parent_relations)
                    .selectinload(WikidataRelation.parent_entity)
                )
                .filter(Position.embedding.isnot(None))
                .order_by(Position.embedding.cosine_distance(query_embedding))
                .limit(100)
                .all()
            )

            if not similar_positions:
                logger.debug(f"No similar positions found for '{free_position.name}'")
                continue

            # Use LLM to map to correct position
            candidate_positions = [
                {
                    "qid": pos.wikidata_id,
                    "name": pos.name,
                    "description": build_entity_description(db, pos),
                }
                for pos in similar_positions
            ]
            mapped_qid = map_to_wikidata_position(
                openai_client,
                free_position.name,
                free_position.proof,
                candidate_positions,
                politician,
            )

            if mapped_qid:
                # Verify position exists in database
                position = db.query(Position).filter_by(wikidata_id=mapped_qid).first()
                if position:
                    mapped_positions.append(
                        ExtractedPosition(
                            wikidata_id=position.wikidata_id,
                            start_date=free_position.start_date,
                            end_date=free_position.end_date,
                            proof=free_position.proof,
                        )
                    )
                    logger.debug(
                        f"Mapped '{free_position.name}' -> '{position.name}' ({mapped_qid})"
                    )

        logger.info(
            f"Stage 2: Mapped {len(mapped_positions)} of {len(free_form_positions)} positions for {politician.name}"
        )
        return mapped_positions

    except Exception as e:
        logger.error(f"Error extracting positions: {e}")
        return None


def extract_birthplaces(
    openai_client: OpenAI,
    db: Session,
    content: str,
    politician: Politician,
) -> Optional[List[ExtractedBirthplace]]:
    """Extract birthplace from content using two-stage approach."""
    try:
        # Build comprehensive politician context
        politician_context = build_politician_context_xml(
            politician,
            existing_birthplaces=politician.wikidata_birthplaces,
        )

        birthplace_analysis_focus = ""
        if politician.wikidata_birthplaces:
            birthplace_analysis_focus = """
<birthplace_analysis_focus>
Use this information to:
- Identify mentions of these locations in the text (they may appear with different wordings)
- Find more specific birthplace information (e.g., specific city if only country is known)
- Identify any conflicting birthplace claims
</birthplace_analysis_focus>
"""

        # Stage 1: Free-form extraction
        system_prompt = """You are a biographical data specialist extracting location information from Wikipedia articles and official government profiles.

<extraction_scope>
Extract birthplace information following these rules:
- Extract birthplace as mentioned in the source (city, town, village or region)
- When the article clearly indicates the geographic context, enhance location names with state/country information (e.g., "Yangon, Myanmar" or "Springfield, Illinois, USA")
- Only add geographic context when you have high confidence from the article content
- Preserve the original location name without additions when geographic context is uncertain
- Return an empty list if no birthplace information is found in the content
- Only extract actual location names that are explicitly stated in the text
</extraction_scope>

<proof_requirements>
- Provide one exact verbatim quote from the source content that mentions the birthplace
- The quote must be copied exactly as it appears in the source, word-for-word
- When multiple sentences support the claim, choose the most important and relevant single quote
- The quote must actually exist in the provided content
</proof_requirements>"""

        user_prompt = f"""Extract the birthplace of {politician.name} from the content below.

{politician_context}
{birthplace_analysis_focus}

<article_content>
{content}
</article_content>"""

        logger.debug(f"Stage 1: Extracting birthplace for {politician.name}")

        response = openai_client.responses.parse(
            model="gpt-5",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=FreeFormBirthplaceResult,
            reasoning={"effort": "minimal"},
        )

        if response.output_parsed is None:
            logger.error("OpenAI birthplace extraction returned None")
            return None

        free_form_birthplaces = response.output_parsed.birthplaces
        if not free_form_birthplaces:
            logger.info(f"No birthplace extracted for {politician.name}")
            return []

        logger.info(
            f"Stage 1: Extracted {len(free_form_birthplaces)} free-form birthplaces for {politician.name}"
        )

        # Stage 2: Map to Wikidata locations
        mapped_birthplaces = []
        for free_birthplace in free_form_birthplaces:
            # Find similar locations using embeddings
            query_embedding = generate_embedding(free_birthplace.location_name)

            similar_locations = (
                db.query(Location)
                .options(
                    selectinload(Location.wikidata_entity)
                    .selectinload(WikidataEntity.parent_relations)
                    .selectinload(WikidataRelation.parent_entity)
                )
                .filter(Location.embedding.isnot(None))
                .order_by(Location.embedding.cosine_distance(query_embedding))
                .limit(100)
                .all()
            )

            if not similar_locations:
                logger.debug(
                    f"No similar locations found for '{free_birthplace.location_name}'"
                )
                continue

            # Use LLM to map to correct location
            candidate_locations = [
                {
                    "qid": loc.wikidata_id,
                    "name": loc.name,
                    "description": build_entity_description(db, loc),
                }
                for loc in similar_locations
            ]
            mapped_qid = map_to_wikidata_location(
                openai_client,
                free_birthplace.location_name,
                free_birthplace.proof,
                candidate_locations,
                politician,
            )

            if mapped_qid:
                # Verify location exists in database
                location = db.query(Location).filter_by(wikidata_id=mapped_qid).first()
                if location:
                    mapped_birthplaces.append(
                        ExtractedBirthplace(
                            wikidata_id=location.wikidata_id,
                            proof=free_birthplace.proof,
                        )
                    )
                    logger.debug(
                        f"Mapped '{free_birthplace.location_name}' -> '{location.name}' ({mapped_qid})"
                    )

        logger.info(
            f"Stage 2: Mapped {len(mapped_birthplaces)} of {len(free_form_birthplaces)} birthplaces for {politician.name}"
        )
        return mapped_birthplaces

    except Exception as e:
        logger.error(f"Error extracting birthplaces: {e}")
        return None


def format_candidates_as_xml(candidates: List[dict]) -> str:
    """Format candidate entities as XML structure with rich descriptions."""
    return "\n".join(
        [
            f"<entity>\n    <qid>{candidate['qid']}</qid>\n    <name>{candidate['name']}</name>\n    <description>{candidate['description']}</description>\n</entity>"
            for candidate in candidates
        ]
    )


def build_politician_context_xml(
    politician,
    existing_properties=None,
    existing_positions=None,
    existing_birthplaces=None,
) -> str:
    """Build comprehensive politician context as XML structure for LLM prompts.

    Args:
        politician: Politician model instance
        existing_properties: Optional list of existing Property instances
        existing_positions: Optional list of existing HoldsPosition instances
        existing_birthplaces: Optional list of existing BornAt instances

    Returns:
        XML formatted politician context string
    """
    context_sections = []

    # Basic politician info
    basic_info = [
        f"<name>{politician.name}</name>",
        f"<wikidata_id>{politician.wikidata_id}</wikidata_id>",
    ]

    # Add citizenship information if available
    if politician.citizenships:
        countries = [
            citizenship.country.name
            for citizenship in politician.citizenships
            if citizenship.country and citizenship.country.name
        ]
        if countries:
            basic_info.append(f"<citizenships>{', '.join(countries)}</citizenships>")

    context_sections.append(
        f"<politician_info>\n    {chr(10).join(['    ' + info for info in basic_info])}\n</politician_info>"
    )

    # Add existing Wikidata properties
    if existing_properties:
        existing_props = []
        for prop in existing_properties:
            if prop.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
                existing_props.append(f"- {prop.type.value}: {prop.value}")

        if existing_props:
            context_sections.append(f"""<existing_wikidata>
{chr(10).join(existing_props)}
</existing_wikidata>""")

    # Add existing positions
    if existing_positions:
        existing_pos = []
        for holds in existing_positions:
            date_range = ""
            if holds.start_date:
                date_range = f" ({holds.start_date}"
                if holds.end_date:
                    date_range += f" - {holds.end_date})"
                else:
                    date_range += " - present)"
            elif holds.end_date:
                date_range = f" (until {holds.end_date})"
            existing_pos.append(f"- {holds.position.name}{date_range}")

        if existing_pos:
            context_sections.append(f"""<existing_wikidata_positions>
{chr(10).join(existing_pos)}
</existing_wikidata_positions>""")

    # Add existing birthplaces
    if existing_birthplaces:
        existing_bp = []
        for born_at in existing_birthplaces:
            existing_bp.append(f"- {born_at.location.name}")

        if existing_bp:
            context_sections.append(f"""<existing_wikidata_birthplaces>
{chr(10).join(existing_bp)}
</existing_wikidata_birthplaces>""")

    return chr(10).join(context_sections)


def build_entity_description(db: Session, entity) -> str:
    """Build rich description from WikidataRelations dynamically.

    Args:
        db: Database session (unused when relations are preloaded)
        entity: Position or Location instance with preloaded relations

    Returns:
        Rich description string built from relations
    """
    if not hasattr(entity, "wikidata_entity") or not entity.wikidata_entity:
        return ""

    # Use preloaded relations instead of querying database
    relations = entity.wikidata_entity.parent_relations

    # Group relations by type using defaultdict
    relations_by_type = defaultdict(list)
    for relation in relations:
        if relation.parent_entity and relation.parent_entity.name:
            relations_by_type[relation.relation_type].append(
                relation.parent_entity.name
            )

    description_parts = []

    # Build description based on available relations
    if relations_by_type[RelationType.INSTANCE_OF]:
        instances = relations_by_type[RelationType.INSTANCE_OF]
        description_parts.append(", ".join(instances))

    if relations_by_type[RelationType.SUBCLASS_OF]:
        subclasses = relations_by_type[RelationType.SUBCLASS_OF]
        description_parts.append(f"subclass of {', '.join(subclasses)}")

    if relations_by_type[RelationType.PART_OF]:
        parts = relations_by_type[RelationType.PART_OF]
        description_parts.append(f"part of {', '.join(parts)}")

    if relations_by_type[RelationType.APPLIES_TO_JURISDICTION]:
        jurisdictions = relations_by_type[RelationType.APPLIES_TO_JURISDICTION]
        description_parts.append(f"applies to jurisdiction {', '.join(jurisdictions)}")

    if relations_by_type[RelationType.LOCATED_IN]:
        locations = relations_by_type[RelationType.LOCATED_IN]
        description_parts.append(f"located in {', '.join(locations)}")

    if relations_by_type[RelationType.COUNTRY]:
        countries = relations_by_type[RelationType.COUNTRY]
        description_parts.append(f"country {', '.join(countries)}")

    return ", ".join(description_parts) if description_parts else ""


def map_to_wikidata_position(
    openai_client: OpenAI,
    extracted_name: str,
    proof_text: str,
    candidate_positions: List[dict],
    politician: Politician,
) -> Optional[str]:
    """Map extracted position name to Wikidata position using LLM."""
    try:
        # Create dynamic model with candidate position QIDs
        entity_qids = [
            position["qid"] for position in candidate_positions if position.get("qid")
        ]
        PositionQidType = Optional[Literal[tuple(entity_qids)]]

        DynamicMappingResult = create_model(
            "PositionMappingResult",
            wikidata_position_qid=(PositionQidType, None),
        )

        system_prompt = """You are a Wikidata mapping specialist with expertise in political positions and government structures.

<mapping_objective>
Map the extracted position to the most accurate Wikidata position following these rules:
</mapping_objective>

<matching_criteria>
1. Strongly prefer country-specific positions (e.g., "Minister of Foreign Affairs (Myanmar)" over generic "Minister of Foreign Affairs")
2. Prefer positions from the same political system/country context
3. Match only when confidence is high - be precise about role equivalence
</matching_criteria>

<rejection_criteria>
- Return None if no candidate is a good match
- Reject if the positions clearly refer to different roles
- Reject if geographic/jurisdictional scope differs significantly
</rejection_criteria>"""

        # Format candidates with XML structure and rich descriptions
        candidates_text = format_candidates_as_xml(candidate_positions)

        # Build politician context for stage 2 mapping
        politician_context = build_politician_context_xml(politician)

        user_prompt = f"""Map this extracted position to the correct Wikidata position:

{politician_context}

Extracted Position: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata Positions:
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

        return response.output_parsed.wikidata_position_qid

    except Exception as e:
        logger.error(f"Error mapping position with LLM: {e}")
        return None


def map_to_wikidata_location(
    openai_client: OpenAI,
    extracted_name: str,
    proof_text: str,
    candidate_locations: List[dict],
    politician: Politician,
) -> Optional[str]:
    """Map extracted location name to Wikidata location using LLM."""
    try:
        # Create dynamic model with candidate location QIDs
        entity_qids = [
            location["qid"] for location in candidate_locations if location.get("qid")
        ]
        LocationQidType = Optional[Literal[tuple(entity_qids)]]

        DynamicMappingResult = create_model(
            "LocationMappingResult",
            wikidata_location_qid=(LocationQidType, None),
        )

        system_prompt = """You are a Wikidata location mapping specialist with expertise in geographic locations and administrative divisions.

<mapping_objective>
Map the extracted birthplace to the correct Wikidata location entity.
</mapping_objective>

<matching_criteria>
1. Match the most specific location level mentioned in the proof text
   - If proof says "City, Country" → match the city, not the country
   - If proof says only "Country" → match the country

2. Use context from the proof text to disambiguate between similar names
   - Look for parent locations mentioned (district, region, country)
   - These help identify which specific location is meant

3. Account for spelling variations and transliterations
</matching_criteria>

<rejection_criteria>
- Return None if uncertain which candidate matches
- Return None if the location type doesn't match what's described
</rejection_criteria>"""

        # Format candidates with XML structure and rich descriptions
        candidates_text = format_candidates_as_xml(candidate_locations)

        # Build politician context for stage 2 mapping
        politician_context = build_politician_context_xml(politician)

        user_prompt = f"""Map this extracted birthplace to the correct Wikidata location:

{politician_context}

Extracted Birthplace: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata Locations:
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

        return response.output_parsed.wikidata_location_qid

    except Exception as e:
        logger.error(f"Error mapping location with LLM: {e}")
        return None


async def enrich_politician_from_wikipedia(politician: Politician) -> None:
    """
    Enrich a politician's data by extracting information from their Wikipedia sources.

    Args:
        politician: The Politician model instance to enrich

    Raises:
        ValueError: If politician has no Wikipedia links or no English Wikipedia link
    """
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with Session(get_engine()) as db:
        try:
            # Merge the politician into this session
            politician = db.merge(politician)

            if not politician.wikipedia_links:
                raise ValueError(
                    f"No Wikipedia links found for politician {politician.name}"
                )

            # Process only English Wikipedia source
            english_wikipedia_link = None
            for wikipedia_link in politician.wikipedia_links:
                if "en.wikipedia.org" in wikipedia_link.url:
                    english_wikipedia_link = wikipedia_link
                    break

            if not english_wikipedia_link:
                raise ValueError(
                    f"No English Wikipedia source found for politician {politician.name}"
                )

            logger.info(
                f"Processing English Wikipedia source: {english_wikipedia_link.url}"
            )

            # Check if we already have this page archived
            existing_page = (
                db.query(ArchivedPage)
                .filter(ArchivedPage.url == english_wikipedia_link.url)
                .first()
            )

            if existing_page:
                logger.info(
                    f"Using existing archived page for {english_wikipedia_link.url}"
                )
                archived_page = existing_page
            else:
                # Fetch and archive the page
                archived_page = await fetch_and_archive_page(
                    english_wikipedia_link.url, db
                )

            # Read content from archived page
            html_content = archive.read_archived_content(
                archived_page.path_root, "html"
            )

            soup = BeautifulSoup(html_content, "html.parser")
            text = soup.get_text()
            content = " ".join(text.split())

            # Extract properties
            properties = extract_properties(openai_client, content, politician)

            # Extract positions
            positions = extract_positions(
                openai_client,
                db,
                content,
                politician,
            )

            # Extract birthplaces
            birthplaces = extract_birthplaces(
                openai_client,
                db,
                content,
                politician,
            )

            # Log extraction results
            logger.info(
                f"LLM extracted data for {politician.name} ({politician.wikidata_id}):"
            )
            if properties:
                logger.info(f"  Properties ({len(properties)}):")
                for prop in properties:
                    logger.info(f"    {prop.type}: {prop.value}")
            else:
                logger.info("  No properties extracted")

            if positions:
                logger.info(f"  Positions ({len(positions)}):")
                for position in positions:
                    date_info = ""
                    if position.start_date:
                        date_info = f" ({position.start_date}"
                        if position.end_date:
                            date_info += f" - {position.end_date})"
                        else:
                            date_info += " - present)"
                    elif position.end_date:
                        date_info = f" (until {position.end_date})"
                    logger.info(f"    {position.wikidata_id}{date_info}")
            else:
                logger.info("  No positions extracted")

            if birthplaces:
                logger.info(f"  Birthplaces ({len(birthplaces)}):")
                for birthplace in birthplaces:
                    logger.info(f"    {birthplace.wikidata_id}")
            else:
                logger.info("  No birthplaces extracted")

            # Store extracted data in database
            success = store_extracted_data(
                db, politician, archived_page, properties, positions, birthplaces
            )

            if success:
                db.commit()
                logger.info(
                    f"Successfully enriched politician {politician.name} ({politician.wikidata_id})"
                )
            else:
                db.rollback()
                raise RuntimeError(
                    f"Failed to store extracted data for {politician.name} ({politician.wikidata_id})"
                )

        except Exception as e:
            logger.error(f"Error enriching politician {politician.wikidata_id}: {e}")
            raise

        finally:
            # Always update enriched_at timestamp regardless of success/failure
            politician.enriched_at = datetime.now(timezone.utc)
            db.commit()


def store_extracted_data(
    db: Session,
    politician: Politician,
    archived_page: ArchivedPage,
    properties: Optional[List[ExtractedProperty]],
    positions: Optional[List[ExtractedPosition]],
    birthplaces: Optional[List[ExtractedBirthplace]],
) -> bool:
    """Store extracted data in the database."""
    try:
        # Store properties
        if properties:
            for property_data in properties:
                if property_data.value:
                    # Check if similar property already exists
                    existing_prop = (
                        db.query(Property)
                        .filter_by(
                            politician_id=politician.id,
                            type=property_data.type,
                            value=property_data.value,
                        )
                        .first()
                    )

                    if not existing_prop:
                        new_property = Property(
                            politician_id=politician.id,
                            type=property_data.type,
                            value=property_data.value,
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

                    # Check for overlapping position timeframes
                    all_existing_holds = (
                        db.query(HoldsPosition)
                        .filter_by(
                            politician_id=politician.id,
                            position_id=position.wikidata_id,
                        )
                        .all()
                    )

                    overlapping_hold = None

                    for existing_hold in all_existing_holds:
                        # Check if the date ranges could refer to the same time period
                        if WikidataDate.dates_could_be_same(
                            existing_hold.start_date, position_data.start_date
                        ) and WikidataDate.dates_could_be_same(
                            existing_hold.end_date, position_data.end_date
                        ):
                            overlapping_hold = existing_hold
                            break

                    if overlapping_hold:
                        # Dates could be the same - use precision to decide
                        new_prec = WikidataDate.get_date_precision(
                            position_data.start_date
                        ) + WikidataDate.get_date_precision(position_data.end_date)
                        existing_prec = WikidataDate.get_date_precision(
                            overlapping_hold.start_date
                        ) + WikidataDate.get_date_precision(overlapping_hold.end_date)

                        if new_prec > existing_prec:
                            # New data has higher precision - update existing record
                            old_range = f"{overlapping_hold.start_date or 'unknown'}-{overlapping_hold.end_date or 'present'}"
                            new_range = f"{position_data.start_date or 'unknown'}-{position_data.end_date or 'present'}"

                            overlapping_hold.start_date = position_data.start_date
                            overlapping_hold.end_date = position_data.end_date
                            overlapping_hold.archived_page_id = archived_page.id
                            overlapping_hold.proof_line = position_data.proof
                            db.flush()

                            logger.info(
                                f"Updated position with higher precision: '{position.name}' ({position.wikidata_id}) "
                                f"from ({old_range}) to ({new_range}) for {politician.name}"
                            )
                        else:
                            # Existing data has equal or higher precision - skip new data
                            logger.info(
                                f"Skipped position with equal/lower precision: '{position.name}' ({position.wikidata_id}) "
                                f"({position_data.start_date or 'unknown'}-{position_data.end_date or 'present'}) "
                                f"for {politician.name}"
                            )
                    else:
                        # No overlap, add as new record
                        holds_position = HoldsPosition(
                            politician_id=politician.id,
                            position_id=position.wikidata_id,
                            start_date=position_data.start_date,
                            end_date=position_data.end_date,
                            archived_page_id=archived_page.id,
                            proof_line=position_data.proof,
                        )
                        db.add(holds_position)
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
                        db.query(BornAt)
                        .filter_by(
                            politician_id=politician.id,
                            location_id=location.wikidata_id,
                        )
                        .first()
                    )

                    if not existing_birth:
                        born_at = BornAt(
                            politician_id=politician.id,
                            location_id=location.wikidata_id,
                            archived_page_id=archived_page.id,
                            proof_line=birthplace_data.proof,
                        )
                        db.add(born_at)
                        db.flush()
                        logger.info(
                            f"Added new birthplace: '{location.name}' ({location.wikidata_id}) for {politician.name}"
                        )

        return True

    except Exception as e:
        logger.error(f"Error storing extracted data: {e}")
        return False
