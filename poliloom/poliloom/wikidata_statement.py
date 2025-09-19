"""Wikidata statement creation functions for pushing confirmed evaluations to Wikidata."""

import logging
import os
from typing import Dict, Any, Optional, List

import httpx
from sqlalchemy.orm import Session

from .models import (
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
) -> None:
    """
    Delete a Wikidata statement.

    Args:
        entity_id: Wikidata entity ID (e.g., 'Q42')
        statement_id: Statement ID to delete
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Raises:
        ValueError: If JWT token is missing
        httpx.RequestError: For network errors
        Exception: For other errors including failed API responses
    """
    if not jwt_token:
        raise ValueError("JWT token is required for Wikidata API calls")

    logger.info(f"Deleting statement {statement_id} from entity {entity_id}")

    url = f"{WIKIDATA_API_ROOT}/entities/items/{entity_id}/statements/{statement_id}"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": USER_AGENT,
    }

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
            return
        else:
            raise Exception(
                f"Failed to delete statement {statement_id} from entity {entity_id}: HTTP {response.status_code} - {response.text}"
            )


async def create_statement(
    entity_id: str,
    property_id: str,
    value: Dict[str, Any],
    references: Optional[List[Dict[str, Any]]] = None,
    qualifiers: Optional[List[Dict[str, Any]]] = None,
    jwt_token: str = None,
) -> str:
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
        Statement ID

    Raises:
        ValueError: If JWT token is missing
        httpx.RequestError: For network errors
        Exception: For other errors including failed API responses
    """
    if not jwt_token:
        raise ValueError("JWT token is required for Wikidata API calls")

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
            if not statement_id:
                raise Exception("No statement ID returned from Wikidata API")
            logger.info(
                f"Successfully created statement {statement_id} for entity {entity_id} with property {property_id}"
            )
            return statement_id
        else:
            error_msg = f"Failed to create statement for entity {entity_id} with property {property_id}: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)


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

    # Map evaluation types to entity attributes, classes, and builder functions
    entity_map = {
        "PropertyEvaluation": ("property_id", Property, _build_property_statement),
        "PositionEvaluation": (
            "holds_position_id",
            HoldsPosition,
            _build_position_statement,
        ),
        "BirthplaceEvaluation": ("born_at_id", BornAt, _build_birthplace_statement),
    }

    entity_attr, entity_class, builder_func = entity_map.get(
        eval_type, (None, None, None)
    )
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

    # Access politician relationship while entity is bound to session
    politician_wikidata_id = entity.politician.wikidata_id

    # Check if this is existing Wikidata data (has statement_id but no archived_page_id)
    is_existing_statement = entity.statement_id and not entity.archived_page_id

    try:
        if not evaluation.is_confirmed and is_existing_statement:
            # Negative evaluation of existing statement - delete from Wikidata
            logger.info(
                f"Processing negative evaluation {evaluation.id} (type: {eval_type}) - deleting from Wikidata"
            )

            logger.info(
                f"Deleting {entity_class.__name__.lower()} statement {entity.statement_id} for politician {politician_wikidata_id}"
            )

            await delete_statement(
                politician_wikidata_id,
                entity.statement_id,
                jwt_token,
            )

            # Only delete from database if Wikidata deletion succeeded
            db.delete(entity)
            db.commit()
            logger.info(
                f"Successfully deleted {entity_class.__name__.lower()} statement for politician {politician_wikidata_id}"
            )

        elif not evaluation.is_confirmed and not is_existing_statement:
            # Negative evaluation of extracted data - delete from database only
            logger.info(
                f"Processing negative evaluation {evaluation.id} (type: {eval_type}) - removing extracted data"
            )

            db.delete(entity)
            db.commit()
            logger.info(
                f"Successfully removed {entity_class.__name__.lower()} extracted data for politician {politician_wikidata_id}"
            )

        elif evaluation.is_confirmed and not is_existing_statement:
            # Confirmed evaluation of extracted data - create new statement
            logger.info(
                f"Processing confirmed evaluation {evaluation.id} (type: {eval_type}) - creating in Wikidata"
            )

            logger.info(
                f"Processing {eval_type} {evaluation.id}: politician {politician_wikidata_id}"
            )

            # Build statement data using the appropriate builder function
            property_id, wikidata_value, qualifiers = builder_func(entity)

            # Create reference to Wikipedia article
            references = [
                {
                    "property": {"id": "P854"},  # Reference URL
                    "value": {"type": "value", "content": entity.archived_page.url},
                }
            ]

            # Create statement
            statement_id = await create_statement(
                politician_wikidata_id,
                property_id,
                wikidata_value,
                references=references,
                qualifiers=qualifiers,
                jwt_token=jwt_token,
            )

            # Update the entity with the statement ID
            entity.statement_id = statement_id
            db.commit()
            logger.info(
                f"Successfully pushed {eval_type} {evaluation.id} to Wikidata with statement ID {statement_id}"
            )

        else:
            # Skip other cases (confirmed existing statements)
            logger.info(
                f"Skipping evaluation {evaluation.id} (type: {eval_type}) - no Wikidata action needed"
            )

        return True

    except Exception as e:
        logger.error(
            f"Error processing evaluation {evaluation.id} (type: {eval_type}): {e}"
        )
        return False


def _build_property_statement(entity: Property) -> tuple[str, dict, list]:
    """
    Build statement data for PropertyEvaluation.

    Returns:
        tuple of (property_id, wikidata_value, qualifiers)
    """
    property_map = {
        PropertyType.BIRTH_DATE: "P569",
        PropertyType.DEATH_DATE: "P570",
    }

    property_id = property_map[entity.type]
    wikidata_value = _parse_date_for_wikidata(entity.value)
    if not wikidata_value:
        raise ValueError(f"Cannot parse date value: {entity.value}")

    return property_id, wikidata_value, None


def _build_position_statement(entity: HoldsPosition) -> tuple[str, dict, list]:
    """
    Build statement data for PositionEvaluation.

    Returns:
        tuple of (property_id, wikidata_value, qualifiers)
    """
    property_id = "P39"
    wikidata_value = {"type": "value", "content": entity.position.wikidata_id}

    # Create qualifiers for start/end dates
    qualifiers = []
    if entity.start_date:
        start_date_value = _parse_date_for_wikidata(entity.start_date)
        if start_date_value:
            qualifiers.append(
                {
                    "property": {"id": "P580"},  # Start time
                    "value": start_date_value,
                }
            )
        else:
            logger.warning(f"Cannot parse start date: {entity.start_date}")

    if entity.end_date:
        end_date_value = _parse_date_for_wikidata(entity.end_date)
        if end_date_value:
            qualifiers.append(
                {
                    "property": {"id": "P582"},  # End time
                    "value": end_date_value,
                }
            )
        else:
            logger.warning(f"Cannot parse end date: {entity.end_date}")

    return property_id, wikidata_value, qualifiers if qualifiers else None


def _build_birthplace_statement(entity: BornAt) -> tuple[str, dict, list]:
    """
    Build statement data for BirthplaceEvaluation.

    Returns:
        tuple of (property_id, wikidata_value, qualifiers)
    """
    property_id = "P19"
    wikidata_value = {"type": "value", "content": entity.location.wikidata_id}

    return property_id, wikidata_value, None
