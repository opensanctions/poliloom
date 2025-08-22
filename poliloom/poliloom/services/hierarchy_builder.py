"""Hierarchy tree building for Wikidata entities."""

import logging
from typing import Dict, Set, Optional, List
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text


logger = logging.getLogger(__name__)


class HierarchyBuilder:
    """Builds and manages Wikidata entity hierarchy trees."""

    def __init__(self, session: Optional[Session] = None):
        self.session = session
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

    def _get_truthy_claims(self, entity: Dict, property_id: str) -> List[Dict]:
        """Get truthy claims for a property using the same logic as WikidataEntity.

        Args:
            entity: Raw Wikidata entity dictionary
            property_id: The property ID (e.g., 'P279')

        Returns:
            List of truthy claims for the property
        """
        claims = entity.get("claims", {}).get(property_id, [])

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

        # Use WikidataEntity's truthy filtering logic consistently
        subclass_claims = self._get_truthy_claims(entity, "P279")

        for claim in subclass_claims:
            try:
                parent_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                subclass_relations[parent_id].add(entity_id)
            except (KeyError, TypeError):
                continue

        return dict(subclass_relations)

    def extract_entity_name_from_entity(self, entity: Dict) -> Optional[str]:
        """
        Extract entity name from Wikidata entity labels.

        Args:
            entity: Parsed Wikidata entity

        Returns:
            Entity name (preferring English) or None
        """
        labels = entity.get("labels", {})

        # Try English first
        if "en" in labels:
            return labels["en"]["value"]

        # Fallback to any available language
        if labels:
            return next(iter(labels.values()))["value"]

        return None

    def save_complete_hierarchy_to_database(
        self,
        subclass_relations: Dict[str, Set[str]],
        entity_names: Dict[str, str],
        session: Session,
    ) -> None:
        """
        Save the complete hierarchy (P279 subclass relationships) to database.

        Args:
            subclass_relations: Dictionary mapping parent QIDs to sets of child QIDs (P279)
            entity_names: Dictionary mapping QIDs to entity names
            session: Database session
        """
        from ..models import WikidataClass, SubclassRelation

        logger.info("Saving hierarchy to database...")

        # Clear existing hierarchy data
        logger.info("Clearing existing hierarchy data...")
        session.execute(text("DELETE FROM subclass_relations"))
        session.execute(text("DELETE FROM wikidata_classes"))

        # Collect all unique entity IDs that participate in the hierarchy
        all_entities = set()
        for parent_id, children in subclass_relations.items():
            all_entities.add(parent_id)
            all_entities.update(children)

        # Insert WikidataClass records
        logger.info(f"Inserting {len(all_entities)} Wikidata classes...")
        classes_to_insert = []
        for entity_id in all_entities:
            name = entity_names.get(entity_id, entity_id)  # Fallback to ID if no name
            classes_to_insert.append(WikidataClass(class_id=entity_id, name=name))

        # Bulk insert classes
        session.bulk_save_objects(classes_to_insert)

        # Insert SubclassRelation records
        total_relations = sum(len(children) for children in subclass_relations.values())
        logger.info(f"Inserting {total_relations} subclass relations...")

        relations_to_insert = []
        for parent_id, children in subclass_relations.items():
            for child_id in children:
                relations_to_insert.append(
                    SubclassRelation(parent_class_id=parent_id, child_class_id=child_id)
                )

        # Bulk insert relations
        session.bulk_save_objects(relations_to_insert)

        logger.info(
            f"Successfully saved hierarchy with {len(all_entities)} classes and {total_relations} relations"
        )

    def load_complete_hierarchy_from_database(
        self, session: Session
    ) -> Optional[Dict[str, Set[str]]]:
        """
        Load the complete hierarchy from database.

        Args:
            session: Database session

        Returns:
            Dictionary of subclass_relations, or None if no data exists
        """
        from ..models import SubclassRelation

        logger.info("Loading hierarchy from database...")

        # Query all subclass relations
        relations = session.query(SubclassRelation).all()

        if not relations:
            logger.warning("No hierarchy data found in database")
            return None

        # Convert to the expected format
        subclass_relations = defaultdict(set)
        for relation in relations:
            subclass_relations[relation.parent_class_id].add(relation.child_class_id)

        # Convert defaultdict to regular dict
        subclass_relations = dict(subclass_relations)

        logger.info(f"Loaded hierarchy with {len(subclass_relations)} parent classes")
        total_relations = sum(len(children) for children in subclass_relations.values())
        logger.info(f"Total subclass relations: {total_relations}")

        return subclass_relations

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

    def query_descendants_from_database(
        self, root_id: str, session: Session
    ) -> Set[str]:
        """
        Query all descendants of a root entity from database using recursive SQL.

        Args:
            root_id: The root entity QID
            session: Database session

        Returns:
            Set of all descendant QIDs (including the root)
        """
        # Use recursive CTE to find all descendants
        sql = text("""
            WITH RECURSIVE descendants AS (
                -- Base case: start with the root entity
                SELECT CAST(:root_id AS VARCHAR) AS class_id
                UNION
                -- Recursive case: find all children
                SELECT sr.child_class_id
                FROM subclass_relations sr
                JOIN descendants d ON sr.parent_class_id = d.class_id
            )
            SELECT DISTINCT class_id FROM descendants
        """)

        result = session.execute(sql, {"root_id": root_id})
        return {row[0] for row in result.fetchall()}

    def get_position_and_location_descendants_from_database(
        self, session: Session
    ) -> Dict[str, Set[str]]:
        """
        Get descendant sets for positions and locations from database using optimized query.

        This loads ONLY position and location descendants, not the entire hierarchy,
        making it much more memory efficient for dump processing.

        Args:
            session: Database session

        Returns:
            Dictionary with 'positions' and 'locations' keys containing descendant sets
        """
        # Single optimized query to get both position and location descendants
        sql = text("""
            WITH RECURSIVE position_descendants AS (
                SELECT CAST(:position_root AS VARCHAR) AS class_id, 'position' as type
                UNION
                SELECT sr.child_class_id, 'position' as type
                FROM subclass_relations sr
                JOIN position_descendants d ON sr.parent_class_id = d.class_id
            ),
            location_descendants AS (
                SELECT CAST(:location_root AS VARCHAR) AS class_id, 'location' as type
                UNION
                SELECT sr.child_class_id, 'location' as type
                FROM subclass_relations sr
                JOIN location_descendants d ON sr.parent_class_id = d.class_id
            )
            SELECT type, class_id FROM position_descendants
            UNION ALL
            SELECT type, class_id FROM location_descendants
        """)

        result = session.execute(
            sql,
            {"position_root": self.position_root, "location_root": self.location_root},
        )

        positions = set()
        locations = set()

        for row in result.fetchall():
            if row[0] == "position":
                positions.add(row[1])
            else:  # location
                locations.add(row[1])

        logger.info(
            f"Loaded {len(positions)} position descendants and {len(locations)} location descendants"
        )

        return {"positions": positions, "locations": locations}
