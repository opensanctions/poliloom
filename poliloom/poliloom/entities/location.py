"""WikidataLocation entity class for location-specific extraction."""

from typing import Dict, Set, Any
from .wikidata_entity import WikidataEntity


class WikidataLocation(WikidataEntity):
    """Represents a location entity from Wikidata with extraction methods."""

    @classmethod
    def is_location(
        cls, raw_data: Dict[str, Any], location_descendants: Set[str]
    ) -> bool:
        """Check if an entity is a location based on instance of (P31) properties.

        Args:
            raw_data: Raw Wikidata entity JSON data
            location_descendants: Set of Wikidata IDs that are descendants of Q2221906 (geographic location)

        Returns:
            True if the entity is a location, False otherwise
        """
        # Create temporary instance to use inherited methods
        temp_entity = cls(raw_data)

        # Check if this entity is an instance of any location type
        instance_ids = temp_entity.get_instance_of_ids()

        # Check if any instance type is in location descendants
        return bool(instance_ids.intersection(location_descendants))

    def to_database_dict(self) -> Dict[str, Any]:
        """Convert location to dictionary format for database insertion.

        Returns:
            Dictionary with keys matching Location table columns
        """
        name = self.get_entity_name()
        if not name:
            raise ValueError(f"Location {self.get_wikidata_id()} has no name")

        return {
            "wikidata_id": self.get_wikidata_id(),
            "name": name,
        }
