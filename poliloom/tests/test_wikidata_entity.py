"""Tests for the unified WikidataEntity class."""

import pytest
from poliloom.wikidata_entity import WikidataEntity


class TestWikidataEntity:
    """Core tests for WikidataEntity functionality."""

    @pytest.mark.parametrize(
        "entity_data,descendants,expected_type",
        [
            # Politician (by occupation)
            (
                {
                    "id": "Q123",
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                            }
                        ],
                        "P106": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                            }
                        ],
                    },
                },
                {},
                "politician",
            ),
            # Politician (by position)
            (
                {
                    "id": "Q124",
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                            }
                        ],
                        "P39": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q30185"}}},
                            }
                        ],
                    },
                },
                {},
                "politician",
            ),
            # Position
            (
                {
                    "id": "Q125",
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q294414"}}},
                            }
                        ]
                    },
                },
                {"position_descendants": {"Q294414": True}},
                "position",
            ),
            # Location
            (
                {
                    "id": "Q126",
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q515"}}},
                            }
                        ]
                    },
                },
                {"location_descendants": {"Q515": True}},
                "location",
            ),
            # Country
            (
                {
                    "id": "Q127",
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q6256"}}},
                            }
                        ]
                    },
                },
                {},
                "country",
            ),
            # Unknown type
            (
                {
                    "id": "Q128",
                    "claims": {
                        "P31": [
                            {
                                "rank": "normal",
                                "mainsnak": {"datavalue": {"value": {"id": "Q999"}}},
                            }
                        ]
                    },
                },
                {},
                None,
            ),
        ],
    )
    def test_entity_type_detection(self, entity_data, descendants, expected_type):
        """Test entity type detection."""
        entity = WikidataEntity(entity_data, **descendants)
        assert entity.entity_type == expected_type

    @pytest.mark.parametrize(
        "death_claims,expected_import",
        [
            # Living (no death date)
            ([], True),
            # Died after 1950
            (
                [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+1980-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ],
                True,
            ),
            # Died before 1950
            (
                [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+1940-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ],
                False,
            ),
        ],
    )
    def test_politician_import_logic(self, death_claims, expected_import):
        """Test politician import logic based on death date."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                    }
                ],
            },
        }
        if death_claims:
            entity_data["claims"]["P570"] = death_claims

        entity = WikidataEntity(entity_data)
        assert entity.should_import() == expected_import

    def test_truthy_claims_filtering(self):
        """Test truthy claims filtering logic."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "preferred",
                        "mainsnak": {"datavalue": {"value": {"id": "Q1"}}},
                    },
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q2"}}},
                    },
                    {
                        "rank": "deprecated",
                        "mainsnak": {"datavalue": {"value": {"id": "Q3"}}},
                    },
                ]
            },
        }
        entity = WikidataEntity(entity_data)
        claims = entity.get_truthy_claims("P31")

        # Should return only preferred rank
        assert len(claims) == 1
        assert claims[0]["rank"] == "preferred"

    def test_basic_to_database_dict(self):
        """Test basic database dictionary conversion."""
        entity_data = {"id": "Q123", "labels": {"en": {"value": "Test Entity"}}}
        entity = WikidataEntity(entity_data)
        result = entity.to_database_dict()

        assert result["wikidata_id"] == "Q123"
        assert result["name"] == "Test Entity"

    def test_country_to_database_dict_with_iso(self):
        """Test country database dict includes ISO code."""
        entity_data = {
            "id": "Q456",
            "labels": {"en": {"value": "Test Country"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q6256"}}},
                    }
                ],
                "P297": [
                    {"rank": "normal", "mainsnak": {"datavalue": {"value": "US"}}}
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        result = entity.to_database_dict()

        assert result["wikidata_id"] == "Q456"
        assert result["name"] == "Test Country"
        assert result["iso_code"] == "US"

    def test_date_extraction(self):
        """Test date extraction from claims."""
        claims = [
            {
                "rank": "normal",
                "mainsnak": {
                    "datavalue": {
                        "type": "time",
                        "value": {"time": "+1980-01-01T00:00:00Z", "precision": 11},
                    }
                },
            }
        ]
        entity = WikidataEntity({"id": "Q123"})
        date = entity.extract_date_from_claims(claims)
        assert date == {"date": "1980-01-01", "precision": 11}
