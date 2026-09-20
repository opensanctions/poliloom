"""Execute accepted Actions against the Wikibase REST API.

The action's stored payload is sent verbatim; the API response body becomes
the cached Statement document, so statements are never reconstructed locally.
Preconditions travel inside the payload itself: edit bodies are JSON Patches
whose ``test`` ops fail the request server-side when the statement changed.
"""

import logging
import os
from datetime import UTC, datetime

import httpx2
from sqlalchemy.orm import Session

from ..models import Action, ActionKind, Statement

logger = logging.getLogger(__name__)

WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://www.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


def _failure_message(response: httpx2.Response) -> str:
    """Build the concise error message recorded on a failed API response.

    For 409 responses the Wikibase error code is included: it distinguishes
    ``patch-test-failed`` (the statement changed underneath us) from
    ``patch-target-not-found`` (an expected array entry or path is gone).
    """
    message = f"Wikidata API returned HTTP {response.status_code}"
    if response.status_code == 409:
        try:
            code = response.json()["error"]["code"]
        except (ValueError, KeyError, TypeError):
            code = None
        if code:
            message += f" ({code})"
    return message


async def apply_action(db: Session, action: Action, jwt_token: str) -> bool:
    """Apply an accepted action to Wikidata and cache the resulting statement.

    The payload is sent as stored; on success the response body becomes the
    cached Statement document (upserted for creates, replacing the target
    statement's document for edits), ``applied_at`` is set, and True is
    returned. On a non-2xx response or network error the failure is recorded
    in ``error`` and False is returned — nothing else is mutated and failures
    are never retried.

    Raises:
        ValueError: For an EDIT_STATEMENT action without a target statement.
    """
    if action.kind is ActionKind.CREATE_STATEMENT:
        url = f"{WIKIDATA_API_ROOT}/entities/items/{action.politician.wikidata_id}/statements"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        method, expected_status = "POST", 201
    else:
        target = action.statement
        if target is None:
            raise ValueError(
                f"EDIT_STATEMENT action {action.id} has no target statement"
            )
        url = f"{WIKIDATA_API_ROOT}/statements/{target.wikidata_statement_id}"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json-patch+json",
            "User-Agent": USER_AGENT,
        }
        method, expected_status = "PATCH", 200

    async with httpx2.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.request(
                method, url, json=action.payload, headers=headers
            )
        except httpx2.RequestError as exc:
            action.error = f"Wikidata API request failed: {exc}"
            db.commit()
            logger.warning("Applying action %s failed: %s", action.id, action.error)
            return False

        if response.status_code != expected_status:
            action.error = _failure_message(response)
            db.commit()
            logger.warning("Applying action %s failed: %s", action.id, action.error)
            return False

        document = response.json()

    if action.kind is ActionKind.CREATE_STATEMENT:
        rows = Statement.upsert_batch(
            db,
            [{"politician_id": action.politician_id, "document": document}],
            returning_columns=[Statement.id],
        )
        action.statement_id = rows[0].id
    else:
        action.statement.document = document
    action.applied_at = datetime.now(UTC)
    action.error = None
    db.commit()
    logger.info("Applied action %s", action.id)
    return True
