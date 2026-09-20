"""Tests for Action API to REST API statement conversion."""

from poliloom.wikidata.rest import action_api_statement_to_rest


def _minimal_claim(mainsnak: dict) -> dict:
    return {
        "id": "Q42$00000000-0000-0000-0000-000000000000",
        "rank": "normal",
        "mainsnak": mainsnak,
    }


def _p39_claim() -> dict:
    """Full P39 claim in Action API shape, as found in the dump."""
    return {
        "id": "Q42$7b80d2d0-4cc1-8d1e-1a1f-2f3f4f5f6f7f",
        "type": "statement",
        "mainsnak": {
            "snaktype": "value",
            "property": "P39",
            "datatype": "wikibase-item",
            "datavalue": {
                "value": {
                    "entity-type": "item",
                    "numeric-id": 11696,
                    "id": "Q11696",
                },
                "type": "wikibase-entityid",
            },
            "hash": "1" * 40,
        },
        "rank": "normal",
        "qualifiers": {
            "P580": [
                {
                    "snaktype": "value",
                    "property": "P580",
                    "datatype": "time",
                    "datavalue": {
                        "value": {
                            "time": "+2020-01-01T00:00:00Z",
                            "timezone": 0,
                            "before": 0,
                            "after": 0,
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                        "type": "time",
                    },
                    "hash": "2" * 40,
                }
            ],
            "P582": [
                {
                    "snaktype": "value",
                    "property": "P582",
                    "datatype": "time",
                    "datavalue": {
                        "value": {
                            "time": "+2021-06-30T00:00:00Z",
                            "timezone": 0,
                            "before": 0,
                            "after": 0,
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                        "type": "time",
                    },
                    "hash": "3" * 40,
                }
            ],
        },
        "qualifiers-order": ["P580", "P582"],
        "references": [
            {
                "hash": "4" * 40,
                "snaks": {
                    "P854": [
                        {
                            "snaktype": "value",
                            "property": "P854",
                            "datatype": "url",
                            "datavalue": {
                                "value": "https://example.org/source",
                                "type": "string",
                            },
                            "hash": "5" * 40,
                        }
                    ],
                    "P813": [
                        {
                            "snaktype": "value",
                            "property": "P813",
                            "datatype": "time",
                            "datavalue": {
                                "value": {
                                    "time": "+2022-03-04T00:00:00Z",
                                    "timezone": 0,
                                    "before": 0,
                                    "after": 0,
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                                "type": "time",
                            },
                            "hash": "6" * 40,
                        }
                    ],
                },
                "snaks-order": ["P854", "P813"],
            }
        ],
    }


class TestFullClaimRoundTrip:
    def test_p39_claim_converts_to_rest_shape(self):
        result = action_api_statement_to_rest(_p39_claim())

        assert result == {
            "id": "Q42$7b80d2d0-4cc1-8d1e-1a1f-2f3f4f5f6f7f",
            "rank": "normal",
            "property": {"id": "P39", "data_type": "wikibase-item"},
            "value": {"type": "value", "content": "Q11696"},
            "qualifiers": [
                {
                    "property": {"id": "P580", "data_type": "time"},
                    "value": {
                        "type": "value",
                        "content": {
                            "time": "+2020-01-01T00:00:00Z",
                            "precision": 9,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                },
                {
                    "property": {"id": "P582", "data_type": "time"},
                    "value": {
                        "type": "value",
                        "content": {
                            "time": "+2021-06-30T00:00:00Z",
                            "precision": 11,
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                },
            ],
            "references": [
                {
                    "hash": "4" * 40,
                    "parts": [
                        {
                            "property": {"id": "P854", "data_type": "url"},
                            "value": {
                                "type": "value",
                                "content": "https://example.org/source",
                            },
                        },
                        {
                            "property": {"id": "P813", "data_type": "time"},
                            "value": {
                                "type": "value",
                                "content": {
                                    "time": "+2022-03-04T00:00:00Z",
                                    "precision": 11,
                                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                                },
                            },
                        },
                    ],
                }
            ],
        }


class TestValueConversion:
    def test_entityid_value_becomes_id_string(self):
        claim = _minimal_claim(
            {
                "snaktype": "value",
                "property": "P39",
                "datatype": "wikibase-item",
                "datavalue": {
                    "value": {
                        "entity-type": "item",
                        "numeric-id": 11696,
                        "id": "Q11696",
                    },
                    "type": "wikibase-entityid",
                },
            }
        )

        assert action_api_statement_to_rest(claim)["value"] == {
            "type": "value",
            "content": "Q11696",
        }

    def test_time_value_drops_before_after_timezone(self):
        claim = _minimal_claim(
            {
                "snaktype": "value",
                "property": "P569",
                "datatype": "time",
                "datavalue": {
                    "value": {
                        "time": "+1942-01-08T00:00:00Z",
                        "timezone": 1,
                        "before": 5,
                        "after": 5,
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                    "type": "time",
                },
            }
        )

        assert action_api_statement_to_rest(claim)["value"] == {
            "type": "value",
            "content": {
                "time": "+1942-01-08T00:00:00Z",
                "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
            },
        }

    def test_globecoordinate_value_drops_altitude(self):
        claim = _minimal_claim(
            {
                "snaktype": "value",
                "property": "P625",
                "datatype": "globe-coordinate",
                "datavalue": {
                    "value": {
                        "latitude": 51.9187,
                        "longitude": 4.4755,
                        "precision": 0.0001,
                        "globe": "http://www.wikidata.org/entity/Q2",
                        "altitude": 12.5,
                    },
                    "type": "globecoordinate",
                },
            }
        )

        assert action_api_statement_to_rest(claim)["value"] == {
            "type": "value",
            "content": {
                "latitude": 51.9187,
                "longitude": 4.4755,
                "precision": 0.0001,
                "globe": "http://www.wikidata.org/entity/Q2",
            },
        }

    def test_quantity_and_monolingualtext_pass_through_unchanged(self):
        quantity_claim = _minimal_claim(
            {
                "snaktype": "value",
                "property": "P1111",
                "datatype": "quantity",
                "datavalue": {
                    "value": {"amount": "+314963", "unit": "1"},
                    "type": "quantity",
                },
            }
        )
        assert action_api_statement_to_rest(quantity_claim)["value"] == {
            "type": "value",
            "content": {"amount": "+314963", "unit": "1"},
        }

        monolingualtext_claim = _minimal_claim(
            {
                "snaktype": "value",
                "property": "P6375",
                "datatype": "monolingualtext",
                "datavalue": {
                    "value": {"text": "Rubanda", "language": "en"},
                    "type": "monolingualtext",
                },
            }
        )
        assert action_api_statement_to_rest(monolingualtext_claim)["value"] == {
            "type": "value",
            "content": {"text": "Rubanda", "language": "en"},
        }

    def test_somevalue_omits_content(self):
        claim = _minimal_claim(
            {"snaktype": "somevalue", "property": "P39", "datatype": "wikibase-item"}
        )

        result = action_api_statement_to_rest(claim)

        assert result["value"] == {"type": "somevalue"}

    def test_novalue_omits_content(self):
        claim = _minimal_claim(
            {"snaktype": "novalue", "property": "P582", "datatype": "time"}
        )

        result = action_api_statement_to_rest(claim)

        assert result["value"] == {"type": "novalue"}

    def test_claim_without_qualifiers_or_references_omits_keys(self):
        claim = _minimal_claim(
            {
                "snaktype": "value",
                "property": "P39",
                "datatype": "wikibase-item",
                "datavalue": {
                    "value": {
                        "entity-type": "item",
                        "numeric-id": 11696,
                        "id": "Q11696",
                    },
                    "type": "wikibase-entityid",
                },
            }
        )

        result = action_api_statement_to_rest(claim)

        assert "qualifiers" not in result
        assert "references" not in result

    def test_only_reference_hash_is_retained(self):
        result = action_api_statement_to_rest(_p39_claim())

        assert _hashes(result) == {"4" * 40}


def _hashes(node) -> set:
    """Collect every value under a "hash" key in a nested structure."""
    if isinstance(node, dict):
        found = set()
        for key, value in node.items():
            if key == "hash":
                found.add(value)
            found |= _hashes(value)
        return found
    if isinstance(node, list):
        found = set()
        for item in node:
            found |= _hashes(item)
        return found
    return set()


class TestOrdering:
    def test_qualifiers_order_overrides_insertion_order(self):
        claim = _p39_claim()
        # Insertion order differs from qualifiers-order.
        claim["qualifiers"] = {
            "P582": claim["qualifiers"]["P582"],
            "P580": claim["qualifiers"]["P580"],
        }
        claim["qualifiers-order"] = ["P580", "P582"]

        result = action_api_statement_to_rest(claim)

        assert [q["property"]["id"] for q in result["qualifiers"]] == ["P580", "P582"]

    def test_insertion_order_used_without_qualifiers_order(self):
        claim = _p39_claim()
        # Insertion order differs from what qualifiers-order would say.
        claim["qualifiers"] = {
            "P582": claim["qualifiers"]["P582"],
            "P580": claim["qualifiers"]["P580"],
        }
        del claim["qualifiers-order"]

        result = action_api_statement_to_rest(claim)

        assert [q["property"]["id"] for q in result["qualifiers"]] == ["P582", "P580"]

    def test_snaks_within_one_property_keep_list_order(self):
        claim = _p39_claim()
        claim["qualifiers"]["P580"].append(
            {
                "snaktype": "value",
                "property": "P580",
                "datatype": "time",
                "datavalue": {
                    "value": {
                        "time": "+2015-01-01T00:00:00Z",
                        "timezone": 0,
                        "before": 0,
                        "after": 0,
                        "precision": 9,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                    "type": "time",
                },
                "hash": "7" * 40,
            }
        )

        result = action_api_statement_to_rest(claim)

        p580_times = [
            q["value"]["content"]["time"]
            for q in result["qualifiers"]
            if q["property"]["id"] == "P580"
        ]
        assert p580_times == ["+2020-01-01T00:00:00Z", "+2015-01-01T00:00:00Z"]

    def test_reference_snaks_order_overrides_insertion_order(self):
        claim = _p39_claim()
        # Insertion order differs from snaks-order.
        claim["references"][0]["snaks"] = {
            "P813": claim["references"][0]["snaks"]["P813"],
            "P854": claim["references"][0]["snaks"]["P854"],
        }
        claim["references"][0]["snaks-order"] = ["P854", "P813"]

        result = action_api_statement_to_rest(claim)

        part_ids = [p["property"]["id"] for p in result["references"][0]["parts"]]
        assert part_ids == ["P854", "P813"]

    def test_reference_insertion_order_used_without_snaks_order(self):
        claim = _p39_claim()
        claim["references"][0]["snaks"] = {
            "P813": claim["references"][0]["snaks"]["P813"],
            "P854": claim["references"][0]["snaks"]["P854"],
        }
        del claim["references"][0]["snaks-order"]

        result = action_api_statement_to_rest(claim)

        part_ids = [p["property"]["id"] for p in result["references"][0]["parts"]]
        assert part_ids == ["P813", "P854"]
