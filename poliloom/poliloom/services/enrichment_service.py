"""Service for enriching politician data from Wikipedia using LLM extraction."""

import os
from typing import List, Optional
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session
import httpx
from bs4 import BeautifulSoup
import logging
from openai import OpenAI
from pydantic import BaseModel, create_model
from typing import Literal

from ..models import Politician, Property, Position, HoldsPosition
from ..database import SessionLocal

logger = logging.getLogger(__name__)


class PropertyType(str, Enum):
    """Allowed property types for extraction."""

    BIRTH_DATE = "BirthDate"
    BIRTH_PLACE = "BirthPlace"
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


class PropertyExtractionResult(BaseModel):
    """Schema for property-only LLM extraction result."""

    properties: List[ExtractedProperty]


class PositionExtractionResult(BaseModel):
    """Schema for position-only LLM extraction result."""

    positions: List[ExtractedPosition]


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

    def _get_relevant_positions_for_content(
        self, db: Session, content: str, politician: Politician, max_positions: int = 100
    ) -> List[str]:
        """Get list of position names that are relevant to the Wikipedia content and politician's citizenships."""
        if not politician.citizenships:
            return []

        # Get all countries this politician has citizenship in
        citizenship_countries = [citizenship.country.iso_code for citizenship in politician.citizenships]
        
        # Find relevant positions for each citizenship country and combine results
        all_relevant_positions = []
        positions_per_country = max(max_positions // len(citizenship_countries), 10)
        
        for country_code in citizenship_countries:
            # Use vector similarity to find relevant positions based on content
            similar_positions = Position.find_similar(
                db, content, top_k=positions_per_country, country_filter=country_code
            )
            all_relevant_positions.extend([position.name for position, similarity in similar_positions])
        
        # Remove duplicates while preserving order, then limit to max_positions
        seen = set()
        unique_positions = []
        for pos_name in all_relevant_positions:
            if pos_name not in seen:
                seen.add(pos_name)
                unique_positions.append(pos_name)
                if len(unique_positions) >= max_positions:
                    break
        
        return unique_positions

    def _extract_data_with_llm(
        self, content: str, politician_name: str, country: str, politician: Politician
    ) -> Optional[dict]:
        """Extract structured data from Wikipedia content using separate OpenAI calls for properties and positions."""
        try:
            # Extract properties first
            properties = self._extract_properties_with_llm(content, politician_name, country)
            
            # Extract positions second
            positions = self._extract_positions_with_llm(content, politician_name, country, politician)
            
            return {
                'properties': properties or [],
                'positions': positions or []
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

Extract ONLY these three property types:
- BirthDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates
- BirthPlace: City, Country format
- DeathDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates

Rules:
- Only extract information explicitly stated in the text
- ONLY extract BirthDate, BirthPlace, and DeathDate - ignore all other personal information
- Use partial dates if full dates aren't available
- Be precise and only extract what is clearly stated"""

            user_prompt = f"""Extract personal properties about {politician_name} from this Wikipedia article text:

{content}

Politician name: {politician_name}
Country: {country or 'Unknown'}"""

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
        """Extract positions from Wikipedia content using OpenAI structured output."""
        try:
            # Get relevant positions for this politician based on content
            db = SessionLocal()
            try:
                allowed_positions = self._get_relevant_positions_for_content(
                    db, content, politician
                )
            finally:
                db.close()

            # Create dynamic Pydantic model with position constraints
            DynamicPositionExtractionResult = create_dynamic_position_model(allowed_positions)
            logger.debug(
                f"Allowed positions for {politician_name}: {allowed_positions}"
            )

            system_prompt = """You are a data extraction assistant. Extract ONLY political positions from Wikipedia article text.

Extract political offices, government roles, elected positions with start/end dates in YYYY-MM-DD, YYYY-MM, or YYYY format.

Rules:
- Only extract information explicitly stated in the text
- Use partial dates if full dates aren't available
- Leave end_date null if position is current or unknown
- Only extract positions that are relevant to the politician's country of citizenship
- Focus on formal political positions, not informal roles or titles
- For each position, provide a 'proof' field containing the exact quote from the Wikipedia text that supports this position
- The proof should be the specific sentence or phrase that mentions the position"""

            user_prompt = f"""Extract political positions held by {politician_name} from this Wikipedia article text:

{content}

Politician name: {politician_name}
Country: {country or 'Unknown'}"""

            logger.debug(f"Extracting positions for {politician_name}")

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=DynamicPositionExtractionResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error("OpenAI position extraction returned None for parsed data")
                logger.error(f"Response content: {message.content}")
                logger.error(f"Response refusal: {getattr(message, 'refusal', None)}")
                return None

            # Convert positions from dynamic model to standard ExtractedPosition
            positions = []
            for pos in message.parsed.positions:
                positions.append(
                    ExtractedPosition(
                        name=pos.name,
                        start_date=pos.start_date,
                        end_date=pos.end_date,
                        proof=pos.proof,
                    )
                )

            return positions

        except Exception as e:
            logger.error(f"Error extracting positions with LLM: {e}")
            return None

    def _log_extraction_results(
        self, politician_name: str, data: dict
    ) -> None:
        """Log what the LLM extracted from Wikipedia."""
        logger.info(f"LLM extracted data for {politician_name}:")

        properties = data.get('properties', [])
        if properties:
            logger.info(f"  Properties ({len(properties)}):")
            for prop in properties:
                logger.info(f"    {prop.type}: {prop.value}")
        else:
            logger.info("  No properties extracted")

        positions = data.get('positions', [])
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

    def _store_extracted_data(
        self, db: Session, politician: Politician, extracted_data: List[tuple]
    ) -> bool:
        """Store extracted data in the database."""
        try:
            for source, data in extracted_data:
                # Update source extraction timestamp
                source.extracted_at = datetime.utcnow()

                # Store properties
                for prop_data in data.get('properties', []):
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
                for pos_data in data.get('positions', []):
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

            return True

        except Exception as e:
            logger.error(f"Error storing extracted data: {e}")
            return False

    def close(self):
        """Close HTTP client."""
        self.http_client.close()
