"""Wikidata API client for fetching politician data."""

import httpx
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class WikidataClient:
    """Client for interacting with Wikidata API."""

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    API_ENDPOINT = "https://www.wikidata.org/w/api.php"

    def __init__(self):
        self.session = httpx.Client(timeout=30.0)

    def get_politician_by_id(self, wikidata_id: str) -> Optional[Dict[str, Any]]:
        """Fetch politician data from Wikidata by ID."""
        # Remove Q prefix if present
        entity_id = wikidata_id.upper()
        if not entity_id.startswith("Q"):
            entity_id = f"Q{entity_id}"

        try:
            # Get entity data from Wikidata API
            response = self.session.get(
                self.API_ENDPOINT,
                params={
                    "action": "wbgetentities",
                    "ids": entity_id,
                    "format": "json",
                    "languages": "en",
                    "props": "labels|descriptions|claims|sitelinks",
                },
            )
            response.raise_for_status()
            data = response.json()

            if "entities" not in data or entity_id not in data["entities"]:
                logger.warning(f"Entity {entity_id} not found in Wikidata")
                return None

            entity = data["entities"][entity_id]

            # Check if this is a person (instance of human - Q5)
            if not self._is_human(entity):
                logger.warning(f"Entity {entity_id} is not a human")
                return None

            # Check if this person has politician-related occupations/positions
            if not self._is_politician(entity):
                logger.warning(f"Entity {entity_id} is not identified as a politician")
                return None

            return self._parse_politician_data(entity)

        except httpx.RequestError as e:
            logger.error(f"Error fetching data for {entity_id}: {e}")
            return None

    def _is_human(self, entity: Dict[str, Any]) -> bool:
        """Check if entity is an instance of human (Q5)."""
        claims = entity.get("claims", {})
        instance_of = claims.get("P31", [])  # instance of property

        for claim in instance_of:
            if (
                claim.get("mainsnak", {})
                .get("datavalue", {})
                .get("value", {})
                .get("id")
                == "Q5"
            ):
                return True
        return False

    def _is_politician(self, entity: Dict[str, Any]) -> bool:
        """Check if entity has politician-related occupations or positions."""
        claims = entity.get("claims", {})

        # Check occupation (P106)
        occupations = claims.get("P106", [])
        politician_occupations = {"Q82955"}  # politician

        for claim in occupations:
            occupation_id = (
                claim.get("mainsnak", {})
                .get("datavalue", {})
                .get("value", {})
                .get("id")
            )
            if occupation_id in politician_occupations:
                return True

        # Check position held (P39) - if they have any political positions
        positions = claims.get("P39", [])
        if positions:
            return True

        return False

    def _parse_politician_data(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Wikidata entity into politician data structure."""
        claims = entity.get("claims", {})

        # Basic info
        name = entity.get("labels", {}).get("en", {}).get("value", "")
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")

        # Extract properties (supporting multiple values where appropriate)
        properties = []

        # Birth date (P569) - single value
        birth_date = self._extract_date_claim(claims.get("P569", []))
        if birth_date:
            properties.append({"type": "BirthDate", "value": birth_date})

        # Birth place (P19) - single value
        birth_place = self._extract_place_claim(claims.get("P19", []))
        if birth_place:
            properties.append({"type": "BirthPlace", "value": birth_place})

        # Death date (P570) - single value
        death_date = self._extract_date_claim(claims.get("P570", []))
        is_deceased = death_date is not None
        if death_date:
            properties.append({"type": "DeathDate", "value": death_date})

        # Citizenship (P27) - can have multiple values
        citizenships = self._extract_all_citizenship_claims(claims.get("P27", []))
        for citizenship in citizenships:
            properties.append({"type": "Citizenship", "value": citizenship})

        # Extract positions held
        positions = self._extract_positions(claims.get("P39", []))

        # Extract Wikipedia links
        wikipedia_links = self._extract_wikipedia_links(entity.get("sitelinks", {}))

        return {
            "wikidata_id": entity["id"],
            "name": name,
            "description": description,
            "is_deceased": is_deceased,
            "properties": properties,
            "positions": positions,
            "wikipedia_links": wikipedia_links,
        }

    def _extract_date_claim(self, claims: List[Dict[str, Any]]) -> Optional[str]:
        """Extract date from Wikidata claim."""
        for claim in claims:
            # Handle both main claims (with mainsnak) and qualifier claims (direct structure)
            if "mainsnak" in claim:
                datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            else:
                datavalue = claim.get("datavalue", {})

            if datavalue.get("type") == "time":
                time_value = datavalue.get("value", {}).get("time", "")
                # Convert from Wikidata format (+1970-01-15T00:00:00Z) to simpler format
                if time_value.startswith("+"):
                    date_part = time_value[1:].split("T")[0]
                    # Handle precision - only return what's specified
                    precision = datavalue.get("value", {}).get("precision", 11)
                    if precision >= 11:  # day precision
                        return date_part
                    elif precision == 10:  # month precision
                        return date_part[:7]  # YYYY-MM
                    elif precision == 9:  # year precision
                        return date_part[:4]  # YYYY
        return None

    def _extract_place_claim(self, claims: List[Dict[str, Any]]) -> Optional[str]:
        """Extract place name from Wikidata claim."""
        for claim in claims:
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") == "wikibase-entityid":
                entity_id = datavalue.get("value", {}).get("id")
                if entity_id:
                    # Get the place name
                    place_name = self._get_entity_label(entity_id)
                    if place_name:
                        return place_name
        return None

    def _extract_all_citizenship_claims(self, claims: List[Dict[str, Any]]) -> List[str]:
        """Extract all citizenship values from claims."""
        citizenships = []
        for claim in claims:
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") == "wikibase-entityid":
                entity_id = datavalue.get("value", {}).get("id")
                if entity_id:
                    # Get country name first, fallback to country code
                    country_name = self._get_entity_label(entity_id)
                    if country_name:
                        citizenships.append(country_name)
                    else:
                        # Fallback to country code if name not available
                        country_code = self._get_country_code(entity_id)
                        if country_code:
                            citizenships.append(country_code)
        return citizenships

    def _extract_country_claim(self, claims: List[Dict[str, Any]]) -> List[str]:
        """Extract country codes from citizenship claims."""
        countries = []
        for claim in claims:
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") == "wikibase-entityid":
                entity_id = datavalue.get("value", {}).get("id")
                if entity_id:
                    # Try to get ISO country code, fallback to country name
                    country_code = self._get_country_code(entity_id)
                    if country_code:
                        countries.append(country_code)
        return countries

    def _extract_positions(self, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract political positions from claims."""
        positions = []
        for claim in claims:
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") == "wikibase-entityid":
                position_id = datavalue.get("value", {}).get("id")
                if position_id:
                    position_name = self._get_entity_label(position_id)
                    if position_name:
                        # Extract qualifiers for start/end dates
                        qualifiers = claim.get("qualifiers", {})
                        start_date = self._extract_date_claim(
                            qualifiers.get("P580", [])
                        )  # start time
                        end_date = self._extract_date_claim(
                            qualifiers.get("P582", [])
                        )  # end time

                        positions.append(
                            {
                                "wikidata_id": position_id,
                                "name": position_name,
                                "start_date": start_date,
                                "end_date": end_date,
                            }
                        )
        return positions

    def _extract_wikipedia_links(
        self, sitelinks: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Extract Wikipedia article links."""
        links = []
        for site, link_data in sitelinks.items():
            if site.endswith("wiki"):  # Wikipedia sites
                lang = site.replace("wiki", "")
                title = link_data.get("title", "")
                if title:
                    url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    links.append({"language": lang, "title": title, "url": url})
        return links

    def _get_entity_label(self, entity_id: str) -> Optional[str]:
        """Get the English label for a Wikidata entity."""
        try:
            response = self.session.get(
                self.API_ENDPOINT,
                params={
                    "action": "wbgetentities",
                    "ids": entity_id,
                    "format": "json",
                    "languages": "en",
                    "props": "labels",
                },
            )
            response.raise_for_status()
            data = response.json()

            if "entities" in data and entity_id in data["entities"]:
                return (
                    data["entities"][entity_id]
                    .get("labels", {})
                    .get("en", {})
                    .get("value")
                )
        except httpx.RequestError:
            logger.warning(f"Could not fetch label for entity {entity_id}")
        return None

    def _get_country_code(self, entity_id: str) -> Optional[str]:
        """Get ISO country code for a country entity."""
        try:
            response = self.session.get(
                self.API_ENDPOINT,
                params={
                    "action": "wbgetentities",
                    "ids": entity_id,
                    "format": "json",
                    "languages": "en",
                    "props": "claims",
                },
            )
            response.raise_for_status()
            data = response.json()

            if "entities" in data and entity_id in data["entities"]:
                claims = data["entities"][entity_id].get("claims", {})
                # ISO 3166-1 alpha-2 code (P297)
                iso_codes = claims.get("P297", [])
                for claim in iso_codes:
                    datavalue = claim.get("mainsnak", {}).get("datavalue", {})
                    if datavalue.get("type") == "string":
                        return datavalue.get("value")
        except httpx.RequestError:
            logger.warning(f"Could not fetch country code for entity {entity_id}")
        return None

    def close(self):
        """Close the HTTP session."""
        self.session.close()
