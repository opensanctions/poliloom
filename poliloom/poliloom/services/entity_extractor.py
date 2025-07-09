"""Entity identification and data extraction from Wikidata dumps."""

import logging
from typing import Dict, Set, Optional, Any

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts and identifies entities from Wikidata dump data."""

    def is_instance_of_position(
        self, entity: Dict[str, Any], position_descendants: Set[str]
    ) -> bool:
        """Check if an entity is an instance of any position type (P31 instance of position descendants)."""
        # Only check if this entity is an instance of a position type
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in position_descendants:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def is_instance_of_location(
        self, entity: Dict[str, Any], location_descendants: Set[str]
    ) -> bool:
        """Check if an entity is an instance of any location type (P31 instance of location descendants)."""
        # Only check if this entity is an instance of a location type
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in location_descendants:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def is_country_entity(self, entity: Dict[str, Any]) -> bool:
        """Check if an entity is a country based on its instance of (P31) properties."""
        claims = entity.get("claims", {})
        instance_of_claims = claims.get("P31", [])

        # Common country instance types
        country_types = {
            "Q6256",  # country
            "Q3624078",  # sovereign state
            "Q3624078",  # country
            "Q20181813",  # historic country
            "Q1520223",  # independent city
            "Q1489259",  # city-state
        }

        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id in country_types:
                    return True
            except (KeyError, TypeError):
                continue

        return False

    def extract_position_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract position data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        return {
            "wikidata_id": entity["id"],
            "name": name,
        }

    def extract_location_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract location data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        return {
            "wikidata_id": entity["id"],
            "name": name,
        }

    def extract_country_data(self, entity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract country data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        # Try to get ISO code from claims
        iso_code = None
        claims = entity.get("claims", {})

        # P297 is the property for ISO 3166-1 alpha-2 code
        iso_claims = claims.get("P297", [])
        for claim in iso_claims:
            try:
                iso_code = claim["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                continue

        return {
            "wikidata_id": entity["id"],
            "name": name,
            "iso_code": iso_code,
        }

    def is_politician(self, entity: Dict[str, Any]) -> bool:
        """Check if an entity is a politician based on occupation (P106) or position held (P39)."""
        claims = entity.get("claims", {})

        # Check if it's a human first (P31 instance of Q5)
        instance_of_claims = claims.get("P31", [])
        is_human = False
        for claim in instance_of_claims:
            try:
                instance_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if instance_id == "Q5":  # human
                    is_human = True
                    break
            except (KeyError, TypeError):
                continue

        if not is_human:
            return False

        # Check occupation (P106) for politician (Q82955)
        occupation_claims = claims.get("P106", [])
        for claim in occupation_claims:
            try:
                occupation_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if occupation_id == "Q82955":  # politician
                    return True
            except (KeyError, TypeError):
                continue

        # Check if they have any position held (P39)
        position_claims = claims.get("P39", [])
        if position_claims:
            return True

        return False

    def extract_politician_data(
        self, entity: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extract politician data from a Wikidata entity."""
        name = self.get_entity_name(entity)
        if not name:
            return None

        claims = entity.get("claims", {})

        # Basic politician data
        politician_data = {
            "wikidata_id": entity["id"],
            "name": name,
            "is_deceased": False,
            "properties": [],
            "citizenships": [],
            "positions": [],
            "wikipedia_links": [],
            "birthplace": None,
        }

        # Check if deceased (P570 death date)
        death_date_claims = claims.get("P570", [])
        if death_date_claims:
            politician_data["is_deceased"] = True
            death_date = self._extract_date_from_claims(death_date_claims)
            if death_date:
                politician_data["properties"].append(
                    {"type": "DeathDate", "value": death_date}
                )

        # Extract birth date (P569)
        birth_date_claims = claims.get("P569", [])
        birth_date = self._extract_date_from_claims(birth_date_claims)
        if birth_date:
            politician_data["properties"].append(
                {"type": "BirthDate", "value": birth_date}
            )

        # Extract citizenships (P27) - get country codes
        citizenship_claims = claims.get("P27", [])
        for claim in citizenship_claims:
            try:
                country_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                # We'll need to resolve country codes later in the database
                politician_data["citizenships"].append(country_id)
            except (KeyError, TypeError):
                continue

        # Extract positions held (P39)
        position_claims = claims.get("P39", [])
        for claim in position_claims:
            try:
                position_id = claim["mainsnak"]["datavalue"]["value"]["id"]

                # Extract start/end dates from qualifiers
                start_date = None
                end_date = None
                qualifiers = claim.get("qualifiers", {})

                # Start time (P580)
                start_claims = qualifiers.get("P580", [])
                if start_claims:
                    start_date = self._extract_date_from_claims(start_claims)

                # End time (P582)
                end_claims = qualifiers.get("P582", [])
                if end_claims:
                    end_date = self._extract_date_from_claims(end_claims)

                politician_data["positions"].append(
                    {
                        "wikidata_id": position_id,
                        "start_date": start_date,
                        "end_date": end_date,
                    }
                )
            except (KeyError, TypeError):
                continue

        # Extract birthplace (P19)
        birthplace_claims = claims.get("P19", [])
        if birthplace_claims:
            try:
                birthplace_id = birthplace_claims[0]["mainsnak"]["datavalue"]["value"][
                    "id"
                ]
                politician_data["birthplace"] = birthplace_id
            except (KeyError, TypeError):
                pass

        # Extract Wikipedia links from sitelinks
        sitelinks = entity.get("sitelinks", {})
        for site, link_data in sitelinks.items():
            if site.endswith("wiki"):  # Wikipedia sites
                lang = site.replace("wiki", "")
                title = link_data.get("title", "")
                if title:
                    url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    politician_data["wikipedia_links"].append(
                        {
                            "language": lang,
                            "title": title,
                            "url": url,
                        }
                    )

        return politician_data

    def _extract_date_from_claims(self, claims: list) -> Optional[str]:
        """Extract date from Wikidata claims."""
        for claim in claims:
            try:
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
            except (KeyError, TypeError):
                continue
        return None

    def get_entity_name(self, entity: Dict[str, Any]) -> Optional[str]:
        """Extract the primary name from a Wikidata entity."""
        labels = entity.get("labels", {})

        # Try English first
        if "en" in labels:
            return labels["en"]["value"]

        # Fallback to any available language
        if labels:
            return next(iter(labels.values()))["value"]

        return None
