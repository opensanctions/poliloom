"""Wikidata REST API statement and entity creation functions."""

import logging
import os
from typing import Any

import httpx2

logger = logging.getLogger(__name__)


# Get API root from environment variable
WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://www.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


class WikidataApiError(Exception):
    """Raised when the Wikidata API rejects or fails an operation."""


async def create_entity(
    label: str,
    description: str | None = None,
    jwt_token: str | None = None,
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
        httpx2.RequestError: For network errors
        WikidataApiError: For other API errors
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

    async with httpx2.AsyncClient(timeout=30.0) as client:
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
                raise WikidataApiError("No entity ID returned from Wikidata API")
            logger.info(f"Successfully created entity {entity_id} with label: {label}")
            return entity_id
        else:
            error_msg = f"Failed to create entity with label '{label}': HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WikidataApiError(error_msg)


async def create_statement(
    entity_id: str,
    property_id: str,
    value: dict[str, Any],
    references: list[dict[str, Any]] | None = None,
    qualifiers: list[dict[str, Any]] | None = None,
    jwt_token: str | None = None,
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
        httpx2.RequestError: For network errors
        WikidataApiError: For other API errors including failed API responses
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

    async with httpx2.AsyncClient(timeout=30.0) as client:
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
                raise WikidataApiError("No statement ID returned from Wikidata API")
            logger.info(
                f"Successfully created statement {statement_id} for entity {entity_id} with property {property_id}"
            )
            return statement_id
        else:
            error_msg = f"Failed to create statement for entity {entity_id} with property {property_id}: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise WikidataApiError(error_msg)
