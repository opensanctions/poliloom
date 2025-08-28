"""Hierarchy tree building for Wikidata entities."""

import logging
from typing import Set
from sqlalchemy.orm import Session
from sqlalchemy import text


logger = logging.getLogger(__name__)


def query_hierarchy_descendants(root_id: str, session: Session) -> Set[str]:
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
