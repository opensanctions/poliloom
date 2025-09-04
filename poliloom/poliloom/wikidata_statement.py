"""Wikidata statement creation functions for pushing confirmed evaluations to Wikidata."""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from .models import (
    PropertyEvaluation,
    PositionEvaluation,
    BirthplaceEvaluation,
    Property,
    HoldsPosition,
    BornAt,
)

logger = logging.getLogger(__name__)

# Get API root from environment variable, default to test site for safety
WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://test.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


async def create_statement(
    entity_id: str,
    property_id: str,
    value: Dict[str, Any],
    references: Optional[List[Dict[str, Any]]] = None,
    qualifiers: Optional[List[Dict[str, Any]]] = None,
    jwt_token: str = None,
) -> Optional[str]:
    """
    Create a generic Wikidata statement.

    Args:
        entity_id: Wikidata entity ID (e.g., 'Q42')
        property_id: Wikidata property ID (e.g., 'P569')
        value: Statement value in Wikidata format
        references: List of reference claims
        qualifiers: List of qualifier claims
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Returns:
        Statement ID if successful, None if failed
    """
    if not jwt_token:
        logger.error("JWT token is required for Wikidata API calls")
        return None

    url = f"{WIKIDATA_API_ROOT}/entities/items/{entity_id}/statements"

    statement_data = {
        "statement": {
            "property": {"id": property_id},
            "value": value,
        }
    }

    # Add qualifiers if provided
    if qualifiers:
        statement_data["statement"]["qualifiers"] = qualifiers

    # Add references if provided
    if references:
        statement_data["statement"]["references"] = [{"parts": references}]

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=statement_data, headers=headers)

            if response.status_code == 201:
                result = response.json()
                statement_id = result.get("id")
                logger.info(f"Created statement {statement_id} for {entity_id}")
                return statement_id
            else:
                logger.error(
                    f"Failed to create statement: {response.status_code} - {response.text}"
                )
                return None

    except httpx.RequestError as e:
        logger.error(f"Network error creating statement: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating statement: {e}")
        return None


async def create_birth_date_statement(
    politician_id: str,
    date_value: str,
    source_url: str,
    jwt_token: str,
) -> Optional[str]:
    """
    Create a birth date statement (P569) with Wikipedia reference.

    Args:
        politician_id: Wikidata ID of the politician
        date_value: Birth date value (ISO format or partial)
        source_url: Wikipedia article URL as reference
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Returns:
        Statement ID if successful, None if failed
    """
    # Format date value for Wikidata
    try:
        # Try to parse as full date first
        dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        wikidata_value = {
            "type": "time",
            "value": {
                "time": f"+{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T00:00:00Z",
                "timezone": 0,
                "before": 0,
                "after": 0,
                "precision": 11,  # Day precision
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
            },
        }
    except ValueError:
        # Handle partial dates like "1962" or "JUN 1982"
        if len(date_value) == 4 and date_value.isdigit():
            # Year only
            year = int(date_value)
            wikidata_value = {
                "type": "time",
                "value": {
                    "time": f"+{year:04d}-00-00T00:00:00Z",
                    "timezone": 0,
                    "before": 0,
                    "after": 0,
                    "precision": 9,  # Year precision
                    "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                },
            }
        else:
            logger.error(f"Cannot parse date value: {date_value}")
            return None

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "string", "value": source_url},
        }
    ]

    return await create_statement(
        politician_id,
        "P569",  # Date of birth
        wikidata_value,
        references=references,
        jwt_token=jwt_token,
    )


async def create_birthplace_statement(
    politician_id: str,
    location_id: str,
    source_url: str,
    jwt_token: str,
) -> Optional[str]:
    """
    Create a birthplace statement (P19) with Wikipedia reference.

    Args:
        politician_id: Wikidata ID of the politician
        location_id: Wikidata ID of the location
        source_url: Wikipedia article URL as reference
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Returns:
        Statement ID if successful, None if failed
    """
    wikidata_value = {"type": "wikibase-entityid", "value": {"id": location_id}}

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "string", "value": source_url},
        }
    ]

    return await create_statement(
        politician_id,
        "P19",  # Place of birth
        wikidata_value,
        references=references,
        jwt_token=jwt_token,
    )


async def create_position_held_statement(
    politician_id: str,
    position_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
    source_url: str,
    jwt_token: str,
) -> Optional[str]:
    """
    Create a position held statement (P39) with qualifiers and Wikipedia reference.

    Args:
        politician_id: Wikidata ID of the politician
        position_id: Wikidata ID of the position
        start_date: Start date (optional)
        end_date: End date (optional)
        source_url: Wikipedia article URL as reference
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Returns:
        Statement ID if successful, None if failed
    """
    wikidata_value = {"type": "wikibase-entityid", "value": {"id": position_id}}

    # Create qualifiers for start/end dates
    qualifiers = []

    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            qualifiers.append(
                {
                    "property": {"id": "P580"},  # Start time
                    "value": {
                        "type": "time",
                        "value": {
                            "time": f"+{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T00:00:00Z",
                            "timezone": 0,
                            "before": 0,
                            "after": 0,
                            "precision": 11,  # Day precision
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            )
        except ValueError:
            logger.warning(f"Cannot parse start date: {start_date}")

    if end_date:
        try:
            dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            qualifiers.append(
                {
                    "property": {"id": "P582"},  # End time
                    "value": {
                        "type": "time",
                        "value": {
                            "time": f"+{dt.year:04d}-{dt.month:02d}-{dt.day:02d}T00:00:00Z",
                            "timezone": 0,
                            "before": 0,
                            "after": 0,
                            "precision": 11,  # Day precision
                            "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
                        },
                    },
                }
            )
        except ValueError:
            logger.warning(f"Cannot parse end date: {end_date}")

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "string", "value": source_url},
        }
    ]

    return await create_statement(
        politician_id,
        "P39",  # Position held
        wikidata_value,
        references=references,
        qualifiers=qualifiers if qualifiers else None,
        jwt_token=jwt_token,
    )


async def push_confirmed_evaluation(
    evaluation: Any,
    jwt_token: str,
    db: Session,
) -> bool:
    """
    Push a confirmed evaluation to Wikidata as a new statement.

    Args:
        evaluation: PropertyEvaluation, PositionEvaluation, or BirthplaceEvaluation
        jwt_token: MediaWiki OAuth 2.0 JWT token
        db: Database session

    Returns:
        True if successful, False if failed
    """
    if not evaluation.is_confirmed:
        logger.info("Skipping unconfirmed evaluation")
        return True  # Not an error, just skip

    try:
        if isinstance(evaluation, PropertyEvaluation):
            return await _push_property_evaluation(evaluation, jwt_token, db)
        elif isinstance(evaluation, PositionEvaluation):
            return await _push_position_evaluation(evaluation, jwt_token, db)
        elif isinstance(evaluation, BirthplaceEvaluation):
            return await _push_birthplace_evaluation(evaluation, jwt_token, db)
        else:
            logger.error(f"Unknown evaluation type: {type(evaluation)}")
            return False

    except Exception as e:
        logger.error(f"Error pushing evaluation to Wikidata: {e}")
        return False


async def _push_property_evaluation(
    evaluation: PropertyEvaluation,
    jwt_token: str,
    db: Session,
) -> bool:
    """Push a confirmed property evaluation to Wikidata."""
    prop = db.get(Property, evaluation.property_id)
    if not prop or not prop.politician:
        logger.error(f"Property {evaluation.property_id} or politician not found")
        return False

    if prop.type == "date_of_birth":
        statement_id = await create_birth_date_statement(
            prop.politician.wikidata_id,
            prop.value,
            prop.archived_page.original_url,
            jwt_token,
        )
        return statement_id is not None
    else:
        logger.warning(f"Property type {prop.type} not yet supported")
        return True  # Don't fail on unsupported types


async def _push_position_evaluation(
    evaluation: PositionEvaluation,
    jwt_token: str,
    db: Session,
) -> bool:
    """Push a confirmed position evaluation to Wikidata."""
    position = db.get(HoldsPosition, evaluation.holds_position_id)
    if not position or not position.politician or not position.position:
        logger.error(
            f"Position {evaluation.holds_position_id} or related entities not found"
        )
        return False

    statement_id = await create_position_held_statement(
        position.politician.wikidata_id,
        position.position.wikidata_id,
        position.start_date,
        position.end_date,
        position.archived_page.original_url,
        jwt_token,
    )
    return statement_id is not None


async def _push_birthplace_evaluation(
    evaluation: BirthplaceEvaluation,
    jwt_token: str,
    db: Session,
) -> bool:
    """Push a confirmed birthplace evaluation to Wikidata."""
    birthplace = db.get(BornAt, evaluation.born_at_id)
    if not birthplace or not birthplace.politician or not birthplace.location:
        logger.error(
            f"Birthplace {evaluation.born_at_id} or related entities not found"
        )
        return False

    statement_id = await create_birthplace_statement(
        birthplace.politician.wikidata_id,
        birthplace.location.wikidata_id,
        birthplace.archived_page.original_url,
        jwt_token,
    )
    return statement_id is not None
