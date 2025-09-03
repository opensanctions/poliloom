"""Tests for WikidataEntityImporter."""

import json
import tempfile
import os
from unittest.mock import patch

from poliloom.models import WikidataClass, SubclassRelation, Position, Location, Country
from poliloom.importer.entity import (
    import_entities,
    _query_hierarchy_descendants,
    _insert_positions_batch,
    _insert_locations_batch,
    _insert_countries_batch,
)
from sqlalchemy.dialects.postgresql import insert


class TestWikidataEntityImporter:
    """Test entity importing functionality."""

    def test_import_entities_integration(self, db_session):
        """Test complete entity extraction workflow integration."""

        # First, set up hierarchy in database using current approach
        hierarchy_data = [
            # Position hierarchy: Q294414 (position) -> Q4164871 (office)
            {"wikidata_id": "Q294414", "name": "position"},  # Root position class
            {
                "wikidata_id": "Q4164871",
                "name": "office",
            },  # Office (subclass of position)
            # Location hierarchy: Q27096213 (geographic entity) -> Q515 (city)
            {
                "wikidata_id": "Q27096213",
                "name": "geographic entity",
            },  # Root location class
            {"wikidata_id": "Q515", "name": "city"},  # City (subclass of location)
        ]

        hierarchy_relations = [
            {"parent_class_id": "Q294414", "child_class_id": "Q4164871"},
            {"parent_class_id": "Q27096213", "child_class_id": "Q515"},
        ]

        # Insert hierarchy data first
        stmt = insert(WikidataClass).values(hierarchy_data)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(SubclassRelation).values(hierarchy_relations)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_subclass_parent_child")
        db_session.execute(stmt)
        db_session.commit()

        # Create test entities covering all types we extract
        test_entities = [
            # Position entity - should be extracted
            {
                "id": "Q123456",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Office Position"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q4164871"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            # Location entity - should be extracted
            {
                "id": "Q789012",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test City Location"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q515"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
            # Country entity - should be extracted
            {
                "id": "Q345678",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Country"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q6256"},
                                    "type": "wikibase-entityid",
                                },  # country
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P297": [
                        {  # ISO 3166-1 alpha-2 code
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P297",
                                "datavalue": {"value": "TC", "type": "string"},
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Politician entity - should be ignored (wrong type for this extractor)
            {
                "id": "Q999999",
                "type": "item",
                "labels": {"en": {"language": "en", "value": "Test Politician"}},
                "claims": {
                    "P31": [
                        {  # instance of
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q5"},
                                    "type": "wikibase-entityid",
                                },  # human
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                    "P106": [
                        {  # occupation
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P106",
                                "datavalue": {
                                    "value": {"id": "Q82955"},
                                    "type": "wikibase-entityid",
                                },  # politician
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ],
                },
            },
            # Entity without name - should be ignored
            {
                "id": "Q111111",
                "type": "item",
                "labels": {},  # No labels/name
                "claims": {
                    "P31": [
                        {
                            "mainsnak": {
                                "snaktype": "value",
                                "property": "P31",
                                "datavalue": {
                                    "value": {"id": "Q4164871"},
                                    "type": "wikibase-entityid",
                                },
                            },
                            "type": "statement",
                            "rank": "normal",
                        }
                    ]
                },
            },
        ]

        # Create temporary dump file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp_file:
            for entity in test_entities:
                temp_file.write(json.dumps(entity) + "\n")
            temp_file_path = temp_file.name

        try:
            # Clear existing entity data
            db_session.query(Position).delete()
            db_session.query(Location).delete()
            db_session.query(Country).delete()
            db_session.commit()

            # Test extraction
            with patch("poliloom.dump_reader.calculate_file_chunks") as mock_chunks:
                # Mock chunks to return single chunk for simpler testing
                file_size = os.path.getsize(temp_file_path)
                mock_chunks.return_value = [(0, file_size)]

                result = import_entities(temp_file_path, batch_size=10)

            # Verify counts returned
            assert result["positions"] == 1
            assert result["locations"] == 1
            assert result["countries"] == 1

            # Verify entities were actually saved to database
            positions = db_session.query(Position).all()
            locations = db_session.query(Location).all()
            countries = db_session.query(Country).all()

            assert len(positions) == 1
            assert len(locations) == 1
            assert len(countries) == 1

            # Verify specific entity data
            position = positions[0]
            assert position.wikidata_id == "Q123456"
            assert position.name == "Test Office Position"
            assert len(position.wikidata_classes) > 0
            assert any(
                cls.wikidata_id == "Q4164871" for cls in position.wikidata_classes
            )

            location = locations[0]
            assert location.wikidata_id == "Q789012"
            assert location.name == "Test City Location"
            assert len(location.wikidata_classes) > 0
            assert any(cls.wikidata_id == "Q515" for cls in location.wikidata_classes)

            country = countries[0]
            assert country.wikidata_id == "Q345678"
            assert country.name == "Test Country"
            assert country.iso_code == "TC"

        finally:
            os.unlink(temp_file_path)

    def test_insert_positions_batch(self, db_session):
        """Test inserting a batch of positions."""
        positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
            {"wikidata_id": "Q2", "name": "Position 2"},
        ]

        _insert_positions_batch(positions)

        # Verify positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 2
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_positions_batch_with_duplicates(self, db_session):
        """Test inserting positions with some duplicates."""
        # Insert initial batch
        initial_positions = [
            {"wikidata_id": "Q1", "name": "Position 1"},
            {"wikidata_id": "Q2", "name": "Position 2"},
        ]
        _insert_positions_batch(initial_positions)

        # Insert batch with some duplicates and new items
        positions_with_duplicates = [
            {
                "wikidata_id": "Q1",
                "name": "Position 1 Updated",
            },  # Duplicate (should update)
            {"wikidata_id": "Q2", "name": "Position 2"},  # Duplicate (no change)
            {"wikidata_id": "Q3", "name": "Position 3"},  # New
        ]
        _insert_positions_batch(positions_with_duplicates)

        # Verify all positions exist with correct data
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 3
        wikidata_ids = {pos.wikidata_id for pos in inserted_positions}
        assert wikidata_ids == {"Q1", "Q2", "Q3"}

        # Verify Q1 was updated
        q1_position = (
            db_session.query(Position).filter(Position.wikidata_id == "Q1").first()
        )
        assert q1_position.name == "Position 1 Updated"

    def test_insert_positions_batch_empty(self, db_session):
        """Test inserting empty batch of positions."""
        positions = []

        # Should handle empty batch gracefully without errors
        _insert_positions_batch(positions)

        # Verify no positions were inserted
        inserted_positions = db_session.query(Position).all()
        assert len(inserted_positions) == 0

    def test_insert_locations_batch(self, db_session):
        """Test inserting a batch of locations."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
        ]

        _insert_locations_batch(locations)

        # Verify locations were inserted
        inserted_locations = db_session.query(Location).all()
        assert len(inserted_locations) == 2
        wikidata_ids = {loc.wikidata_id for loc in inserted_locations}
        assert wikidata_ids == {"Q1", "Q2"}

    def test_insert_locations_batch_with_duplicates(self, db_session):
        """Test inserting locations with some duplicates."""
        locations = [
            {"wikidata_id": "Q1", "name": "Location 1"},
            {"wikidata_id": "Q2", "name": "Location 2"},
            {"wikidata_id": "Q3", "name": "Location 3"},
        ]

        _insert_locations_batch(locations)

        # Insert again with some duplicates - should handle gracefully
        locations_with_duplicates = [
            {"wikidata_id": "Q1", "name": "Location 1 Updated"},  # Duplicate
            {"wikidata_id": "Q4", "name": "Location 4"},  # New
        ]
        _insert_locations_batch(locations_with_duplicates)

        # Should now have 4 total locations
        all_locations = db_session.query(Location).all()
        assert len(all_locations) == 4
        wikidata_ids = {loc.wikidata_id for loc in all_locations}
        assert wikidata_ids == {"Q1", "Q2", "Q3", "Q4"}

    def test_insert_locations_batch_empty(self, db_session):
        """Test inserting empty batch of locations."""
        locations = []

        # Should handle empty batch gracefully without errors
        _insert_locations_batch(locations)

        # Verify no locations were inserted
        inserted_locations = db_session.query(Location).all()
        assert len(inserted_locations) == 0

    def test_insert_countries_batch(self, db_session):
        """Test inserting a batch of countries."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
            {"wikidata_id": "Q2", "name": "Country 2", "iso_code": "C2"},
        ]

        _insert_countries_batch(countries)

        # Verify countries were inserted
        inserted_countries = db_session.query(Country).all()
        assert len(inserted_countries) == 2
        wikidata_ids = {country.wikidata_id for country in inserted_countries}
        assert wikidata_ids == {"Q1", "Q2"}

        # Verify specific country data
        country1 = db_session.query(Country).filter(Country.wikidata_id == "Q1").first()
        assert country1.name == "Country 1"
        assert country1.iso_code == "C1"

    def test_insert_countries_batch_empty(self, db_session):
        """Test inserting empty batch of countries."""
        countries = []

        # Should handle empty batch gracefully without errors
        _insert_countries_batch(countries)

        # Verify no countries were inserted
        inserted_countries = db_session.query(Country).all()
        assert len(inserted_countries) == 0

    def test_insert_countries_batch_with_duplicates_handling(self, db_session):
        """Test that countries batch uses ON CONFLICT DO UPDATE."""
        countries = [
            {"wikidata_id": "Q1", "name": "Country 1", "iso_code": "C1"},
        ]

        # Insert first time
        _insert_countries_batch(countries)

        # Insert again with updated name - should update
        updated_countries = [
            {"wikidata_id": "Q1", "name": "Country 1 Updated", "iso_code": "C1"},
        ]
        _insert_countries_batch(updated_countries)

        # Should still have only one country but with updated name
        final_countries = db_session.query(Country).all()
        assert len(final_countries) == 1
        assert final_countries[0].wikidata_id == "Q1"
        assert final_countries[0].name == "Country 1 Updated"

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
            {"parent_class_id": "Q1", "child_class_id": "Q2"},
            {"parent_class_id": "Q2", "child_class_id": "Q3"},
            {"parent_class_id": "Q1", "child_class_id": "Q4"},
        ]

        # Insert test data
        stmt = insert(WikidataClass).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(SubclassRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_subclass_parent_child")
        db_session.execute(stmt)
        db_session.commit()

        # Test querying descendants
        descendants = _query_hierarchy_descendants(["Q1"], db_session)

        # Should include Q1 itself and all its descendants with names
        assert descendants == {"Q1", "Q2", "Q3", "Q4"}

    def test_query_hierarchy_descendants_single_node(self, db_session):
        """Test querying descendants for a single node with no children."""
        # Set up single node
        test_classes = [{"wikidata_id": "Q1", "name": "Single Node"}]

        stmt = insert(WikidataClass).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)
        db_session.commit()

        # Test querying descendants
        descendants = _query_hierarchy_descendants(["Q1"], db_session)

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
            {"parent_class_id": "Q1", "child_class_id": "Q2"},
            {"parent_class_id": "Q1", "child_class_id": "Q3"},
            {"parent_class_id": "Q2", "child_class_id": "Q4"},
            {"parent_class_id": "Q2", "child_class_id": "Q5"},
        ]

        stmt = insert(WikidataClass).values(test_classes)
        stmt = stmt.on_conflict_do_nothing(index_elements=["wikidata_id"])
        db_session.execute(stmt)

        stmt = insert(SubclassRelation).values(test_relations)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_subclass_parent_child")
        db_session.execute(stmt)
        db_session.commit()

        # Test querying descendants of Q2 (should include Q2, Q4, Q5)
        descendants = _query_hierarchy_descendants(["Q2"], db_session)
        assert descendants == {"Q2", "Q4", "Q5"}

        # Test querying descendants of Q3 (should only include Q3)
        descendants_q3 = _query_hierarchy_descendants(["Q3"], db_session)
        assert descendants_q3 == {"Q3"}
