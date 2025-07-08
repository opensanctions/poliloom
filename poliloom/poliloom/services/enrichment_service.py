"""Service for enriching politician data from Wikipedia using LLM extraction."""

import os
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy.orm import Session
import httpx
from bs4 import BeautifulSoup
import logging
from openai import OpenAI
from pydantic import BaseModel, create_model
from typing import Literal

from ..models import (
    Politician,
    Property,
    Position,
    HoldsPosition,
    Location,
    BornAt,
    Country,
)
from ..database import SessionLocal

logger = logging.getLogger(__name__)


class PropertyType(str, Enum):
    """Allowed property types for extraction."""

    BIRTH_DATE = "BirthDate"
    DEATH_DATE = "DeathDate"


class ExtractedProperty(BaseModel):
    """Schema for extracted property data."""

    type: PropertyType
    value: str


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str


class FreeFormExtractedPosition(BaseModel):
    """Schema for free-form position extraction (Stage 1)."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str


class PositionMappingResult(BaseModel):
    """Schema for position mapping result (Stage 2)."""

    wikidata_position_name: Optional[str] = None  # None if no match found


class PropertyExtractionResult(BaseModel):
    """Schema for property-only LLM extraction result."""

    properties: List[ExtractedProperty]


class PositionExtractionResult(BaseModel):
    """Schema for position-only LLM extraction result."""

    positions: List[ExtractedPosition]


class FreeFormPositionExtractionResult(BaseModel):
    """Schema for free-form position extraction result (Stage 1)."""

    positions: List[FreeFormExtractedPosition]


class ExtractedBirthplace(BaseModel):
    """Schema for extracted birthplace data."""

    location_name: str
    proof: str


class FreeFormExtractedBirthplace(BaseModel):
    """Schema for free-form birthplace extraction (Stage 1)."""

    location_name: str
    proof: str


class BirthplaceMappingResult(BaseModel):
    """Schema for birthplace mapping result (Stage 2)."""

    wikidata_location_name: Optional[str] = None  # None if no match found


class BirthplaceExtractionResult(BaseModel):
    """Schema for birthplace-only LLM extraction result."""

    birthplaces: List[ExtractedBirthplace]


class FreeFormBirthplaceExtractionResult(BaseModel):
    """Schema for free-form birthplace extraction result (Stage 1)."""

    birthplaces: List[FreeFormExtractedBirthplace]


def create_dynamic_position_model(allowed_positions: List[str]):
    """Create dynamic Pydantic model that restricts positions to allowed values."""

    # Create dynamic position name type
    if allowed_positions:
        PositionNameType = Literal[tuple(allowed_positions)]
    else:
        # If no positions allowed, create a type that can't match anything
        PositionNameType = Literal["__NO_POSITIONS_ALLOWED__"]

    # Create dynamic ExtractedPosition model
    DynamicExtractedPosition = create_model(
        "DynamicExtractedPosition",
        name=(PositionNameType, ...),
        start_date=(Optional[str], None),
        end_date=(Optional[str], None),
        proof=(str, ...),
    )

    # Create dynamic PositionExtractionResult model
    DynamicPositionExtractionResult = create_model(
        "DynamicPositionExtractionResult",
        positions=(List[DynamicExtractedPosition], []),
    )

    return DynamicPositionExtractionResult


def create_dynamic_mapping_model(allowed_positions: List[str]):
    """Create dynamic Pydantic model for position mapping with None option."""

    # Create union type with positions + None
    if allowed_positions:
        # Filter out None values and add None as separate option
        position_names = [pos for pos in allowed_positions if pos is not None]
        PositionNameType = Optional[Literal[tuple(position_names)]]
    else:
        PositionNameType = Optional[str]  # Fallback

    # Create dynamic PositionMappingResult model
    DynamicPositionMappingResult = create_model(
        "DynamicPositionMappingResult",
        wikidata_position_name=(PositionNameType, None),
    )

    return DynamicPositionMappingResult


def create_dynamic_birthplace_mapping_model(allowed_locations: List[str]):
    """Create dynamic Pydantic model for birthplace mapping with None option."""

    # Create union type with locations + None
    if allowed_locations:
        # Filter out None values and add None as separate option
        location_names = [loc for loc in allowed_locations if loc is not None]
        LocationNameType = Optional[Literal[tuple(location_names)]]
    else:
        LocationNameType = Optional[str]  # Fallback

    # Create dynamic BirthplaceMappingResult model
    DynamicBirthplaceMappingResult = create_model(
        "DynamicBirthplaceMappingResult",
        wikidata_location_name=(LocationNameType, None),
    )

    return DynamicBirthplaceMappingResult


class EnrichmentService:
    """Service for enriching politician data from Wikipedia sources."""

    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.http_client = httpx.Client(timeout=30.0)

    def enrich_politician_from_wikipedia(self, wikidata_id: str) -> bool:
        """
        Enrich a politician's data by extracting information from their Wikipedia sources.

        Args:
            wikidata_id: The Wikidata ID of the politician to enrich (e.g., Q123456)

        Returns:
            True if enrichment was successful, False otherwise
        """
        db = SessionLocal()
        try:
            # Normalize Wikidata ID
            if not wikidata_id.upper().startswith("Q"):
                wikidata_id = f"Q{wikidata_id}"
            else:
                wikidata_id = wikidata_id.upper()

            # Get politician by Wikidata ID
            politician = db.query(Politician).filter_by(wikidata_id=wikidata_id).first()
            if not politician:
                logger.error(f"Politician with Wikidata ID {wikidata_id} not found")
                return False

            if not politician.sources:
                logger.warning(
                    f"No Wikipedia sources found for politician {politician.name}"
                )
                return False

            # Process only English Wikipedia source
            extracted_data = []
            english_source = None
            for source in politician.sources:
                if "en.wikipedia.org" in source.url:
                    english_source = source
                    break

            if english_source:
                logger.info(
                    f"Processing English Wikipedia source: {english_source.url}"
                )
                content = self._fetch_wikipedia_content(english_source.url)
                if content:
                    # Get politician's primary country from citizenships
                    primary_country = None
                    if politician.citizenships:
                        primary_country = politician.citizenships[0].country.name

                    data = self._extract_data_with_llm(
                        content, politician.name, primary_country, politician
                    )
                    if data:
                        # Log what the LLM proposed
                        self._log_extraction_results(politician.name, data)
                        extracted_data.append((english_source, data))
            else:
                logger.warning(
                    f"No English Wikipedia source found for politician {politician.name}"
                )

            if not extracted_data:
                logger.warning(
                    f"No data extracted from Wikipedia sources for {politician.name}"
                )
                return False

            # Store extracted data in database
            success = self._store_extracted_data(db, politician, extracted_data)

            if success:
                db.commit()
                logger.info(f"Successfully enriched politician {politician.name}")
                return True
            else:
                db.rollback()
                return False

        except Exception as e:
            db.rollback()
            logger.error(f"Error enriching politician {wikidata_id}: {e}")
            return False
        finally:
            db.close()

    def _fetch_wikipedia_content(self, url: str) -> Optional[str]:
        """Fetch and clean Wikipedia article content."""
        try:
            response = self.http_client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove unwanted elements
            for element in soup.find_all(
                ["script", "style", "nav", "footer", "header"]
            ):
                element.decompose()

            # Get main content - Wikipedia articles use div with id="mw-content-text"
            content_div = soup.find("div", {"id": "mw-content-text"})
            if content_div:
                # Extract text from paragraphs in the main content
                paragraphs = content_div.find_all("p")
                content = "\n\n".join(
                    [p.get_text().strip() for p in paragraphs if p.get_text().strip()]
                )

                # Limit content length to avoid token limits
                if len(content) > 8000:
                    content = content[:8000] + "..."

                return content

            logger.warning(f"Could not find main content in Wikipedia page: {url}")
            return None

        except httpx.RequestError as e:
            logger.error(f"Error fetching Wikipedia content from {url}: {e}")
            return None

    def _find_exact_position_match(
        self, db: Session, position_name: str
    ) -> Optional[Position]:
        """Find exact match for position name in database."""
        # Try exact match (case-insensitive)
        exact_match = (
            db.query(Position).filter(Position.name.ilike(position_name)).first()
        )

        return exact_match

    def _get_similar_positions_for_mapping(
        self,
        db: Session,
        position_name: str,
        politician: Politician,
        max_positions: int = 100,
    ) -> List[str]:
        """Get similar positions for mapping a single extracted position to Wikidata."""
        # Generate embedding for the position name
        from ..embeddings import generate_embedding

        query_embedding = generate_embedding(position_name)

        # Query similar positions using pgvector (no country filtering)
        positions = (
            db.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(query_embedding))
            .limit(max_positions)
            .all()
        )

        return [position.name for position in positions]

    def _llm_map_to_wikidata_position(
        self, extracted_position: str, candidate_positions: List[str], proof_text: str
    ) -> Optional[str]:
        """Use LLM to map extracted position to correct Wikidata position."""
        try:
            # Create dynamic model with candidate positions
            DynamicPositionMappingResult = create_dynamic_mapping_model(
                candidate_positions
            )

            system_prompt = """You are a position mapping assistant. Given an extracted political position and a list of candidate Wikidata positions, select the most accurate match.

Rules:
- Choose the Wikidata position that best matches the extracted position
- Consider the context provided in the proof text
- PREFER country-specific positions over generic ones (e.g., "Minister of Foreign Affairs (Myanmar)" over "Minister of Foreign Affairs")
- If no candidate position is a good match, return None
- Be precise - only match if you're confident the positions refer to the same role"""

            user_prompt = f"""Map this extracted position to the correct Wikidata position:

Extracted Position: "{extracted_position}"
Proof Context: "{proof_text}"

Candidate Wikidata Positions:
{chr(10).join([f"- {pos}" for pos in candidate_positions])}

Select the best match or None if no good match exists."""

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=DynamicPositionMappingResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error("OpenAI position mapping returned None")
                return None

            return message.parsed.wikidata_position_name

        except Exception as e:
            logger.error(f"Error mapping position with LLM: {e}")
            return None

    def _extract_data_with_llm(
        self, content: str, politician_name: str, country: str, politician: Politician
    ) -> Optional[dict]:
        """Extract structured data from Wikipedia content using separate OpenAI calls for properties, positions, and birthplaces."""
        try:
            # Extract properties first
            properties = self._extract_properties_with_llm(
                content, politician_name, country
            )

            # Extract positions second
            positions = self._extract_positions_with_llm(
                content, politician_name, country, politician
            )

            # Extract birthplaces third
            birthplaces = self._extract_birthplaces_with_llm(
                content, politician_name, country, politician
            )

            return {
                "properties": properties or [],
                "positions": positions or [],
                "birthplaces": birthplaces or [],
            }

        except Exception as e:
            logger.error(f"Error extracting data with LLM: {e}")
            return None

    def _extract_properties_with_llm(
        self, content: str, politician_name: str, country: str
    ) -> Optional[List[ExtractedProperty]]:
        """Extract properties from Wikipedia content using OpenAI structured output."""
        try:
            system_prompt = """You are a data extraction assistant. Extract ONLY personal properties from Wikipedia article text.

Extract ONLY these two property types:
- BirthDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates
- DeathDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates

Rules:
- Only extract information explicitly stated in the text
- ONLY extract BirthDate and DeathDate - ignore all other personal information
- Use partial dates if full dates aren't available
- Be precise and only extract what is clearly stated"""

            user_prompt = f"""Extract personal properties about {politician_name} from this Wikipedia article text:

{content}

Politician name: {politician_name}
Country: {country or "Unknown"}"""

            logger.debug(f"Extracting properties for {politician_name}")

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=PropertyExtractionResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error("OpenAI property extraction returned None for parsed data")
                logger.error(f"Response content: {message.content}")
                logger.error(f"Response refusal: {getattr(message, 'refusal', None)}")
                return None

            return message.parsed.properties

        except Exception as e:
            logger.error(f"Error extracting properties with LLM: {e}")
            return None

    def _extract_positions_with_llm(
        self, content: str, politician_name: str, country: str, politician: Politician
    ) -> Optional[List[ExtractedPosition]]:
        """Extract positions using two-stage approach: free-form extraction + Wikidata mapping."""
        try:
            # Stage 1: Free-form position extraction
            free_form_positions = self._extract_positions_free_form(
                content, politician_name, country
            )

            if not free_form_positions:
                logger.warning(
                    f"No free-form positions extracted for {politician_name}"
                )
                return []

            # Stage 2: Map each position to Wikidata
            mapped_positions = []
            db = SessionLocal()
            try:
                for free_pos in free_form_positions:
                    mapped_pos = self._map_position_to_wikidata(
                        db, free_pos, politician
                    )
                    if mapped_pos:
                        mapped_positions.append(mapped_pos)
            finally:
                db.close()

            logger.info(
                f"Mapped {len(mapped_positions)} out of {len(free_form_positions)} "
                f"extracted positions for {politician_name}"
            )

            return mapped_positions

        except Exception as e:
            logger.error(f"Error extracting positions with two-stage approach: {e}")
            return None

    def _extract_positions_free_form(
        self, content: str, politician_name: str, country: str
    ) -> Optional[List[FreeFormExtractedPosition]]:
        """Stage 1: Extract positions in free-form without constraints."""
        try:
            system_prompt = """You are a data extraction assistant. Extract ALL political positions from Wikipedia article text.

Extract any political offices, government roles, elected positions, or political appointments mentioned in the text. Use natural language descriptions as they appear in the text.

Rules:
- Extract ALL political positions mentioned in the text, even if informal
- Use the exact position names as they appear in Wikipedia 
- Include start/end dates in YYYY-MM-DD, YYYY-MM, or YYYY format if available
- Leave end_date null if position is current or dates are unknown
- For each position, provide a 'proof' field with the exact quote that mentions this position
- Do not worry about exact Wikidata position names - extract naturally"""

            user_prompt = f"""Extract ALL political positions held by {politician_name} from this Wikipedia article:

{content}

Politician name: {politician_name}
Country: {country or "Unknown"}"""

            logger.debug(
                f"Stage 1: Free-form position extraction for {politician_name}"
            )

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=FreeFormPositionExtractionResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error("OpenAI free-form position extraction returned None")
                logger.error(f"Response content: {message.content}")
                logger.error(f"Response refusal: {getattr(message, 'refusal', None)}")
                return None

            logger.info(
                f"Stage 1: Extracted {len(message.parsed.positions)} free-form positions "
                f"for {politician_name}"
            )

            return message.parsed.positions

        except Exception as e:
            logger.error(f"Error in Stage 1 free-form position extraction: {e}")
            return None

    def _map_position_to_wikidata(
        self, db: Session, free_pos: FreeFormExtractedPosition, politician: Politician
    ) -> Optional[ExtractedPosition]:
        """Stage 2: Map a free-form position to Wikidata position using similarity search + LLM mapping."""
        try:
            # Use similarity search + LLM mapping
            similar_positions = self._get_similar_positions_for_mapping(
                db, free_pos.name, politician
            )

            if not similar_positions:
                logger.debug(f"No similar positions found for '{free_pos.name}'")
                return None

            # Use LLM to map to correct Wikidata position
            mapped_position_name = self._llm_map_to_wikidata_position(
                free_pos.name, similar_positions, free_pos.proof
            )

            if not mapped_position_name:
                logger.debug(
                    f"LLM could not map '{free_pos.name}' to Wikidata position"
                )
                return None

            # Verify the mapped position exists in our database
            final_position = (
                db.query(Position).filter_by(name=mapped_position_name).first()
            )
            if not final_position:
                logger.warning(
                    f"LLM mapped to non-existent position: '{mapped_position_name}'"
                )
                return None

            logger.debug(f"LLM mapped '{free_pos.name}' -> '{mapped_position_name}'")
            return ExtractedPosition(
                name=final_position.name,
                start_date=free_pos.start_date,
                end_date=free_pos.end_date,
                proof=free_pos.proof,
            )

        except Exception as e:
            logger.error(f"Error mapping position '{free_pos.name}' to Wikidata: {e}")
            return None

    def _extract_birthplaces_with_llm(
        self, content: str, politician_name: str, country: str, politician: Politician
    ) -> Optional[List[ExtractedBirthplace]]:
        """Extract birthplaces using two-stage approach: free-form extraction + Wikidata mapping."""
        try:
            # Stage 1: Free-form birthplace extraction
            free_form_birthplaces = self._extract_birthplaces_free_form(
                content, politician_name, country
            )

            if not free_form_birthplaces:
                logger.info(f"No free-form birthplaces extracted for {politician_name}")
                return []

            # Stage 2: Map each birthplace to Wikidata
            mapped_birthplaces = []
            db = SessionLocal()
            try:
                for free_birth in free_form_birthplaces:
                    mapped_birth = self._map_birthplace_to_wikidata(
                        db, free_birth, politician
                    )
                    if mapped_birth:
                        mapped_birthplaces.append(mapped_birth)
            finally:
                db.close()

            logger.info(
                f"Mapped {len(mapped_birthplaces)} out of {len(free_form_birthplaces)} "
                f"extracted birthplaces for {politician_name}"
            )

            return mapped_birthplaces

        except Exception as e:
            logger.error(f"Error extracting birthplaces with two-stage approach: {e}")
            return None

    def _extract_birthplaces_free_form(
        self, content: str, politician_name: str, country: str
    ) -> Optional[List[FreeFormExtractedBirthplace]]:
        """Stage 1: Extract birthplaces in free-form without constraints."""
        try:
            system_prompt = """You are a data extraction assistant. Extract birthplace information from Wikipedia article text.

Extract the birthplace of the politician mentioned in the text. Use natural language descriptions as they appear in the text.

Rules:
- Extract the birthplace location as mentioned in the Wikipedia article
- Include city, town, village, or region names as they appear
- For each birthplace, provide a 'proof' field with the exact quote that mentions this birthplace
- Only extract birthplace information explicitly stated in the text
- Do not worry about exact Wikidata location names - extract naturally"""

            user_prompt = f"""Extract the birthplace of {politician_name} from this Wikipedia article:

{content}

Politician name: {politician_name}
Country: {country or "Unknown"}"""

            logger.debug(
                f"Stage 1: Free-form birthplace extraction for {politician_name}"
            )

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=FreeFormBirthplaceExtractionResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error("OpenAI free-form birthplace extraction returned None")
                logger.error(f"Response content: {message.content}")
                logger.error(f"Response refusal: {getattr(message, 'refusal', None)}")
                return None

            logger.info(
                f"Stage 1: Extracted {len(message.parsed.birthplaces)} free-form birthplaces "
                f"for {politician_name}"
            )

            return message.parsed.birthplaces

        except Exception as e:
            logger.error(f"Error in Stage 1 free-form birthplace extraction: {e}")
            return None

    def _find_exact_location_match(
        self, db: Session, location_name: str
    ) -> Optional[Location]:
        """Find exact match for location name in database."""
        # Try exact match (case-insensitive)
        exact_match = (
            db.query(Location).filter(Location.name.ilike(location_name)).first()
        )

        return exact_match

    def _get_similar_locations_for_mapping(
        self, db: Session, location_name: str, max_locations: int = 100
    ) -> List[str]:
        """Get similar locations for mapping a single extracted birthplace to Wikidata."""
        # Generate embedding for the location name
        from ..embeddings import generate_embedding

        query_embedding = generate_embedding(location_name)

        # Query similar locations using pgvector
        locations = (
            db.query(Location)
            .filter(Location.embedding.isnot(None))
            .order_by(Location.embedding.cosine_distance(query_embedding))
            .limit(max_locations)
            .all()
        )

        return [location.name for location in locations]

    def _llm_map_to_wikidata_location(
        self, extracted_location: str, candidate_locations: List[str], proof_text: str
    ) -> Optional[str]:
        """Use LLM to map extracted birthplace to correct Wikidata location."""
        try:
            # Create dynamic model with candidate locations
            DynamicBirthplaceMappingResult = create_dynamic_birthplace_mapping_model(
                candidate_locations
            )

            system_prompt = """You are a location mapping assistant. Given an extracted birthplace and a list of candidate Wikidata locations, select the most accurate match.

Rules:
- Choose the Wikidata location that best matches the extracted birthplace
- Consider the context provided in the proof text
- If no candidate location is a good match, return None
- Be precise - only match if you're confident the locations refer to the same place
- Consider that birthplaces can be cities, towns, villages, regions, or even countries"""

            user_prompt = f"""Map this extracted birthplace to the correct Wikidata location:

Extracted Birthplace: "{extracted_location}"
Proof Context: "{proof_text}"

Candidate Wikidata Locations:
{chr(10).join([f"- {loc}" for loc in candidate_locations])}

Select the best match or None if no good match exists."""

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=DynamicBirthplaceMappingResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error("OpenAI birthplace mapping returned None")
                return None

            return message.parsed.wikidata_location_name

        except Exception as e:
            logger.error(f"Error mapping birthplace with LLM: {e}")
            return None

    def _map_birthplace_to_wikidata(
        self,
        db: Session,
        free_birth: FreeFormExtractedBirthplace,
        politician: Politician,
    ) -> Optional[ExtractedBirthplace]:
        """Stage 2: Map a free-form birthplace to Wikidata location using similarity search + LLM mapping."""
        try:
            # Use similarity search + LLM mapping
            similar_locations = self._get_similar_locations_for_mapping(
                db, free_birth.location_name
            )

            if not similar_locations:
                logger.debug(
                    f"No similar locations found for '{free_birth.location_name}'"
                )
                return None

            # Use LLM to map to correct Wikidata location
            mapped_location_name = self._llm_map_to_wikidata_location(
                free_birth.location_name, similar_locations, free_birth.proof
            )

            if not mapped_location_name:
                logger.debug(
                    f"LLM could not map '{free_birth.location_name}' to Wikidata location"
                )
                return None

            # Verify the mapped location exists in our database
            final_location = (
                db.query(Location).filter_by(name=mapped_location_name).first()
            )
            if not final_location:
                logger.warning(
                    f"LLM mapped to non-existent location: '{mapped_location_name}'"
                )
                return None

            logger.debug(
                f"LLM mapped '{free_birth.location_name}' -> '{mapped_location_name}'"
            )
            return ExtractedBirthplace(
                location_name=final_location.name,
                proof=free_birth.proof,
            )

        except Exception as e:
            logger.error(
                f"Error mapping birthplace '{free_birth.location_name}' to Wikidata: {e}"
            )
            return None

    def _log_extraction_results(self, politician_name: str, data: dict) -> None:
        """Log what the LLM extracted from Wikipedia."""
        logger.info(f"LLM extracted data for {politician_name}:")

        properties = data.get("properties", [])
        if properties:
            logger.info(f"  Properties ({len(properties)}):")
            for prop in properties:
                logger.info(f"    {prop.type}: {prop.value}")
        else:
            logger.info("  No properties extracted")

        positions = data.get("positions", [])
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
                logger.info(f"      Proof: {pos.proof}")
        else:
            logger.info("  No positions extracted")

        birthplaces = data.get("birthplaces", [])
        if birthplaces:
            logger.info(f"  Birthplaces ({len(birthplaces)}):")
            for birth in birthplaces:
                logger.info(f"    {birth.location_name}")
                logger.info(f"      Proof: {birth.proof}")
        else:
            logger.info("  No birthplaces extracted")

    def _store_extracted_data(
        self, db: Session, politician: Politician, extracted_data: List[tuple]
    ) -> bool:
        """Store extracted data in the database."""
        try:
            for source, data in extracted_data:
                # Update source extraction timestamp
                source.extracted_at = datetime.now(timezone.utc)

                # Store properties
                for prop_data in data.get("properties", []):
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
                                is_extracted=True,  # Newly extracted, needs confirmation
                            )
                            db.add(new_property)
                            db.flush()  # Get the ID

                            # Link to source
                            new_property.sources.append(source)
                            logger.info(
                                f"Added new property: {prop_data.type} = '{prop_data.value}' for {politician.name}"
                            )

                # Store positions - only link to existing positions
                for pos_data in data.get("positions", []):
                    if pos_data.name:
                        # Only find existing positions, don't create new ones
                        position = (
                            db.query(Position).filter_by(name=pos_data.name).first()
                        )

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
                                position_id=position.id,
                                start_date=pos_data.start_date,
                                end_date=pos_data.end_date,
                            )
                            .first()
                        )

                        if not existing_holds:
                            holds_position = HoldsPosition(
                                politician_id=politician.id,
                                position_id=position.id,
                                start_date=pos_data.start_date,
                                end_date=pos_data.end_date,
                                is_extracted=True,  # Newly extracted, needs confirmation
                            )
                            db.add(holds_position)
                            db.flush()

                            # Link to source
                            holds_position.sources.append(source)

                            # Format date range for logging
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
                for birth_data in data.get("birthplaces", []):
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
                                location_id=location.id,
                            )
                            .first()
                        )

                        if not existing_birth:
                            born_at = BornAt(
                                politician_id=politician.id,
                                location_id=location.id,
                                is_extracted=True,  # Newly extracted, needs confirmation
                            )
                            db.add(born_at)
                            db.flush()

                            # Link to source
                            born_at.sources.append(source)

                            logger.info(
                                f"Added new birthplace: '{birth_data.location_name}' for {politician.name}"
                            )

            return True

        except Exception as e:
            logger.error(f"Error storing extracted data: {e}")
            return False

    def close(self):
        """Close HTTP client."""
        self.http_client.close()
