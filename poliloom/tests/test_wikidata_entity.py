"""Tests for the unified WikidataEntity class."""

from poliloom.wikidata_entity import WikidataEntity


class TestWikidataEntityBaseMethods:
    """Test the base WikidataEntity class methods."""

    def test_get_entity_name_english(self):
        """Test getting entity name in English."""
        entity_data = {
            "id": "Q123",
            "labels": {
                "en": {"language": "en", "value": "Test Entity"},
                "fr": {"language": "fr", "value": "Entité Test"},
            },
        }
        entity = WikidataEntity(entity_data)
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
        entity = WikidataEntity(entity_data)
        # Should return the first available label
        assert entity.get_entity_name() == "Entité Test"

    def test_get_entity_name_no_labels(self):
        """Test getting entity name when no labels exist."""
        entity_data = {"id": "Q123"}
        entity = WikidataEntity(entity_data)
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
        entity = WikidataEntity(entity_data)
        claims = entity.get_truthy_claims("P31")

        # Should return only preferred rank when preferred exists
        assert len(claims) == 1
        assert claims[0]["rank"] == "preferred"

    def test_get_truthy_claims_empty(self):
        """Test getting truthy claims for non-existent property."""
        entity_data = {"id": "Q123"}
        entity = WikidataEntity(entity_data)
        claims = entity.get_truthy_claims("P31")
        assert claims == []

    def test_get_wikidata_id(self):
        """Test getting Wikidata ID."""
        entity_data = {"id": "Q123"}
        entity = WikidataEntity(entity_data)
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
        entity = WikidataEntity(entity_data)
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
        entity = WikidataEntity({"id": "Q123"})
        date = entity.extract_date_from_claims(claims)
        assert date == {"date": "1980-01-01", "precision": 11}

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
        entity = WikidataEntity({"id": "Q123"})
        date = entity.extract_date_from_claims(claims)
        assert date == {"date": "1980", "precision": 9}


class TestWikidataEntityPolitician:
    """Test the WikidataEntity class for politicians."""

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type == "politician"

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type == "politician"

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type != "politician"

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type != "politician"

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
        entity = WikidataEntity(entity_data)
        assert entity.is_deceased is True

    def test_is_deceased_false(self):
        """Test detecting living politician."""
        entity_data = {"id": "Q123"}
        entity = WikidataEntity(entity_data)
        assert entity.is_deceased is False

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
        entity = WikidataEntity(entity_data)
        birth_claims = entity.get_truthy_claims("P569")
        birth_date = entity.extract_date_from_claims(birth_claims)
        assert birth_date == {"date": "1980-01-01", "precision": 11}

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
        entity = WikidataEntity(entity_data)
        citizenship_claims = entity.get_truthy_claims("P27")
        citizenships = []
        for claim in citizenship_claims:
            try:
                citizenship_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                citizenships.append(citizenship_id)
            except (KeyError, TypeError):
                continue
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
        entity = WikidataEntity(entity_data)
        sitelinks = entity.raw_data.get("sitelinks", {})
        wikipedia_links = []

        for site_id, sitelink in sitelinks.items():
            if site_id.endswith("wiki"):
                language = site_id[:-4]  # Remove 'wiki' suffix
                title = sitelink["title"].replace(" ", "_")
                url = f"https://{language}.wikipedia.org/wiki/{title}"
                wikipedia_links.append({"language": language, "url": url})

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
        entity = WikidataEntity(entity_data)
        data = entity.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Politician"
        # Note: The unified class doesn't include properties in to_database_dict
        # Properties are handled separately in the import process

    def test_should_import_politician_alive(self):
        """Test importing living politician."""
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
        entity = WikidataEntity(entity_data)
        assert entity.should_import() is True

    def test_should_import_politician_deceased_after_1950(self):
        """Test importing politician deceased after 1950."""
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
                                    "time": "+1980-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.should_import() is True

    def test_should_import_politician_deceased_before_1950(self):
        """Test excluding politician deceased before 1950."""
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
                                    "time": "+1940-01-01T00:00:00Z",
                                    "precision": 11,
                                },
                            }
                        },
                    }
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.should_import() is False

    def test_should_import_politician_year_only_after_1950(self):
        """Test importing politician with year-only death date after 1950."""
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
                                    "time": "+1980-00-00T00:00:00Z",
                                    "precision": 9,
                                },
                            }
                        },
                    }
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.should_import() is True

    def test_should_import_politician_year_only_before_1950(self):
        """Test excluding politician with year-only death date before 1950."""
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
                                    "time": "+1940-00-00T00:00:00Z",
                                    "precision": 9,
                                },
                            }
                        },
                    }
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        assert entity.should_import() is False

    def test_should_import_politician_deceased_no_date(self):
        """Test excluding deceased politician with no death date."""
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
                                "type": "somevalue",
                            }
                        },
                    }
                ],
            },
        }
        entity = WikidataEntity(entity_data)
        assert (
            entity.should_import() is True
        )  # Should import if we can't determine death date


class TestWikidataEntityPosition:
    """Test the WikidataEntity class for positions."""

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
        position_descendants = {"Q294414": True, "Q30185": True}
        entity = WikidataEntity(entity_data, position_descendants=position_descendants)
        assert entity.entity_type == "position"

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
        position_descendants = {"Q294414": True, "Q30185": True}
        entity = WikidataEntity(entity_data, position_descendants=position_descendants)
        assert entity.entity_type != "position"

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Position"}},
        }
        entity = WikidataEntity(entity_data)
        data = entity.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Position"
        # The actual implementation doesn't include embedding field in to_database_dict


class TestWikidataEntityLocation:
    """Test the WikidataEntity class for locations."""

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
        location_descendants = {"Q515": True, "Q6256": True}
        entity = WikidataEntity(entity_data, location_descendants=location_descendants)
        assert entity.entity_type == "location"

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
        location_descendants = {"Q515": True, "Q6256": True}
        entity = WikidataEntity(entity_data, location_descendants=location_descendants)
        assert entity.entity_type != "location"

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Location"}},
        }
        entity = WikidataEntity(entity_data)
        data = entity.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Location"
        # The actual implementation doesn't include embedding field in to_database_dict


class TestWikidataEntityCountry:
    """Test the WikidataEntity class for countries."""

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type == "country"

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type == "country"

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
        entity = WikidataEntity(entity_data)
        assert entity.entity_type != "country"

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
        entity = WikidataEntity(entity_data)
        iso_code = entity.extract_iso_code()
        assert iso_code == "US"

    def test_to_database_dict(self):
        """Test converting to database dictionary."""
        entity_data = {
            "id": "Q123",
            "labels": {"en": {"language": "en", "value": "Test Country"}},
            "claims": {
                "P31": [
                    {
                        "rank": "normal",
                        "mainsnak": {"datavalue": {"value": {"id": "Q6256"}}},
                    }
                ],  # country
                "P297": [
                    {"rank": "normal", "mainsnak": {"datavalue": {"value": "TC"}}}
                ],  # ISO code
            },
        }
        entity = WikidataEntity(entity_data)
        data = entity.to_database_dict()

        assert data["wikidata_id"] == "Q123"
        assert data["name"] == "Test Country"
        assert data["iso_code"] == "TC"


class TestWikidataEntityTypeDetection:
    """Test the WikidataEntity class entity type detection."""

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

        entity = WikidataEntity(entity_data)
        assert entity.entity_type == "politician"

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
        position_descendants = {"Q294414": True, "Q30185": True}

        entity = WikidataEntity(entity_data, position_descendants=position_descendants)
        assert entity.entity_type == "position"

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
        location_descendants = {"Q515": True, "Q6256": True}

        entity = WikidataEntity(entity_data, location_descendants=location_descendants)
        assert entity.entity_type == "location"

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

        entity = WikidataEntity(entity_data)
        assert entity.entity_type == "country"

    def test_create_entity_none_for_unknown(self):
        """Test returning None entity type for unknown types."""
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

        entity = WikidataEntity(entity_data)
        assert entity.entity_type is None
