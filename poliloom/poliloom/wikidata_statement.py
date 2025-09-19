"""Wikidata statement creation functions for pushing confirmed evaluations to Wikidata."""

import logging
import os
from typing import Dict, Any, Optional, List

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
from .wikidata_date import WikidataDate

logger = logging.getLogger(__name__)

# Get API root from environment variable, default to test site for safety
WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://test.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


def _parse_date_for_wikidata(date_value: str) -> Optional[Dict[str, Any]]:
    """
    Parse a date string and convert it to Wikidata time format.

    Supports YYYY, YYYY-MM, and YYYY-MM-DD formats.

    Args:
        date_value: Date string in YYYY, YYYY-MM, or YYYY-MM-DD format

    Returns:
        Wikidata time value dict or None if parsing fails
    """
    try:
        wikidata_date = WikidataDate.from_date_string(date_value)
        if not wikidata_date:
            logger.error(f"Cannot parse date value: {date_value}")
            return None

        return wikidata_date.to_wikidata_value()

    except Exception as e:
        logger.error(f"Cannot parse date value: {date_value} - {e}")
        return None


async def delete_statement(
    entity_id: str,
    statement_id: str,
    jwt_token: str,
) -> bool:
    """
    Delete a Wikidata statement.

    Args:
        entity_id: Wikidata entity ID (e.g., 'Q42')
        statement_id: Statement ID to delete
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Returns:
        True if successful, False if failed
    """
    if not jwt_token:
        logger.error("JWT token is required for Wikidata API calls")
        return False

    logger.info(f"Deleting statement {statement_id} from entity {entity_id}")

    url = f"{WIKIDATA_API_ROOT}/entities/items/{entity_id}/statements/{statement_id}"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url, headers=headers)

            # Debug logging for request details
            if logger.isEnabledFor(logging.DEBUG):
                request = response.request
                logger.debug(f"Request URL: {request.url}")
                logger.debug(f"Request Headers: {dict(request.headers)}")
                logger.debug(f"Response Status Code: {response.status_code}")

            if response.status_code == 200:
                logger.info(
                    f"Successfully deleted statement {statement_id} from entity {entity_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to delete statement {statement_id} from entity {entity_id}: HTTP {response.status_code} - {response.text}"
                )
                return False

    except httpx.RequestError as e:
        logger.error(
            f"Network error deleting statement {statement_id} from entity {entity_id}: {e}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error deleting statement {statement_id} from entity {entity_id}: {e}"
        )
        return False


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

            # Debug logging for request details
            if logger.isEnabledFor(logging.DEBUG):
                request = response.request
                logger.debug(f"Request URL: {request.url}")
                logger.debug(f"Request Headers: {dict(request.headers)}")
                logger.debug(f"Request Body: {request.content.decode('utf-8')}")
                logger.debug(f"Response Status Code: {response.status_code}")

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


async def push_evaluation(
    evaluation: Any,
    jwt_token: str,
    db: Session,
) -> bool:
    """
    Push an evaluation to Wikidata - either create a new statement or delete an existing one.

    For confirmed evaluations of extracted data: creates new statements
    For negative evaluations of existing statements: deletes statements

    Args:
        evaluation: PropertyEvaluation, PositionEvaluation, or BirthplaceEvaluation
        jwt_token: MediaWiki OAuth 2.0 JWT token
        db: Database session

    Returns:
        True if successful, False if failed
    """
    eval_type = type(evaluation).__name__

    # Determine if this is a negative evaluation of existing data or confirmed extracted data
    entity_map = {
        "PropertyEvaluation": ("property_id", Property),
        "PositionEvaluation": ("holds_position_id", HoldsPosition),
        "BirthplaceEvaluation": ("born_at_id", BornAt),
    }

    entity_attr, entity_class = entity_map.get(eval_type, (None, None))
    if not entity_attr:
        logger.error(
            f"Unknown evaluation type: {eval_type} for evaluation {evaluation.id}"
        )
        return False

    entity_id = getattr(evaluation, entity_attr)
    entity = db.get(entity_class, entity_id)

    if not entity:
        logger.error(
            f"{entity_class.__name__} {entity_id} not found for {eval_type} {evaluation.id}"
        )
        return False

    # Check if this is existing Wikidata data (has statement_id but no archived_page_id)
    is_existing_statement = entity.statement_id and not entity.archived_page_id

    if not evaluation.is_confirmed and is_existing_statement:
        # Negative evaluation of existing statement - delete it
        logger.info(
            f"Processing negative evaluation {evaluation.id} (type: {eval_type}) - deleting from Wikidata"
        )
        return await delete_negative_evaluation(evaluation, jwt_token, db)
    elif evaluation.is_confirmed and not is_existing_statement:
        # Confirmed evaluation of extracted data - create new statement
        logger.info(
            f"Processing confirmed evaluation {evaluation.id} (type: {eval_type}) - creating in Wikidata"
        )
        return await push_confirmed_evaluation(evaluation, jwt_token, db)
    else:
        # Skip other cases (confirmed existing statements, negative extracted data)
        logger.info(
            f"Skipping evaluation {evaluation.id} (type: {eval_type}) - no Wikidata action needed"
        )
        return True


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
    eval_type = type(evaluation).__name__

    if not evaluation.is_confirmed:
        logger.info(
            f"Skipping unconfirmed evaluation {evaluation.id} (type: {eval_type})"
        )
        return True  # Not an error, just skip

    logger.info(
        f"Pushing confirmed evaluation {evaluation.id} (type: {eval_type}) to Wikidata"
    )

    try:
        handler_map = {
            "PropertyEvaluation": _push_property_evaluation,
            "PositionEvaluation": _push_position_evaluation,
            "BirthplaceEvaluation": _push_birthplace_evaluation,
        }

        handler = handler_map.get(eval_type)
        if not handler:
            logger.error(
                f"Unknown evaluation type: {eval_type} for evaluation {evaluation.id}"
            )
            return False

        success = await handler(evaluation, jwt_token, db)
        if success:
            logger.info(f"Successfully pushed {eval_type} {evaluation.id} to Wikidata")
        else:
            logger.error(f"Failed to push {eval_type} {evaluation.id} to Wikidata")
        return success

    except Exception as e:
        logger.error(
            f"Error pushing evaluation {evaluation.id} (type: {eval_type}) to Wikidata: {e}"
        )
        return False


async def delete_negative_evaluation(
    evaluation: Any,
    jwt_token: str,
    db: Session,
) -> bool:
    """
    Delete a statement from Wikidata for a negative evaluation of existing data.

    Args:
        evaluation: PropertyEvaluation, PositionEvaluation, or BirthplaceEvaluation
        jwt_token: MediaWiki OAuth 2.0 JWT token
        db: Database session

    Returns:
        True if successful, False if failed
    """
    eval_type = type(evaluation).__name__

    if evaluation.is_confirmed:
        logger.info(
            f"Skipping confirmed evaluation {evaluation.id} (type: {eval_type}) - not for deletion"
        )
        return True  # Not an error, just skip

    logger.info(
        f"Deleting Wikidata statement for negative evaluation {evaluation.id} (type: {eval_type})"
    )

    try:
        # Get the related entity and politician based on evaluation type
        entity_map = {
            "PropertyEvaluation": ("property_id", Property),
            "PositionEvaluation": ("holds_position_id", HoldsPosition),
            "BirthplaceEvaluation": ("born_at_id", BornAt),
        }

        entity_attr, entity_class = entity_map.get(eval_type, (None, None))
        if not entity_attr:
            logger.error(
                f"Unknown evaluation type: {eval_type} for evaluation {evaluation.id}"
            )
            return False

        entity_id = getattr(evaluation, entity_attr)
        entity = db.get(entity_class, entity_id)

        if not entity or not entity.politician:
            logger.error(
                f"{entity_class.__name__} {entity_id} or politician not found for {eval_type} {evaluation.id}"
            )
            return False

        if not entity.statement_id:
            logger.error(
                f"No statement ID found for {entity_class.__name__.lower()} {entity_id} - cannot delete from Wikidata"
            )
            return False

        logger.info(
            f"Deleting {entity_class.__name__.lower()} statement {entity.statement_id} for politician {entity.politician.wikidata_id}"
        )

        success = await delete_statement(
            entity.politician.wikidata_id,
            entity.statement_id,
            jwt_token,
        )

        if success:
            # Remove the statement ID from the database since it's deleted
            entity.statement_id = None
            db.commit()
            logger.info(
                f"Successfully deleted {entity_class.__name__.lower()} statement for politician {entity.politician.wikidata_id}"
            )

        return success

    except Exception as e:
        logger.error(
            f"Error deleting statement for evaluation {evaluation.id} (type: {eval_type}): {e}"
        )
        return False


async def _push_property_evaluation(
    evaluation: PropertyEvaluation,
    jwt_token: str,
    db: Session,
) -> bool:
    """Push a confirmed property evaluation to Wikidata."""
    property = db.get(Property, evaluation.property_id)
    if not property or not property.politician:
        logger.error(
            f"Property {evaluation.property_id} or politician not found for PropertyEvaluation {evaluation.id}"
        )
        return False

    logger.info(
        f"Processing PropertyEvaluation {evaluation.id}: property type '{property.type}', politician {property.politician.wikidata_id}"
    )

    # Map property types to Wikidata properties
    property_map = {
        PropertyType.BIRTH_DATE: "P569",
        PropertyType.DEATH_DATE: "P570",
    }

    property_id = property_map[property.type]
    logger.info(
        f"Creating {property.type} statement for politician {property.politician.wikidata_id} with value '{property.value}'"
    )

    # Format date value for Wikidata
    wikidata_value = _parse_date_for_wikidata(property.value)
    if not wikidata_value:
        return False

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "value", "content": property.archived_page.url},
        }
    ]

    statement_id = await create_statement(
        property.politician.wikidata_id,
        property_id,
        wikidata_value,
        references=references,
        jwt_token=jwt_token,
    )
    if statement_id:
        # Store the statement ID in the database
        property.statement_id = statement_id
        db.commit()
        logger.info(
            f"{property.type} statement {statement_id} created successfully for politician {property.politician.wikidata_id}"
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
        "type": "value",
        "content": position.position.wikidata_id,
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
            "value": {"type": "value", "content": position.archived_page.url},
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
        # Store the statement ID in the database
        position.statement_id = statement_id
        db.commit()
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
        "type": "value",
        "content": birthplace.location.wikidata_id,
    }

    # Create reference to Wikipedia article
    references = [
        {
            "property": {"id": "P854"},  # Reference URL
            "value": {"type": "value", "content": birthplace.archived_page.url},
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
        # Store the statement ID in the database
        birthplace.statement_id = statement_id
        db.commit()
        logger.info(
            f"Birthplace statement {statement_id} created successfully for politician {birthplace.politician.wikidata_id}"
        )
    return statement_id is not None
