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

    def test_is_politician_with_occupation(self, extractor):
        """Test checking if entity is a politician based on occupation."""
        # Entity that is a human with politician occupation
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P106": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q82955"}  # politician
                            }
                        }
                    }
                ],
            },
        }

        result = extractor.is_politician(entity)
        assert result is True

    def test_is_politician_with_position(self, extractor):
        """Test checking if entity is a politician based on position held."""
        # Entity that is a human with political position
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P39": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q30185"}  # mayor
                            }
                        }
                    }
                ],
            },
        }

        result = extractor.is_politician(entity)
        assert result is True

    def test_is_politician_not_human(self, extractor):
        """Test checking if entity is NOT a politician when not human."""
        # Entity that is not human
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q123"}  # not human
                            }
                        }
                    }
                ],
                "P106": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q82955"}  # politician
                            }
                        }
                    }
                ],
            },
        }

        result = extractor.is_politician(entity)
        assert result is False

    def test_is_politician_false(self, extractor):
        """Test checking if entity is NOT a politician."""
        # Entity that is human but not a politician
        entity = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P106": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q999999"}  # not politician
                            }
                        }
                    }
                ],
            },
        }

        result = extractor.is_politician(entity)
        assert result is False

    def test_is_politician_no_claims(self, extractor):
        """Test checking if entity is NOT a politician when no claims."""
        # Entity with no claims
        entity = {"id": "Q123", "claims": {}}

        result = extractor.is_politician(entity)
        assert result is False

    def test_extract_politician_data_basic(self, extractor):
        """Test extracting basic politician data."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P106": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q82955"}  # politician
                            }
                        }
                    }
                ],
            },
        }

        data = extractor.extract_politician_data(entity)

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "John Doe"
        assert data["is_deceased"] is False
        assert data["properties"] == []
        assert data["citizenships"] == []
        assert data["positions"] == []
        assert data["wikipedia_links"] == []
        assert data["birthplace"] is None

    def test_extract_politician_data_with_death(self, extractor):
        """Test extracting politician data with death date."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P570": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+2020-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        }
                    }
                ],
            },
        }

        data = extractor.extract_politician_data(entity)

        assert data["is_deceased"] is True
        assert len(data["properties"]) == 1
        assert data["properties"][0]["type"] == "DeathDate"
        assert data["properties"][0]["value"] == "2020-01-01"

    def test_extract_politician_data_with_birth_date(self, extractor):
        """Test extracting politician data with birth date."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P569": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+1970-05-15T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        }
                    }
                ],
            },
        }

        data = extractor.extract_politician_data(entity)

        assert len(data["properties"]) == 1
        assert data["properties"][0]["type"] == "BirthDate"
        assert data["properties"][0]["value"] == "1970-05-15"

    def test_extract_politician_data_with_citizenships(self, extractor):
        """Test extracting politician data with citizenships."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P27": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q30"}  # United States
                            }
                        }
                    },
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q16"}  # Canada
                            }
                        }
                    },
                ],
            },
        }

        data = extractor.extract_politician_data(entity)

        assert len(data["citizenships"]) == 2
        assert "Q30" in data["citizenships"]
        assert "Q16" in data["citizenships"]

    def test_extract_politician_data_with_positions(self, extractor):
        """Test extracting politician data with positions."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P39": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q30185"}  # mayor
                            }
                        },
                        "qualifiers": {
                            "P580": [
                                {
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+2020-01-01T00:00:00Z",
                                            "precision": 11,
                                        },
                                    }
                                }
                            ],
                            "P582": [
                                {
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+2024-01-01T00:00:00Z",
                                            "precision": 11,
                                        },
                                    }
                                }
                            ],
                        },
                    }
                ],
            },
        }

        data = extractor.extract_politician_data(entity)

        assert len(data["positions"]) == 1
        position = data["positions"][0]
        assert position["wikidata_id"] == "Q30185"
        assert position["start_date"] == "2020-01-01"
        assert position["end_date"] == "2024-01-01"

    def test_extract_politician_data_with_birthplace(self, extractor):
        """Test extracting politician data with birthplace."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
                "P19": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q60"}  # New York City
                            }
                        }
                    }
                ],
            },
        }

        data = extractor.extract_politician_data(entity)

        assert data["birthplace"] == "Q60"

    def test_extract_politician_data_with_wikipedia_links(self, extractor):
        """Test extracting politician data with Wikipedia links."""
        entity = {
            "id": "Q123",
            "labels": {"en": {"value": "John Doe"}},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
            },
            "sitelinks": {
                "enwiki": {"title": "John Doe"},
                "frwiki": {"title": "John Doe"},
            },
        }

        data = extractor.extract_politician_data(entity)

        assert len(data["wikipedia_links"]) == 2

        # Check English Wikipedia link
        en_link = next(
            link for link in data["wikipedia_links"] if link["language"] == "en"
        )
        assert en_link["title"] == "John Doe"
        assert en_link["url"] == "https://en.wikipedia.org/wiki/John_Doe"

        # Check French Wikipedia link
        fr_link = next(
            link for link in data["wikipedia_links"] if link["language"] == "fr"
        )
        assert fr_link["title"] == "John Doe"
        assert fr_link["url"] == "https://fr.wikipedia.org/wiki/John_Doe"

    def test_extract_politician_data_no_name(self, extractor):
        """Test extracting politician data when entity has no name."""
        entity = {
            "id": "Q123",
            "labels": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"id": "Q5"}  # human
                            }
                        }
                    }
                ],
            },
        }

        data = extractor.extract_politician_data(entity)
        assert data is None

    def test_extract_date_from_claims(self, extractor):
        """Test extracting date from claims with different precisions."""
        # Test day precision
        claims = [
            {
                "mainsnak": {
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+1970-05-15T00:00:00Z",
                            "precision": 11,
                        },
                    }
                }
            }
        ]

        date = extractor._extract_date_from_claims(claims)
        assert date == "1970-05-15"

        # Test month precision
        claims = [
            {
                "mainsnak": {
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+1970-05-00T00:00:00Z",
                            "precision": 10,
                        },
                    }
                }
            }
        ]

        date = extractor._extract_date_from_claims(claims)
        assert date == "1970-05"

        # Test year precision
        claims = [
            {
                "mainsnak": {
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+1970-00-00T00:00:00Z",
                            "precision": 9,
                        },
                    }
                }
            }
        ]

        date = extractor._extract_date_from_claims(claims)
        assert date == "1970"

    def test_extract_date_from_claims_malformed(self, extractor):
        """Test extracting date from malformed claims."""
        # Test malformed claim
        claims = [
            {
                "mainsnak": {
                    # Missing datavalue
                }
            },
            {
                "mainsnak": {
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+1970-05-15T00:00:00Z",
                            "precision": 11,
                        },
                    }
                }
            },
        ]

        date = extractor._extract_date_from_claims(claims)
        assert date == "1970-05-15"  # Should find the valid one

    def test_extract_date_from_claims_qualifier_format(self, extractor):
        """Test extracting date from qualifier format claims."""
        # Test qualifier format (direct datavalue)
        claims = [
            {
                "datavalue": {
                    "type": "time",
                    "value": {
                        "time": "+1970-05-15T00:00:00Z",
                        "precision": 11,
                    },
                }
            }
        ]

        date = extractor._extract_date_from_claims(claims)
        assert date == "1970-05-15"

    def test_extract_date_from_claims_empty(self, extractor):
        """Test extracting date from empty claims."""
        claims = []

        date = extractor._extract_date_from_claims(claims)
        assert date is None
