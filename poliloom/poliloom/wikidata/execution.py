"""Execute accepted Actions against the Wikibase REST API.

Equivalent actions share one request. If the proposed data is already in
place, the request adds only missing references. Data and reference guards
protect against concurrent edits. The API response becomes the cached
Statement document.
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime

import httpx2
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Action, ActionKind, Statement
from ..payloads import statement_fact_guards
from .references import is_wikimedia_import, missing_references

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


def _is_reference_append(operation: dict) -> bool:
    return operation["op"] == "add" and operation["path"] == "/references/-"


def _data_patch(action: Action) -> list[dict]:
    return [op for op in action.payload["patch"] if not _is_reference_append(op)]


def _action_group_key(action: Action) -> str:
    """Identify the same proposed write independently of reference additions."""
    if action.kind is ActionKind.CREATE_STATEMENT:
        data = {
            k: v for k, v in action.payload["statement"].items() if k != "references"
        }
    else:
        data = _data_patch(action)
    return json.dumps(
        (str(action.politician_id), action.kind, str(action.statement_id), data),
        sort_keys=True,
    )


def group_actions(actions: list[Action]) -> list[list[Action]]:
    groups: dict[str, list[Action]] = {}
    for action in actions:
        groups.setdefault(_action_group_key(action), []).append(action)
    return list(groups.values())


def _proposed_references(action: Action) -> list[dict]:
    if action.kind is ActionKind.CREATE_STATEMENT:
        return action.payload["statement"].get("references", [])
    return [op["value"] for op in action.payload["patch"] if _is_reference_append(op)]


def _qualifier_key(qualifier: dict) -> str:
    return json.dumps((qualifier["property"]["id"], qualifier["value"]), sort_keys=True)


def _statement_data(document: dict) -> tuple:
    """Compare a create body to a cached response, ignoring server metadata."""
    qualifiers = sorted(map(_qualifier_key, document.get("qualifiers", [])))
    return document.get("rank", "normal"), document["value"], qualifiers


def _edit_already_present(document: dict, patch: list[dict]) -> bool:
    """Check the result of a planner edit without replaying its mutation."""
    match patch:
        case [
            {"op": "test", "path": "/value", "value": _},
            {"op": "replace", "path": "/value", "value": value},
        ]:
            return document["value"] == value
        case [
            {"op": "test", "path": "/value", "value": office},
            {"op": "test", "path": "/qualifiers", "value": qualifiers},
            {"op": "add", "path": "/qualifiers/-", "value": qualifier},
        ]:
            return document["value"] == office and sorted(
                map(_qualifier_key, document["qualifiers"])
            ) == sorted(map(_qualifier_key, [*qualifiers, qualifier]))
        case [
            {"op": "test", "path": "/value", "value": office},
            {"op": "test", "path": path, "value": _},
            {"op": "replace", "path": replacement_path, "value": qualifier},
        ] if path == replacement_path:
            return document["value"] == office and any(
                path == f"/qualifiers/{index}"
                and _qualifier_key(current) == _qualifier_key(qualifier)
                for index, current in enumerate(document["qualifiers"])
            )
    return False


def _find_created_statement(db: Session, action: Action) -> Statement | None:
    proposed = action.payload["statement"]
    candidates = db.scalars(
        select(Statement)
        .where(
            Statement.politician_id == action.politician_id,
            Statement.property_id == proposed["property"]["id"],
        )
        .execution_options(populate_existing=True)
    )
    data = _statement_data(proposed)
    matches = [row for row in candidates if _statement_data(row.document) == data]
    if len(matches) > 1:
        raise ValueError("Multiple cached statements match the proposed create")
    return matches[0] if matches else None


async def _lock_writes(db: Session, politician_id) -> None:
    # Waiting on a blocking SQL lock would block the event loop while its holder
    # awaits Wikidata. Release the connection between attempts.
    lock = select(
        func.pg_try_advisory_xact_lock(
            func.hashtextextended(f"poliloom:wikidata:{politician_id}", 0)
        )
    )
    while not db.scalar(lock):
        db.rollback()
        await asyncio.sleep(0.05)


def _mark_applied(db: Session, actions: list[Action]) -> None:
    applied_at = datetime.now(UTC)
    for action in actions:
        action.applied_at = applied_at
        action.error = None
    db.commit()


async def apply_action_group(
    db: Session, actions: list[Action], jwt_token: str
) -> bool:
    """Apply one logical action group to Wikidata and cache the result.

    Cache the response and mark the group applied on success. If an edit has
    no data change and no new references, mark it applied without a request.
    On HTTP or network failure record the error on the group without retrying.

    Raises:
        ValueError: For an empty group or an EDIT_STATEMENT group without a
            target statement.
    """
    if not actions:
        raise ValueError("Cannot apply an empty action group")

    action = actions[0]
    if action.kind is ActionKind.EDIT_STATEMENT and action.statement_id is None:
        raise ValueError(f"EDIT_STATEMENT action {action.id} has no target statement")

    try:
        await _lock_writes(db, action.politician_id)
        return await _apply_locked(db, actions, jwt_token)
    except BaseException:
        db.rollback()
        raise


async def _apply_locked(db: Session, actions: list[Action], jwt_token: str) -> bool:
    action = actions[0]
    creates = action.kind is ActionKind.CREATE_STATEMENT
    proposed = [ref for member in actions for ref in _proposed_references(member)]
    if creates:
        target = _find_created_statement(db, action)
    else:
        target = db.get(Statement, action.statement_id, populate_existing=True)
        if target is None:
            raise ValueError(f"Target statement {action.statement_id} no longer exists")

    if target is None:
        statement = action.payload["statement"]
        payload = {
            "statement": {**statement, "references": missing_references(proposed, [])}
        }
        url = f"{WIKIDATA_API_ROOT}/entities/items/{action.politician.wikidata_id}/statements"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        method, expected_status = "POST", 201
    else:
        references = target.document["references"]
        if creates:
            proposed = [ref for ref in proposed if not is_wikimedia_import(ref)]
            patch = statement_fact_guards(target.document)
        else:
            patch = _data_patch(action)
            if _edit_already_present(target.document, patch):
                patch = statement_fact_guards(target.document)
        additions = missing_references(proposed, references)
        if additions:
            patch = [
                *patch,
                {"op": "test", "path": "/references", "value": references},
                *(
                    {"op": "add", "path": "/references/-", "value": reference}
                    for reference in additions
                ),
            ]
        elif all(operation["op"] == "test" for operation in patch):
            if creates:
                for member in actions:
                    member.statement_id = target.id
            _mark_applied(db, actions)
            return True
        payload = {"patch": patch}
        url = f"{WIKIDATA_API_ROOT}/statements/{target.wikidata_statement_id}"
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json-patch+json",
            "User-Agent": USER_AGENT,
        }
        method, expected_status = "PATCH", 200

    async with httpx2.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.request(method, url, json=payload, headers=headers)
        except httpx2.RequestError as exc:
            for grouped_action in actions:
                grouped_action.error = f"Wikidata API request failed: {exc}"
            db.commit()
            logger.warning("Applying action %s failed: %s", action.id, action.error)
            return False

        if response.status_code != expected_status:
            for grouped_action in actions:
                grouped_action.error = _failure_message(response)
            db.commit()
            logger.warning("Applying action %s failed: %s", action.id, action.error)
            return False

        document = response.json()

    if target is None:
        rows = Statement.upsert_batch(
            db,
            [{"politician_id": action.politician_id, "document": document}],
            returning_columns=[Statement.id],
        )
        statement_id = rows[0].id
    else:
        target.document = document
        statement_id = target.id

    if creates:
        for member in actions:
            member.statement_id = statement_id
    _mark_applied(db, actions)
    logger.info("Applied action group %s", [str(grouped.id) for grouped in actions])
    return True
