"""Unified Wikidata entity processing class."""

from typing import Dict, List, Optional, Any, Set
import logging

logger = logging.getLogger(__name__)


class WikidataEntity:
    """Unified class for all Wikidata entities with type-specific processing."""

    def __init__(self, raw_data: Dict[str, Any]):
        """Initialize with raw Wikidata entity JSON data."""
        self.raw_data = raw_data
        self._entity_id = raw_data.get("id", "")
        self._claims = raw_data.get("claims", {})
        self._labels = raw_data.get("labels", {})
        self._sitelinks = raw_data.get("sitelinks", {})

    def get_wikidata_id(self) -> str:
        """Get the Wikidata entity ID (QID)."""
        return self._entity_id

    def get_entity_name(self) -> Optional[str]:
        """Extract the primary name from the entity's labels.

        Returns:
            Primary name string, preferring English, or None if no labels exist
        """
        # Try English first
        if "en" in self._labels:
            return self._labels["en"]["value"]

        # Fallback to any available language
        if self._labels:
            return next(iter(self._labels.values()))["value"]

        return None

    def get_truthy_claims(self, property_id: str) -> List[Dict[str, Any]]:
        """Get truthy claims for a property using rank-based filtering.

        Implements Wikidata's truthy filtering logic:
        - If preferred rank statements exist, only return those
        - Otherwise, return all normal rank statements
        - Always exclude deprecated rank statements

        Args:
            property_id: The property ID (e.g., 'P31', 'P279')

        Returns:
            List of truthy claims for the property
        """
        claims = self._claims.get(property_id, [])

        non_deprecated_claims = []
        preferred_claims = []

        for claim in claims:
            try:
                rank = claim.get("rank", "normal")
                if rank == "deprecated":
                    continue

                non_deprecated_claims.append(claim)
                if rank == "preferred":
                    preferred_claims.append(claim)
            except (KeyError, TypeError):
                continue

        # Apply truthy filtering logic
        return preferred_claims if preferred_claims else non_deprecated_claims

    def extract_date_from_claims(
        self, claims: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Extract date from Wikidata claims with precision handling.

        Args:
            claims: List of Wikidata claims (from get_truthy_claims or qualifiers)

        Returns:
            Dictionary with 'date' (string) and 'precision' (int) keys, or None
        """
        for claim in claims:
            try:
                # Handle both main claims (with mainsnak) and qualifier claims (direct structure)
                if "mainsnak" in claim:
                    datavalue = claim.get("mainsnak", {}).get("datavalue", {})
                else:
                    datavalue = claim.get("datavalue", {})

                if datavalue.get("type") == "time":
                    time_value = datavalue.get("value", {}).get("time", "")
                    # Convert from Wikidata format (+1970-01-15T00:00:00Z) to simpler format
                    if time_value.startswith("+"):
                        date_part = time_value[1:].split("T")[0]
                        # Handle precision - only return what's specified
                        precision = datavalue.get("value", {}).get("precision", 11)
                        if precision >= 11:  # day precision
                            return {"date": date_part, "precision": precision}
                        elif precision == 10:  # month precision
                            return {
                                "date": date_part[:7],
                                "precision": precision,
                            }  # YYYY-MM
                        elif precision == 9:  # year precision
                            return {
                                "date": date_part[:4],
                                "precision": precision,
                            }  # YYYY
            except (KeyError, TypeError):
                continue
        return None

    def get_instance_of_ids(self) -> Set[str]:
        """Get all instance of (P31) entity IDs using truthy filtering.

        Returns:
            Set of entity IDs that this entity is an instance of
        """
        instance_ids = set()
        instance_claims = self.get_truthy_claims("P31")

        for claim in instance_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                instance_ids.add(instance_id)
            except (KeyError, TypeError):
                continue

        return instance_ids

    def get_subclass_of_ids(self) -> Set[str]:
        """Get all subclass of (P279) entity IDs using truthy filtering.

        Returns:
            Set of entity IDs that this entity is a subclass of
        """
        subclass_ids = set()
        subclass_claims = self.get_truthy_claims("P279")

        for claim in subclass_claims:
            try:
                subclass_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                subclass_ids.add(subclass_id)
            except (KeyError, TypeError):
                continue

        return subclass_ids

    def is_politician(self, relevant_position_qids: frozenset[str]) -> bool:
        """Check if entity is a politician based on occupation or positions held in our database."""
        # Must be human first
        instance_ids = self.get_instance_of_ids()
        if "Q5" not in instance_ids:
            return False

        # Check occupation for politician
        occupation_claims = self.get_truthy_claims("P106")
        for claim in occupation_claims:
            try:
                occupation_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if occupation_id == "Q82955":  # politician
                    return True
            except (KeyError, TypeError):
                continue

        # Check if they have any position held that exists in our database
        position_claims = self.get_truthy_claims("P39")
        for claim in position_claims:
            try:
                position_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if position_id in relevant_position_qids:
                    return True
            except (KeyError, TypeError):
                continue
        return False

    @classmethod
    def from_raw(cls, raw_data: Dict[str, Any]) -> "WikidataEntity":
        """Create entity instance from raw Wikidata JSON data.

        Args:
            raw_data: Raw Wikidata entity JSON

        Returns:
            Entity instance
        """
        return cls(raw_data)
