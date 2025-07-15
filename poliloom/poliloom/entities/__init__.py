"""Entity classes for Wikidata entity processing and extraction."""

from .wikidata_entity import WikidataEntity
from .politician import WikidataPolitician
from .position import WikidataPosition
from .location import WikidataLocation
from .country import WikidataCountry
from .factory import WikidataEntityFactory

__all__ = [
    "WikidataEntity",
    "WikidataPolitician",
    "WikidataPosition",
    "WikidataLocation",
    "WikidataCountry",
    "WikidataEntityFactory",
]
