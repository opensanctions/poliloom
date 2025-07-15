"""WikidataCountry entity class for country-specific extraction."""

from typing import Dict, Optional, Any
from .wikidata_entity import WikidataEntity


class WikidataCountry(WikidataEntity):
    """Represents a country entity from Wikidata with extraction methods."""

    @classmethod
    def is_country(cls, raw_data: Dict[str, Any]) -> bool:
        """Check if an entity is a country based on instance of (P31) properties.

        Args:
            raw_data: Raw Wikidata entity JSON data

        Returns:
            True if the entity is a country, False otherwise
        """
        # Create temporary instance to use inherited methods
        temp_entity = cls(raw_data)

        # Common country instance types
        country_types = {
            "Q6256",  # country
            "Q3624078",  # sovereign state
            "Q20181813",  # historic country
            "Q1520223",  # independent city
            "Q1489259",  # city-state
        }

        # Check if this entity is an instance of any country type
        instance_ids = temp_entity.get_instance_of_ids()

        return bool(instance_ids.intersection(country_types))

    def extract_iso_code(self) -> Optional[str]:
        """Extract ISO 3166-1 alpha-2 code (P297) using truthy filtering.

        Returns:
            ISO code string, or None if not available
        """
        iso_claims = self.get_truthy_claims("P297")

        for claim in iso_claims:
            try:
                iso_code = claim["mainsnak"]["datavalue"]["value"]
                return iso_code
            except (KeyError, TypeError):
                continue

        return None

    def to_database_dict(self) -> Dict[str, Any]:
        """Convert country to dictionary format for database insertion.

        Returns:
            Dictionary with keys matching Country table columns
        """
        name = self.get_entity_name()
        if not name:
            raise ValueError(f"Country {self.get_wikidata_id()} has no name")

        return {
            "wikidata_id": self.get_wikidata_id(),
            "name": name,
            "iso_code": self.extract_iso_code(),
        }
