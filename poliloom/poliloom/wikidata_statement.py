"""Wikidata statement creation functions for pushing confirmed evaluations to Wikidata."""

import logging
import os
from typing import Dict, Any, Optional, List

import httpx
from sqlalchemy.orm import Session

from .models import (
    Property,
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
        evaluation: Evaluation
        jwt_token: MediaWiki OAuth 2.0 JWT token
        db: Database session

    Returns:
        True if successful, False if failed
    """
    # Access politician relationship while entity is bound to session
    politician_wikidata_id = evaluation.property.politician.wikidata_id

    # Check if this is existing Wikidata data (has statement_id but no archived_page_id)
    is_existing_statement = (
        evaluation.property.statement_id and not evaluation.property.archived_page_id
    )

    try:
        if not evaluation.is_confirmed and is_existing_statement:
            # Negative evaluation of existing statement - delete from Wikidata
            logger.info(
                f"Processing negative evaluation {evaluation.id} - deleting from Wikidata"
            )

            logger.info(
                f"Deleting property statement {evaluation.property.statement_id} for politician {politician_wikidata_id}"
            )

            await delete_statement(
                politician_wikidata_id,
                evaluation.property.statement_id,
                jwt_token,
            )

            # Only delete from database if Wikidata deletion succeeded
            db.delete(evaluation.property)
            db.commit()
            logger.info(
                f"Successfully deleted property statement for politician {politician_wikidata_id}"
            )

        elif not evaluation.is_confirmed and not is_existing_statement:
            # Negative evaluation of extracted data - delete from database only
            logger.info(
                f"Processing negative evaluation {evaluation.id} - removing extracted data"
            )

            db.delete(evaluation.property)
            db.commit()
            logger.info(
                f"Successfully removed property extracted data for politician {politician_wikidata_id}"
            )

        elif evaluation.is_confirmed and not is_existing_statement:
            # Confirmed evaluation of extracted data - create new statement
            logger.info(
                f"Processing confirmed evaluation {evaluation.id} - creating in Wikidata"
            )

            logger.info(
                f"Processing evaluation {evaluation.id}: politician {politician_wikidata_id}"
            )

            # Build statement data using the appropriate builder function
            wikidata_value, qualifiers = _build_property_statement(evaluation.property)

            # Use qualifiers from Property model if available, otherwise use builder result
            if evaluation.property.qualifiers_json:
                qualifiers = evaluation.property.qualifiers_json

            # Create statement using property type as Wikidata property ID
            statement_id = await create_statement(
                politician_wikidata_id,
                evaluation.property.type.value,  # PropertyType enum values are the Wikidata property IDs
                wikidata_value,
                references=evaluation.property.references_json,
                qualifiers=qualifiers,
                jwt_token=jwt_token,
            )

            # Update the evaluation.property with the statement ID
            evaluation.property.statement_id = statement_id
            db.commit()
            logger.info(
                f"Successfully pushed evaluation {evaluation.id} to Wikidata with statement ID {statement_id}"
            )

        else:
            # Skip other cases (confirmed existing statements)
            logger.info(
                f"Skipping evaluation {evaluation.id} - no Wikidata action needed"
            )

        return True

    except Exception as e:
        logger.error(f"Error processing evaluation {evaluation.id}: {e}")
        return False


def _build_property_statement(property: Property) -> tuple[dict, list]:
    """
    Build statement data for Property.

    Returns:
        tuple of (wikidata_value, qualifiers)
    """
    # Handle date properties (birth date, death date)
    if property.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
        if not property.value:
            raise ValueError(
                f"Date value is required for property type {property.type}"
            )
        wikidata_value = _parse_date_for_wikidata(property.value)
        if not wikidata_value:
            raise ValueError(f"Cannot parse date value: {property.value}")
        return wikidata_value, None

    # Handle property properties (birthplace, position, citizenship)
    elif property.type in [
        PropertyType.BIRTHPLACE,
        PropertyType.POSITION,
        PropertyType.CITIZENSHIP,
    ]:
        if not property.entity_id:
            raise ValueError(
                f"Property ID is required for property type {property.type}"
            )
        wikidata_value = {"type": "value", "content": property.entity_id}
        return wikidata_value, None

    else:
        raise ValueError(f"Unknown property type: {property.type}")
