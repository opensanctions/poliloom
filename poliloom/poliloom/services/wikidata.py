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
        """Fetch politician data from Wikidata by ID using SPARQL for efficient country code retrieval."""
        # Remove Q prefix if present
        entity_id = wikidata_id.upper()
        if not entity_id.startswith("Q"):
            entity_id = f"Q{entity_id}"

        try:
            # Use SPARQL to get comprehensive politician data including country codes
            sparql_data = self._get_politician_sparql_data(entity_id)
            if not sparql_data:
                logger.warning(
                    f"Entity {entity_id} not found or not a politician in Wikidata"
                )
                return None

            return sparql_data

        except httpx.RequestError as e:
            logger.error(f"Error fetching data for {entity_id}: {e}")
            return None

    def _get_politician_sparql_data(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive politician data using SPARQL including country codes."""
        sparql_query = f"""
        SELECT ?person ?personLabel ?personDescription 
               ?birthDate ?deathDate ?birthPlace ?birthPlaceLabel
               (GROUP_CONCAT(DISTINCT ?citizenshipCode; separator=",") AS ?citizenshipCodes)
               (GROUP_CONCAT(DISTINCT ?positionId; separator=",") AS ?positionIds)
               (GROUP_CONCAT(DISTINCT ?positionLabel; separator="|") AS ?positionLabels)
               (GROUP_CONCAT(DISTINCT ?startDate; separator=",") AS ?startDates)
               (GROUP_CONCAT(DISTINCT ?endDate; separator=",") AS ?endDates)
               (GROUP_CONCAT(DISTINCT ?sitelink; separator=",") AS ?sitelinks)
               (GROUP_CONCAT(DISTINCT ?siteLang; separator=",") AS ?siteLangs)
        WHERE {{
          BIND(wd:{entity_id} AS ?person)
          
          ?person wdt:P31 wd:Q5 .
          {{
            ?person wdt:P106 wd:Q82955 .
          }} UNION {{
            ?person wdt:P39 ?anyPosition .
          }}
          
          OPTIONAL {{ ?person wdt:P569 ?birthDate . }}
          OPTIONAL {{ ?person wdt:P570 ?deathDate . }}
          OPTIONAL {{ 
            ?person wdt:P19 ?birthPlace . 
            ?birthPlace rdfs:label ?birthPlaceLabel .
            FILTER(LANG(?birthPlaceLabel) = "en")
          }}
          
          OPTIONAL {{
            ?person wdt:P27 ?citizenship .
            ?citizenship wdt:P297 ?citizenshipCode .
          }}
          
          OPTIONAL {{
            ?person p:P39 ?posStatement .
            ?posStatement ps:P39 ?position .
            BIND(STRAFTER(STR(?position), "http://www.wikidata.org/entity/") AS ?positionId)
            ?position rdfs:label ?positionLabel .
            FILTER(LANG(?positionLabel) = "en")
            
            OPTIONAL {{ ?posStatement pq:P580 ?startDate . }}
            OPTIONAL {{ ?posStatement pq:P582 ?endDate . }}
          }}
          
          OPTIONAL {{
            ?sitelink schema:about ?person .
            ?sitelink schema:isPartOf ?site .
            ?site wikibase:wikiGroup "wikipedia" .
            BIND(REPLACE(STR(?site), "https://([^.]+)\\\\.wikipedia\\\\.org/", "$1") AS ?siteLang)
          }}
          
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
        }} GROUP BY ?person ?personLabel ?personDescription ?birthDate ?deathDate ?birthPlace ?birthPlaceLabel
        """

        try:
            response = self.session.get(
                self.SPARQL_ENDPOINT,
                params={"query": sparql_query, "format": "json"},
                headers={
                    "User-Agent": "PoliLoom/1.0 (https://github.com/user/poliloom)"
                },
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", {}).get("bindings", [])
            if not results:
                return None

            result = results[0]  # Should only be one result for specific entity

            return self._parse_sparql_politician_data(result)

        except httpx.RequestError as e:
            logger.error(f"Error fetching SPARQL data for {entity_id}: {e}")
            return None

    def _parse_sparql_politician_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse politician data from SPARQL result."""
        # Basic info
        name = result.get("personLabel", {}).get("value", "")
        description = result.get("personDescription", {}).get("value", "")

        # Extract properties
        properties = []

        # Birth date
        birth_date = result.get("birthDate", {}).get("value")
        if birth_date:
            # Parse date format and precision from SPARQL result
            formatted_date = self._format_sparql_date(birth_date)
            if formatted_date:
                properties.append({"type": "BirthDate", "value": formatted_date})

        # Death date
        death_date = result.get("deathDate", {}).get("value")
        is_deceased = death_date is not None
        if death_date:
            formatted_date = self._format_sparql_date(death_date)
            if formatted_date:
                properties.append({"type": "DeathDate", "value": formatted_date})

        # Citizenships (as country codes) - extract separately
        citizenships = []
        citizenship_codes_str = result.get("citizenshipCodes", {}).get("value", "")
        if citizenship_codes_str:
            citizenship_codes = [
                code.strip()
                for code in citizenship_codes_str.split(",")
                if code.strip()
            ]
            citizenships = citizenship_codes

        # Positions held
        positions = []
        position_ids_str = result.get("positionIds", {}).get("value", "")
        position_labels_str = result.get("positionLabels", {}).get("value", "")
        start_dates_str = result.get("startDates", {}).get("value", "")
        end_dates_str = result.get("endDates", {}).get("value", "")

        if position_ids_str and position_labels_str:
            position_ids = [
                id.strip() for id in position_ids_str.split(",") if id.strip()
            ]
            position_labels = [
                label.strip()
                for label in position_labels_str.split("|")
                if label.strip()
            ]
            start_dates = (
                [date.strip() for date in start_dates_str.split(",")]
                if start_dates_str
                else []
            )
            end_dates = (
                [date.strip() for date in end_dates_str.split(",")]
                if end_dates_str
                else []
            )

            for i, (pos_id, pos_label) in enumerate(zip(position_ids, position_labels)):
                start_date = (
                    self._format_sparql_date(start_dates[i])
                    if i < len(start_dates) and start_dates[i]
                    else None
                )
                end_date = (
                    self._format_sparql_date(end_dates[i])
                    if i < len(end_dates) and end_dates[i]
                    else None
                )

                positions.append(
                    {
                        "wikidata_id": pos_id,
                        "name": pos_label,
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                )

        # Wikipedia links
        wikipedia_links = []
        sitelinks_str = result.get("sitelinks", {}).get("value", "")
        site_langs_str = result.get("siteLangs", {}).get("value", "")

        if sitelinks_str and site_langs_str:
            sitelinks = [
                link.strip() for link in sitelinks_str.split(",") if link.strip()
            ]
            site_langs = [
                lang.strip() for lang in site_langs_str.split(",") if lang.strip()
            ]

            for sitelink, lang in zip(sitelinks, site_langs):
                # Extract title from Wikipedia URL
                title = sitelink.split("/wiki/")[-1] if "/wiki/" in sitelink else ""
                if title:
                    wikipedia_links.append(
                        {
                            "language": lang,
                            "title": title.replace("_", " "),
                            "url": sitelink,
                        }
                    )

        # Get entity ID from result
        person_uri = result.get("person", {}).get("value", "")
        wikidata_id = person_uri.split("/")[-1] if person_uri else ""

        return {
            "wikidata_id": wikidata_id,
            "name": name,
            "description": description,
            "is_deceased": is_deceased,
            "properties": properties,
            "citizenships": citizenships,
            "positions": positions,
            "wikipedia_links": wikipedia_links,
        }

    def _format_sparql_date(self, date_str: str) -> Optional[str]:
        """Format date from SPARQL result to consistent format."""
        if not date_str:
            return None

        # SPARQL dates come in ISO format, extract the date part
        if "T" in date_str:
            date_part = date_str.split("T")[0]
        else:
            date_part = date_str

        # Handle different precisions based on the date format
        if len(date_part) >= 10:  # YYYY-MM-DD
            return date_part[:10]
        elif len(date_part) >= 7:  # YYYY-MM
            return date_part[:7]
        elif len(date_part) >= 4:  # YYYY
            return date_part[:4]

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

        # Death date (P570) - single value
        death_date = self._extract_date_claim(claims.get("P570", []))
        is_deceased = death_date is not None
        if death_date:
            properties.append({"type": "DeathDate", "value": death_date})

        # Citizenship (P27) - can have multiple values, extract separately
        citizenships = self._extract_all_citizenship_claims(claims.get("P27", []))

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
            "citizenships": citizenships,
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

    def _extract_all_citizenship_claims(
        self, claims: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract all citizenship values from claims as country codes."""
        citizenships = []
        for claim in claims:
            datavalue = claim.get("mainsnak", {}).get("datavalue", {})
            if datavalue.get("type") == "wikibase-entityid":
                entity_id = datavalue.get("value", {}).get("id")
                if entity_id:
                    # Always use country code for citizenship properties
                    country_code = self._get_country_code(entity_id)
                    if country_code:
                        citizenships.append(country_code)
                    # Skip citizenship properties where country code can't be found
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

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Fetch all political positions from Wikidata using SPARQL."""
        sparql_query = """
        SELECT DISTINCT ?position ?positionLabel 
               (GROUP_CONCAT(DISTINCT ?countryCode; separator=",") AS ?countryCodes) WHERE {
          ?position wdt:P31/wdt:P279* wd:Q294414 . # elected or appointed political position
          OPTIONAL {
            ?position wdt:P17 ?country . # country property
            ?country wdt:P297 ?countryCode . # ISO code
          }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
        } GROUP BY ?position ?positionLabel
        """

        try:
            response = self.session.get(
                self.SPARQL_ENDPOINT,
                params={"query": sparql_query, "format": "json"},
                headers={
                    "User-Agent": "PoliLoom/1.0 (https://github.com/user/poliloom)"
                },
            )
            response.raise_for_status()
            data = response.json()

            positions = []
            for result in data.get("results", {}).get("bindings", []):
                position_uri = result.get("position", {}).get("value", "")
                position_id = position_uri.split("/")[-1] if position_uri else None

                if position_id:
                    # Parse country codes
                    country_codes_str = result.get("countryCodes", {}).get("value", "")
                    country_codes = (
                        [
                            code.strip()
                            for code in country_codes_str.split(",")
                            if code.strip()
                        ]
                        if country_codes_str
                        else []
                    )

                    positions.append(
                        {
                            "wikidata_id": position_id,
                            "name": result.get("positionLabel", {}).get("value", ""),
                            "country_codes": country_codes,
                        }
                    )

            logger.info(f"Fetched {len(positions)} political positions from Wikidata")
            return positions

        except httpx.RequestError as e:
            logger.error(f"Error fetching positions from Wikidata: {e}")
            return []

    def get_all_locations(self, limit: int = 10000, offset: int = 0) -> List[Dict[str, Any]]:
        """Fetch all geographic locations from Wikidata using SPARQL with pagination."""
        sparql_query = f"""
        SELECT DISTINCT ?place ?placeLabel WHERE {{
          ?place wdt:P31/wdt:P279* ?type .
          VALUES ?type {{ 
            wd:Q2221906    # geographic location
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        LIMIT {limit}
        OFFSET {offset}
        """

        try:
            response = self.session.get(
                self.SPARQL_ENDPOINT,
                params={"query": sparql_query, "format": "json"},
                headers={
                    "User-Agent": "PoliLoom/1.0 (https://github.com/user/poliloom)"
                },
            )
            response.raise_for_status()
            data = response.json()

            locations = []
            for result in data.get("results", {}).get("bindings", []):
                place_uri = result.get("place", {}).get("value", "")
                place_id = place_uri.split("/")[-1] if place_uri else None

                if place_id:
                    locations.append(
                        {
                            "wikidata_id": place_id,
                            "name": result.get("placeLabel", {}).get("value", ""),
                        }
                    )

            logger.info(f"Fetched {len(locations)} geographic locations from Wikidata (offset: {offset})")
            return locations

        except httpx.RequestError as e:
            logger.error(f"Error fetching locations from Wikidata: {e}")
            return []

    def close(self):
        """Close the HTTP session."""
        self.session.close()
