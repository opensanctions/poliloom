"""Tests for reading canonical Wikibase REST API statement documents."""

from poliloom.wikidata.date import WikidataDate
from poliloom.wikidata.document import (
    find_qualifiers,
    qualifier_time_value,
    statement_entity_id,
    statement_property_id,
    statement_time_value,
)


def entity_statement() -> dict:
    """A wikibase-item valued statement (position held) with qualifiers."""
    return {
        "id": "Q42$8c1a1f90-4d1f-1a67-8d3f-3a1a9b8e21aa",
        "rank": "normal",
        "property": {"id": "P39", "data_type": "wikibase-item"},
        "value": {"type": "value", "content": "Q123"},
        "qualifiers": [
            {
                "property": {"id": "P580", "data_type": "time"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2020-01-01T00:00:00Z",
                        "precision": 11,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            },
            {
                "property": {"id": "P1365", "data_type": "wikibase-item"},
                "value": {"type": "value", "content": "Q777"},
            },
        ],
        "references": [
            {
                "hash": "85cc2508c0893d4ba7e91c8605b0f67d0e6a41b7",
                "parts": [
                    {
                        "property": {"id": "P854", "data_type": "url"},
                        "value": {
                            "type": "value",
                            "content": "https://example.org/source",
                        },
                    }
                ],
            }
        ],
    }


def time_statement() -> dict:
    """A time valued statement (date of birth)."""
    return {
        "id": "Q42$6d59fbb2-4d0f-43a4-a2f6-93f7b0d90e11",
        "rank": "normal",
        "property": {"id": "P569", "data_type": "time"},
        "value": {
            "type": "value",
            "content": {
                "time": "+1946-06-14T00:00:00Z",
                "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
            },
        },
    }


def somevalue_statement() -> dict:
    """A statement with an unknown value."""
    return {
        "id": "Q42$ab12cd34-4d0f-43a4-a2f6-93f7b0d90e11",
        "rank": "normal",
        "property": {"id": "P39", "data_type": "wikibase-item"},
        "value": {"type": "somevalue"},
    }


def novalue_statement() -> dict:
    """A statement with no value."""
    return {
        "id": "Q42$ef56ab78-4d0f-43a4-a2f6-93f7b0d90e11",
        "rank": "normal",
        "property": {"id": "P39", "data_type": "wikibase-item"},
        "value": {"type": "novalue"},
    }


class TestStatementPropertyId:
    """Test reading the property ID."""

    def test_entity_valued_statement(self):
        """A wikibase-item statement has a property ID."""
        assert statement_property_id(entity_statement()) == "P39"

    def test_time_valued_statement(self):
        """A time statement has a property ID."""
        assert statement_property_id(time_statement()) == "P569"

    def test_somevalue_statement(self):
        """A somevalue statement has a property ID."""
        assert statement_property_id(somevalue_statement()) == "P39"

    def test_novalue_statement(self):
        """A novalue statement has a property ID."""
        assert statement_property_id(novalue_statement()) == "P39"


class TestStatementEntityId:
    """Test reading the entity ID from the main value."""

    def test_entity_valued_statement(self):
        """A wikibase-item statement points to an entity ID."""
        assert statement_entity_id(entity_statement()) == "Q123"

    def test_time_valued_statement_returns_none(self):
        """A time value has dict content, not an entity ID string."""
        assert statement_entity_id(time_statement()) is None

    def test_somevalue_statement_returns_none(self):
        """A somevalue statement has no content."""
        assert statement_entity_id(somevalue_statement()) is None

    def test_novalue_statement_returns_none(self):
        """A novalue statement has no content."""
        assert statement_entity_id(novalue_statement()) is None

    def test_non_entity_string_content_returns_none(self):
        """String content that is not an entity ID returns None."""
        url_statement = {
            "property": {"id": "P854", "data_type": "url"},
            "value": {"type": "value", "content": "https://example.org/source"},
        }
        assert statement_entity_id(url_statement) is None


class TestStatementTimeValue:
    """Test reading the time value from the main value."""

    def test_time_valued_statement(self):
        """A time statement yields a WikidataDate with time and precision."""
        assert statement_time_value(time_statement()) == WikidataDate(
            time_string="+1946-06-14T00:00:00Z", precision=11
        )

    def test_entity_valued_statement_returns_none(self):
        """An entity statement has no time value."""
        assert statement_time_value(entity_statement()) is None

    def test_somevalue_statement_returns_none(self):
        """A somevalue statement has no time value."""
        assert statement_time_value(somevalue_statement()) is None

    def test_novalue_statement_returns_none(self):
        """A novalue statement has no time value."""
        assert statement_time_value(novalue_statement()) is None


class TestFindQualifiers:
    """Test qualifier lookup by property."""

    def test_returns_matching_qualifier(self):
        """A qualifier is found by its property ID."""
        qualifiers = find_qualifiers(entity_statement(), "P580")
        assert len(qualifiers) == 1
        assert qualifiers[0]["property"]["id"] == "P580"

    def test_multiple_qualifiers_on_one_property_preserve_order(self):
        """All qualifiers on one property are returned in document order."""
        document = entity_statement()
        document["qualifiers"].append(
            {
                "property": {"id": "P580", "data_type": "time"},
                "value": {
                    "type": "value",
                    "content": {
                        "time": "+2021-00-00T00:00:00Z",
                        "precision": 9,
                        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                    },
                },
            }
        )
        qualifiers = find_qualifiers(document, "P580")
        times = [qualifier["value"]["content"]["time"] for qualifier in qualifiers]
        assert times == ["+2020-01-01T00:00:00Z", "+2021-00-00T00:00:00Z"]

    def test_no_matching_qualifiers_returns_empty_list(self):
        """A property without qualifiers yields an empty list."""
        assert find_qualifiers(entity_statement(), "P582") == []


class TestQualifierTimeValue:
    """Test reading the time value from a qualifier."""

    def test_time_qualifier(self):
        """A time qualifier yields a WikidataDate with time and precision."""
        qualifier = find_qualifiers(entity_statement(), "P580")[0]
        assert qualifier_time_value(qualifier) == WikidataDate(
            time_string="+2020-01-01T00:00:00Z", precision=11
        )

    def test_entity_qualifier_returns_none(self):
        """An entity qualifier has no time value."""
        qualifier = find_qualifiers(entity_statement(), "P1365")[0]
        assert qualifier_time_value(qualifier) is None

    def test_somevalue_qualifier_returns_none(self):
        """A somevalue qualifier has no time value."""
        qualifier = {
            "property": {"id": "P582", "data_type": "time"},
            "value": {"type": "somevalue"},
        }
        assert qualifier_time_value(qualifier) is None
