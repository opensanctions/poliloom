"""Tests for the WikidataEntity class."""

from poliloom.wikidata_entity import WikidataEntity


class TestWikidataEntity:
    """Core tests for WikidataEntity functionality."""

    def test_basic_entity_creation(self):
        """Test creating a basic WikidataEntity."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"value": "Test Entity"}},
            "claims": {},
        }
        entity = WikidataEntity(entity_data)

        assert entity.get_wikidata_id() == "Q123"
        assert entity.get_entity_name() == "Test Entity"

    def test_is_politician_by_occupation(self):
        """Test politician detection by occupation."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"value": "John Politician"}},
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
        entity = WikidataEntity(entity_data)
        assert entity.is_politician() is True

    def test_is_politician_by_position(self):
        """Test politician detection by held position."""
        entity_data = {
            "id": "Q124",
            "labels": {"en": {"value": "Jane Mayor"}},
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
        }
        entity = WikidataEntity(entity_data)
        assert entity.is_politician() is True

    def test_is_not_politician_non_human(self):
        """Test that non-humans are not politicians."""
        entity_data = {
            "id": "Q125",
            "labels": {"en": {"value": "Some Organization"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q43229"}}
                        },  # organization
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
        entity = WikidataEntity(entity_data)
        assert entity.is_politician() is False

    def test_is_position(self):
        """Test position detection."""
        entity_data = {
            "id": "Q126",
            "labels": {"en": {"value": "Mayor"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q294414"}}},
                    }
                ]
            },
        }
        entity = WikidataEntity(entity_data)
        position_classes = {"Q294414", "Q4164871"}

        assert entity.is_position(position_classes) is True
        assert entity.is_position({"Q999999"}) is False

    def test_is_location(self):
        """Test location detection."""
        entity_data = {
            "id": "Q127",
            "labels": {"en": {"value": "New York City"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q515"}}},  # city
                    }
                ]
            },
        }
        entity = WikidataEntity(entity_data)
        location_classes = {"Q515", "Q486972"}

        assert entity.is_location(location_classes) is True
        assert entity.is_location({"Q999999"}) is False

    def test_is_country(self):
        """Test country detection."""
        entity_data = {
            "id": "Q128",
            "labels": {"en": {"value": "United States"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q6256"}}
                        },  # country
                    }
                ]
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.is_country() is True

        # Test with sovereign state
        entity_data["claims"]["P31"][0]["mainsnak"]["datavalue"]["value"]["id"] = (
            "Q3624078"
        )
        entity = WikidataEntity(entity_data)
        assert entity.is_country() is True

    def test_is_not_country(self):
        """Test non-country entity."""
        entity_data = {
            "id": "Q129",
            "labels": {"en": {"value": "Some City"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q515"}}},  # city
                    }
                ]
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.is_country() is False

    def test_is_deceased(self):
        """Test deceased detection."""
        # Living person
        entity_data = {
            "id": "Q130",
            "claims": {},
        }
        entity = WikidataEntity(entity_data)
        assert entity.is_deceased is False

        # Deceased person
        entity_data["claims"]["P570"] = [
            {
                "rank": "normal",
                "mainsnak": {"datavalue": {"value": {"time": "+1980-01-01T00:00:00Z"}}},
            }
        ]
        entity = WikidataEntity(entity_data)
        assert entity.is_deceased is True

    def test_extract_iso_code(self):
        """Test ISO code extraction for countries."""
        entity_data = {
            "id": "Q131",
            "claims": {
                "P297": [
                    {"rank": "normal", "mainsnak": {"datavalue": {"value": "US"}}}
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.extract_iso_code() == "US"

        # No ISO code
        entity_data = {"id": "Q132", "claims": {}}
        entity = WikidataEntity(entity_data)
        assert entity.extract_iso_code() is None

    def test_get_most_specific_class_wikidata_id(self):
        """Test getting most specific class ID."""
        entity_data = {
            "id": "Q133",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q515"}}},  # city
                    }
                ]
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.get_most_specific_class_wikidata_id() == "Q515"

        # No instance claims
        entity_data = {"id": "Q134", "claims": {}}
        entity = WikidataEntity(entity_data)
        assert entity.get_most_specific_class_wikidata_id() is None

    def test_truthy_claims_filtering(self):
        """Test truthy claims filtering with rank precedence."""
        entity_data = {
            "id": "Q135",
            "claims": {
                "P31": [
                    {
                        "rank": "deprecated",
                        "mainsnak": {"datavalue": {"value": {"id": "Q1"}}},
                    },
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q2"}}},
                    },
                    {
                        "rank": "preferred",
                        "mainsnak": {"datavalue": {"value": {"id": "Q3"}}},
                    },
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q4"}}},
                    },
                ]
            },
        }
        entity = WikidataEntity(entity_data)

        # Should only return preferred claims when they exist
        truthy_claims = entity.get_truthy_claims("P31")
        assert len(truthy_claims) == 1
        assert truthy_claims[0]["mainsnak"]["datavalue"]["value"]["id"] == "Q3"

        # When no preferred claims exist, should return all normal claims
        entity_data["claims"]["P31"] = [
            {
                "rank": "deprecated",
                "mainsnak": {"datavalue": {"value": {"id": "Q1"}}},
            },
            {
                "rank": "normal",
                "mainsnak": {"datavalue": {"value": {"id": "Q2"}}},
            },
            {
                "rank": "normal",
                "mainsnak": {"datavalue": {"value": {"id": "Q4"}}},
            },
        ]
        entity = WikidataEntity(entity_data)
        truthy_claims = entity.get_truthy_claims("P31")
        assert len(truthy_claims) == 2

    def test_date_extraction(self):
        """Test date extraction with different precisions."""
        entity_data = {
            "id": "Q136",
            "claims": {
                "P580": [  # start time
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+1970-06-15T00:00:00Z",
                                    "precision": 11,  # day precision
                                },
                            }
                        },
                    }
                ]
            },
        }
        entity = WikidataEntity(entity_data)

        claims = entity.get_truthy_claims("P580")
        date_info = entity.extract_date_from_claims(claims)

        assert date_info is not None
        assert date_info["date"] == "1970-06-15"
        assert date_info["precision"] == 11

        # Test year precision
        entity_data["claims"]["P580"][0]["mainsnak"]["datavalue"]["value"][
            "precision"
        ] = 9
        entity = WikidataEntity(entity_data)

        claims = entity.get_truthy_claims("P580")
        date_info = entity.extract_date_from_claims(claims)

        assert date_info["date"] == "1970"
        assert date_info["precision"] == 9

    def test_entity_name_fallback(self):
        """Test entity name extraction with language fallback."""
        # English preferred
        entity_data = {
            "id": "Q137",
            "labels": {
                "en": {"value": "English Name"},
                "fr": {"value": "Nom Français"},
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.get_entity_name() == "English Name"

        # No English, fallback to any available
        entity_data = {
            "id": "Q138",
            "labels": {
                "fr": {"value": "Nom Français"},
                "de": {"value": "Deutscher Name"},
            },
        }
        entity = WikidataEntity(entity_data)
        name = entity.get_entity_name()
        assert name in ["Nom Français", "Deutscher Name"]  # Could be either

        # No labels
        entity_data = {"id": "Q139", "labels": {}}
        entity = WikidataEntity(entity_data)
        assert entity.get_entity_name() is None
