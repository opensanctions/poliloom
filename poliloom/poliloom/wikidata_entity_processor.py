"""Unified Wikidata entity processing class."""

from typing import Dict, List, Optional, Any, Set
import logging
from poliloom.wikidata_date import WikidataDate

logger = logging.getLogger(__name__)


class WikidataEntityProcessor:
    """Unified class for all Wikidata entities with type-specific processing."""

    def __init__(self, raw_data: Dict[str, Any]):
        """Initialize with raw Wikidata entity JSON data."""
        self.raw_data = raw_data
        self._entity_id = raw_data.get("id", "")
        self._claims = raw_data.get("claims", {})
        self._labels = raw_data.get("labels", {})
        self._descriptions = raw_data.get("descriptions", {})
        self._sitelinks = raw_data.get("sitelinks", {})

    def get_wikidata_id(self) -> str:
        """Get the Wikidata entity ID (QID)."""
        return self._entity_id

    def get_entity_name(self) -> Optional[str]:
        """Extract the primary name from the entity's labels.

        Returns:
            Primary name string, preferring multilingual, then English, or None if no labels exist
        """
        # Try multilingual (mul) first - most universally appropriate
        if "mul" in self._labels:
            return self._labels["mul"]["value"]

        # Try English as second choice
        if "en" in self._labels:
            return self._labels["en"]["value"]

        # Fallback to any available language
        if self._labels:
            return next(iter(self._labels.values()))["value"]

        return None

    def get_entity_description(self) -> Optional[str]:
        """Extract the primary description from the entity's descriptions.

        Returns:
            Primary description string, preferring multilingual, then English, or None if no descriptions exist
        """
        # Try multilingual (mul) first - most universally appropriate
        if "mul" in self._descriptions:
            return self._descriptions["mul"]["value"]

        # Try English as second choice
        if "en" in self._descriptions:
            return self._descriptions["en"]["value"]

        # Fallback to any available language
        if self._descriptions:
            return next(iter(self._descriptions.values()))["value"]

        return None

    def get_all_labels(self) -> List[str]:
        """Extract all unique label values across all languages.

        Returns:
            List of unique label strings
        """
        unique_labels = set()
        for label_data in self._labels.values():
            if "value" in label_data:
                unique_labels.add(label_data["value"])
        return list(unique_labels)

    @property
    def sitelinks(self) -> Dict[str, Any]:
        """Get the sitelinks for this entity.

        Returns:
            Dictionary of sitelinks (site_key -> sitelink data)
        """
        return self._sitelinks

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

    def extract_date_from_claim(self, claim: Dict[str, Any]) -> Optional[WikidataDate]:
        """Extract date from a single Wikidata claim with precision handling.

        Args:
            claim: Single Wikidata claim (from get_truthy_claims or qualifiers)

        Returns:
            WikidataDate object or None
        """
        try:
            # Handle both main claims (with mainsnak) and qualifier claims (direct structure)
            if "mainsnak" in claim:
                datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            else:
                datavalue = claim.get("datavalue", {})

            if datavalue.get("type") == "time":
                time_value = datavalue.get("value", {}).get("time", "")
                precision = datavalue.get("value", {}).get("precision", 11)

                # Create and return WikidataDate object
                return WikidataDate.from_wikidata_time(time_value, precision)
        except (KeyError, TypeError):
            pass
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

    def extract_all_relations(self) -> List[Dict]:
        """
        Extract all tracked relations from this Wikidata entity.

        Returns:
            List of relation dictionaries with keys:
            - parent_entity_id: The parent entity QID
            - child_entity_id: The current entity QID
            - relation_type: RelationType enum value
            - statement_id: The Wikidata statement ID
        """
        from .models import RelationType

        entity_id = self.get_wikidata_id()
        if not entity_id:
            return []

        relations = []

        # Extract all relations using tracked properties
        for relation_type in RelationType:
            property_id = relation_type.value
            claims = self.get_truthy_claims(property_id)
            for claim in claims:
                try:
                    parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    statement_id = claim["id"]
                    relations.append(
                        {
                            "parent_entity_id": parent_id,
                            "child_entity_id": entity_id,
                            "relation_type": relation_type,
                            "statement_id": statement_id,
                        }
                    )
                except (KeyError, TypeError):
                    continue

        return relations

    def collect_parent_ids(self) -> Set[str]:
        """
        Collect all parent entity IDs from this entity's relations.

        Returns:
            Set of parent entity QIDs
        """
        from .models import RelationType

        parent_ids = set()

        # Get tracked properties from RelationType enum
        tracked_properties = [rt.value for rt in RelationType]

        # Collect parent IDs from all tracked relations
        for property_id in tracked_properties:
            claims = self.get_truthy_claims(property_id)
            for claim in claims:
                try:
                    parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                    parent_ids.add(parent_id)
                except (KeyError, TypeError):
                    continue

        return parent_ids

    @classmethod
    def from_raw(cls, raw_data: Dict[str, Any]) -> "WikidataEntityProcessor":
        """Create entity instance from raw Wikidata JSON data.

        Args:
            raw_data: Raw Wikidata entity JSON

        Returns:
            Entity instance
        """
        return cls(raw_data)
