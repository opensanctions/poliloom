"""Functions for interacting with the Wikipedia API."""

from typing import Dict, Any, Optional
import requests
from pydantic import BaseModel, Field
import urllib.parse

ACTIVE_SITES = [
    "enwiki", "frwiki", "ruwiki", "dewiki", "eswiki", "itwiki",
    "plwiki", "ptwiki", "svwiki", "ukwiki", "viwiki", "zhwiki",
    "trwiki", "arwiki", "nlwiki", "idwiki", "svwiki", "arzwiki",
]

class Page(BaseModel):
    """A Wikipedia page with its content and metadata."""
    pageid: int
    title: str
    extract: str = Field(default="")
    fulltext: str = Field(default="")
    site: str = Field(default="enwiki")  # Add site field to store the wiki site

    @classmethod
    def fetch(cls, title: str, site: str = "enwiki") -> Optional["Page"]:
        """Fetch a Wikipedia page by its title, or return None for special sites.
        
        Args:
            title: The Wikipedia page title
            site: The Wikipedia site identifier (e.g., "enwiki", "frwiki")
            
        Returns:
            A Page instance with the fetched data, or None if site is special
            
        Raises:
            requests.RequestException: If the API request fails
            ValueError: If the response indicates an error or page not found
        """
        if site not in ACTIVE_SITES:
            return None
        # Extract language code from site (e.g., "en" from "enwiki")
        lang = site.replace("wiki", "")
        wikipedia_api = f"https://{lang}.wikipedia.org/w/api.php"
        
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts|revisions",
            "rvprop": "content",
            "titles": title,
            "exintro": "0",  # Get full content, not just intro
            "explaintext": "0",  # Keep HTML formatting
        }

        response = requests.get(wikipedia_api, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            raise ValueError(f"Wikipedia API error: {data['error']['info']}")
        
        pages = data["query"]["pages"]
        # Get the first (and should be only) page
        page = next(iter(pages.values()))
        
        if "missing" in page:
            raise ValueError(f"Wikipedia page not found: {title}")
        
        return cls(
            pageid=page["pageid"],
            title=page["title"],
            extract=page.get("extract", ""),
            fulltext=page["revisions"][0]["*"] if "revisions" in page else "",
            site=site,  # Store the site
        )

    def get_content(self) -> str:
        """Get the full page content."""
        return self.fulltext

    def get_summary(self) -> str:
        """Get the page summary."""
        return self.extract

    def get_url(self) -> str:
        """Generate the URL for this Wikipedia page.
        
        Returns:
            The full URL to the Wikipedia page
        """
        lang = self.site.replace("wiki", "")
        # URL encode the title to handle special characters
        encoded_title = urllib.parse.quote(self.title.replace(" ", "_"))
        return f"https://{lang}.wikipedia.org/wiki/{encoded_title}"
