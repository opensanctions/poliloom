"""Functions for interacting with the Wikidata API."""

from typing import Any, Dict, Optional, List
import requests
from pydantic import BaseModel, Field


class Sitelink(BaseModel):
    site: str
    title: str

    class Config:
        extra = "ignore"


class Item(BaseModel):
    """A Wikidata item with its properties and sitelinks."""

    id: str
    labels: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    descriptions: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    aliases: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)
    claims: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    sitelinks: Dict[str, Sitelink] = Field(default_factory=dict)

    @classmethod
    def fetch(cls, qid: str) -> "Item":
        """Fetch a Wikidata item by its QID.

        Args:
            qid: The Wikidata item ID (e.g., "Q12345")

        Returns:
            An Item instance with the fetched data

        Raises:
            requests.RequestException: If the API request fails
            ValueError: If the response indicates an error
        """
        params = {
            "action": "wbgetentities",
            "format": "json",
            "ids": qid,
            "props": "labels|descriptions|aliases|claims|sitelinks",
        }

        response = requests.get(WIKIDATA_API, params=params)
        response.raise_for_status()

        data = response.json()

        if "error" in data:
            raise ValueError(f"Wikidata API error: {data['error']['info']}")

        if "entities" not in data or qid not in data["entities"]:
            raise ValueError(f"No data found for Wikidata item {qid}")

        entity_data = data["entities"][qid]
        # Remove the id field from entity_data since we're passing it separately
        entity_data.pop("id", None)
        return cls(id=qid, **entity_data)

    def get_aliases(self, lang: str = "en") -> List[str]:
        """Get aliases for a specific language."""
        aliases = self.aliases.get(lang, [])
        return [alias["value"] for alias in aliases]

    def get_label(self, lang: str = "en") -> Optional[str]:
        """Get the label (name) in a specific language."""
        label = self.labels.get(lang, {})
        return label.get("value") if label else None


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
