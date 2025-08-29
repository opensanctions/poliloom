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
