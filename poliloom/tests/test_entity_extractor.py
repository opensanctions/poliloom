"""Tests for EntityExtractor."""

import pytest

from poliloom.services.entity_extractor import EntityExtractor


class TestEntityExtractor:
    """Test EntityExtractor functionality."""

    @pytest.fixture
    def extractor(self):
        """Create an EntityExtractor instance."""
        return EntityExtractor()

    def test_is_instance_of_position(self, extractor):
        """Test checking if entity is instance of position type."""
        position_descendants = {"Q294414", "Q30185"}

        # Entity that is a position
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q294414"}  # public office
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_instance_of_position(entity, position_descendants)
        assert result is True

    def test_is_instance_of_position_false(self, extractor):
        """Test checking if entity is NOT instance of position type."""
        position_descendants = {"Q294414", "Q30185"}

        # Entity that is not a position
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q999999"}  # not a position
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_instance_of_position(entity, position_descendants)
        assert result is False

    def test_is_instance_of_location(self, extractor):
        """Test checking if entity is instance of location type."""
        location_descendants = {"Q2221906", "Q515"}

        # Entity that is a location
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q2221906"}  # geographic location
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_instance_of_location(entity, location_descendants)
        assert result is True

    def test_is_instance_of_location_false(self, extractor):
        """Test checking if entity is NOT instance of location type."""
        location_descendants = {"Q2221906", "Q515"}

        # Entity that is not a location
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q999999"}  # not a location
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_instance_of_location(entity, location_descendants)
        assert result is False

    def test_is_country_entity(self, extractor):
        """Test checking if entity is a country."""
        # Entity that is a country
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q6256"}  # country
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_country_entity(entity)
        assert result is True

    def test_is_country_entity_sovereign_state(self, extractor):
        """Test checking if entity is a sovereign state (also treated as country)."""
        # Entity that is a sovereign state
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q3624078"}  # sovereign state
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_country_entity(entity)
        assert result is True

    def test_is_country_entity_false(self, extractor):
        """Test checking if entity is NOT a country."""
        # Entity that is not a country
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q999999"}  # not a country
                            }
                        }
                    }
                ]
            },
        }

        result = extractor.is_country_entity(entity)
        assert result is False

    def test_get_entity_name(self, extractor):
        """Test extracting entity name."""
        # Entity with English label
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "Test Entity"}, "fr": {"value": "Entité Test"}},
        }

        name = extractor.get_entity_name(entity)
        assert name == "Test Entity"

    def test_get_entity_name_no_english(self, extractor):
        """Test extracting entity name when no English label."""
        # Entity without English label
        entity = {
            "id": "Q123",
            "labels": {"fr": {"value": "Entité Test"}, "de": {"value": "Test Entität"}},
        }

        name = extractor.get_entity_name(entity)
        # Should return any available language
        assert name in ["Entité Test", "Test Entität"]

    def test_get_entity_name_no_labels(self, extractor):
        """Test extracting entity name when no labels."""
        # Entity without labels
        entity = {"id": "Q123", "labels": {}}

        name = extractor.get_entity_name(entity)
        assert name is None

    def test_extract_position_data(self, extractor):
        """Test extracting position data from entity."""
        entity = {"id": "Q123", "labels": {"en": {"value": "Test Position"}}}

        data = extractor.extract_position_data(entity)

        expected = {"wikidata_id": "Q123", "name": "Test Position"}
        assert data == expected

    def test_extract_position_data_no_name(self, extractor):
        """Test extracting position data when entity has no name."""
        entity = {"id": "Q123", "labels": {}}

        data = extractor.extract_position_data(entity)
        assert data is None

    def test_extract_location_data(self, extractor):
        """Test extracting location data from entity."""
        entity = {"id": "Q123", "labels": {"en": {"value": "Test Location"}}}

        data = extractor.extract_location_data(entity)

        expected = {"wikidata_id": "Q123", "name": "Test Location"}
        assert data == expected

    def test_extract_location_data_no_name(self, extractor):
        """Test extracting location data when entity has no name."""
        entity = {"id": "Q123", "labels": {}}

        data = extractor.extract_location_data(entity)
        assert data is None

    def test_extract_country_data(self, extractor):
        """Test extracting country data from entity."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "Test Country"}},
            "claims": {"P297": [{"mainsnak": {"datavalue": {"value": "TC"}}}]},
        }

        data = extractor.extract_country_data(entity)

        expected = {"wikidata_id": "Q123", "name": "Test Country", "iso_code": "TC"}
        assert data == expected

    def test_extract_country_data_no_iso_code(self, extractor):
        """Test extracting country data when entity has no ISO code."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "Test Country"}},
            "claims": {},
        }

        data = extractor.extract_country_data(entity)

        expected = {"wikidata_id": "Q123", "name": "Test Country", "iso_code": None}
        assert data == expected

    def test_extract_country_data_no_name(self, extractor):
        """Test extracting country data when entity has no name."""
        entity = {"id": "Q123", "labels": {}}

        data = extractor.extract_country_data(entity)
        assert data is None

    def test_extract_country_data_malformed_iso_claim(self, extractor):
        """Test extracting country data with malformed ISO claim."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "Test Country"}},
            "claims": {
                "P297": [
                    {
                        "mainsnak": {
                            # Missing datavalue
                        }
                    },
                    {"mainsnak": {"datavalue": {"value": "TC"}}},
                ]
            },
        }

        data = extractor.extract_country_data(entity)

        expected = {
            "wikidata_id": "Q123",
            "name": "Test Country",
            "iso_code": "TC",  # Should find the valid one
        }
        assert data == expected
