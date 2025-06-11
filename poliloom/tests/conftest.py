"""Test configuration and fixtures for PoliLoom tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from poliloom.database import get_db
from poliloom.models import Base, Politician, Source, Property, Position, HoldsPosition


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_politician(test_session):
    """Create a sample politician for testing."""
    politician = Politician(
        name="John Doe",
        wikidata_id="Q123456",
        is_deceased=False
    )
    test_session.add(politician)
    test_session.commit()
    test_session.refresh(politician)
    return politician


@pytest.fixture
def sample_source(test_session):
    """Create a sample source for testing."""
    source = Source(
        url="https://example.com/john-doe",
        extracted_at=datetime(2024, 1, 15, 10, 30, 0)
    )
    test_session.add(source)
    test_session.commit()
    test_session.refresh(source)
    return source


@pytest.fixture
def sample_position(test_session):
    """Create a sample position for testing."""
    position = Position(
        name="Mayor",
        country="US",
        wikidata_id="Q30185"
    )
    test_session.add(position)
    test_session.commit()
    test_session.refresh(position)
    return position


@pytest.fixture
def sample_property(test_session, sample_politician, sample_source):
    """Create a sample property for testing."""
    prop = Property(
        politician_id=sample_politician.id,
        type="BirthDate",
        value="1970-01-15",
        is_extracted=True,
        confirmed_by=None,
        confirmed_at=None
    )
    prop.sources.append(sample_source)
    test_session.add(prop)
    test_session.commit()
    test_session.refresh(prop)
    return prop


@pytest.fixture
def sample_holds_position(test_session, sample_politician, sample_position, sample_source):
    """Create a sample holds position relationship for testing."""
    holds_pos = HoldsPosition(
        politician_id=sample_politician.id,
        position_id=sample_position.id,
        start_date="2020",
        end_date="2024",
        is_extracted=True,
        confirmed_by=None,
        confirmed_at=None
    )
    holds_pos.sources.append(sample_source)
    test_session.add(holds_pos)
    test_session.commit()
    test_session.refresh(holds_pos)
    return holds_pos


@pytest.fixture
def mock_wikidata_responses():
    """Mock Wikidata API responses for testing."""
    return {
        'politician_response': {
            "entities": {
                "Q123456": {
                    "id": "Q123456",
                    "labels": {
                        "en": {"value": "John Doe"}
                    },
                    "descriptions": {
                        "en": {"value": "American politician"}
                    },
                    "claims": {
                        "P31": [  # instance of
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {"id": "Q5"}  # human
                                    }
                                }
                            }
                        ],
                        "P106": [  # occupation
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {"id": "Q82955"}  # politician
                                    }
                                }
                            }
                        ],
                        "P569": [  # birth date
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "time",
                                        "value": {
                                            "time": "+1970-01-15T00:00:00Z",
                                            "precision": 11
                                        }
                                    }
                                }
                            }
                        ],
                        "P19": [  # birth place
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "wikibase-entityid",
                                        "value": {"id": "Q60"}  # New York City
                                    }
                                }
                            }
                        ],
                        "P27": [  # citizenship
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "wikibase-entityid",
                                        "value": {"id": "Q30"}  # United States
                                    }
                                }
                            }
                        ],
                        "P39": [  # position held
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "wikibase-entityid",
                                        "value": {"id": "Q30185"}  # mayor
                                    }
                                },
                                "qualifiers": {
                                    "P580": [  # start time
                                        {
                                            "mainsnak": {
                                                "datavalue": {
                                                    "type": "time",
                                                    "value": {
                                                        "time": "+2020-01-01T00:00:00Z",
                                                        "precision": 9
                                                    }
                                                }
                                            }
                                        }
                                    ],
                                    "P582": [  # end time
                                        {
                                            "mainsnak": {
                                                "datavalue": {
                                                    "type": "time",
                                                    "value": {
                                                        "time": "+2024-12-31T00:00:00Z",
                                                        "precision": 9
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    "sitelinks": {
                        "enwiki": {"title": "John Doe"},
                        "eswiki": {"title": "John Doe"}
                    }
                }
            }
        },
        'place_response': {
            "entities": {
                "Q60": {
                    "labels": {
                        "en": {"value": "New York City"}
                    }
                }
            }
        },
        'position_response': {
            "entities": {
                "Q30185": {
                    "labels": {
                        "en": {"value": "mayor"}
                    }
                }
            }
        },
        'country_response': {
            "entities": {
                "Q30": {
                    "claims": {
                        "P297": [  # ISO 3166-1 alpha-2 code
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "string",
                                        "value": "US"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },
        'sparql_politicians_response': {
            "head": {
                "vars": ["politician", "politicianLabel", "country"]
            },
            "results": {
                "bindings": [
                    {
                        "politician": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q123456"
                        },
                        "politicianLabel": {
                            "type": "literal",
                            "value": "John Doe"
                        },
                        "country": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q30"
                        }
                    },
                    {
                        "politician": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q789012"
                        },
                        "politicianLabel": {
                            "type": "literal",
                            "value": "Jane Smith"
                        },
                        "country": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q16"
                        }
                    }
                ]
            }
        }
    }