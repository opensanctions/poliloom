"""Hierarchy tree building for Wikidata entities."""

import json
import logging
import os
from typing import Dict, Set, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class HierarchyBuilder:
    """Builds and manages Wikidata entity hierarchy trees."""

    def __init__(self):
        self.position_root = "Q294414"  # public office
        self.location_root = "Q2221906"  # geographic location

    def get_all_descendants(
        self,
        root_id: str,
        subclass_relations: Dict[str, Set[str]],
    ) -> Set[str]:
        """
        Get all descendants of a root entity using BFS, traversing only subclass relationships.

        Args:
            root_id: The root entity QID
            subclass_relations: Dict mapping parent QIDs to sets of child QIDs (P279)

        Returns:
            Set of all descendant QIDs (including the root and its subclasses)
        """
        descendants = {root_id}
        queue = [root_id]

        while queue:
            current = queue.pop(0)

            # Get direct subclasses
            subclasses = subclass_relations.get(current, set())
            for subclass in subclasses:
                if subclass not in descendants:
                    descendants.add(subclass)
                    queue.append(subclass)

        return descendants

    def extract_subclass_relations_from_entity(
        self, entity: Dict
    ) -> Dict[str, Set[str]]:
        """
        Extract P279 (subclass of) relationships from a single entity.

        Args:
            entity: Parsed Wikidata entity

        Returns:
            Dictionary mapping parent QIDs to sets of child QIDs
        """
        subclass_relations = defaultdict(set)

        # Extract P279 (subclass of) relationships
        entity_id = entity.get("id", "")
        if not entity_id:
            return {}

        claims = entity.get("claims", {})
        subclass_claims = claims.get("P279", [])

        # Implement truthy filtering: if preferred rank statements exist, only use those
        # Otherwise, use all normal rank statements (always exclude deprecated)
        non_deprecated_claims = []
        preferred_claims = []

        for claim in subclass_claims:
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
        claims_to_process = (
            preferred_claims if preferred_claims else non_deprecated_claims
        )

        for claim in claims_to_process:
            try:
                parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                subclass_relations[parent_id].add(entity_id)
            except (KeyError, TypeError):
                continue

        return dict(subclass_relations)

    def save_complete_hierarchy_trees(
        self,
        subclass_relations: Dict[str, Set[str]],
        output_dir: str = ".",
    ) -> None:
        """
        Save the complete hierarchy (P279 subclass relationships) to JSON file.

        This creates a comprehensive reference of all subclass relationships in Wikidata,
        enabling extraction of any entity type hierarchy without re-processing the dump.

        Args:
            subclass_relations: Dictionary mapping parent QIDs to sets of child QIDs (P279)
            output_dir: Directory to save the JSON file
        """
        hierarchy_file = os.path.join(output_dir, "complete_hierarchy.json")

        # Convert sets to sorted lists for JSON serialization
        hierarchy_data = {
            "subclass_of": {},  # P279 relationships
        }

        # Process subclass relations
        for parent_id, children in subclass_relations.items():
            if children:
                hierarchy_data["subclass_of"][parent_id] = sorted(list(children))

        # Sort keys for consistent output
        hierarchy_data["subclass_of"] = dict(
            sorted(hierarchy_data["subclass_of"].items())
        )

        with open(hierarchy_file, "w", encoding="utf-8") as f:
            json.dump(hierarchy_data, f, indent=2, ensure_ascii=False)

        # Calculate and log file size
        file_size = os.path.getsize(hierarchy_file)
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Saved complete hierarchy to {hierarchy_file}")
        logger.info(
            f"Hierarchy contains {len(hierarchy_data['subclass_of'])} entities with subclasses"
        )
        logger.info(f"File size: {file_size_mb:.1f} MB ({file_size:,} bytes)")

    def load_complete_hierarchy(
        self, tree_dir: str = "."
    ) -> Optional[Dict[str, Set[str]]]:
        """
        Load the complete hierarchy from JSON file.

        Args:
            tree_dir: Directory containing the complete hierarchy file

        Returns:
            Dictionary of subclass_relations, or None if file doesn't exist
        """
        hierarchy_file = os.path.join(tree_dir, "complete_hierarchy.json")

        if not os.path.exists(hierarchy_file):
            logger.warning(f"Complete hierarchy file not found: {hierarchy_file}")
            return None

        try:
            with open(hierarchy_file, "r", encoding="utf-8") as f:
                hierarchy_data = json.load(f)

            # Convert lists back to sets
            subclass_relations = {}
            for parent_id, children in hierarchy_data.get("subclass_of", {}).items():
                subclass_relations[parent_id] = set(children)

            logger.info(f"Loaded complete hierarchy from {hierarchy_file}")
            logger.info(
                f"Hierarchy contains {len(subclass_relations)} entities with subclasses"
            )

            return subclass_relations

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load complete hierarchy: {e}")
            return None

    def get_position_and_location_descendants(
        self, subclass_relations: Dict[str, Set[str]]
    ) -> Dict[str, Set[str]]:
        """
        Get descendant sets for positions and locations from complete hierarchy.

        Args:
            subclass_relations: Complete hierarchy mapping

        Returns:
            Dictionary with 'positions' and 'locations' keys containing descendant sets
        """
        position_descendants = self.get_all_descendants(
            self.position_root, subclass_relations
        )
        location_descendants = self.get_all_descendants(
            self.location_root, subclass_relations
        )

        return {"positions": position_descendants, "locations": location_descendants}
