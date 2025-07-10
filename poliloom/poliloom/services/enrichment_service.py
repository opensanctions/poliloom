"""Service for enriching politician data from Wikipedia using LLM extraction."""

import os
from typing import List, Optional
from enum import Enum
from sqlalchemy.orm import Session
import httpx
from bs4 import BeautifulSoup
import logging
from openai import OpenAI
from pydantic import BaseModel

from ..models import (
    Politician,
    Property,
    Position,
    HoldsPosition,
    Location,
    BornAt,
)
from ..database import get_db_session, get_db_session_no_commit
from .position_extraction_service import PositionExtractionService, ExtractedPosition
from .birthplace_extraction_service import (
    BirthplaceExtractionService,
    ExtractedBirthplace,
)

logger = logging.getLogger(__name__)


class PropertyType(str, Enum):
    """Allowed property types for extraction."""

    BIRTH_DATE = "BirthDate"
    DEATH_DATE = "DeathDate"


class ExtractedProperty(BaseModel):
    """Schema for extracted property data."""

    type: PropertyType
    value: str


class PropertyExtractionResult(BaseModel):
    """Schema for property-only LLM extraction result."""

    properties: List[ExtractedProperty]


class EnrichmentService:
    """Service for enriching politician data from Wikipedia sources."""

    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.http_client = httpx.Client(timeout=30.0)
        self.position_extraction_service = PositionExtractionService(self.openai_client)
        self.birthplace_extraction_service = BirthplaceExtractionService(
            self.openai_client
        )

    def enrich_politician_from_wikipedia(self, wikidata_id: str) -> bool:
        """
        Enrich a politician's data by extracting information from their Wikipedia sources.

        Args:
            wikidata_id: The Wikidata ID of the politician to enrich (e.g., Q123456)

        Returns:
            True if enrichment was successful, False otherwise
        """
        try:
            with get_db_session() as db:
                # Normalize Wikidata ID
                if not wikidata_id.upper().startswith("Q"):
                    wikidata_id = f"Q{wikidata_id}"
                else:
                    wikidata_id = wikidata_id.upper()

                # Get politician by Wikidata ID
                politician = (
                    db.query(Politician).filter_by(wikidata_id=wikidata_id).first()
                )
                if not politician:
                    logger.error(f"Politician with Wikidata ID {wikidata_id} not found")
                    return False

                if not politician.wikipedia_links:
                    logger.warning(
                        f"No Wikipedia links found for politician {politician.name}"
                    )
                    return False

                # Process only English Wikipedia source
                extracted_data = []
                english_wikipedia_link = None
                for wikipedia_link in politician.wikipedia_links:
                    if "en.wikipedia.org" in wikipedia_link.url:
                        english_wikipedia_link = wikipedia_link
                        break

                if english_wikipedia_link:
                    logger.info(
                        f"Processing English Wikipedia source: {english_wikipedia_link.url}"
                    )
                    content = self._fetch_wikipedia_content(english_wikipedia_link.url)
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
                            extracted_data.append((english_wikipedia_link, data))
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
                    logger.info(f"Successfully enriched politician {politician.name}")
                    return True
                else:
                    # Context manager will handle rollback
                    return False

        except Exception as e:
            logger.error(f"Error enriching politician {wikidata_id}: {e}")
            return False

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
            with get_db_session_no_commit() as db:
                return self.position_extraction_service.extract_and_map(
                    db, content, politician_name, country, politician, "positions"
                )
        except Exception as e:
            logger.error(f"Error extracting positions with two-stage approach: {e}")
            return None

    def _extract_birthplaces_with_llm(
        self, content: str, politician_name: str, country: str, politician: Politician
    ) -> Optional[List[ExtractedBirthplace]]:
        """Extract birthplaces using two-stage approach: free-form extraction + Wikidata mapping."""
        try:
            with get_db_session_no_commit() as db:
                return self.birthplace_extraction_service.extract_and_map(
                    db, content, politician_name, country, politician, "birthplaces"
                )
        except Exception as e:
            logger.error(f"Error extracting birthplaces with two-stage approach: {e}")
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
            for wikipedia_link, data in extracted_data:
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
