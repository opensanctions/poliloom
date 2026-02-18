"""Tests for the /politicians endpoint (search/list and create)."""

from poliloom.models import (
    Politician,
    Property,
    PropertyType,
)


class TestGetPoliticiansEndpoint:
    """Test the GET /politicians endpoint for unevaluated politicians."""

    def test_returns_wrapped_response(
        self, client, mock_auth, politician_with_unevaluated_data
    ):
        """Test that endpoint returns a PoliticiansListResponse."""
        response = client.get("/politicians", headers=mock_auth)

        assert response.status_code == 200
        data = response.json()

        # Should be wrapped in {"politicians": [...], "meta": {...}}
        assert "politicians" in data
        assert "meta" in data
        assert isinstance(data["politicians"], list)

        # Meta should have expected fields
        assert "has_enrichable_politicians" in data["meta"]
        assert "total_matching_filters" in data["meta"]

        # Each politician should have expected fields
        if len(data["politicians"]) >= 1:
            politician = data["politicians"][0]
            assert "id" in politician
            assert "name" in politician
            assert "wikidata_id" in politician
            assert "properties" in politician

    def test_pagination(self, client, mock_auth, db_session):
        """Test pagination with limit and offset."""
        # Create multiple politicians with unevaluated extracted properties
        for i in range(5):
            politician = Politician.create_with_entity(
                db_session, f"Q{800000 + i}", f"Pagination Test {i}"
            )
            db_session.add(politician)
            db_session.flush()

            # Add unevaluated property (no statement_id = extracted)
            prop = Property(
                politician_id=politician.id,
                type=PropertyType.BIRTH_DATE,
                value=f"+196{i}-00-00T00:00:00Z",
                value_precision=9,
            )
            db_session.add(prop)
        db_session.flush()

        # Test limit
        response = client.get("/politicians?limit=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2

        # Test offset
        response = client.get("/politicians?limit=2&offset=2", headers=mock_auth)
        assert response.status_code == 200
        data = response.json()
        assert len(data["politicians"]) == 2

    def test_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/politicians")
        assert response.status_code in [401, 403]


class TestSearchPoliticiansEndpoint:
    """Test the GET /politicians/search endpoint."""

    def test_search_by_name(self, client, mock_auth, db_session):
        """Test searching politicians by name."""
        # Create a politician with a unique name and label for search
        politician = Politician.create_with_entity(
            db_session,
            "Q999888",
            "Unique Search Test Name",
            labels=["Unique Search Test Name"],
        )
        db_session.add(politician)
        db_session.flush()

        response = client.get(
            "/politicians/search?q=Unique%20Search%20Test", headers=mock_auth
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # The search result should include our politician
        names = [p["name"] for p in data]
        assert "Unique Search Test Name" in names

    def test_search_requires_query(self, client, mock_auth):
        """Test that search endpoint requires a query parameter."""
        response = client.get("/politicians/search", headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_search_requires_authentication(self, client):
        """Test that search endpoint requires authentication."""
        response = client.get("/politicians/search?q=test")
        assert response.status_code in [401, 403]


class TestCreatePoliticianEndpoint:
    """Test the POST /politicians endpoint for creating new politicians."""

    def test_create_politician_minimal(self, client, mock_auth, db_session):
        """Test creating a politician with minimal data (just name)."""
        payload = {
            "politicians": [
                {
                    "name": "New Politician",
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1
        assert data["errors"] == []

        politician = data["politicians"][0]
        assert politician["id"] is not None
        assert politician["name"] == "New Politician"
        assert politician["wikidata_id"] is not None  # Wikidata entity was created
        assert politician["wikidata_id"].startswith("Q")
        assert politician["properties"] == []

        # Verify politician was created in database with wikidata_id
        db_politician = (
            db_session.query(Politician)
            .filter(Politician.name == "New Politician")
            .first()
        )
        assert db_politician is not None
        assert db_politician.wikidata_id is not None
        assert db_politician.wikidata_id.startswith("Q")

    def test_create_politician_with_properties(self, client, mock_auth, db_session):
        """Test creating a politician with properties."""
        payload = {
            "politicians": [
                {
                    "name": "John Smith",
                    "labels": ["John Smith", "J. Smith"],
                    "description": "American politician",
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
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert politician["id"] is not None
        assert politician["wikidata_id"] is not None  # Wikidata entity was created
        assert politician["wikidata_id"].startswith("Q")
        assert len(politician["properties"]) == 2

        # Verify property data is returned
        property_types = [p["type"] for p in politician["properties"]]
        assert "P569" in property_types
        assert "P570" in property_types

        # Verify politician was created
        politician = (
            db_session.query(Politician).filter(Politician.name == "John Smith").first()
        )
        assert politician is not None

        # Verify properties were created
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .all()
        )
        assert len(properties) == 2

        birth_prop = next(p for p in properties if p.type == PropertyType.BIRTH_DATE)
        assert birth_prop.value == "+1962-00-00T00:00:00Z"
        assert birth_prop.value_precision == 9

        death_prop = next(p for p in properties if p.type == PropertyType.DEATH_DATE)
        assert death_prop.value == "+2024-01-15T00:00:00Z"
        assert death_prop.value_precision == 11

    def test_create_politician_with_entity_properties(
        self, client, mock_auth, db_session, sample_position, sample_location
    ):
        """Test creating a politician with entity relationship properties."""
        payload = {
            "politicians": [
                {
                    "name": "Jane Doe",
                    "properties": [
                        {"type": "P19", "entity_id": sample_location.wikidata_id},
                        {"type": "P39", "entity_id": sample_position.wikidata_id},
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert len(politician["properties"]) == 2

        # Verify entity names are included
        for prop in politician["properties"]:
            if prop["type"] == "P19":
                assert prop["entity_id"] == sample_location.wikidata_id
                assert prop["entity_name"] is not None
            elif prop["type"] == "P39":
                assert prop["entity_id"] == sample_position.wikidata_id
                assert prop["entity_name"] is not None

        # Verify properties reference entities correctly
        politician = (
            db_session.query(Politician).filter(Politician.name == "Jane Doe").first()
        )
        properties = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .all()
        )

        birthplace_prop = next(
            p for p in properties if p.type == PropertyType.BIRTHPLACE
        )
        assert birthplace_prop.entity_id == sample_location.wikidata_id

        position_prop = next(p for p in properties if p.type == PropertyType.POSITION)
        assert position_prop.entity_id == sample_position.wikidata_id

    def test_create_politician_invalid_property_type(self, client, mock_auth):
        """Test that invalid property type is rejected."""
        payload = {
            "politicians": [
                {
                    "name": "Invalid Properties Politician",
                    "properties": [
                        {
                            "type": "P999",  # Invalid property type
                            "value": "test",
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Pydantic validation error

    def test_create_politician_date_property_missing_value(self, client, mock_auth):
        """Test that date properties require both value and precision."""
        payload = {
            "politicians": [
                {
                    "name": "Missing Value Politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value_precision": 9,  # Missing value
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_date_property_missing_precision(self, client, mock_auth):
        """Test that date properties require both value and precision."""
        payload = {
            "politicians": [
                {
                    "name": "Missing Precision Politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1962-00-00T00:00:00Z",  # Missing precision
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_entity_property_missing_entity_id(
        self, client, mock_auth
    ):
        """Test that entity properties require entity_id."""
        payload = {
            "politicians": [
                {
                    "name": "Missing Entity ID Politician",
                    "properties": [
                        {
                            "type": "P19",  # Birthplace requires entity_id
                            "value": "test",  # Should not have value
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_invalid_precision_value(self, client, mock_auth):
        """Test that invalid precision values are rejected."""
        payload = {
            "politicians": [
                {
                    "name": "Invalid Precision Politician",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1962-00-00T00:00:00Z",
                            "value_precision": 5,  # Invalid precision (must be 9, 10, or 11)
                        }
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_empty_name(self, client, mock_auth):
        """Test that empty name is rejected."""
        payload = {
            "politicians": [
                {
                    "name": "   ",  # Empty/whitespace name
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 422  # Validation error

    def test_create_politician_with_qualifiers_and_references(
        self, client, mock_auth, db_session, sample_position
    ):
        """Test creating a politician with properties that have qualifiers and references."""
        payload = {
            "politicians": [
                {
                    "name": "Qualified Politician",
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
                    ],
                }
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 1

        politician = data["politicians"][0]
        assert len(politician["properties"]) == 1

        # Verify qualifiers and references are returned
        prop = politician["properties"][0]
        assert prop["qualifiers"] is not None
        assert "P580" in prop["qualifiers"]
        assert prop["references"] is not None
        assert len(prop["references"]) == 1

        # Verify qualifiers and references were stored
        politician = (
            db_session.query(Politician)
            .filter(Politician.name == "Qualified Politician")
            .first()
        )
        property = (
            db_session.query(Property)
            .filter(Property.politician_id == politician.id)
            .first()
        )

        assert property.qualifiers_json is not None
        assert "P580" in property.qualifiers_json
        assert property.references_json is not None
        assert len(property.references_json) == 1

    def test_create_politician_requires_authentication(self, client):
        """Test that creating a politician requires authentication."""
        payload = {
            "politicians": [
                {
                    "name": "Unauthenticated Politician",
                }
            ]
        }

        response = client.post("/politicians/", json=payload)
        assert response.status_code in [401, 403]  # Unauthorized or Forbidden

    def test_create_multiple_politicians_batch(self, client, mock_auth, db_session):
        """Test creating multiple politicians in a single batch request."""
        payload = {
            "politicians": [
                {
                    "name": "Politician One",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1960-00-00T00:00:00Z",
                            "value_precision": 9,
                        }
                    ],
                },
                {
                    "name": "Politician Two",
                    "properties": [
                        {
                            "type": "P569",
                            "value": "+1970-00-00T00:00:00Z",
                            "value_precision": 9,
                        }
                    ],
                },
                {
                    "name": "Politician Three",
                },
            ]
        }

        response = client.post("/politicians/", json=payload, headers=mock_auth)
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert len(data["politicians"]) == 3
        assert data["errors"] == []

        # Verify all politicians were created
        politician_names = [p["name"] for p in data["politicians"]]
        assert "Politician One" in politician_names
        assert "Politician Two" in politician_names
        assert "Politician Three" in politician_names

        # Verify properties data
        prop_counts = {p["name"]: len(p["properties"]) for p in data["politicians"]}
        assert prop_counts["Politician One"] == 1
        assert prop_counts["Politician Two"] == 1
        assert prop_counts["Politician Three"] == 0
