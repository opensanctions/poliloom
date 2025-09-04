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
    PropertyType,
)

logger = logging.getLogger(__name__)

# Get API root from environment variable, default to test site for safety
WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://test.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


def _parse_date_for_wikidata(date_value: str) -> Optional[Dict[str, Any]]:
    """
    Parse a date string and convert it to Wikidata time format.

    Args:
        date_value: Date string (ISO format, partial date like "1962", etc.)

    Returns:
        Wikidata time value dict or None if parsing fails
    """
    try:
        # Try to parse as full date first
        dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        return {
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
            return {
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

    logger.info(
        f"Creating statement for entity {entity_id} with property {property_id}"
    )

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
                logger.info(
                    f"Successfully created statement {statement_id} for entity {entity_id} with property {property_id}"
                )
                return statement_id
            else:
                logger.error(
                    f"Failed to create statement for entity {entity_id} with property {property_id}: HTTP {response.status_code} - {response.text}"
                )
                return None

    except httpx.RequestError as e:
        logger.error(
            f"Network error creating statement for entity {entity_id} with property {property_id}: {e}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error creating statement for entity {entity_id} with property {property_id}: {e}"
        )
        return None


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
        logger.info(
            f"Skipping unconfirmed evaluation {evaluation.id} (type: {type(evaluation).__name__})"
        )
        return True  # Not an error, just skip

    logger.info(
        f"Pushing confirmed evaluation {evaluation.id} (type: {type(evaluation).__name__}) to Wikidata"
    )

    try:
        if isinstance(evaluation, PropertyEvaluation):
            success = await _push_property_evaluation(evaluation, jwt_token, db)
            if success:
                logger.info(
                    f"Successfully pushed PropertyEvaluation {evaluation.id} to Wikidata"
                )
            else:
                logger.error(
                    f"Failed to push PropertyEvaluation {evaluation.id} to Wikidata"
                )
            return success
        elif isinstance(evaluation, PositionEvaluation):
            success = await _push_position_evaluation(evaluation, jwt_token, db)
            if success:
                logger.info(
                    f"Successfully pushed PositionEvaluation {evaluation.id} to Wikidata"
                )
            else:
                logger.error(
                    f"Failed to push PositionEvaluation {evaluation.id} to Wikidata"
                )
            return success
        elif isinstance(evaluation, BirthplaceEvaluation):
            success = await _push_birthplace_evaluation(evaluation, jwt_token, db)
            if success:
                logger.info(
                    f"Successfully pushed BirthplaceEvaluation {evaluation.id} to Wikidata"
                )
            else:
                logger.error(
                    f"Failed to push BirthplaceEvaluation {evaluation.id} to Wikidata"
                )
            return success
        else:
            logger.error(
                f"Unknown evaluation type: {type(evaluation)} for evaluation {evaluation.id}"
            )
            return False

    except Exception as e:
        logger.error(
            f"Error pushing evaluation {evaluation.id} (type: {type(evaluation).__name__}) to Wikidata: {e}"
        )
        return False


async def _push_property_evaluation(
    evaluation: PropertyEvaluation,
    jwt_token: str,
    db: Session,
) -> bool:
    """Push a confirmed property evaluation to Wikidata."""
    prop = db.get(Property, evaluation.property_id)
    if not prop or not prop.politician:
        logger.error(
            f"Property {evaluation.property_id} or politician not found for PropertyEvaluation {evaluation.id}"
        )
        return False

    logger.info(
        f"Processing PropertyEvaluation {evaluation.id}: property type '{prop.type}', politician {prop.politician.wikidata_id}"
    )

    # Map property types to Wikidata properties
    property_map = {
        PropertyType.BIRTH_DATE: "P569",
        PropertyType.DEATH_DATE: "P570",
    }

    property_id = property_map[prop.type]
    logger.info(
        f"Creating {prop.type} statement for politician {prop.politician.wikidata_id} with value '{prop.value}'"
    )

    # Format date value for Wikidata
    wikidata_value = _parse_date_for_wikidata(prop.value)
    if not wikidata_value:
        return False

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "string", "value": prop.archived_page.url},
        }
    ]

    statement_id = await create_statement(
        prop.politician.wikidata_id,
        property_id,
        wikidata_value,
        references=references,
        jwt_token=jwt_token,
    )
    if statement_id:
        logger.info(
            f"{prop.type} statement {statement_id} created successfully for politician {prop.politician.wikidata_id}"
        )
    return statement_id is not None


async def _push_position_evaluation(
    evaluation: PositionEvaluation,
    jwt_token: str,
    db: Session,
) -> bool:
    """Push a confirmed position evaluation to Wikidata."""
    position = db.get(HoldsPosition, evaluation.holds_position_id)
    if not position or not position.politician or not position.position:
        logger.error(
            f"Position {evaluation.holds_position_id} or related entities not found for PositionEvaluation {evaluation.id}"
        )
        return False

    logger.info(
        f"Processing PositionEvaluation {evaluation.id}: politician {position.politician.wikidata_id} held position {position.position.wikidata_id} ({position.position.name})"
    )

    logger.info(
        f"Creating position statement for politician {position.politician.wikidata_id} with position {position.position.wikidata_id}, dates: {position.start_date} to {position.end_date}"
    )

    wikidata_value = {
        "type": "wikibase-entityid",
        "value": {"id": position.position.wikidata_id},
    }

    # Create qualifiers for start/end dates
    qualifiers = []

    if position.start_date:
        start_date_value = _parse_date_for_wikidata(position.start_date)
        if start_date_value:
            qualifiers.append(
                {
                    "property": {"id": "P580"},  # Start time
                    "value": start_date_value,
                }
            )
        else:
            logger.warning(f"Cannot parse start date: {position.start_date}")

    if position.end_date:
        end_date_value = _parse_date_for_wikidata(position.end_date)
        if end_date_value:
            qualifiers.append(
                {
                    "property": {"id": "P582"},  # End time
                    "value": end_date_value,
                }
            )
        else:
            logger.warning(f"Cannot parse end date: {position.end_date}")

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "string", "value": position.archived_page.url},
        }
    ]

    statement_id = await create_statement(
        position.politician.wikidata_id,
        "P39",  # Position held
        wikidata_value,
        references=references,
        qualifiers=qualifiers if qualifiers else None,
        jwt_token=jwt_token,
    )
    if statement_id:
        logger.info(
            f"Position statement {statement_id} created successfully for politician {position.politician.wikidata_id}"
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
            f"Birthplace {evaluation.born_at_id} or related entities not found for BirthplaceEvaluation {evaluation.id}"
        )
        return False

    logger.info(
        f"Processing BirthplaceEvaluation {evaluation.id}: politician {birthplace.politician.wikidata_id} born in {birthplace.location.wikidata_id} ({birthplace.location.name})"
    )

    logger.info(
        f"Creating birthplace statement for politician {birthplace.politician.wikidata_id} with location {birthplace.location.wikidata_id}"
    )

    wikidata_value = {
        "type": "wikibase-entityid",
        "value": {"id": birthplace.location.wikidata_id},
    }

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "string", "value": birthplace.archived_page.url},
        }
    ]

    statement_id = await create_statement(
        birthplace.politician.wikidata_id,
        "P19",  # Place of birth
        wikidata_value,
        references=references,
        jwt_token=jwt_token,
    )
    if statement_id:
        logger.info(
            f"Birthplace statement {statement_id} created successfully for politician {birthplace.politician.wikidata_id}"
        )
    return statement_id is not None
