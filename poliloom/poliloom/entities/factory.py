"""Factory pattern for creating appropriate WikidataEntity instances."""

from typing import Dict, Optional, Any, List
import logging

from .wikidata_entity import WikidataEntity
from .politician import WikidataPolitician
from .position import WikidataPosition
from .location import WikidataLocation
from .country import WikidataCountry

logger = logging.getLogger(__name__)


class WikidataEntityFactory:
    """Factory for creating appropriate WikidataEntity instances based on entity type."""

    @classmethod
    def create_entity(
        cls,
        raw_data: Dict[str, Any],
        position_descendants: Optional[Dict[str, Any]] = None,
        location_descendants: Optional[Dict[str, Any]] = None,
        allowed_types: Optional[List[str]] = None,
    ) -> Optional[WikidataEntity]:
        """Create appropriate entity instance based on entity type.

        Args:
            raw_data: Raw Wikidata entity JSON data
            position_descendants: Dict of Wikidata IDs that are descendants of Q294414 (public office)
            location_descendants: Dict of Wikidata IDs that are descendants of Q2221906 (geographic location)
            allowed_types: List of entity types to create (e.g., ['politician', 'position', 'location', 'country'])
                          If None, all types are allowed

        Returns:
            Appropriate entity instance or None if entity type not recognized
        """
        if not raw_data or "id" not in raw_data:
            return None

        entity_id = raw_data["id"]

        try:
            # Check entity types in priority order: politician, position, location, country

            # Politicians are highest priority since they're our primary entities
            if (
                allowed_types is None or "politician" in allowed_types
            ) and WikidataPolitician.is_politician(raw_data):
                politician = WikidataPolitician.from_raw(raw_data)
                # Apply death date filtering
                if politician.should_import_politician():
                    return politician
                else:
                    return None

            # Positions require hierarchy data
            if (
                (allowed_types is None or "position" in allowed_types)
                and position_descendants
                and WikidataPosition.is_position(raw_data, position_descendants)
            ):
                return WikidataPosition.from_raw(raw_data)

            # Locations require hierarchy data
            if (
                (allowed_types is None or "location" in allowed_types)
                and location_descendants
                and WikidataLocation.is_location(raw_data, location_descendants)
            ):
                return WikidataLocation.from_raw(raw_data)

            # Countries don't require hierarchy data
            if (
                allowed_types is None or "country" in allowed_types
            ) and WikidataCountry.is_country(raw_data):
                return WikidataCountry.from_raw(raw_data)

            # Entity type not recognized
            return None

        except Exception as e:
            logger.warning(f"Failed to create entity for {entity_id}: {e}")
            return None
