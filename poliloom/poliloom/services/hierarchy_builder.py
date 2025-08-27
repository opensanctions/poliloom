"""Hierarchy tree building for Wikidata entities."""

import logging
from typing import Dict, Set, Optional
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

    def insert_subclass_relations_batch(
        self, subclass_relations: Dict[str, Set[str]], session: Session
    ) -> None:
        """
        Insert SubclassRelation records using existing WikidataClass records.

        Args:
            subclass_relations: Dictionary mapping parent QIDs to child QID sets
            session: Database session
        """
        from ..models import SubclassRelation
        from sqlalchemy.dialects.postgresql import insert

        # Prepare SubclassRelation data directly using QIDs
        relations_data = []
        for parent_wikidata_id, children in subclass_relations.items():
            for child_wikidata_id in children:
                relations_data.append(
                    {
                        "parent_class_id": parent_wikidata_id,
                        "child_class_id": child_wikidata_id,
                    }
                )

        # Batch insert with conflict handling
        logger.info(f"Inserting {len(relations_data)} SubclassRelation records...")
        if relations_data:
            stmt = insert(SubclassRelation).values(relations_data)
            stmt = stmt.on_conflict_do_nothing(constraint="uq_subclass_parent_child")
            session.execute(stmt)
            session.commit()

        logger.info("SubclassRelation batch insert complete")

    def load_complete_hierarchy(
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

        # Query all subclass relations with their class relationships
        relations = session.query(SubclassRelation).all()

        if not relations:
            logger.warning("No hierarchy data found in database")
            return None

        # Convert to the expected format using QIDs directly
        subclass_relations = defaultdict(set)
        for relation in relations:
            parent_wikidata_id = relation.parent_class_id
            child_wikidata_id = relation.child_class_id
            subclass_relations[parent_wikidata_id].add(child_wikidata_id)

        # Convert defaultdict to regular dict
        subclass_relations = dict(subclass_relations)

        logger.info(f"Loaded hierarchy with {len(subclass_relations)} parent classes")
        total_relations = sum(len(children) for children in subclass_relations.values())
        logger.info(f"Total subclass relations: {total_relations}")

        return subclass_relations

    def query_descendants(self, root_id: str, session: Session) -> Set[str]:
        """
        Query all descendants of a root entity from database using recursive SQL.

        Args:
            root_id: The root entity QID
            session: Database session

        Returns:
            Set of all descendant QIDs (including the root)
        """
        # Use recursive CTE to find all descendants
        sql = text(
            """
            WITH RECURSIVE descendants AS (
                -- Base case: start with the root entity
                SELECT CAST(:root_id AS VARCHAR) AS wikidata_id
                UNION
                -- Recursive case: find all children
                SELECT sr.child_class_id AS wikidata_id
                FROM subclass_relations sr
                JOIN descendants d ON sr.parent_class_id = d.wikidata_id
            )
            SELECT DISTINCT wikidata_id FROM descendants
        """
        )

        result = session.execute(sql, {"root_id": root_id})
        return {row[0] for row in result.fetchall()}
