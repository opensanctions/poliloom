"""Tests for wikidata_statement module functionality."""

from poliloom.wikidata_statement import _convert_qualifiers_to_rest_api


class TestConvertQualifiersToRestApi:
    """Test qualifiers format conversion from Action API to REST API."""

    def test_time_qualifiers(self):
        """Test conversion of time qualifiers (P580, P582)."""
        action_format = {
            "P580": [
                {
                    "hash": "b2ac2678b4dc96ac36ce5ff2db5c9a0d6aa2144e",
                    "datatype": "time",
                    "property": "P580",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2017-05-21T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
            "P582": [
                {
                    "hash": "947c3a6e8d560fb5b357b778369e5f4e1e1a6a78",
                    "datatype": "time",
                    "property": "P582",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2019-02-04T00:00:00Z",
                            "after": 0,
                            "before": 0,
                            "timezone": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P580"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2017-05-21T00:00:00Z",
                        "after": 0,
                        "before": 0,
                        "timezone": 0,
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            },
            {
                "property": {"id": "P582"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2019-02-04T00:00:00Z",
                        "after": 0,
                        "before": 0,
                        "timezone": 0,
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            },
        ]

        assert result == expected

    def test_wikibase_item_qualifiers(self):
        """Test conversion of wikibase-item qualifiers (P1365, P1366)."""
        action_format = {
            "P1365": [
                {
                    "hash": "3df8181e4ff20601e6234c3ffa71eac73b2e2a3b",
                    "datatype": "wikibase-item",
                    "property": "P1365",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "wikibase-entityid",
                        "value": {
                            "id": "Q65423352",
                            "numeric-id": 65423352,
                            "entity-type": "item",
                        },
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P1365"},
                "value": {"type": "value", "content": "Q65423352"},
            }
        ]

        assert result == expected

    def test_string_qualifiers(self):
        """Test conversion of string qualifiers (P1545)."""
        action_format = {
            "P1545": [
                {
                    "hash": "cbff8d4b3b7b35f905ef3147a7a6cb88845a774f",
                    "datatype": "string",
                    "property": "P1545",
                    "snaktype": "value",
                    "datavalue": {"type": "string", "value": "4"},
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {"property": {"id": "P1545"}, "value": {"type": "value", "content": "4"}}
        ]

        assert result == expected

    def test_somevalue_qualifiers(self):
        """Test conversion of somevalue qualifiers."""
        action_format = {
            "P580": [
                {
                    "hash": "abc123",
                    "datatype": "time",
                    "property": "P580",
                    "snaktype": "somevalue",
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [{"property": {"id": "P580"}, "value": {"type": "somevalue"}}]

        assert result == expected

    def test_novalue_qualifiers(self):
        """Test conversion of novalue qualifiers."""
        action_format = {
            "P582": [
                {
                    "hash": "def456",
                    "datatype": "time",
                    "property": "P582",
                    "snaktype": "novalue",
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [{"property": {"id": "P582"}, "value": {"type": "novalue"}}]

        assert result == expected

    def test_mixed_qualifiers(self):
        """Test conversion with multiple qualifier types."""
        action_format = {
            "P580": [
                {
                    "datatype": "time",
                    "property": "P580",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "time",
                        "value": {
                            "time": "+2017-05-21T00:00:00Z",
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            ],
            "P1545": [
                {
                    "datatype": "string",
                    "property": "P1545",
                    "snaktype": "value",
                    "datavalue": {"type": "string", "value": "4"},
                }
            ],
            "P1365": [
                {
                    "datatype": "wikibase-item",
                    "property": "P1365",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "wikibase-entityid",
                        "value": {
                            "id": "Q65423352",
                            "numeric-id": 65423352,
                            "entity-type": "item",
                        },
                    },
                }
            ],
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        # Should have 3 qualifiers
        assert len(result) == 3

        # Check each qualifier exists with correct structure
        property_ids = [q["property"]["id"] for q in result]
        assert "P580" in property_ids
        assert "P1545" in property_ids
        assert "P1365" in property_ids

    def test_quantity_qualifiers(self):
        """Test conversion of quantity qualifiers (P1111)."""
        action_format = {
            "P1111": [
                {
                    "hash": "d0a0f2fb6654bb991907f65ddfc979a1e3fddcfa",
                    "datatype": "quantity",
                    "property": "P1111",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "quantity",
                        "value": {"unit": "1", "amount": "+314963"},
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P1111"},
                "value": {
                    "type": "value",
                    "content": {"unit": "1", "amount": "+314963"},
                },
            }
        ]

        assert result == expected

    def test_external_id_qualifiers(self):
        """Test conversion of external-id qualifiers (P5002)."""
        action_format = {
            "P5002": [
                {
                    "hash": "0e4c138c94b5ccb299139e088b0878d2a4aaa6d4",
                    "datatype": "external-id",
                    "property": "P5002",
                    "snaktype": "value",
                    "datavalue": {"type": "string", "value": "199887"},
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P5002"},
                "value": {"type": "value", "content": "199887"},
            }
        ]

        assert result == expected

    def test_monolingualtext_qualifiers(self):
        """Test conversion of monolingualtext qualifiers (P6375)."""
        action_format = {
            "P6375": [
                {
                    "hash": "e702ce63a07977d232d6114b33d7b734f4079121",
                    "datatype": "monolingualtext",
                    "property": "P6375",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "monolingualtext",
                        "value": {"text": "Rubanda", "language": "en"},
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P6375"},
                "value": {
                    "type": "value",
                    "content": {"text": "Rubanda", "language": "en"},
                },
            }
        ]

        assert result == expected

    def test_commonsmedia_qualifiers(self):
        """Test conversion of commonsMedia qualifiers (P94)."""
        action_format = {
            "P94": [
                {
                    "hash": "2c4e3b501fc36d5c0b5bd304bcc759f9931ccace",
                    "datatype": "commonsMedia",
                    "property": "P94",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "string",
                        "value": "Escudo del Senado de España.svg",
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P94"},
                "value": {
                    "type": "value",
                    "content": "Escudo del Senado de España.svg",
                },
            }
        ]

        assert result == expected

    def test_url_qualifiers(self):
        """Test conversion of url qualifiers (P1065)."""
        action_format = {
            "P1065": [
                {
                    "hash": "77bd2ff4068349bc6a71b1cbcbad23ec01aa15df",
                    "datatype": "url",
                    "property": "P1065",
                    "snaktype": "value",
                    "datavalue": {
                        "type": "string",
                        "value": "https://www.elconfidencial.com/empresas/2022-04-11/planeta-relevo-silvio-gonzalez-consejero-atresmedia_3405523/",
                    },
                }
            ]
        }

        result = _convert_qualifiers_to_rest_api(action_format)

        expected = [
            {
                "property": {"id": "P1065"},
                "value": {
                    "type": "value",
                    "content": "https://www.elconfidencial.com/empresas/2022-04-11/planeta-relevo-silvio-gonzalez-consejero-atresmedia_3405523/",
                },
            }
        ]

        assert result == expected

    def test_empty_qualifiers(self):
        """Test conversion of empty qualifiers."""
        action_format = {}
        result = _convert_qualifiers_to_rest_api(action_format)
        assert result == []
