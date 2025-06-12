"""Service for importing politician data into the database."""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

from ..models import Politician, Property, Position, HoldsPosition, Source, Country
from ..database import SessionLocal
from .wikidata import WikidataClient

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing politician data from Wikidata."""
    
    def __init__(self):
        self.wikidata_client = WikidataClient()
    
    def import_politician_by_id(self, wikidata_id: str) -> Optional[str]:
        """
        Import a politician from Wikidata by their ID.
        
        Returns:
            The politician's database ID if successful, None otherwise.
        """
        # Fetch data from Wikidata
        politician_data = self.wikidata_client.get_politician_by_id(wikidata_id)
        if not politician_data:
            logger.error(f"Could not fetch politician data for {wikidata_id}")
            return None
        
        db = SessionLocal()
        try:
            # Check if politician already exists
            existing = db.query(Politician).filter_by(
                wikidata_id=politician_data['wikidata_id']
            ).first()
            
            if existing:
                logger.info(f"Politician {wikidata_id} already exists in database")
                return existing.id
            
            # Create politician record
            politician = self._create_politician(db, politician_data)
            
            # Create property records (including citizenships)
            self._create_properties(db, politician, politician_data.get('properties', []))
            
            # Create position records
            self._create_positions(db, politician, politician_data.get('positions', []))
            
            # Create source records for Wikipedia links
            self._create_sources(db, politician, politician_data.get('wikipedia_links', []))
            
            db.commit()
            logger.info(f"Successfully imported politician {wikidata_id} as {politician.id}")
            return politician.id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error importing politician {wikidata_id}: {e}")
            return None
        finally:
            db.close()
    
    def _create_politician(self, db: Session, data: Dict[str, Any]) -> Politician:
        """Create a politician record."""
        politician = Politician(
            name=data['name'],
            wikidata_id=data['wikidata_id'],
            is_deceased=data.get('is_deceased', False)
        )
        db.add(politician)
        db.flush()  # Get the ID
        return politician
    
    def _create_properties(self, db: Session, politician: Politician, properties: list):
        """Create property records for the politician."""
        for prop_data in properties:
            if prop_data.get('value'):  # Only create if there's a value
                prop = Property(
                    politician_id=politician.id,
                    type=prop_data['type'],
                    value=prop_data['value'],
                    is_extracted=False  # From Wikidata, so considered confirmed
                )
                db.add(prop)
    
    
    def _create_positions(self, db: Session, politician: Politician, positions: list):
        """Create position and holds_position records."""
        for pos_data in positions:
            # Check if position already exists
            position = db.query(Position).filter_by(
                wikidata_id=pos_data['wikidata_id']
            ).first()
            
            if not position:
                # Create new position
                # Find country if specified
                country_id = None
                if pos_data.get('country'):
                    country = db.query(Country).filter_by(
                        iso_code=pos_data['country']
                    ).first()
                    if country:
                        country_id = country.id
                
                position = Position(
                    name=pos_data['name'],
                    wikidata_id=pos_data['wikidata_id'],
                    country_id=country_id
                )
                db.add(position)
                db.flush()  # Get the ID
            
            # Create holds_position relationship
            holds_position = HoldsPosition(
                politician_id=politician.id,
                position_id=position.id,
                start_date=pos_data.get('start_date'),
                end_date=pos_data.get('end_date'),
                is_extracted=False  # From Wikidata, so considered confirmed
            )
            db.add(holds_position)
    
    def _create_sources(self, db: Session, politician: Politician, wikipedia_links: list):
        """Create source records for Wikipedia links."""
        for link in wikipedia_links:
            try:
                # Check if source already exists
                source = db.query(Source).filter_by(url=link['url']).first()
                
                if not source:
                    source = Source(
                        url=link['url']
                    )
                    db.add(source)
                    db.flush()  # Get the ID
                
                # Link source to politician
                if source not in politician.sources:
                    politician.sources.append(source)
                    
            except IntegrityError:
                # Source already exists, skip
                db.rollback()
                continue
    
    def import_all_countries(self) -> int:
        """
        Import all countries from Wikidata.
        
        Returns:
            Number of countries imported.
        """
        # Fetch all countries from Wikidata
        countries_data = self.wikidata_client.get_all_countries()
        if not countries_data:
            logger.error("Could not fetch countries data from Wikidata")
            return 0
        
        db = SessionLocal()
        try:
            imported_count = 0
            
            for country_data in countries_data:
                # Check if country already exists
                existing = db.query(Country).filter_by(
                    wikidata_id=country_data['wikidata_id']
                ).first()
                
                if existing:
                    logger.debug(f"Country {country_data['name']} already exists")
                    continue
                
                # Create country record
                country = Country(
                    name=country_data['name'],
                    iso_code=country_data.get('iso_code'),
                    wikidata_id=country_data['wikidata_id']
                )
                db.add(country)
                imported_count += 1
                
                # Commit in batches to avoid memory issues
                if imported_count % 100 == 0:
                    db.commit()
                    logger.info(f"Imported {imported_count} countries so far...")
            
            db.commit()
            logger.info(f"Successfully imported {imported_count} countries")
            return imported_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error importing countries: {e}")
            return 0
        finally:
            db.close()
    
    def import_all_positions(self) -> int:
        """
        Import all political positions from Wikidata.
        
        Returns:
            Number of positions imported.
        """
        # Fetch all positions from Wikidata
        positions_data = self.wikidata_client.get_all_positions()
        if not positions_data:
            logger.error("Could not fetch positions data from Wikidata")
            return 0
        
        db = SessionLocal()
        try:
            imported_count = 0
            
            for position_data in positions_data:
                # Check if position already exists
                existing = db.query(Position).filter_by(
                    wikidata_id=position_data['wikidata_id']
                ).first()
                
                if existing:
                    logger.debug(f"Position {position_data['name']} already exists")
                    continue
                
                # Create position record
                position = Position(
                    name=position_data['name'],
                    wikidata_id=position_data['wikidata_id'],
                    country_id=None  # Will be determined when positions are used
                )
                db.add(position)
                imported_count += 1
                
                # Commit in batches to avoid memory issues
                if imported_count % 100 == 0:
                    db.commit()
                    logger.info(f"Imported {imported_count} positions so far...")
            
            db.commit()
            logger.info(f"Successfully imported {imported_count} positions")
            return imported_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error importing positions: {e}")
            return 0
        finally:
            db.close()
    
    def close(self):
        """Close the Wikidata client."""
        self.wikidata_client.close()