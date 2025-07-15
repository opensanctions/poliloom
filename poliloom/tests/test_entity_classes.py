"""Tests for the new entity class hierarchy."""

from poliloom.entities.politician import WikidataPolitician
from poliloom.entities.position import WikidataPosition
from poliloom.entities.location import WikidataLocation
from poliloom.entities.country import WikidataCountry
from poliloom.entities.factory import WikidataEntityFactory


class TestWikidataEntityBaseMethods:
    """Test the base WikidataEntity class methods using concrete subclasses."""

    def test_get_entity_name_english(self):
        """Test getting entity name in English."""
        entity_data = {
            "id": "Q123",
            "labels": {
                "en": {"language": "en", "value": "Test Entity"},
                "fr": {"language": "fr", "value": "Entité Test"},
            },
        }
        entity = WikidataCountry(entity_data)
        assert entity.get_entity_name() == "Test Entity"

    def test_get_entity_name_no_english(self):
        """Test getting entity name when no English label exists."""
        entity_data = {
            "id": "Q123",
            "labels": {
                "fr": {"language": "fr", "value": "Entité Test"},
                "de": {"language": "de", "value": "Test Entität"},
            },
        }
        entity = WikidataCountry(entity_data)
        # Should return the first available label
        assert entity.get_entity_name() == "Entité Test"

    def test_get_entity_name_no_labels(self):
        """Test getting entity name when no labels exist."""
        entity_data = {"id": "Q123"}
        entity = WikidataCountry(entity_data)
        assert entity.get_entity_name() is None

    def test_get_truthy_claims(self):
        """Test getting truthy claims with rank filtering."""
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
        entity = WikidataCountry(entity_data)
        claims = entity.get_truthy_claims("P31")

        # Should return only preferred rank when preferred exists
        assert len(claims) == 1
        assert claims[0]["rank"] == "preferred"

    def test_get_truthy_claims_empty(self):
        """Test getting truthy claims for non-existent property."""
        entity_data = {"id": "Q123"}
        entity = WikidataCountry(entity_data)
        claims = entity.get_truthy_claims("P31")
        assert claims == []

    def test_get_wikidata_id(self):
        """Test getting Wikidata ID."""
        entity_data = {"id": "Q123"}
        entity = WikidataCountry(entity_data)
        assert entity.get_wikidata_id() == "Q123"

    def test_get_instance_of_ids(self):
        """Test getting instance of IDs."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q1"}}},
                    },
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q2"}}},
                    },
                ]
            },
        }
        entity = WikidataCountry(entity_data)
        instance_ids = entity.get_instance_of_ids()
        assert instance_ids == {"Q1", "Q2"}

    def test_extract_date_from_claims(self):
        """Test extracting date from claims."""
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
        entity = WikidataCountry({"id": "Q123"})
        date = entity.extract_date_from_claims(claims)
        assert date == "1980-01-01"

    def test_extract_date_from_claims_partial(self):
        """Test extracting partial date from claims."""
        claims = [
            {
                "rank": "normal",
                "mainsnak": {
                    "datavalue": {
                        "type": "time",
                        "value": {"time": "+1980-00-00T00:00:00Z", "precision": 9},
                    }
                },
            }
        ]
        entity = WikidataCountry({"id": "Q123"})
        date = entity.extract_date_from_claims(claims)
        assert date == "1980"


class TestWikidataPolitician:
    """Test the WikidataPolitician class."""

    def test_is_politician_with_occupation(self):
        """Test identifying politician by occupation."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],  # human
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                    }
                ],  # politician
            },
        }
        assert WikidataPolitician.is_politician(entity_data) is True

    def test_is_politician_with_position(self):
        """Test identifying politician by position held."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],  # human
                "P39": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q30185"}}},
                    }
                ],  # position
            },
        }
        assert WikidataPolitician.is_politician(entity_data) is True

    def test_is_politician_not_human(self):
        """Test rejecting non-human entities."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q43229"}}},
                    }
                ],  # organization
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                    }
                ],  # politician
            },
        }
        assert WikidataPolitician.is_politician(entity_data) is False

    def test_is_politician_false(self):
        """Test rejecting non-politician entities."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],  # human
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q36834"}}},
                    }
                ],  # composer
            },
        }
        assert WikidataPolitician.is_politician(entity_data) is False

    def test_is_deceased_true(self):
        """Test detecting deceased politician."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {"value": {"time": "+2020-01-01T00:00:00Z"}}
                        },
                    }
                ]  # death date
            },
        }
        politician = WikidataPolitician(entity_data)
        assert politician.is_deceased is True

    def test_is_deceased_false(self):
        """Test detecting living politician."""
        entity_data = {"id": "Q123"}
        politician = WikidataPolitician(entity_data)
        assert politician.is_deceased is False

    def test_extract_birth_date(self):
        """Test extracting birth date."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P569": [
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
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        birth_date = politician.extract_birth_date()
        assert birth_date == "1980-01-01"

    def test_extract_citizenships(self):
        """Test extracting citizenships."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P27": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q30"}}},
                    },  # USA
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q16"}}},
                    },  # Canada
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        citizenships = politician.extract_citizenships()
        assert citizenships == ["Q30", "Q16"]

    def test_extract_wikipedia_links(self):
        """Test extracting Wikipedia links."""
        entity_data = {
            "id": "Q123",
            "sitelinks": {
                "enwiki": {"site": "enwiki", "title": "Test Person"},
                "frwiki": {"site": "frwiki", "title": "Test Personne"},
            },
        }
        politician = WikidataPolitician(entity_data)
        wikipedia_links = politician.extract_wikipedia_links()

        assert len(wikipedia_links) == 2
        assert wikipedia_links[0]["language"] == "en"
        assert wikipedia_links[0]["url"] == "https://en.wikipedia.org/wiki/Test_Person"
        assert wikipedia_links[1]["language"] == "fr"
        assert (
            wikipedia_links[1]["url"] == "https://fr.wikipedia.org/wiki/Test_Personne"
        )

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Politician"}},
            "claims": {
                "P569": [
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
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        data = politician.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Politician"
        assert data["is_deceased"] is False
        assert len(data["properties"]) == 1
        assert data["properties"][0]["type"] == "BirthDate"
        assert data["properties"][0]["value"] == "1980-01-01"

    def test_should_import_politician_alive(self):
        """Test importing living politician."""
        entity_data = {"id": "Q123"}
        politician = WikidataPolitician(entity_data)
        assert politician.should_import_politician() is True

    def test_should_import_politician_recently_deceased(self):
        """Test importing recently deceased politician (within 5 years)."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+2022-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        assert politician.should_import_politician() is True

    def test_should_import_politician_old_deceased(self):
        """Test excluding old deceased politician (more than 5 years ago)."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+2015-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        assert politician.should_import_politician() is False

    def test_should_import_politician_year_only_recent(self):
        """Test importing politician with year-only death date (recent)."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+2022-00-00T00:00:00Z",
                                    "precision": 9,
                                },
                            }
                        },
                    }
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        assert politician.should_import_politician() is True

    def test_should_import_politician_year_only_old(self):
        """Test excluding politician with year-only death date (old)."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+2015-00-00T00:00:00Z",
                                    "precision": 9,
                                },
                            }
                        },
                    }
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        assert politician.should_import_politician() is False

    def test_should_import_politician_deceased_no_date(self):
        """Test excluding deceased politician with no death date."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "somevalue",
                            }
                        },
                    }
                ]
            },
        }
        politician = WikidataPolitician(entity_data)
        assert politician.should_import_politician() is False


class TestWikidataPosition:
    """Test the WikidataPosition class."""

    def test_is_position_true(self):
        """Test identifying position entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q294414"}}},
                    }
                ]  # public office
            },
        }
        position_descendants = {"Q294414", "Q30185"}
        assert WikidataPosition.is_position(entity_data, position_descendants) is True

    def test_is_position_false(self):
        """Test rejecting non-position entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ]  # human
            },
        }
        position_descendants = {"Q294414", "Q30185"}
        assert WikidataPosition.is_position(entity_data, position_descendants) is False

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Position"}},
        }
        position = WikidataPosition(entity_data)
        data = position.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Position"
        # The actual implementation doesn't include embedding field in to_database_dict


class TestWikidataLocation:
    """Test the WikidataLocation class."""

    def test_is_location_true(self):
        """Test identifying location entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q515"}}},
                    }
                ]  # city
            },
        }
        location_descendants = {"Q515", "Q6256"}
        assert WikidataLocation.is_location(entity_data, location_descendants) is True

    def test_is_location_false(self):
        """Test rejecting non-location entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ]  # human
            },
        }
        location_descendants = {"Q515", "Q6256"}
        assert WikidataLocation.is_location(entity_data, location_descendants) is False

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Location"}},
        }
        location = WikidataLocation(entity_data)
        data = location.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Location"
        # The actual implementation doesn't include embedding field in to_database_dict


class TestWikidataCountry:
    """Test the WikidataCountry class."""

    def test_is_country_true(self):
        """Test identifying country entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q6256"}}},
                    }
                ]  # country
            },
        }
        assert WikidataCountry.is_country(entity_data) is True

    def test_is_country_sovereign_state(self):
        """Test identifying sovereign state as country."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q3624078"}}},
                    }
                ]  # sovereign state
            },
        }
        assert WikidataCountry.is_country(entity_data) is True

    def test_is_country_false(self):
        """Test rejecting non-country entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ]  # human
            },
        }
        assert WikidataCountry.is_country(entity_data) is False

    def test_extract_iso_code(self):
        """Test extracting ISO code."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P297": [
                    {"rank": "normal", "mainsnak": {"datavalue": {"value": "US"}}}
                ]  # ISO code
            },
        }
        country = WikidataCountry(entity_data)
        iso_code = country.extract_iso_code()
        assert iso_code == "US"

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Country"}},
            "claims": {
                "P297": [
                    {"rank": "normal", "mainsnak": {"datavalue": {"value": "TC"}}}
                ]  # ISO code
            },
        }
        country = WikidataCountry(entity_data)
        data = country.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Country"
        assert data["iso_code"] == "TC"


class TestWikidataEntityFactory:
    """Test the WikidataEntityFactory class."""

    def test_create_politician_entity(self):
        """Test creating politician entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],  # human
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                    }
                ],  # politician
            },
        }

        entity = WikidataEntityFactory.create_entity(entity_data)
        assert isinstance(entity, WikidataPolitician)

    def test_create_position_entity(self):
        """Test creating position entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q294414"}}},
                    }
                ]  # public office
            },
        }
        position_descendants = {"Q294414", "Q30185"}

        entity = WikidataEntityFactory.create_entity(
            entity_data, position_descendants, set()
        )
        assert isinstance(entity, WikidataPosition)

    def test_create_location_entity(self):
        """Test creating location entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q515"}}},
                    }
                ]  # city
            },
        }
        location_descendants = {"Q515", "Q6256"}

        entity = WikidataEntityFactory.create_entity(
            entity_data, set(), location_descendants
        )
        assert isinstance(entity, WikidataLocation)

    def test_create_country_entity(self):
        """Test creating country entity."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q6256"}}},
                    }
                ]  # country
            },
        }

        entity = WikidataEntityFactory.create_entity(entity_data)
        assert isinstance(entity, WikidataCountry)

    def test_create_entity_none_for_unknown(self):
        """Test returning None for unknown entity types."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q12345"}}},
                    }
                ]  # unknown type
            },
        }

        entity = WikidataEntityFactory.create_entity(entity_data)
        assert entity is None

    def test_create_entity_with_allowed_types(self):
        """Test creating entity with allowed types filter."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],  # human
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                    }
                ],  # politician
            },
        }

        # Only allow positions, should return None for politician
        entity = WikidataEntityFactory.create_entity(
            entity_data, set(), set(), allowed_types=["position"]
        )
        assert entity is None

        # Allow politicians, should return politician
        entity = WikidataEntityFactory.create_entity(
            entity_data, set(), set(), allowed_types=["politician"]
        )
        assert isinstance(entity, WikidataPolitician)

    def test_create_entity_malformed_data(self):
        """Test handling malformed entity data."""
        # Missing ID
        entity_data = {}
        entity = WikidataEntityFactory.create_entity(entity_data)
        assert entity is None

        # Empty data
        entity_data = {"id": "Q123"}
        entity = WikidataEntityFactory.create_entity(entity_data)
        assert entity is None

    def test_create_politician_entity_filtered_by_death_date(self):
        """Test that old deceased politicians are filtered out by factory."""
        entity_data = {
            "id": "Q123",
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q5"}}},
                    }
                ],  # human
                "P106": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q82955"}}},
                    }
                ],  # politician
                "P570": [
                    {
                        "rank": "normal",
                        "mainsnak": {
                            "datavalue": {
                                "type": "time",
                                "value": {
                                    "time": "+2015-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ],  # death date more than 5 years ago
            },
        }

        # Should return None because politician died more than 5 years ago
        entity = WikidataEntityFactory.create_entity(entity_data)
        assert entity is None
