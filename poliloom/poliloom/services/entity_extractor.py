"""Entity identification and data extraction from Wikidata dumps."""

import logging
from typing import Dict, Set, Optional, Any

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts and identifies entities from Wikidata dump data."""

    def is_instance_of_position(
        self, entity: Dict[str, Any], position_descendants: Set[str]
    ) -> bool:
        """Check if an entity is an instance of any position type (P31 instance of position descendants)."""
        # Only check if this entity is an instance of a position type
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in position_descendants:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def is_instance_of_location(
        self, entity: Dict[str, Any], location_descendants: Set[str]
    ) -> bool:
        """Check if an entity is an instance of any location type (P31 instance of location descendants)."""
        # Only check if this entity is an instance of a location type
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in location_descendants:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def is_country_entity(self, entity: Dict[str, Any]) -> bool:
        """Check if an entity is a country based on its instance of (P31) properties."""
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        # Common country instance types
        country_types = {
            "Q6256",  # country
            "Q3624078",  # sovereign state
            "Q3624078",  # country
            "Q20181813",  # historic country
            "Q1520223",  # independent city
            "Q1489259",  # city-state
        }

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in country_types:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def extract_position_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract position data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        return {
            "wikidata_id": entity["id"],
            "name": name,
        }

    def extract_location_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract location data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        return {
            "wikidata_id": entity["id"],
            "name": name,
        }

    def extract_country_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract country data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        # Try to get ISO code from claims
        iso_code = None
        claims = entity.get("claims", {})

        # P297 is the property for ISO 3166-1 alpha-2 code
        iso_claims = claims.get("P297", [])
        for claim in iso_claims:
            try:
                iso_code = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        return {
            "wikidata_id": entity["id"],
            "name": name,
            "iso_code": iso_code,
        }

    def get_entity_name(self, entity: Dict[str, Any]) -> Optional[str]:
        """Extract the primary name from a Wikidata entity."""
        labels = entity.get("labels", {})

        # Try English first
        if "en" in labels:
            return labels["en"]["value"]

        # Fallback to any available language
        if labels:
            return next(iter(labels.values()))["value"]

        return None
