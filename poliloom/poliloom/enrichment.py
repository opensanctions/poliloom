"""Simplified enrichment module for extracting politician data from Wikipedia using LLM."""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum
from sqlalchemy.orm import Session
from openai import OpenAI
from pydantic import BaseModel
from unmhtml import MHTMLConverter
import mistune
from bs4 import BeautifulSoup

from .models import (
    Politician,
    Property,
    Position,
    HoldsPosition,
    Location,
    BornAt,
    ArchivedPage,
)
from . import archive
from .database import get_engine

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


def markdown_to_text(markdown_text: str) -> str:
    """Convert markdown text to plain text via HTML rendering then text extraction."""
    if not markdown_text:
        return markdown_text

    html = mistune.html(markdown_text)
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()
    text = " ".join(text.split())
    return text


class PropertyType(str, Enum):
    """Allowed property types for extraction."""

    BIRTH_DATE = "BirthDate"
    DEATH_DATE = "DeathDate"


class ExtractedProperty(BaseModel):
    """Schema for extracted property data."""

    type: PropertyType
    value: str
    proof: str


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str


class ExtractedBirthplace(BaseModel):
    """Schema for extracted birthplace data."""

    location_name: str
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


async def fetch_and_archive_page(
    url: str, db: Session
) -> tuple[Optional[str], Optional[ArchivedPage]]:
    """Fetch web page content and archive it."""
    try:
        # Check if we already have this page archived
        existing_page = db.query(ArchivedPage).filter(ArchivedPage.url == url).first()

        if existing_page:
            logger.info(f"Using existing archived page for {url}")
            try:
                markdown_content = archive.read_archived_content(
                    existing_page.path_root, "md"
                )
                plain_text_content = markdown_to_text(markdown_content)
                return plain_text_content, existing_page
            except FileNotFoundError:
                logger.warning(
                    f"Archived markdown file not found for {existing_page.path_root}"
                )

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
                logger.error(f"Failed to crawl page: {url}")
                db.rollback()
                return None, None

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
                if len(markdown_content) > 50000:
                    markdown_content = markdown_content[:50000] + "..."

                markdown_path = archive.save_archived_content(
                    archived_page.path_root, "md", markdown_content
                )
                logger.info(f"Saved markdown content: {markdown_path}")

                plain_text_content = markdown_to_text(markdown_content)
            else:
                plain_text_content = None

            db.commit()
            return plain_text_content, archived_page

    except Exception as e:
        logger.error(f"Error fetching and archiving page content from {url}: {e}")
        return None, None


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
                if prop.type in ["BirthDate", "DeathDate"]:
                    existing_props.append(f"- {prop.type}: {prop.value}")

            if existing_props:
                existing_context = f"""
### KNOWN WIKIDATA PROPERTIES:
{chr(10).join(existing_props)}

Use this information to:
1. Focus on finding additional or conflicting dates not already in Wikidata
2. Validate or provide more precise versions of existing dates
3. Identify any discrepancies between the article and Wikidata
"""

        system_prompt = """You are a data extraction assistant. Extract ONLY personal properties from Wikipedia article text.

Extract ONLY these two property types:
- BirthDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates
- DeathDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates

Rules:
- Only extract information explicitly stated in the text
- ONLY extract BirthDate and DeathDate - ignore all other personal information
- Use partial dates if full dates aren't available
- For each property, provide a 'proof' field with ONE exact quote that mentions this property
- When multiple sentences support the claim, choose the MOST IMPORTANT/RELEVANT single quote
- Be precise and only extract what is clearly stated"""

        user_prompt = f"""Extract personal properties about {politician_name} from this Wikipedia article text:
{existing_context}
{content}

Politician name: {politician_name}"""

        logger.debug(f"Extracting properties for {politician_name}")

        response = openai_client.beta.chat.completions.parse(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=PropertyExtractionResult,
        )

        message = response.choices[0].message
        if message.parsed is None:
            logger.error("OpenAI property extraction returned None for parsed data")
            return None

        return message.parsed.properties

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
### KNOWN WIKIDATA POSITIONS:
{chr(10).join(existing_pos)}

Use this information to:
1. Identify mentions of these positions in the text (they may appear with different wordings)
2. Find additional positions not already in Wikidata
3. Discover more specific date ranges for known positions
4. Identify more specific variants of generic positions (e.g., specific committee memberships)
"""

        # Stage 1: Free-form extraction
        system_prompt = """You are a political data analyst specializing in extracting structured information from Wikipedia articles and official government websites.

Extract ALL political positions from the provided content following these rules:

### EXTRACTION RULES:
- Extract any political offices, government roles, elected positions, or political appointments
- Include interim/acting positions and temporary appointments
- Use exact position names as they appear in the source

### DATE FORMAT:
- Use YYYY-MM-DD, YYYY-MM, or YYYY format when available
- Leave end_date null if position is current or unknown
- Include "acting" or "interim" in the position name if applicable

### PROOF REQUIREMENT:
- Each position MUST include ONE exact quote mentioning this position
- When multiple sentences support the claim, choose the MOST IMPORTANT/RELEVANT single quote
- The proof should contain sufficient context to verify the claim"""

        user_prompt = f"""Extract ALL political positions held by {politician_name} from the content below.

### CONTEXT:
Politician: {politician_name}
{existing_context}
### CONTENT:
\"\"\"
{content}
\"\"\""""

        logger.debug(f"Stage 1: Extracting positions for {politician_name}")

        response = openai_client.beta.chat.completions.parse(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=FreeFormPositionResult,
        )

        message = response.choices[0].message
        if message.parsed is None:
            logger.error("OpenAI position extraction returned None")
            return None

        free_form_positions = message.parsed.positions
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
            position_names = [pos.name for pos in similar_positions]
            mapped_name = map_to_wikidata_position(
                openai_client, free_pos.name, free_pos.proof, position_names
            )

            if mapped_name:
                # Verify position exists in database
                position = db.query(Position).filter_by(name=mapped_name).first()
                if position:
                    mapped_positions.append(
                        ExtractedPosition(
                            name=position.name,
                            start_date=free_pos.start_date,
                            end_date=free_pos.end_date,
                            proof=free_pos.proof,
                        )
                    )
                    logger.debug(f"Mapped '{free_pos.name}' -> '{position.name}'")

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
### KNOWN WIKIDATA BIRTHPLACES:
{chr(10).join(existing_bp)}

Use this information to:
1. Identify mentions of these locations in the text (they may appear with different wordings)
2. Find more specific birthplace information (e.g., specific city if only country is known)
3. Identify any conflicting birthplace claims
"""

        # Stage 1: Free-form extraction
        system_prompt = """You are a biographical data specialist extracting location information from Wikipedia articles and official government profiles.

Extract birthplace information following these rules:

### EXTRACTION RULES:
- Extract birthplace as mentioned in the source (city, town, village or region)

### PROOF REQUIREMENT:
- Provide ONE exact quote from the source content that mentions the birthplace
- When multiple sentences support the claim, choose the MOST IMPORTANT/RELEVANT single quote"""

        user_prompt = f"""Extract the birthplace of {politician_name} from the content below.

### CONTEXT:
Politician: {politician_name}
{existing_context}
### CONTENT:
\"\"\"
{content}
\"\"\""""

        logger.debug(f"Stage 1: Extracting birthplace for {politician_name}")

        response = openai_client.beta.chat.completions.parse(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=FreeFormBirthplaceResult,
        )

        message = response.choices[0].message
        if message.parsed is None:
            logger.error("OpenAI birthplace extraction returned None")
            return None

        free_form_birthplaces = message.parsed.birthplaces
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
            location_names = [loc.name for loc in similar_locations]
            mapped_name = map_to_wikidata_location(
                openai_client,
                free_birth.location_name,
                free_birth.proof,
                location_names,
            )

            if mapped_name:
                # Verify location exists in database
                location = db.query(Location).filter_by(name=mapped_name).first()
                if location:
                    mapped_birthplaces.append(
                        ExtractedBirthplace(
                            location_name=location.name, proof=free_birth.proof
                        )
                    )
                    logger.debug(
                        f"Mapped '{free_birth.location_name}' -> '{location.name}'"
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
    candidate_positions: List[str],
) -> Optional[str]:
    """Map extracted position name to Wikidata position using LLM."""
    try:
        from typing import Literal
        from pydantic import create_model

        # Create dynamic model with candidate positions
        if candidate_positions:
            entity_names = [pos for pos in candidate_positions if pos is not None]
            PositionNameType = Optional[Literal[tuple(entity_names)]]
        else:
            PositionNameType = Optional[str]

        DynamicMappingResult = create_model(
            "PositionMappingResult",
            wikidata_position_name=(PositionNameType, None),
        )

        system_prompt = """You are a Wikidata mapping specialist with expertise in political positions and government structures.

Map the extracted position to the most accurate Wikidata position following these rules:

### MATCHING CRITERIA:
1. STRONGLY PREFER country-specific positions (e.g., "Minister of Foreign Affairs (Myanmar)" over generic "Minister of Foreign Affairs")
2. PREFER positions from the same political system/country context
4. Match only when confidence is HIGH - be precise about role equivalence

### REJECTION CRITERIA:
- Return None if no candidate is a good match
- Reject if the positions clearly refer to different roles
- Reject if geographic/jurisdictional scope differs significantly"""

        user_prompt = f"""Map this extracted position to the correct Wikidata position:

Extracted Position: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata Positions:
{chr(10).join([f"- {pos}" for pos in candidate_positions])}

Select the best match or None if no good match exists."""

        response = openai_client.beta.chat.completions.parse(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=DynamicMappingResult,
        )

        message = response.choices[0].message
        if message.parsed is None:
            return None

        return message.parsed.wikidata_position_name

    except Exception as e:
        logger.error(f"Error mapping position with LLM: {e}")
        return None


def map_to_wikidata_location(
    openai_client: OpenAI,
    extracted_name: str,
    proof_text: str,
    candidate_locations: List[str],
) -> Optional[str]:
    """Map extracted location name to Wikidata location using LLM."""
    try:
        from typing import Literal
        from pydantic import create_model

        # Create dynamic model with candidate locations
        if candidate_locations:
            entity_names = [loc for loc in candidate_locations if loc is not None]
            LocationNameType = Optional[Literal[tuple(entity_names)]]
        else:
            LocationNameType = Optional[str]

        DynamicMappingResult = create_model(
            "LocationMappingResult",
            wikidata_location_name=(LocationNameType, None),
        )

        system_prompt = """You are a Wikidata location mapping specialist with expertise in geographic locations and administrative divisions.

Map the extracted birthplace to the most accurate Wikidata location following these rules:

### MATCHING CRITERIA:
1. When there's multiple candidate entities with the same name, and you have no proof for which one matches, match the least specific location level (region over city)
2. Account for different name spellings and transliterations

### REJECTION CRITERIA:
- Return None if no candidate is a good match"""

        user_prompt = f"""Map this extracted birthplace to the correct Wikidata location:

Extracted Birthplace: "{extracted_name}"
Proof Context: "{proof_text}"

Candidate Wikidata Locations:
{chr(10).join([f"- {loc}" for loc in candidate_locations])}

Select the best match or None if no good match exists."""

        response = openai_client.beta.chat.completions.parse(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=DynamicMappingResult,
        )

        message = response.choices[0].message
        if message.parsed is None:
            return None

        return message.parsed.wikidata_location_name

    except Exception as e:
        logger.error(f"Error mapping location with LLM: {e}")
        return None


async def enrich_politician_from_wikipedia(politician: Politician) -> bool:
    """
    Enrich a politician's data by extracting information from their Wikipedia sources.

    Args:
        politician: The Politician model instance to enrich

    Returns:
        True if enrichment was successful, False otherwise
    """
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with Session(get_engine()) as db:
        try:
            # Merge the politician into this session
            politician = db.merge(politician)

            if not politician.wikipedia_links:
                logger.warning(
                    f"No Wikipedia links found for politician {politician.name}"
                )
                return False

            # Process only English Wikipedia source
            english_wikipedia_link = None
            for wikipedia_link in politician.wikipedia_links:
                if "en.wikipedia.org" in wikipedia_link.url:
                    english_wikipedia_link = wikipedia_link
                    break

            if not english_wikipedia_link:
                logger.warning(
                    f"No English Wikipedia source found for politician {politician.name}"
                )
                return False

            logger.info(
                f"Processing English Wikipedia source: {english_wikipedia_link.url}"
            )

            # Fetch and archive the page
            content, archived_page = await fetch_and_archive_page(
                english_wikipedia_link.url, db
            )
            if not content or not archived_page:
                logger.warning(f"Failed to fetch content for {politician.name}")
                return False

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
            logger.info(f"LLM extracted data for {politician.name}:")
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
                logger.info(f"Successfully enriched politician {politician.name}")
                return True
            else:
                db.rollback()
                return False

        except Exception as e:
            logger.error(f"Error enriching politician {politician.wikidata_id}: {e}")
            return False

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
                if pos_data.name:
                    # Only find existing positions, don't create new ones
                    position = db.query(Position).filter_by(name=pos_data.name).first()

                    if not position:
                        logger.warning(
                            f"Position '{pos_data.name}' not found in database for {politician.name} - skipping"
                        )
                        continue

                    # Check if this position relationship already exists
                    existing_holds = (
                        db.query(HoldsPosition)
                        .filter_by(
                            politician_id=politician.id,
                            position_id=position.wikidata_id,
                            start_date=pos_data.start_date,
                            end_date=pos_data.end_date,
                        )
                        .first()
                    )

                    if not existing_holds:
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
                            f"Added new position: '{pos_data.name}'{date_range} for {politician.name}"
                        )

        # Store birthplaces - only link to existing locations
        if birthplaces:
            for birth_data in birthplaces:
                if birth_data.location_name:
                    # Only find existing locations, don't create new ones
                    location = (
                        db.query(Location)
                        .filter_by(name=birth_data.location_name)
                        .first()
                    )

                    if not location:
                        logger.warning(
                            f"Location '{birth_data.location_name}' not found in database for {politician.name} - skipping"
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
                            f"Added new birthplace: '{birth_data.location_name}' for {politician.name}"
                        )

        return True

    except Exception as e:
        logger.error(f"Error storing extracted data: {e}")
        return False
