"""Tests for WikidataEntity model."""

from sqlalchemy.dialects.postgresql import insert

from poliloom.models import WikidataEntity, WikidataRelation, RelationType
from poliloom.models.wikidata import WikidataEntityMixin


class TestQueryHierarchyDescendants:
    """Test query_hierarchy_descendants functionality."""

    def _create_test_class(self, roots, ignore=None):
        """Create a test class with hierarchy config for testing."""

        class TestHierarchyClass(WikidataEntityMixin):
            _hierarchy_roots = roots
            _hierarchy_ignore = ignore

        return TestHierarchyClass

    def test_query_hierarchy_descendants(self, db_session):
        """Test querying all descendants in a hierarchy."""
        # Set up test hierarchy in database: Q1 -> Q2 -> Q3, Q1 -> Q4
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Child 1"},
            {"wikidata_id": "Q3", "name": "Grandchild"},
            {"wikidata_id": "Q4", "name": "Child 2"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "statement_id": "Q2$test-statement-1",
            },
            {
                "parent_entity_id": "Q2",
                "child_entity_id": "Q3",
                "statement_id": "Q3$test-statement-1",
            },
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q4",
                "statement_id": "Q4$test-statement-1",
            },
        ]

        # Insert test data
        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        # Test querying descendants
        TestClass = self._create_test_class(["Q1"])
        descendants = TestClass.query_hierarchy_descendants(db_session)

        # Should include Q1 itself and all its descendants
        assert descendants == {"Q1", "Q2", "Q3", "Q4"}

    def test_query_hierarchy_descendants_single_node(self, db_session):
        """Test querying descendants for a single node with no children."""
        # Set up single node
        test_classes = [{"wikidata_id": "Q1", "name": "Single Node"}]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.flush()

        # Test querying descendants
        TestClass = self._create_test_class(["Q1"])
        descendants = TestClass.query_hierarchy_descendants(db_session)

        # Should only include Q1 itself
        assert descendants == {"Q1"}

    def test_query_hierarchy_descendants_partial_tree(self, db_session):
        """Test querying descendants for a subtree in a larger hierarchy."""
        # Create larger hierarchy: Q1 -> {Q2, Q3}, Q2 -> {Q4, Q5}
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Branch"},
            {"wikidata_id": "Q3", "name": "Leaf 1"},
            {"wikidata_id": "Q4", "name": "Leaf 2"},
            {"wikidata_id": "Q5", "name": "Leaf 3"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "statement_id": "Q2$test-statement-2",
            },
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q3",
                "statement_id": "Q3$test-statement-2",
            },
            {
                "parent_entity_id": "Q2",
                "child_entity_id": "Q4",
                "statement_id": "Q4$test-statement-2",
            },
            {
                "parent_entity_id": "Q2",
                "child_entity_id": "Q5",
                "statement_id": "Q5$test-statement-2",
            },
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        # Test querying descendants of Q2 (should include Q2, Q4, Q5)
        TestClass = self._create_test_class(["Q2"])
        descendants = TestClass.query_hierarchy_descendants(db_session)
        assert descendants == {"Q2", "Q4", "Q5"}

        # Test querying descendants of Q3 (should only include Q3)
        TestClass = self._create_test_class(["Q3"])
        descendants_q3 = TestClass.query_hierarchy_descendants(db_session)
        assert descendants_q3 == {"Q3"}

    def test_query_hierarchy_descendants_with_relation_type(self, db_session):
        """Test querying descendants with a specific relation type."""
        # Set up test hierarchy with different relation types
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Child"},
            {"wikidata_id": "Q3", "name": "Instance"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "relation_type": RelationType.SUBCLASS_OF,
                "statement_id": "Q2$test-statement-3",
            },
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q3",
                "relation_type": RelationType.INSTANCE_OF,
                "statement_id": "Q3$test-statement-3",
            },
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        TestClass = self._create_test_class(["Q1"])

        # Test querying with SUBCLASS_OF relation type (default)
        descendants_subclass = TestClass.query_hierarchy_descendants(db_session)
        assert descendants_subclass == {"Q1", "Q2"}

        # Test querying with INSTANCE_OF relation type
        descendants_instance = TestClass.query_hierarchy_descendants(
            db_session, relation_type=RelationType.INSTANCE_OF
        )
        assert descendants_instance == {"Q1", "Q3"}

    def test_query_hierarchy_descendants_no_roots(self, db_session):
        """Test that empty roots returns empty set."""
        TestClass = self._create_test_class([])
        descendants = TestClass.query_hierarchy_descendants(db_session)
        assert descendants == set()

    def test_query_hierarchy_descendants_none_roots(self, db_session):
        """Test that None roots returns empty set."""
        TestClass = self._create_test_class(None)
        descendants = TestClass.query_hierarchy_descendants(db_session)
        assert descendants == set()

    def test_query_hierarchy_descendants_multiple_roots(self, db_session):
        """Test querying descendants from multiple root nodes."""
        # Create two separate hierarchies: Q1 -> Q2, Q10 -> Q11 -> Q12
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root 1"},
            {"wikidata_id": "Q2", "name": "Child of Root 1"},
            {"wikidata_id": "Q10", "name": "Root 2"},
            {"wikidata_id": "Q11", "name": "Child of Root 2"},
            {"wikidata_id": "Q12", "name": "Grandchild of Root 2"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "statement_id": "Q2$multi-root-1",
            },
            {
                "parent_entity_id": "Q10",
                "child_entity_id": "Q11",
                "statement_id": "Q11$multi-root-1",
            },
            {
                "parent_entity_id": "Q11",
                "child_entity_id": "Q12",
                "statement_id": "Q12$multi-root-1",
            },
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        # Test with multiple roots
        TestClass = self._create_test_class(["Q1", "Q10"])
        descendants = TestClass.query_hierarchy_descendants(db_session)

        # Should include both roots and all their descendants
        assert descendants == {"Q1", "Q2", "Q10", "Q11", "Q12"}

    def test_query_hierarchy_descendants_diamond_inheritance(self, db_session):
        """Test that diamond inheritance returns each entity only once."""
        # Diamond: Q1 -> Q2, Q1 -> Q3, Q2 -> Q4, Q3 -> Q4
        # Q4 is reachable via two paths
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Left Branch"},
            {"wikidata_id": "Q3", "name": "Right Branch"},
            {"wikidata_id": "Q4", "name": "Diamond Bottom"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "statement_id": "Q2$diamond-1",
            },
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q3",
                "statement_id": "Q3$diamond-1",
            },
            {
                "parent_entity_id": "Q2",
                "child_entity_id": "Q4",
                "statement_id": "Q4$diamond-left",
            },
            {
                "parent_entity_id": "Q3",
                "child_entity_id": "Q4",
                "statement_id": "Q4$diamond-right",
            },
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        TestClass = self._create_test_class(["Q1"])
        descendants = TestClass.query_hierarchy_descendants(db_session)

        # Q4 should appear only once despite two paths
        assert descendants == {"Q1", "Q2", "Q3", "Q4"}

    def test_query_ignored_hierarchy_descendants(self, db_session):
        """Test querying ignored hierarchy descendants."""
        # Set up hierarchy: Q1 -> Q2 -> Q3, with Q10 -> Q11 as ignored branch
        test_classes = [
            {"wikidata_id": "Q1", "name": "Root"},
            {"wikidata_id": "Q2", "name": "Child"},
            {"wikidata_id": "Q3", "name": "Grandchild"},
            {"wikidata_id": "Q10", "name": "Ignored Root"},
            {"wikidata_id": "Q11", "name": "Ignored Child"},
        ]

        test_relations = [
            {
                "parent_entity_id": "Q1",
                "child_entity_id": "Q2",
                "statement_id": "Q2$ignored-test-1",
            },
            {
                "parent_entity_id": "Q2",
                "child_entity_id": "Q3",
                "statement_id": "Q3$ignored-test-1",
            },
            {
                "parent_entity_id": "Q10",
                "child_entity_id": "Q11",
                "statement_id": "Q11$ignored-test-1",
            },
        ]

        stmt = insert(WikidataEntity).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        TestClass = self._create_test_class(["Q1"], ignore=["Q10"])
        ignored = TestClass.query_ignored_hierarchy_descendants(db_session)

        # Should return only the ignored branch
        assert ignored == {"Q10", "Q11"}

    def test_query_ignored_hierarchy_descendants_empty(self, db_session):
        """Test querying with no ignore config returns empty set."""
        TestClass = self._create_test_class(["Q1"], ignore=[])
        ignored = TestClass.query_ignored_hierarchy_descendants(db_session)
        assert ignored == set()

    def test_query_ignored_hierarchy_descendants_none(self, db_session):
        """Test querying with None ignore config returns empty set."""
        TestClass = self._create_test_class(["Q1"], ignore=None)
        ignored = TestClass.query_ignored_hierarchy_descendants(db_session)
        assert ignored == set()


class TestCleanupOutsideHierarchy:
    """Test cleanup_outside_hierarchy functionality on entity classes."""

    def _create_hierarchy(self, db_session, root_id, child_ids):
        """Helper to create a hierarchy with root and children."""
        from sqlalchemy.dialects.postgresql import insert

        # Create wikidata entities
        entities = [{"wikidata_id": root_id, "name": f"Root {root_id}"}]
        for child_id in child_ids:
            entities.append({"wikidata_id": child_id, "name": f"Child {child_id}"})

        stmt = insert(WikidataEntity).values(entities)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        # Create subclass relations
        relations = []
        for child_id in child_ids:
            relations.append(
                {
                    "parent_entity_id": root_id,
                    "child_entity_id": child_id,
                    "relation_type": RelationType.SUBCLASS_OF,
                    "statement_id": f"{child_id}$subclass-of-{root_id}",
                }
            )

        if relations:
            stmt = insert(WikidataRelation).values(relations)
            stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
            db_session.execute(stmt)

        db_session.flush()

    def _create_position_in_hierarchy(self, db_session, position_id, class_id):
        """Helper to create a position that is an instance of a hierarchy class."""
        from sqlalchemy.dialects.postgresql import insert
        from poliloom.models import Position

        # Create wikidata entity for the position
        stmt = insert(WikidataEntity).values(
            [{"wikidata_id": position_id, "name": f"Position {position_id}"}]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        # Create position record
        stmt = insert(Position.__table__).values([{"wikidata_id": position_id}])
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        # Create instance_of relation to the class
        stmt = insert(WikidataRelation).values(
            [
                {
                    "parent_entity_id": class_id,
                    "child_entity_id": position_id,
                    "relation_type": RelationType.INSTANCE_OF,
                    "statement_id": f"{position_id}$instance-of-{class_id}",
                }
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

    def _create_orphan_position(self, db_session, position_id):
        """Helper to create a position with no hierarchy relations."""
        from sqlalchemy.dialects.postgresql import insert
        from poliloom.models import Position

        # Create wikidata entity
        stmt = insert(WikidataEntity).values(
            [{"wikidata_id": position_id, "name": f"Orphan Position {position_id}"}]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        # Create position record (no relations)
        stmt = insert(Position.__table__).values([{"wikidata_id": position_id}])
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.flush()

    def test_removes_entities_outside_hierarchy(self, db_session):
        """Test that entities without hierarchy relations are removed."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create a position hierarchy root (Q4164871 is in Position._hierarchy_roots)
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create a position inside the hierarchy
        self._create_position_in_hierarchy(db_session, "Q200", "Q100")

        # Create an orphan position (no hierarchy relations)
        self._create_orphan_position(db_session, "Q300")

        # Verify setup
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 2

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Orphan should be removed
        assert stats["entities_removed"] == 1
        assert stats["total_entities"] == 2

        # Verify only the valid position remains
        remaining = db_session.execute(
            text("SELECT wikidata_id FROM positions")
        ).fetchall()
        assert len(remaining) == 1
        assert remaining[0][0] == "Q200"

    def test_keeps_entities_inside_hierarchy(self, db_session):
        """Test that entities with proper hierarchy relations are kept."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create hierarchy
        self._create_hierarchy(db_session, "Q4164871", ["Q100", "Q101"])

        # Create positions inside the hierarchy
        self._create_position_in_hierarchy(db_session, "Q200", "Q100")
        self._create_position_in_hierarchy(db_session, "Q201", "Q101")

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Nothing should be removed
        assert stats["entities_removed"] == 0

        # Both positions should remain
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 2

    def test_dry_run_does_not_modify(self, db_session):
        """Test that dry_run=True returns stats but doesn't delete anything."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create hierarchy
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create one valid and one orphan position
        self._create_position_in_hierarchy(db_session, "Q200", "Q100")
        self._create_orphan_position(db_session, "Q300")

        # Run cleanup with dry_run=True
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=True)

        # Stats should show what would be removed
        assert stats["entities_removed"] == 1
        assert stats["total_entities"] == 2

        # But nothing should actually be deleted
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 2

    def test_removes_entities_in_ignored_branches(self, db_session):
        """Test that entities in ignored hierarchy branches are removed."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create main hierarchy
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create ignored branch hierarchy (Q12737077 is in Position._hierarchy_ignore)
        self._create_hierarchy(db_session, "Q12737077", ["Q500"])

        # Create position in valid hierarchy
        self._create_position_in_hierarchy(db_session, "Q200", "Q100")

        # Create position in ignored branch
        self._create_position_in_hierarchy(db_session, "Q600", "Q500")

        # Verify setup
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 2

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Position in ignored branch should be removed
        assert stats["entities_removed"] == 1

        # Only valid position should remain
        remaining = db_session.execute(
            text("SELECT wikidata_id FROM positions")
        ).fetchall()
        assert len(remaining) == 1
        assert remaining[0][0] == "Q200"

    def test_soft_deletes_properties_referencing_removed_entities(self, db_session):
        """Test that properties referencing removed entities are soft-deleted."""
        from poliloom.models import Position, Property, PropertyType, Politician
        from sqlalchemy import text

        # Create hierarchy
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create a valid position
        self._create_position_in_hierarchy(db_session, "Q200", "Q100")

        # Create an orphan position
        self._create_orphan_position(db_session, "Q300")

        # Create a politician to hold properties
        politician = Politician.create_with_entity(
            db_session, "Q999", "Test Politician"
        )
        db_session.flush()

        # Create properties referencing both positions
        prop_valid = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id="Q200",
        )
        prop_orphan = Property(
            politician_id=politician.id,
            type=PropertyType.POSITION,
            entity_id="Q300",
        )
        db_session.add_all([prop_valid, prop_orphan])
        db_session.flush()

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # One property should be soft-deleted
        assert stats["properties_deleted"] == 1

        # Check that orphan property is soft-deleted
        soft_deleted = db_session.execute(
            text(
                "SELECT COUNT(*) FROM properties WHERE entity_id = 'Q300' AND deleted_at IS NOT NULL"
            )
        ).scalar()
        assert soft_deleted == 1

        # Valid property should not be deleted
        valid_prop = db_session.execute(
            text("SELECT deleted_at FROM properties WHERE entity_id = 'Q200'")
        ).fetchone()
        assert valid_prop[0] is None

    def test_no_hierarchy_config_returns_zero_removed(self, db_session):
        """Test that entity without hierarchy config returns zero removed."""
        from poliloom.models import WikipediaProject

        # WikipediaProject has _hierarchy_roots = None (not configured)
        # So cleanup should return 0 entities removed
        stats = WikipediaProject.cleanup_outside_hierarchy(db_session, dry_run=False)

        assert stats["entities_removed"] == 0

    def test_entity_in_both_valid_and_ignored_branch_is_removed(self, db_session):
        """Test that entity in both valid and ignored branches is removed (ignored wins)."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create valid hierarchy branch
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create ignored hierarchy branch (Q12737077 is in Position._hierarchy_ignore)
        self._create_hierarchy(db_session, "Q12737077", ["Q500"])

        # Create position that is instance of BOTH valid and ignored classes
        stmt = insert(WikidataEntity).values(
            [{"wikidata_id": "Q999", "name": "Position in both branches"}]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        from poliloom.models import Position as PositionModel

        stmt = insert(PositionModel.__table__).values([{"wikidata_id": "Q999"}])
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        # Create relations to both valid and ignored classes
        stmt = insert(WikidataRelation).values(
            [
                {
                    "parent_entity_id": "Q100",
                    "child_entity_id": "Q999",
                    "relation_type": RelationType.INSTANCE_OF,
                    "statement_id": "Q999$instance-of-valid",
                },
                {
                    "parent_entity_id": "Q500",
                    "child_entity_id": "Q999",
                    "relation_type": RelationType.INSTANCE_OF,
                    "statement_id": "Q999$instance-of-ignored",
                },
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Entity should be removed because ignored branch takes precedence
        assert stats["entities_removed"] == 1

        # Verify position was removed
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 0

    def test_ignored_branch_within_valid_hierarchy(self, db_session):
        """Test ignored branch that's a descendant of a valid root."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create hierarchy: Q4164871 -> Q100 -> Q12737077 (ignored) -> Q500
        # Q12737077 is in Position._hierarchy_ignore
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Make Q12737077 a child of Q100 (within valid hierarchy)
        stmt = insert(WikidataEntity).values(
            [{"wikidata_id": "Q12737077", "name": "Ignored Root (as child)"}]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(
            [
                {
                    "parent_entity_id": "Q100",
                    "child_entity_id": "Q12737077",
                    "relation_type": RelationType.SUBCLASS_OF,
                    "statement_id": "Q12737077$subclass-nested",
                }
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)

        # Create Q500 as child of ignored branch
        self._create_hierarchy(db_session, "Q12737077", ["Q500"])

        # Create position in valid part of hierarchy (instance of Q100)
        self._create_position_in_hierarchy(db_session, "Q200", "Q100")

        # Create position in nested ignored branch (instance of Q500)
        self._create_position_in_hierarchy(db_session, "Q600", "Q500")

        db_session.flush()

        # Verify setup
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 2

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Position in ignored branch should be removed
        assert stats["entities_removed"] == 1

        # Only valid position should remain
        remaining = db_session.execute(
            text("SELECT wikidata_id FROM positions")
        ).fetchall()
        assert len(remaining) == 1
        assert remaining[0][0] == "Q200"

    def test_multiple_roots_keeps_entities_from_all_roots(self, db_session):
        """Test cleanup with multiple hierarchy roots keeps entities from all roots."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Position has multiple roots: Q4164871, Q29645880, Q29918328, Q707492
        # Create hierarchies for two of them
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])
        self._create_hierarchy(db_session, "Q29645880", ["Q200"])

        # Create positions in each hierarchy
        self._create_position_in_hierarchy(db_session, "Q1000", "Q100")
        self._create_position_in_hierarchy(db_session, "Q2000", "Q200")

        # Create orphan position
        self._create_orphan_position(db_session, "Q3000")

        # Verify setup
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 3

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Only orphan should be removed
        assert stats["entities_removed"] == 1

        # Both valid positions should remain
        remaining = db_session.execute(
            text("SELECT wikidata_id FROM positions ORDER BY wikidata_id")
        ).fetchall()
        assert len(remaining) == 2
        assert {r[0] for r in remaining} == {"Q1000", "Q2000"}

    def test_deep_ignored_hierarchy(self, db_session):
        """Test that entities deep in ignored hierarchy are removed."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create valid hierarchy
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create deep ignored hierarchy: Q12737077 -> Q500 -> Q501 -> Q502
        self._create_hierarchy(db_session, "Q12737077", ["Q500"])

        stmt = insert(WikidataEntity).values(
            [
                {"wikidata_id": "Q501", "name": "Deep ignored 1"},
                {"wikidata_id": "Q502", "name": "Deep ignored 2"},
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(WikidataRelation).values(
            [
                {
                    "parent_entity_id": "Q500",
                    "child_entity_id": "Q501",
                    "relation_type": RelationType.SUBCLASS_OF,
                    "statement_id": "Q501$subclass-deep",
                },
                {
                    "parent_entity_id": "Q501",
                    "child_entity_id": "Q502",
                    "relation_type": RelationType.SUBCLASS_OF,
                    "statement_id": "Q502$subclass-deep",
                },
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)

        # Create valid position
        self._create_position_in_hierarchy(db_session, "Q1000", "Q100")

        # Create position deep in ignored hierarchy (instance of Q502)
        self._create_position_in_hierarchy(db_session, "Q2000", "Q502")

        db_session.flush()

        # Verify setup
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 2

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Deep ignored position should be removed
        assert stats["entities_removed"] == 1

        # Only valid position should remain
        remaining = db_session.execute(
            text("SELECT wikidata_id FROM positions")
        ).fetchall()
        assert len(remaining) == 1
        assert remaining[0][0] == "Q1000"

    def test_entity_with_subclass_relation_to_hierarchy(self, db_session):
        """Test that SUBCLASS_OF relation also counts as being in hierarchy."""
        from poliloom.models import Position
        from sqlalchemy import text

        # Create hierarchy
        self._create_hierarchy(db_session, "Q4164871", ["Q100"])

        # Create position with SUBCLASS_OF relation (not INSTANCE_OF)
        stmt = insert(WikidataEntity).values(
            [{"wikidata_id": "Q200", "name": "Position via subclass"}]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        from poliloom.models import Position as PositionModel

        stmt = insert(PositionModel.__table__).values([{"wikidata_id": "Q200"}])
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        # Create SUBCLASS_OF relation (instead of INSTANCE_OF)
        stmt = insert(WikidataRelation).values(
            [
                {
                    "parent_entity_id": "Q100",
                    "child_entity_id": "Q200",
                    "relation_type": RelationType.SUBCLASS_OF,
                    "statement_id": "Q200$subclass-of-Q100",
                }
            ]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["statement_id"])
        db_session.execute(stmt)
        db_session.flush()

        # Run cleanup
        stats = Position.cleanup_outside_hierarchy(db_session, dry_run=False)

        # Position should NOT be removed (SUBCLASS_OF is valid for membership)
        assert stats["entities_removed"] == 0

        # Position should remain
        count = db_session.execute(text("SELECT COUNT(*) FROM positions")).scalar()
        assert count == 1
