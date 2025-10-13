"""Tests for the POST /politicians/:id/properties endpoint."""

from poliloom.models import (
    Property,
    PropertyType,
)


class TestAddPropertiesEndpoint:
    """Test the POST /politicians/:id/properties endpoint for adding properties."""

    def test_add_properties_to_existing_politician(
        self, client, mock_auth, db_session, sample_politician
    ):
        """Test adding properties to an existing politician."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1962-00-00T00:00:00Z",
                    "value_precision": 9,
                },
                {
                    "type": "P570",
                    "value": "+2024-01-15T00:00:00Z",
                    "value_precision": 11,
                },
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["properties"]) == 2
        assert data["errors"] == []

        # Verify property data is returned
        property_types = [p["type"] for p in data["properties"]]
        assert "P569" in property_types
        assert "P570" in property_types

        # Verify properties were created in database
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == sample_politician.id)
            .all()
        )
        assert len(properties) == 2

        birth_prop = next(p for p in properties if p.type == PropertyType.BIRTH_DATE)
        assert birth_prop.value == "+1962-00-00T00:00:00Z"
        assert birth_prop.value_precision == 9

        death_prop = next(p for p in properties if p.type == PropertyType.DEATH_DATE)
        assert death_prop.value == "+2024-01-15T00:00:00Z"
        assert death_prop.value_precision == 11

    def test_add_entity_properties(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_position,
        sample_location,
    ):
        """Test adding entity relationship properties."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {"type": "P19", "entity_id": sample_location.wikidata_id},
                {"type": "P39", "entity_id": sample_position.wikidata_id},
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["properties"]) == 2

        # Verify entity names are included
        for prop in data["properties"]:
            if prop["type"] == "P19":
                assert prop["entity_id"] == sample_location.wikidata_id
                assert prop["entity_name"] is not None
            elif prop["type"] == "P39":
                assert prop["entity_id"] == sample_position.wikidata_id
                assert prop["entity_name"] is not None

    def test_add_properties_with_qualifiers_and_references(
        self, client, mock_auth, db_session, sample_politician, sample_position
    ):
        """Test adding properties with qualifiers and references."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P39",
                    "entity_id": sample_position.wikidata_id,
                    "qualifiers_json": {
                        "P580": [
                            {
                                "datavalue": {
                                    "value": {
                                        "time": "+2020-00-00T00:00:00Z",
                                        "precision": 9,
                                    },
                                    "type": "time",
                                }
                            }
                        ]
                    },
                    "references_json": [
                        {
                            "property": {"id": "P854"},
                            "value": {
                                "type": "value",
                                "content": "https://example.com",
                            },
                        }
                    ],
                }
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["properties"]) == 1

        # Verify qualifiers and references are returned
        prop = data["properties"][0]
        assert prop["qualifiers"] is not None
        assert "P580" in prop["qualifiers"]
        assert prop["references"] is not None
        assert len(prop["references"]) == 1

        # Verify qualifiers and references were stored
        property = (
            db_session.query(Property)
            .filter(Property.politician_id == sample_politician.id)
            .first()
        )
        assert property.qualifiers_json is not None
        assert "P580" in property.qualifiers_json
        assert property.references_json is not None
        assert len(property.references_json) == 1

    def test_add_properties_politician_not_found(self, client, mock_auth):
        """Test adding properties to non-existent politician."""
        non_existent_id = "12345678-1234-1234-1234-123456789012"
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1962-00-00T00:00:00Z",
                    "value_precision": 9,
                }
            ]
        }

        response = client.post(
            f"/politicians/{non_existent_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 201  # Still returns 201
        data = response.json()

        assert data["success"] is False
        assert "not found" in data["message"].lower()
        assert len(data["properties"]) == 0

    def test_add_properties_invalid_politician_id_format(self, client, mock_auth):
        """Test adding properties with invalid UUID format."""
        invalid_id = "invalid-uuid"
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1962-00-00T00:00:00Z",
                    "value_precision": 9,
                }
            ]
        }

        response = client.post(
            f"/politicians/{invalid_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 201  # Still returns 201
        data = response.json()

        assert data["success"] is False
        assert "invalid" in data["message"].lower()
        assert len(data["properties"]) == 0

    def test_add_properties_invalid_property_type(
        self, client, mock_auth, sample_politician
    ):
        """Test that invalid property type is rejected."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P999",  # Invalid property type
                    "value": "test",
                }
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_add_properties_date_missing_value(
        self, client, mock_auth, sample_politician
    ):
        """Test that date properties require both value and precision."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value_precision": 9,  # Missing value
                }
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 422  # Validation error

    def test_add_properties_date_missing_precision(
        self, client, mock_auth, sample_politician
    ):
        """Test that date properties require both value and precision."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1962-00-00T00:00:00Z",  # Missing precision
                }
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 422  # Validation error

    def test_add_properties_entity_missing_entity_id(
        self, client, mock_auth, sample_politician
    ):
        """Test that entity properties require entity_id."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P19",  # Birthplace requires entity_id
                    "value": "test",  # Should not have value
                }
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 422  # Validation error

    def test_add_properties_invalid_precision_value(
        self, client, mock_auth, sample_politician
    ):
        """Test that invalid precision values are rejected."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1962-00-00T00:00:00Z",
                    "value_precision": 5,  # Invalid precision (must be 9, 10, or 11)
                }
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 422  # Validation error

    def test_add_properties_requires_authentication(self, client, sample_politician):
        """Test that adding properties requires authentication."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1962-00-00T00:00:00Z",
                    "value_precision": 9,
                }
            ]
        }

        response = client.post(f"/politicians/{politician_id}/properties", json=payload)
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    def test_add_multiple_properties_batch(
        self,
        client,
        mock_auth,
        db_session,
        sample_politician,
        sample_position,
        sample_location,
    ):
        """Test adding multiple properties in a single request."""
        politician_id = str(sample_politician.id)
        payload = {
            "properties": [
                {
                    "type": "P569",
                    "value": "+1960-00-00T00:00:00Z",
                    "value_precision": 9,
                },
                {
                    "type": "P19",
                    "entity_id": sample_location.wikidata_id,
                },
                {
                    "type": "P39",
                    "entity_id": sample_position.wikidata_id,
                },
            ]
        }

        response = client.post(
            f"/politicians/{politician_id}/properties",
            json=payload,
            headers=mock_auth,
        )
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["properties"]) == 3
        assert data["errors"] == []

        # Verify all property types
        property_types = [p["type"] for p in data["properties"]]
        assert "P569" in property_types
        assert "P19" in property_types
        assert "P39" in property_types

        # Verify all properties were created in database
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == sample_politician.id)
            .all()
        )
        assert len(properties) == 3
