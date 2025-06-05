"""Functions for parsing Wikipedia page content."""

from typing import Optional, Dict, Any
import wikitextparser as wtp
import re
from datetime import datetime

def parse_infobox(wikitext: str) -> Optional[Dict[str, Any]]:
    """Extract information from a Wikipedia infobox.
    
    Args:
        wikitext: The wikitext content of the Wikipedia page
        
    Returns:
        A dictionary containing the extracted information, or None if no infobox found
    """
    parsed = wtp.parse(wikitext)
    
    # Find the first infobox template
    infobox = None
    for template in parsed.templates:
        if template.name.lower().startswith('infobox'):
            infobox = template
            break
    
    if not infobox:
        return None
        
    data = {}
    
    # Extract birth information
    for arg in infobox.arguments:
        name = arg.name.strip().lower()
        value = arg.value.strip()
        
        if name == 'birth_date':
            # Handle birth date template
            birth_date_template = wtp.parse(value).templates
            if birth_date_template:
                # Extract date components from the template
                date_args = {a.name.strip(): a.value.strip() for a in birth_date_template[0].arguments}
                try:
                    year = date_args.get('3', '')  # Year is usually the 3rd parameter
                    month = date_args.get('2', '')  # Month is usually the 2nd parameter
                    day = date_args.get('1', '')    # Day is usually the 1st parameter
                    if year and month and day:
                        data['birth_date'] = f"{day} {month} {year}"
                        try:
                            data['birth_date_parsed'] = datetime.strptime(data['birth_date'], '%d %m %Y')
                        except ValueError:
                            pass
                except Exception:
                    data['birth_date'] = value
            else:
                data['birth_date'] = value
                
        elif name == 'birth_place':
            # Clean up the birth place text
            # Remove HTML comments
            value = re.sub(r'<!--.*?-->', '', value)
            # Remove wikilinks but keep their text
            value = re.sub(r'\[\[(.*?)\]\]', r'\1', value)
            data['birth_place'] = value.strip()
    
    return data

def parse_page(page_content: str) -> Optional[Dict[str, Any]]:
    """Parse a Wikipedia page and extract structured information.
    
    Args:
        page_content: The wikitext content of the Wikipedia page
        
    Returns:
        A dictionary containing the extracted information, or None if parsing failed
    """
    try:
        return parse_infobox(page_content)
    except Exception as e:
        print(f"Error parsing page: {e}")
        return None 