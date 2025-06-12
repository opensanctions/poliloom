"""Service for enriching politician data from Wikipedia using LLM extraction."""

import os
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import httpx
from bs4 import BeautifulSoup
import logging
from openai import OpenAI
from pydantic import BaseModel

from ..models import Politician, Property, Position, HoldsPosition
from ..database import SessionLocal

logger = logging.getLogger(__name__)


class ExtractedProperty(BaseModel):
    """Schema for extracted property data."""
    type: str
    value: str


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ExtractionResult(BaseModel):
    """Schema for LLM extraction result."""
    properties: List[ExtractedProperty]
    positions: List[ExtractedPosition]


class EnrichmentService:
    """Service for enriching politician data from Wikipedia sources."""
    
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
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
            if not wikidata_id.upper().startswith('Q'):
                wikidata_id = f'Q{wikidata_id}'
            else:
                wikidata_id = wikidata_id.upper()
            
            # Get politician by Wikidata ID
            politician = db.query(Politician).filter_by(wikidata_id=wikidata_id).first()
            if not politician:
                logger.error(f"Politician with Wikidata ID {wikidata_id} not found")
                return False
            
            if not politician.sources:
                logger.warning(f"No Wikipedia sources found for politician {politician.name}")
                return False
            
            # Process each Wikipedia source
            extracted_data = []
            for source in politician.sources:
                if 'wikipedia.org' in source.url:
                    logger.info(f"Processing Wikipedia source: {source.url}")
                    content = self._fetch_wikipedia_content(source.url)
                    if content:
                        data = self._extract_data_with_llm(content, politician.name, politician.country)
                        if data:
                            extracted_data.append((source, data))
            
            if not extracted_data:
                logger.warning(f"No data extracted from Wikipedia sources for {politician.name}")
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
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Get main content - Wikipedia articles use div with id="mw-content-text"
            content_div = soup.find('div', {'id': 'mw-content-text'})
            if content_div:
                # Extract text from paragraphs in the main content
                paragraphs = content_div.find_all('p')
                content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                
                # Limit content length to avoid token limits
                if len(content) > 8000:
                    content = content[:8000] + "..."
                
                return content
            
            logger.warning(f"Could not find main content in Wikipedia page: {url}")
            return None
            
        except httpx.RequestError as e:
            logger.error(f"Error fetching Wikipedia content from {url}: {e}")
            return None
    
    def _extract_data_with_llm(self, content: str, politician_name: str, country: str) -> Optional[ExtractionResult]:
        """Extract structured data from Wikipedia content using OpenAI structured output."""
        try:
            system_prompt = """You are a data extraction assistant. Extract politician information from Wikipedia article text.

For properties, extract:
- BirthDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates
- BirthPlace: City, Country format
- DeathDate: Use format YYYY-MM-DD, YYYY-MM, or YYYY for incomplete dates  
- Education: Institution names
- Spouse: Spouse names

For positions, extract political offices, government roles, elected positions with start/end dates in YYYY-MM-DD, YYYY-MM, or YYYY format.

Rules:
- Only extract information explicitly stated in the text
- Use partial dates if full dates aren't available
- Leave end_date null if position is current or unknown"""

            user_prompt = f"""Extract information about {politician_name} from this Wikipedia article text:

{content}

Politician name: {politician_name}
Country: {country or 'Unknown'}"""

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ExtractionResult,
                temperature=0.1
            )
            
            return response.choices[0].message.parsed
            
        except Exception as e:
            logger.error(f"Error extracting data with LLM: {e}")
            return None
    
    def _store_extracted_data(self, db: Session, politician: Politician, extracted_data: List[tuple]) -> bool:
        """Store extracted data in the database."""
        try:
            for source, data in extracted_data:
                # Update source extraction timestamp
                source.extracted_at = datetime.utcnow()
                
                # Store properties
                for prop_data in data.properties:
                    if prop_data.value:
                        # Check if similar property already exists
                        existing_prop = db.query(Property).filter_by(
                            politician_id=politician.id,
                            type=prop_data.type,
                            value=prop_data.value
                        ).first()
                        
                        if not existing_prop:
                            new_property = Property(
                                politician_id=politician.id,
                                type=prop_data.type,
                                value=prop_data.value,
                                is_extracted=True  # Newly extracted, needs confirmation
                            )
                            db.add(new_property)
                            db.flush()  # Get the ID
                            
                            # Link to source
                            new_property.sources.append(source)
                
                # Store positions
                for pos_data in data.positions:
                    if pos_data.name:
                        # Try to find existing position by name and country
                        position = db.query(Position).filter_by(
                            name=pos_data.name,
                            country=politician.country
                        ).first()
                        
                        if not position:
                            # Create new position
                            position = Position(
                                name=pos_data.name,
                                country=politician.country
                            )
                            db.add(position)
                            db.flush()
                        
                        # Check if this position relationship already exists
                        existing_holds = db.query(HoldsPosition).filter_by(
                            politician_id=politician.id,
                            position_id=position.id,
                            start_date=pos_data.start_date,
                            end_date=pos_data.end_date
                        ).first()
                        
                        if not existing_holds:
                            holds_position = HoldsPosition(
                                politician_id=politician.id,
                                position_id=position.id,
                                start_date=pos_data.start_date,
                                end_date=pos_data.end_date,
                                is_extracted=True  # Newly extracted, needs confirmation
                            )
                            db.add(holds_position)
                            db.flush()
                            
                            # Link to source
                            holds_position.sources.append(source)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing extracted data: {e}")
            return False
    
    def close(self):
        """Close HTTP client."""
        self.http_client.close()