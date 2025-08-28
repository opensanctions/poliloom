"""Tests for hierarchy builder functionality."""

from sqlalchemy.dialects.postgresql import insert

from poliloom.models import WikidataClass
from poliloom.services.class_hierarchy import query_hierarchy_descendants


class TestHierarchyBuilder:
    """Test hierarchy builder functionality."""

    def test_query_descendants(self, db_session):
        """Test querying descendants from database using recursive SQL."""
        from poliloom.models import SubclassRelation

        # Create WikidataClass records first (required for foreign key constraints)
        wikidata_classes_data = [
            {"wikidata_id": "Q1", "name": "Entity 1"},
            {"wikidata_id": "Q2", "name": "Entity 2"},
            {"wikidata_id": "Q3", "name": "Entity 3"},
            {"wikidata_id": "Q4", "name": "Entity 4"},
            {"wikidata_id": "Q5", "name": "Entity 5"},
            {"wikidata_id": "Q6", "name": "Entity 6"},
        ]

        stmt = insert(WikidataClass).values(wikidata_classes_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        # Create SubclassRelation records directly using SQLAlchemy
        # Hierarchy: Q1 -> {Q2, Q3}, Q2 -> {Q4}, Q3 -> {Q5, Q6}
        relations_data = [
            {"parent_class_id": "Q1", "child_class_id": "Q2"},
            {"parent_class_id": "Q1", "child_class_id": "Q3"},
            {"parent_class_id": "Q2", "child_class_id": "Q4"},
            {"parent_class_id": "Q3", "child_class_id": "Q5"},
            {"parent_class_id": "Q3", "child_class_id": "Q6"},
        ]

        stmt = insert(SubclassRelation).values(relations_data)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["parent_class_id", "child_class_id"]
        )
        db_session.execute(stmt)
        db_session.commit()

        # Query descendants of Q1
        descendants = query_hierarchy_descendants("Q1", db_session)

        # Should include root and all descendants
        expected = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6"}
        assert descendants == expected

    def test_query_descendants_single_node(self, db_session):
        """Test querying descendants for single node with no children."""

        # Query descendants of Q1 with no subclass relations in database
        descendants = query_hierarchy_descendants("Q1", db_session)

        # Should include only the root (base case of recursive query)
        expected = {"Q1"}
        assert descendants == expected

    def test_query_descendants_partial_tree(self, db_session):
        """Test querying descendants for a subtree in a larger hierarchy."""
        from poliloom.models import SubclassRelation

        # Create WikidataClass records first (required for foreign key constraints)
        wikidata_classes_data = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Branch A"},
            {"wikidata_id": "Q3", "name": "Branch B"},
            {"wikidata_id": "Q4", "name": "Leaf A1"},
            {"wikidata_id": "Q5", "name": "Leaf A2"},
        ]

        stmt = insert(WikidataClass).values(wikidata_classes_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        # Create larger hierarchy: Q1 -> {Q2, Q3}, Q2 -> {Q4, Q5}
        relations_data = [
            {"parent_class_id": "Q1", "child_class_id": "Q2"},
            {"parent_class_id": "Q1", "child_class_id": "Q3"},
            {"parent_class_id": "Q2", "child_class_id": "Q4"},
            {"parent_class_id": "Q2", "child_class_id": "Q5"},
        ]

        stmt = insert(SubclassRelation).values(relations_data)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["parent_class_id", "child_class_id"]
        )
        db_session.execute(stmt)
        db_session.commit()

        # Query descendants of Q2 (should not include Q1 or Q3)
        descendants = query_hierarchy_descendants("Q2", db_session)

        expected = {"Q2", "Q4", "Q5"}  # Q2 and its children only
        assert descendants == expected

        # Query descendants of Q3 (leaf node)
        descendants_q3 = query_hierarchy_descendants("Q3", db_session)
        expected_q3 = {"Q3"}  # Only itself
        assert descendants_q3 == expected_q3
