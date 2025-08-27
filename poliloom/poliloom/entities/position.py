"""WikidataPosition entity class for position-specific extraction."""

from typing import Dict, Any, Optional
from .wikidata_entity import WikidataEntity


class WikidataPosition(WikidataEntity):
    """Represents a position entity from Wikidata with extraction methods."""

    @classmethod
    def is_position(
        cls, raw_data: Dict[str, Any], position_descendants: Dict[str, Any]
    ) -> bool:
        """Check if an entity is a position based on instance of (P31) properties.

        Args:
            raw_data: Raw Wikidata entity JSON data
            position_descendants: Dict of Wikidata IDs that are descendants of Q294414 (public office)

        Returns:
            True if the entity is a position, False otherwise
        """
        # Create temporary instance to use inherited methods
        temp_entity = cls(raw_data)

        # Check if this entity is an instance of any position type
        instance_ids = temp_entity.get_instance_of_ids()

        # Check if any instance type is in position descendants dict
        return any(instance_id in position_descendants for instance_id in instance_ids)

    def to_database_dict(self, class_lookup: Dict[str, str] = None) -> Dict[str, Any]:
        """Convert position to dictionary format for database insertion.

        Args:
            class_lookup: Unused parameter kept for compatibility

        Returns:
            Dictionary with keys matching Position table columns
        """
        # Get base fields from parent class
        result = super().to_database_dict()

        # Store the most specific wikidata class ID (not UUID) for later foreign key resolution
        most_specific_class_id = self._find_most_specific_class_wikidata_id()
        if most_specific_class_id:
            result["wikidata_class_id"] = most_specific_class_id

        return result

    def _find_most_specific_class_wikidata_id(self) -> Optional[str]:
        """Find the most specific wikidata class for this position from its instance-of claims.

        Returns:
            Wikidata QID of the most specific class, or None if not found
        """
        instance_ids = self.get_instance_of_ids()

        # For now, return the first instance-of class
        # In the future, we could implement logic to find the most specific class
        if instance_ids:
            return instance_ids[0]

        return None
