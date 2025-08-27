"""WikidataPolitician entity class for politician-specific extraction."""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from .wikidata_entity import WikidataEntity


class WikidataPolitician(WikidataEntity):
    """Represents a politician entity from Wikidata with extraction methods."""

    @classmethod
    def is_politician(cls, raw_data: Dict[str, Any]) -> bool:
        """Check if an entity is a politician based on occupation (P106) or position held (P39).

        Args:
            raw_data: Raw Wikidata entity JSON data

        Returns:
            True if the entity is a politician, False otherwise
        """
        # Create temporary instance to use inherited methods
        temp_entity = cls(raw_data)

        # Check if it's a human first (P31 instance of Q5)
        instance_ids = temp_entity.get_instance_of_ids()
        if "Q5" not in instance_ids:  # Not human
            return False

        # Check occupation (P106) for politician (Q82955)
        occupation_claims = temp_entity.get_truthy_claims("P106")
        for claim in occupation_claims:
            try:
                occupation_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                if occupation_id == "Q82955":  # politician
                    return True
            except (KeyError, TypeError):
                continue

        # Check if they have any position held (P39)
        position_claims = temp_entity.get_truthy_claims("P39")
        if position_claims:
            return True

        return False

    @property
    def is_deceased(self) -> bool:
        """Check if politician is deceased based on death date (P570)."""
        death_claims = self.get_truthy_claims("P570")
        return len(death_claims) > 0

    def should_import_politician(self) -> bool:
        """Check if politician should be imported based on death date.

        Only import politicians who are alive or have been dead for less than 5 years.

        Returns:
            True if politician should be imported, False otherwise
        """
        if not self.is_deceased:
            return True

        death_date_result = self.extract_death_date()
        if not death_date_result:
            # If deceased but no death date, be conservative and exclude
            return False

        # Parse death date and check if within 5 years
        try:
            death_date_str = death_date_result["date"]
            death_precision = death_date_result["precision"]
            current_year = datetime.now().year

            # Handle different date precisions using precision integer
            if death_precision == 9:  # Year only (YYYY)
                death_year = int(death_date_str)
                # Use conservative approach: assume death occurred on January 1st
                years_since_death = current_year - death_year
            elif death_precision == 10:  # Year-month (YYYY-MM)
                death_year = int(death_date_str[:4])
                death_month = int(death_date_str[5:7])
                # Use conservative approach: assume death occurred on 1st of month
                death_date = date(death_year, death_month, 1)
                years_since_death = (date.today() - death_date).days / 365.25
            else:  # Full date (YYYY-MM-DD), precision >= 11
                death_year = int(death_date_str[:4])
                death_month = int(death_date_str[5:7])
                death_day = int(death_date_str[8:10])
                death_date = date(death_year, death_month, death_day)
                years_since_death = (date.today() - death_date).days / 365.25

            return years_since_death < 5.0

        except (ValueError, IndexError):
            # If we can't parse the date, be conservative and exclude
            return False

    def extract_birth_date(self) -> Optional[Dict[str, Any]]:
        """Extract birth date (P569) using truthy filtering.

        Returns:
            Dictionary with 'date' (string) and 'precision' (int) keys, or None
        """
        birth_claims = self.get_truthy_claims("P569")
        return self.extract_date_from_claims(birth_claims)

    def extract_death_date(self) -> Optional[Dict[str, Any]]:
        """Extract death date (P570) using truthy filtering.

        Returns:
            Dictionary with 'date' (string) and 'precision' (int) keys, or None
        """
        death_claims = self.get_truthy_claims("P570")
        return self.extract_date_from_claims(death_claims)

    def extract_citizenships(self) -> List[str]:
        """Extract citizenships (P27) using truthy filtering.

        Returns:
            List of country Wikidata IDs for citizenships
        """
        citizenships = []
        citizenship_claims = self.get_truthy_claims("P27")

        for claim in citizenship_claims:
            try:
                country_id = claim["mainsnak"]["datavalue"]["value"]["id"]
                citizenships.append(country_id)
            except (KeyError, TypeError):
                continue

        return citizenships

    def extract_positions(self) -> List[Dict[str, Any]]:
        """Extract positions held (P39) with qualifiers using truthy filtering.

        Returns:
            List of position dictionaries with wikidata_id, start_date, end_date
        """
        positions = []
        position_claims = self.get_truthy_claims("P39")

        for claim in position_claims:
            try:
                position_id = claim["mainsnak"]["datavalue"]["value"]["id"]

                # Extract start/end dates from qualifiers
                qualifiers = claim.get("qualifiers", {})

                # Start time (P580)
                start_claims = qualifiers.get("P580", [])
                start_date_result = None
                if start_claims:
                    start_date_result = self.extract_date_from_claims(start_claims)

                # End time (P582)
                end_claims = qualifiers.get("P582", [])
                end_date_result = None
                if end_claims:
                    end_date_result = self.extract_date_from_claims(end_claims)

                positions.append(
                    {
                        "wikidata_id": position_id,
                        "start_date": start_date_result["date"]
                        if start_date_result
                        else None,
                        "start_date_precision": start_date_result["precision"]
                        if start_date_result
                        else None,
                        "end_date": end_date_result["date"]
                        if end_date_result
                        else None,
                        "end_date_precision": end_date_result["precision"]
                        if end_date_result
                        else None,
                    }
                )
            except (KeyError, TypeError):
                continue

        return positions

    def extract_birthplace(self) -> Optional[str]:
        """Extract birthplace (P19) using truthy filtering.

        Returns:
            Birthplace Wikidata ID, or None
        """
        birthplace_claims = self.get_truthy_claims("P19")
        if birthplace_claims:
            try:
                return birthplace_claims[0]["mainsnak"]["datavalue"]["value"]["id"]
            except (KeyError, TypeError):
                pass
        return None

    def extract_wikipedia_links(self) -> List[Dict[str, str]]:
        """Extract Wikipedia links from sitelinks.

        Returns:
            List of dictionaries with language, title, and url keys
        """
        wikipedia_links = []

        for site, link_data in self._sitelinks.items():
            if site.endswith("wiki"):  # Wikipedia sites
                lang = site.replace("wiki", "")
                title = link_data.get("title", "")
                if title:
                    url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    wikipedia_links.append(
                        {
                            "language": lang,
                            "title": title,
                            "url": url,
                        }
                    )

        return wikipedia_links

    def to_database_dict(self) -> Dict[str, Any]:
        """Convert politician to dictionary format for database insertion.

        Returns:
            Dictionary with keys matching Politician table columns
        """
        # Get base fields from parent class
        result = super().to_database_dict()

        # Extract basic data
        birth_date_result = self.extract_birth_date()
        death_date_result = self.extract_death_date()
        birthplace = self.extract_birthplace()

        # Build properties list
        properties = []
        if birth_date_result:
            properties.append(
                {
                    "type": "BirthDate",
                    "value": birth_date_result["date"],
                    "value_precision": birth_date_result["precision"],
                }
            )
        if death_date_result:
            properties.append(
                {
                    "type": "DeathDate",
                    "value": death_date_result["date"],
                    "value_precision": death_date_result["precision"],
                }
            )

        # Add politician-specific fields
        result.update(
            {
                "properties": properties,
                "citizenships": self.extract_citizenships(),
                "positions": self.extract_positions(),
                "wikipedia_links": self.extract_wikipedia_links(),
                "birthplace": birthplace,
            }
        )

        return result
