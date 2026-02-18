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
from .wikidata_date import WikidataDate

logger = logging.getLogger(__name__)


# Get API root from environment variable
WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://www.wikidata.org/w/rest.php/wikibase/v1"
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


def prepare_property_for_statement(
    prop: Any,
) -> tuple[Dict[str, Any], Optional[List[Dict[str, Any]]]]:
    """
    Convert a Property object into REST API format for statement creation.

    Args:
        prop: Property object with type, value, entity_id, qualifiers_json, etc.

    Returns:
        Tuple of (value_dict, qualifiers_list) ready for create_statement

    Raises:
        ValueError: If property type is invalid or date format is wrong
    """

    # Build statement value based on property type
    if prop.type in [PropertyType.BIRTH_DATE, PropertyType.DEATH_DATE]:
        # Convert stored date to proper Wikidata format
        wikidata_date = WikidataDate.from_wikidata_time(
            prop.value, prop.value_precision
        )
        if not wikidata_date:
            raise ValueError(f"Invalid date for property {prop.id}: {prop.value}")
        value = {
            "type": "value",
            "content": wikidata_date.to_wikidata_value(),
        }
    elif prop.type in [
        PropertyType.BIRTHPLACE,
        PropertyType.POSITION,
        PropertyType.CITIZENSHIP,
    ]:
        value = {
            "type": "value",
            "content": prop.entity_id,
        }
    else:
        raise ValueError(f"Unknown property type: {prop.type}")

    # Convert qualifiers from Action API format to REST API format
    qualifiers = None
    if prop.qualifiers_json:
        qualifiers = _convert_qualifiers_to_rest_api(prop.qualifiers_json)

    return value, qualifiers


async def create_entity(
    label: str,
    description: Optional[str] = None,
    jwt_token: str = None,
) -> str:
    """
    Create a new Wikidata entity (item).

    Args:
        label: Entity label (name)
        description: Optional entity description
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Returns:
        The new entity's QID (e.g., "Q123456")

    Raises:
        ValueError: If JWT token is missing
        httpx.RequestError: For network errors
        Exception: For other API errors
    """
    if not jwt_token:
        raise ValueError("JWT token is required for Wikidata API calls")

    logger.info(f"Creating new Wikidata entity with label: {label}")

    url = f"{WIKIDATA_API_ROOT}/entities/items"

    # Build item data structure - set both en and mul (multilingual) labels
    item_data = {"item": {"labels": {"en": label, "mul": label}}}

    # Add description if provided
    if description:
        item_data["item"]["descriptions"] = {"en": description}

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=item_data, headers=headers)

        # Debug logging for request details
        if logger.isEnabledFor(logging.DEBUG):
            request = response.request
            logger.debug(f"Request URL: {request.url}")
            logger.debug(f"Request Headers: {dict(request.headers)}")
            logger.debug(f"Request Body: {request.content.decode('utf-8')}")
            logger.debug(f"Response Status Code: {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            entity_id = result.get("id")
            if not entity_id:
                raise Exception("No entity ID returned from Wikidata API")
            logger.info(f"Successfully created entity {entity_id} with label: {label}")
            return entity_id
        else:
            error_msg = f"Failed to create entity with label '{label}': HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)


async def deprecate_statement(
    entity_id: str,
    statement_id: str,
    jwt_token: str,
) -> None:
    """
    Deprecate a Wikidata statement by setting its rank to 'deprecated'.

    Args:
        entity_id: Wikidata entity ID (e.g., 'Q42')
        statement_id: Statement ID to deprecate
        jwt_token: MediaWiki OAuth 2.0 JWT token

    Raises:
        ValueError: If JWT token is missing
        httpx.RequestError: For network errors
        Exception: For other API errors
    """
    if not jwt_token:
        raise ValueError("JWT token is required for Wikidata API calls")

    logger.info(f"Deprecating statement {statement_id} on entity {entity_id}")

    url = f"{WIKIDATA_API_ROOT}/statements/{statement_id}"

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json-patch+json",
        "User-Agent": USER_AGENT,
    }

    # Use JSON Patch format to update the rank
    patch_data = [{"op": "replace", "path": "/rank", "value": "deprecated"}]

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.patch(url, json={"patch": patch_data}, headers=headers)

        # Debug logging for request details
        if logger.isEnabledFor(logging.DEBUG):
            request = response.request
            logger.debug(f"Request URL: {request.url}")
            logger.debug(f"Request Headers: {dict(request.headers)}")
            logger.debug(f"Request Body: {request.content.decode('utf-8')}")
            logger.debug(f"Response Status Code: {response.status_code}")

        if response.status_code == 200:
            logger.info(
                f"Successfully deprecated statement {statement_id} on entity {entity_id}"
            )
            return
        elif response.status_code == 404:
            # Statement or entity not found
            logger.warning(f"Statement {statement_id} or entity {entity_id} not found")
            raise Exception(f"Statement {statement_id} or entity {entity_id} not found")
        else:
            # Other errors - raise exception
            raise Exception(
                f"Failed to deprecate statement {statement_id} on entity {entity_id}: HTTP {response.status_code} - {response.text}"
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

    if references:
        statement_data["statement"]["references"] = references

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
    Push an evaluation to Wikidata - either create a new statement or deprecate an existing one.

    For accepted evaluations of extracted data: creates new statements (Accept)
    For rejected evaluations of extracted data: soft deletes from database (Reject)
    For rejected evaluations of existing statements: deprecates statements on Wikidata (Deprecate)

    Args:
        evaluation: Evaluation
        jwt_token: MediaWiki OAuth 2.0 JWT token
        db: Database session

    Returns:
        True if successful, False if failed
    """
    # Access politician relationship while entity is bound to session
    politician_wikidata_id = evaluation.property.politician.wikidata_id

    # Check if this is existing Wikidata data (has statement_id)
    is_existing_statement = bool(evaluation.property.statement_id)

    try:
        if not evaluation.is_accepted and is_existing_statement:
            # Rejected evaluation of existing statement - deprecate on Wikidata
            logger.info(
                f"Processing rejected evaluation {evaluation.id} - deprecating on Wikidata"
            )

            logger.info(
                f"Deprecating property statement {evaluation.property.statement_id} for politician {politician_wikidata_id}"
            )

            try:
                await deprecate_statement(
                    politician_wikidata_id,
                    evaluation.property.statement_id,
                    jwt_token,
                )

                # Soft delete from database if Wikidata deprecation succeeded
                evaluation.property.deleted_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(
                    f"Successfully processed deprecation for property statement for politician {politician_wikidata_id}"
                )
            except Exception as e:
                # Wikidata deprecation failed - don't delete from database, but log the issue
                logger.error(
                    f"Wikidata deprecation failed for statement {evaluation.property.statement_id}: {e} - keeping in database"
                )
                return False

        elif not evaluation.is_accepted and not is_existing_statement:
            # Rejected evaluation of extracted data - soft delete from database only
            logger.info(
                f"Processing rejected evaluation {evaluation.id} - soft deleting extracted data"
            )

            evaluation.property.deleted_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(
                f"Successfully soft deleted property extracted data for politician {politician_wikidata_id}"
            )

        elif evaluation.is_accepted and not is_existing_statement:
            # Accepted evaluation of extracted data - create new statement
            logger.info(
                f"Processing accepted evaluation {evaluation.id} - creating in Wikidata"
            )

            logger.info(
                f"Processing evaluation {evaluation.id}: politician {politician_wikidata_id}"
            )

            # Prepare property for statement creation
            wikidata_value, qualifiers = prepare_property_for_statement(
                evaluation.property
            )

            # Build reference blocks from all PropertyReferences
            references = [
                {"parts": ref.archived_page.create_references_json()}
                for ref in evaluation.property.property_references
            ] or None

            # Create statement using property type as Wikidata property ID
            statement_id = await create_statement(
                politician_wikidata_id,
                evaluation.property.type.value,  # PropertyType enum values are the Wikidata property IDs
                wikidata_value,
                references=references,
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
            # Skip other cases (accepted existing statements)
            logger.info(
                f"Skipping evaluation {evaluation.id} - no Wikidata action needed"
            )

        return True

    except Exception as e:
        logger.error(f"Error processing evaluation {evaluation.id}: {e}")
        return False
