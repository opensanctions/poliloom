"""Simplified enrichment module for extracting politician data from Wikipedia using LLM."""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from openai import OpenAI
from pydantic import BaseModel, field_validator
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
)
from . import archive
from .database import get_engine
from .dates import (
    validate_date_format,
    get_date_precision,
    dates_could_be_same,
)

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
        return validate_date_format(v)


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""

    wikidata_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_dates(cls, v: Optional[str]) -> Optional[str]:
        return validate_date_format(v)


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
        return validate_date_format(v)


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
                converter = MHTMLConverter()
                html_content = converter.convert_file(mhtml_path)
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
    politician_name: str,
    existing_properties: Optional[List] = None,
) -> Optional[List[ExtractedProperty]]:
    """Extract birth and death dates from content using OpenAI."""
    try:
        # Build context about existing properties
        existing_context = ""
        if existing_properties:
            existing_props = []
            for prop in existing_properties:
                if prop.type in ["birth_date", "death_date"]:
                    existing_props.append(f"- {prop.type}: {prop.value}")

            if existing_props:
                existing_context = f"""
<existing_wikidata>
{chr(10).join(existing_props)}
</existing_wikidata>

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

        user_prompt = f"""Extract personal properties about {politician_name} from this Wikipedia article text:

<politician_name>{politician_name}</politician_name>

{existing_context}

<article_content>
{content}
</article_content>"""

        logger.debug(f"Extracting properties for {politician_name}")

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
    politician_name: str,
    existing_positions: Optional[List] = None,
) -> Optional[List[ExtractedPosition]]:
    """Extract political positions from content using two-stage approach."""
    try:
        # Build context about existing positions
        existing_context = ""
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
                existing_context = f"""
<existing_wikidata_positions>
{chr(10).join(existing_pos)}
</existing_wikidata_positions>

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
- Use exact position names as they appear in the source
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

        user_prompt = f"""Extract all political positions held by {politician_name} from the content below.

<politician_name>{politician_name}</politician_name>

{existing_context}

<article_content>
{content}
</article_content>"""

        logger.debug(f"Stage 1: Extracting positions for {politician_name}")

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
            logger.info(f"No positions extracted for {politician_name}")
            return []

        logger.info(
            f"Stage 1: Extracted {len(free_form_positions)} free-form positions for {politician_name}"
        )

        # Stage 2: Map to Wikidata positions
        mapped_positions = []
        for free_pos in free_form_positions:
            # Find similar positions using embeddings
            query_embedding = generate_embedding(free_pos.name)

            similar_positions = (
                db.query(Position)
                .filter(Position.embedding.isnot(None))
                .order_by(Position.embedding.cosine_distance(query_embedding))
                .limit(100)
                .all()
            )

            if not similar_positions:
                logger.debug(f"No similar positions found for '{free_pos.name}'")
                continue

            # Use LLM to map to correct position
            candidate_positions = [
                {
                    "qid": pos.wikidata_id,
                    "name": pos.name,
                    "classes": [
                        rel.parent_entity.name
                        for rel in pos.wikidata_entity.parent_relations
                        if rel.parent_entity and rel.parent_entity.name
                    ]
                    if pos.wikidata_entity
                    else [],
                }
                for pos in similar_positions
            ]
            mapped_qid = map_to_wikidata_position(
                openai_client, free_pos.name, free_pos.proof, candidate_positions
            )

            if mapped_qid:
                # Verify position exists in database
                position = db.query(Position).filter_by(wikidata_id=mapped_qid).first()
                if position:
                    mapped_positions.append(
                        ExtractedPosition(
                            wikidata_id=position.wikidata_id,
                            start_date=free_pos.start_date,
                            end_date=free_pos.end_date,
                            proof=free_pos.proof,
                        )
                    )
                    logger.debug(
                        f"Mapped '{free_pos.name}' -> '{position.name}' ({mapped_qid})"
                    )

        logger.info(
            f"Stage 2: Mapped {len(mapped_positions)} of {len(free_form_positions)} positions for {politician_name}"
        )
        return mapped_positions

    except Exception as e:
        logger.error(f"Error extracting positions: {e}")
        return None


def extract_birthplaces(
    openai_client: OpenAI,
    db: Session,
    content: str,
    politician_name: str,
    existing_birthplaces: Optional[List] = None,
) -> Optional[List[ExtractedBirthplace]]:
    """Extract birthplace from content using two-stage approach."""
    try:
        # Build context about existing birthplaces
        existing_context = ""
        if existing_birthplaces:
            existing_bp = []
            for born_at in existing_birthplaces:
                existing_bp.append(f"- {born_at.location.name}")

            if existing_bp:
                existing_context = f"""
<existing_wikidata_birthplaces>
{chr(10).join(existing_bp)}
</existing_wikidata_birthplaces>

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
- Return an empty list if no birthplace information is found in the content
- Only extract actual location names that are explicitly stated in the text
</extraction_scope>

<proof_requirements>
- Provide one exact verbatim quote from the source content that mentions the birthplace
- The quote must be copied exactly as it appears in the source, word-for-word
- When multiple sentences support the claim, choose the most important and relevant single quote
- The quote must actually exist in the provided content
</proof_requirements>"""

        user_prompt = f"""Extract the birthplace of {politician_name} from the content below.

<politician_name>{politician_name}</politician_name>

{existing_context}

<article_content>
{content}
</article_content>"""

        logger.debug(f"Stage 1: Extracting birthplace for {politician_name}")

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
            logger.info(f"No birthplace extracted for {politician_name}")
            return []

        logger.info(
            f"Stage 1: Extracted {len(free_form_birthplaces)} free-form birthplaces for {politician_name}"
        )

        # Stage 2: Map to Wikidata locations
        mapped_birthplaces = []
        for free_birth in free_form_birthplaces:
            # Find similar locations using embeddings
            query_embedding = generate_embedding(free_birth.location_name)

            similar_locations = (
                db.query(Location)
                .filter(Location.embedding.isnot(None))
                .order_by(Location.embedding.cosine_distance(query_embedding))
                .limit(100)
                .all()
            )

            if not similar_locations:
                logger.debug(
                    f"No similar locations found for '{free_birth.location_name}'"
                )
                continue

            # Use LLM to map to correct location
            candidate_locations = [
                {
                    "qid": loc.wikidata_id,
                    "name": loc.name,
                    "classes": [
                        rel.parent_entity.name
                        for rel in loc.wikidata_entity.parent_relations
                        if rel.parent_entity and rel.parent_entity.name
                    ]
                    if loc.wikidata_entity
                    else [],
                }
                for loc in similar_locations
            ]
            mapped_qid = map_to_wikidata_location(
                openai_client,
                free_birth.location_name,
                free_birth.proof,
                candidate_locations,
            )

            if mapped_qid:
                # Verify location exists in database
                location = db.query(Location).filter_by(wikidata_id=mapped_qid).first()
                if location:
                    mapped_birthplaces.append(
                        ExtractedBirthplace(
                            wikidata_id=location.wikidata_id, proof=free_birth.proof
                        )
                    )
                    logger.debug(
                        f"Mapped '{free_birth.location_name}' -> '{location.name}' ({mapped_qid})"
                    )

        logger.info(
            f"Stage 2: Mapped {len(mapped_birthplaces)} of {len(free_form_birthplaces)} birthplaces for {politician_name}"
        )
        return mapped_birthplaces

    except Exception as e:
        logger.error(f"Error extracting birthplaces: {e}")
        return None


def map_to_wikidata_position(
    openai_client: OpenAI,
    extracted_name: str,
    proof_text: str,
    candidate_positions: List[dict],
) -> Optional[str]:
    """Map extracted position name to Wikidata position using LLM."""
    try:
        from typing import Literal
        from pydantic import create_model

        # Create dynamic model with candidate position QIDs
        if candidate_positions:
            entity_qids = [pos["qid"] for pos in candidate_positions if pos.get("qid")]
            PositionQidType = Optional[Literal[tuple(entity_qids)]]
        else:
            PositionQidType = Optional[str]

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

        # Format candidates with QID, name, and classes
        candidates_text = "\n".join(
            [
                f"- {pos['qid']}: {pos['name']}"
                + (f" (classes: {', '.join(pos['classes'])})" if pos["classes"] else "")
                for pos in candidate_positions
            ]
        )

        user_prompt = f"""Map this extracted position to the correct Wikidata position:

Extracted Position: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata Positions (QID: Name - Classes):
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
) -> Optional[str]:
    """Map extracted location name to Wikidata location using LLM."""
    try:
        from typing import Literal
        from pydantic import create_model

        # Create dynamic model with candidate location QIDs
        if candidate_locations:
            entity_qids = [loc["qid"] for loc in candidate_locations if loc.get("qid")]
            LocationQidType = Optional[Literal[tuple(entity_qids)]]
        else:
            LocationQidType = Optional[str]

        DynamicMappingResult = create_model(
            "LocationMappingResult",
            wikidata_location_qid=(LocationQidType, None),
        )

        system_prompt = """You are a Wikidata location mapping specialist with expertise in geographic locations and administrative divisions.

<mapping_objective>
Map the extracted birthplace to the most accurate Wikidata location following these rules:
</mapping_objective>

<matching_criteria>
1. When there's multiple candidate entities with the same name, and you have no proof for which one matches, match the least specific location level (region over city)
2. Account for different name spellings and transliterations
</matching_criteria>

<rejection_criteria>
- Return None if no candidate is a good match
</rejection_criteria>"""

        # Format candidates with QID, name, and classes
        candidates_text = "\n".join(
            [
                f"- {loc['qid']}: {loc['name']}"
                + (f" (classes: {', '.join(loc['classes'])})" if loc["classes"] else "")
                for loc in candidate_locations
            ]
        )

        user_prompt = f"""Map this extracted birthplace to the correct Wikidata location:

Extracted Birthplace: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata Locations (QID: Name - Classes):
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
            properties = extract_properties(
                openai_client, content, politician.name, politician.wikidata_properties
            )

            # Extract positions
            positions = extract_positions(
                openai_client,
                db,
                content,
                politician.name,
                politician.wikidata_positions,
            )

            # Extract birthplaces
            birthplaces = extract_birthplaces(
                openai_client,
                db,
                content,
                politician.name,
                politician.wikidata_birthplaces,
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
                for pos in positions:
                    date_info = ""
                    if pos.start_date:
                        date_info = f" ({pos.start_date}"
                        if pos.end_date:
                            date_info += f" - {pos.end_date})"
                        else:
                            date_info += " - present)"
                    elif pos.end_date:
                        date_info = f" (until {pos.end_date})"
                    logger.info(f"    {pos.name}{date_info}")
            else:
                logger.info("  No positions extracted")

            if birthplaces:
                logger.info(f"  Birthplaces ({len(birthplaces)}):")
                for birth in birthplaces:
                    logger.info(f"    {birth.location_name}")
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
            for prop_data in properties:
                if prop_data.value:
                    # Check if similar property already exists
                    existing_prop = (
                        db.query(Property)
                        .filter_by(
                            politician_id=politician.id,
                            type=prop_data.type,
                            value=prop_data.value,
                        )
                        .first()
                    )

                    if not existing_prop:
                        new_property = Property(
                            politician_id=politician.id,
                            type=prop_data.type,
                            value=prop_data.value,
                            archived_page_id=archived_page.id,
                            proof_line=prop_data.proof,
                        )
                        db.add(new_property)
                        db.flush()
                        logger.info(
                            f"Added new property: {prop_data.type} = '{prop_data.value}' for {politician.name}"
                        )

        # Store positions - only link to existing positions
        if positions:
            for pos_data in positions:
                if pos_data.wikidata_id:
                    # Only find existing positions, don't create new ones
                    position = (
                        db.query(Position)
                        .filter_by(wikidata_id=pos_data.wikidata_id)
                        .first()
                    )

                    if not position:
                        logger.warning(
                            f"Position '{pos_data.wikidata_id}' not found in database for {politician.name} - skipping"
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
                        if dates_could_be_same(
                            existing_hold.start_date, pos_data.start_date
                        ) and dates_could_be_same(
                            existing_hold.end_date, pos_data.end_date
                        ):
                            overlapping_hold = existing_hold
                            break

                    if overlapping_hold:
                        # Dates could be the same - use precision to decide
                        new_prec = get_date_precision(
                            pos_data.start_date
                        ) + get_date_precision(pos_data.end_date)
                        existing_prec = get_date_precision(
                            overlapping_hold.start_date
                        ) + get_date_precision(overlapping_hold.end_date)

                        if new_prec > existing_prec:
                            # New data has higher precision - update existing record
                            old_range = f"{overlapping_hold.start_date or 'unknown'}-{overlapping_hold.end_date or 'present'}"
                            new_range = f"{pos_data.start_date or 'unknown'}-{pos_data.end_date or 'present'}"

                            overlapping_hold.start_date = pos_data.start_date
                            overlapping_hold.end_date = pos_data.end_date
                            overlapping_hold.archived_page_id = archived_page.id
                            overlapping_hold.proof_line = pos_data.proof
                            db.flush()

                            logger.info(
                                f"Updated position with higher precision: '{position.name}' ({position.wikidata_id}) "
                                f"from ({old_range}) to ({new_range}) for {politician.name}"
                            )
                        else:
                            # Existing data has equal or higher precision - skip new data
                            logger.info(
                                f"Skipped position with equal/lower precision: '{position.name}' ({position.wikidata_id}) "
                                f"({pos_data.start_date or 'unknown'}-{pos_data.end_date or 'present'}) "
                                f"for {politician.name}"
                            )
                    else:
                        # No overlap, add as new record
                        holds_position = HoldsPosition(
                            politician_id=politician.id,
                            position_id=position.wikidata_id,
                            start_date=pos_data.start_date,
                            end_date=pos_data.end_date,
                            archived_page_id=archived_page.id,
                            proof_line=pos_data.proof,
                        )
                        db.add(holds_position)
                        db.flush()

                        date_range = ""
                        if pos_data.start_date:
                            date_range = f" ({pos_data.start_date}"
                            if pos_data.end_date:
                                date_range += f" - {pos_data.end_date})"
                            else:
                                date_range += " - present)"
                        elif pos_data.end_date:
                            date_range = f" (until {pos_data.end_date})"

                        logger.info(
                            f"Added new position: '{position.name}' ({position.wikidata_id}){date_range} for {politician.name}"
                        )

        # Store birthplaces - only link to existing locations
        if birthplaces:
            for birth_data in birthplaces:
                if birth_data.wikidata_id:
                    # Only find existing locations, don't create new ones
                    location = (
                        db.query(Location)
                        .filter_by(wikidata_id=birth_data.wikidata_id)
                        .first()
                    )

                    if not location:
                        logger.warning(
                            f"Location '{birth_data.wikidata_id}' not found in database for {politician.name} - skipping"
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
                            proof_line=birth_data.proof,
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
