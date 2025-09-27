"""Wikidata statement creation functions for pushing confirmed evaluations to Wikidata."""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import httpx
from sqlalchemy.orm import Session

from .models import (
    PropertyType,
)

logger = logging.getLogger(__name__)


# Get API root from environment variable, default to test site for safety
WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://test.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


def _convert_qualifiers_to_rest_api(
    qualifiers_json: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Convert qualifiers from Action API format to REST API format."""
    rest_qualifiers = []

    for property_id, qualifier_list in qualifiers_json.items():
        for qualifier in qualifier_list:
            rest_qualifier = {"property": {"id": property_id}}

            if qualifier.get("snaktype") == "value" and "datavalue" in qualifier:
                datavalue = qualifier["datavalue"]
                if datavalue["type"] == "wikibase-entityid":
                    content = datavalue["value"]["id"]
                else:
                    content = datavalue["value"]

                rest_qualifier["value"] = {"type": "value", "content": content}
            else:
                rest_qualifier["value"] = {"type": qualifier.get("snaktype", "value")}

            rest_qualifiers.append(rest_qualifier)

    return rest_qualifiers


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
        Exception: For other API errors
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
        elif response.status_code == 404:
            # Statement or entity not found - already deleted, which is the desired state
            logger.info(
                f"Statement {statement_id} or entity {entity_id} not found - already deleted"
            )
            return
        else:
            # Other errors - raise exception
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

            try:
                await delete_statement(
                    politician_wikidata_id,
                    evaluation.property.statement_id,
                    jwt_token,
                )

                # Soft delete from database if Wikidata deletion succeeded or statement was already deleted
                evaluation.property.deleted_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(
                    f"Successfully processed deletion for property statement for politician {politician_wikidata_id}"
                )
            except Exception as e:
                # Wikidata deletion failed - don't delete from database, but log the issue
                logger.error(
                    f"Wikidata deletion failed for statement {evaluation.property.statement_id}: {e} - keeping in database"
                )
                return False

        elif not evaluation.is_confirmed and not is_existing_statement:
            # Negative evaluation of extracted data - delete from database only
            logger.info(
                f"Processing negative evaluation {evaluation.id} - removing extracted data"
            )

            evaluation.property.deleted_at = datetime.now(timezone.utc)
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

            # Build statement value directly from Property fields
            if evaluation.property.type in [
                PropertyType.BIRTH_DATE,
                PropertyType.DEATH_DATE,
            ]:
                wikidata_value = {"type": "value", "content": evaluation.property.value}
            elif evaluation.property.type in [
                PropertyType.BIRTHPLACE,
                PropertyType.POSITION,
                PropertyType.CITIZENSHIP,
            ]:
                wikidata_value = {
                    "type": "value",
                    "content": evaluation.property.entity_id,
                }

            # Convert qualifiers from Action API format to REST API format
            qualifiers = None
            if evaluation.property.qualifiers_json:
                qualifiers = _convert_qualifiers_to_rest_api(
                    evaluation.property.qualifiers_json
                )

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
