"""Tests for the WikidataEntityProcessor class."""

from poliloom.wikidata_entity_processor import WikidataEntityProcessor


class TestWikidataEntityProcessor:
    """Core tests for WikidataEntityProcessor functionality."""

    def test_basic_entity_creation(self):
        """Test creating a basic WikidataEntityProcessor."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"value": "Test Entity"}},
            "claims": {},
        }
        entity = WikidataEntityProcessor(entity_data)

        assert entity.get_wikidata_id() == "Q123"
        assert entity.get_entity_name() == "Test Entity"

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
        entity = WikidataEntityProcessor(entity_data)

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
        entity = WikidataEntityProcessor(entity_data)
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
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P580")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info is not None
        assert date_info.date == "1970-06-15"
        assert date_info.precision == 11
        assert not date_info.is_bce

        # Test year precision
        entity_data["claims"]["P580"][0]["mainsnak"]["datavalue"]["value"][
            "precision"
        ] = 9
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P580")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info.date == "1970"
        assert date_info.precision == 9

    def test_bce_date_extraction(self):
        """Test BCE date extraction (negative years)."""
        entity_data = {
            "id": "Q859",  # Plato
            "claims": {
                "P570": [  # death date
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "-0347-00-00T00:00:00Z",  # 347 BCE
                                    "precision": 9,  # year precision
                                },
                            }
                        },
                    }
                ]
            },
        }
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P570")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info is not None
        assert date_info.date == "0347"  # The negative sign is stripped
        assert date_info.precision == 9
        assert date_info.is_bce

        # Test BCE date with day precision
        entity_data["claims"]["P570"][0]["mainsnak"]["datavalue"]["value"] = {
            "time": "-0322-10-07T00:00:00Z",  # Aristotle's death date
            "precision": 11,  # day precision
        }
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P570")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info is not None
        assert date_info.date == "0322-10-07"
        assert date_info.precision == 11
        assert date_info.is_bce

        # Test BCE date with decade precision (precision 8)
        entity_data["claims"]["P570"][0]["mainsnak"]["datavalue"]["value"] = {
            "time": "-0348-00-00T00:00:00Z",  # Plato's preferred death date
            "precision": 8,  # decade precision
        }
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P570")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info is not None
        assert date_info.date == "0348"  # Should parse decade as year
        assert date_info.precision == 8
        assert date_info.is_bce

        # Test BCE date with century precision (precision 7)
        entity_data["claims"]["P570"][0]["mainsnak"]["datavalue"]["value"] = {
            "time": "-0400-00-00T00:00:00Z",  # 5th century BCE
            "precision": 7,  # century precision
        }
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P570")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info is not None
        assert date_info.date == "0400"  # Should parse century as year
        assert date_info.precision == 7
        assert date_info.is_bce

        # Test BCE date with millennium precision (precision 6)
        entity_data["claims"]["P570"][0]["mainsnak"]["datavalue"]["value"] = {
            "time": "-1000-00-00T00:00:00Z",  # 2nd millennium BCE
            "precision": 6,  # millennium precision
        }
        entity = WikidataEntityProcessor(entity_data)

        claims = entity.get_truthy_claims("P570")
        date_info = entity.extract_date_from_claim(claims[0])

        assert date_info is not None
        assert date_info.date == "1000"  # Should parse millennium as year
        assert date_info.precision == 6
        assert date_info.is_bce

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
        entity = WikidataEntityProcessor(entity_data)
        assert entity.get_entity_name() == "English Name"

        # No English, fallback to any available
        entity_data = {
            "id": "Q138",
            "labels": {
                "fr": {"value": "Nom Français"},
                "de": {"value": "Deutscher Name"},
            },
        }
        entity = WikidataEntityProcessor(entity_data)
        name = entity.get_entity_name()
        assert name in ["Nom Français", "Deutscher Name"]  # Could be either

        # No labels
        entity_data = {"id": "Q139", "labels": {}}
        entity = WikidataEntityProcessor(entity_data)
        assert entity.get_entity_name() is None
