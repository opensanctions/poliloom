"""WikidataPosition entity class for position-specific extraction."""

from typing import Dict, Set, Any, Optional
from .wikidata_entity import WikidataEntity


class WikidataPosition(WikidataEntity):
    """Represents a position entity from Wikidata with extraction methods."""

    @classmethod
    def is_position(
        cls, raw_data: Dict[str, Any], position_descendants: Set[str]
    ) -> bool:
        """Check if an entity is a position based on instance of (P31) properties.

        Args:
            raw_data: Raw Wikidata entity JSON data
            position_descendants: Set of Wikidata IDs that are descendants of Q294414 (public office)

        Returns:
            True if the entity is a position, False otherwise
        """
        # Create temporary instance to use inherited methods
        temp_entity = cls(raw_data)

        # Check if this entity is an instance of any position type
        instance_ids = temp_entity.get_instance_of_ids()

        # Check if any instance type is in position descendants
        return bool(instance_ids.intersection(position_descendants))

    def to_database_dict(self, class_lookup: Dict[str, str] = None) -> Dict[str, Any]:
        """Convert position to dictionary format for database insertion.

        Args:
            class_lookup: Optional dictionary mapping wikidata_id to UUID for class lookups

        Returns:
            Dictionary with keys matching Position table columns
        """
        name = self.get_entity_name()
        if not name:
            raise ValueError(f"Position {self.get_wikidata_id()} has no name")

        result = {
            "wikidata_id": self.get_wikidata_id(),
            "name": name,
        }

        # Find the most specific class for this position
        if class_lookup:
            class_id = self._find_most_specific_class(class_lookup)
            if class_id:
                result["class_id"] = class_id

        return result

    def _find_most_specific_class(self, class_lookup: Dict[str, str]) -> Optional[str]:
        """Find the most specific class for this position from its instance-of claims.

        Args:
            class_lookup: Dictionary mapping wikidata_id to UUID for class lookups

        Returns:
            UUID of the most specific class, or None if not found
        """
        instance_ids = self.get_instance_of_ids()

        # For now, return the first matching class
        # In the future, we could implement logic to find the most specific class
        for instance_id in instance_ids:
            if instance_id in class_lookup:
                return class_lookup[instance_id]

        return None
