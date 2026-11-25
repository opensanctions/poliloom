"""Execute accepted statement proposals against the Wikibase REST API.

The adapter reads the live Wikidata state before every write instead of
trusting the statement cache. Equivalent accepted proposals share one request
and contribute their references to the same write. A live statement may
already satisfy a proposal; in that case only missing, non-Wikimedia
references are appended. Every write carries guards for the complete live
fact, its rank, and its references when those are extended.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime

import httpx2
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Action, Statement
from ..proposals import (
    Mutation,
    action_group_key,
    fact_key,
    proposal_mutation,
    qualifier_key,
    statement_fact,
    validate_proposal,
)
from .references import is_wikimedia_import, missing_references

logger = logging.getLogger(__name__)

WIKIDATA_API_ROOT = os.getenv(
    "WIKIDATA_API_ROOT", "https://www.wikidata.org/w/rest.php/wikibase/v1"
)
USER_AGENT = "PoliLoom API/0.1.0"


class _Conflict(Exception):
    """The live Wikidata state no longer supports the approved proposal."""


class _ExecutionFailure(Exception):
    """The Wikidata API could not complete the approved proposal."""


def _failure_message(response: httpx2.Response) -> str:
    """Build the concise error message recorded on a failed API response."""
    message = f"Wikidata API returned HTTP {response.status_code}"
    if response.status_code == 409:
        try:
            code = response.json()["code"]
        except (ValueError, KeyError, TypeError):
            code = None
        if code:
            message += f" ({code})"
    return message


def group_actions(actions: list[Action]) -> list[list[Action]]:
    groups: dict[str, list[Action]] = {}
    for action in actions:
        groups.setdefault(action_group_key(action), []).append(action)
    return list(groups.values())


def _proposed_references(actions: list[Action]) -> list[dict]:
    return [reference for action in actions for reference in action.references_to_add]


def _headers(jwt_token: str, content_type: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": USER_AGENT,
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


async def _get_property_statements(
    client: httpx2.AsyncClient,
    politician_qid: str,
    property_id: str,
    jwt_token: str,
) -> list[dict]:
    try:
        response = await client.request(
            "GET",
            f"{WIKIDATA_API_ROOT}/entities/items/{politician_qid}/statements",
            params={"property": property_id},
            headers=_headers(jwt_token),
        )
    except httpx2.RequestError as exc:
        raise _ExecutionFailure(f"Wikidata API request failed: {exc}") from exc
    if response.status_code != 200:
        raise _ExecutionFailure(_failure_message(response))
    statements = response.json()
    if not isinstance(statements, dict):
        raise _ExecutionFailure("Wikidata returned an invalid statement list")
    return statements.get(property_id, [])


async def _get_statement(
    client: httpx2.AsyncClient,
    statement_id: str,
    jwt_token: str,
) -> dict | None:
    try:
        response = await client.request(
            "GET",
            f"{WIKIDATA_API_ROOT}/statements/{statement_id}",
            headers=_headers(jwt_token),
            follow_redirects=True,
        )
    except httpx2.RequestError as exc:
        raise _ExecutionFailure(f"Wikidata API request failed: {exc}") from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise _ExecutionFailure(_failure_message(response))
    return response.json()


def _fact_guards(document: dict) -> list[dict]:
    return [
        {"op": "test", "path": "/property", "value": document["property"]},
        {"op": "test", "path": "/value", "value": document["value"]},
        {"op": "test", "path": "/qualifiers", "value": document["qualifiers"]},
        {"op": "test", "path": "/rank", "value": document["rank"]},
    ]


def _mutation_operation(mutation: Mutation, document: dict) -> dict:
    match mutation.kind:
        case "value":
            return {"op": "replace", "path": "/value", "value": mutation.new}
        case "qualifier_append":
            return {"op": "add", "path": "/qualifiers/-", "value": mutation.new}
        case "qualifier_replace":
            old_key = qualifier_key(mutation.old)
            index = next(
                (
                    index
                    for index, qualifier in enumerate(document["qualifiers"])
                    if qualifier_key(qualifier) == old_key
                ),
                None,
            )
            if index is None:
                raise _Conflict(
                    f"Target statement {document['id']} no longer has the proposed qualifier"
                )
            return {
                "op": "replace",
                "path": f"/qualifiers/{index}",
                "value": mutation.new,
            }
    raise ValueError(f"Unsupported proposal mutation: {mutation.kind}")


def _cache_statement(db: Session, action: Action, document: dict) -> None:
    Statement.upsert_batch(
        db,
        [{"politician_id": action.politician_id, "document": document}],
    )


def _mark_satisfied(db: Session, actions: list[Action], statement_id: str) -> None:
    applied_at = datetime.now(UTC)
    for action in actions:
        action.applied_wikidata_statement_id = statement_id
        action.applied_at = applied_at
        action.error = None
    db.commit()


def _record_failure(db: Session, actions: list[Action], message: str) -> None:
    for action in actions:
        action.error = message
    db.commit()
    logger.warning(
        "Applying action group %s failed: %s", [a.id for a in actions], message
    )


async def _write(
    client: httpx2.AsyncClient,
    method: str,
    url: str,
    payload: dict,
    expected_status: int,
    jwt_token: str,
) -> dict:
    content_type = (
        "application/json-patch+json" if method == "PATCH" else "application/json"
    )
    try:
        response = await client.request(
            method,
            url,
            json=payload,
            headers=_headers(jwt_token, content_type),
        )
    except httpx2.RequestError as exc:
        raise _ExecutionFailure(f"Wikidata API request failed: {exc}") from exc
    if response.status_code != expected_status:
        raise _ExecutionFailure(_failure_message(response))
    return response.json()


async def _satisfy_existing(
    db: Session,
    actions: list[Action],
    client: httpx2.AsyncClient,
    live: dict,
    jwt_token: str,
    proposed_references: list[dict],
    *,
    mutation: Mutation | None = None,
) -> bool:
    """Apply references and an optional mutation to a live statement."""
    eligible_references = [
        reference
        for reference in proposed_references
        if not is_wikimedia_import(reference)
    ]
    additions = missing_references(eligible_references, live["references"])

    if mutation is None and not additions:
        _cache_statement(db, actions[0], live)
        _mark_satisfied(db, actions, live["id"])
        return True

    patch = _fact_guards(live)
    if mutation is not None:
        patch.append(_mutation_operation(mutation, live))
    if additions:
        patch.extend(
            [
                {"op": "test", "path": "/references", "value": live["references"]},
                *(
                    {"op": "add", "path": "/references/-", "value": reference}
                    for reference in additions
                ),
            ]
        )

    document = await _write(
        client,
        "PATCH",
        f"{WIKIDATA_API_ROOT}/statements/{live['id']}",
        {"patch": patch},
        200,
        jwt_token,
    )

    _cache_statement(db, actions[0], document)
    _mark_satisfied(db, actions, document["id"])
    logger.info("Applied action group %s", [str(action.id) for action in actions])
    return True


async def _apply_untargeted(
    db: Session,
    actions: list[Action],
    jwt_token: str,
) -> bool:
    action = actions[0]
    after_key = fact_key(action.after)
    proposed_references = _proposed_references(actions)

    async with httpx2.AsyncClient(timeout=30.0) as client:
        statements = await _get_property_statements(
            client,
            action.politician.wikidata_id,
            action.after["property"]["id"],
            jwt_token,
        )
        matches = [
            document
            for document in statements
            if document["rank"] == "normal"
            and fact_key(statement_fact(document)) == after_key
        ]

        if len(matches) > 1:
            raise _Conflict(
                "Multiple current statements exactly match the proposed fact"
            )
        if matches:
            return await _satisfy_existing(
                db,
                actions,
                client,
                matches[0],
                jwt_token,
                proposed_references,
            )

        statement = {
            "property": action.after["property"],
            "value": action.after["value"],
            "qualifiers": action.after["qualifiers"],
            "rank": "normal",
            "references": missing_references(proposed_references, []),
        }
        document = await _write(
            client,
            "POST",
            f"{WIKIDATA_API_ROOT}/entities/items/"
            f"{action.politician.wikidata_id}/statements",
            {"statement": statement},
            201,
            jwt_token,
        )

    _cache_statement(db, action, document)
    _mark_satisfied(db, actions, document["id"])
    logger.info("Applied action group %s", [str(action.id) for action in actions])
    return True


async def _apply_targeted(
    db: Session,
    actions: list[Action],
    jwt_token: str,
) -> bool:
    action = actions[0]
    target_id = action.target_wikidata_statement_id
    proposed_references = _proposed_references(actions)

    async with httpx2.AsyncClient(timeout=30.0) as client:
        live = await _get_statement(client, target_id, jwt_token)
        if live is None:
            raise _Conflict(f"Target statement {target_id} no longer exists")
        if live["id"].casefold() != target_id.casefold():
            raise _Conflict(
                f"Wikidata returned a different statement for target {target_id}"
            )
        if live["rank"] == "deprecated":
            raise _Conflict(f"Target statement {target_id} is deprecated")

        live_key = fact_key(statement_fact(live))
        before_key = fact_key(action.before)
        after_key = fact_key(action.after)

        if live_key == after_key:
            return await _satisfy_existing(
                db,
                actions,
                client,
                live,
                jwt_token,
                proposed_references,
            )
        if live_key != before_key:
            raise _Conflict(
                f"Target statement {target_id} no longer matches the proposed fact"
            )

        mutation = proposal_mutation(action.before, action.after)
        if mutation is None:
            raise _Conflict(
                f"Target statement {target_id} does not have a supported change"
            )
        return await _satisfy_existing(
            db,
            actions,
            client,
            live,
            jwt_token,
            proposed_references,
            mutation=mutation,
        )


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


async def apply_action_group(
    db: Session, actions: list[Action], jwt_token: str
) -> bool:
    """Apply one approved group of equivalent proposals to Wikidata.

    The live fact is read before every write. A successfully satisfied group,
    including a no-write result, records its stable statement ID and
    application timestamp. Conflicts and API failures record an error and
    leave the review decision untouched.

    Raises:
        ValueError: For an empty group or a proposal that does not satisfy the
            proposal invariants.
    """
    if not actions:
        raise ValueError("Cannot apply an empty action group")

    for action in actions:
        if action.is_accepted is not True or action.applied_at is not None:
            raise ValueError(f"Action {action.id} is not an unapplied approval")
        validate_proposal(action, action.politician.wikidata_id)

    try:
        await _lock_writes(db, actions[0].politician_id)
        try:
            if actions[0].target_wikidata_statement_id is None:
                return await _apply_untargeted(db, actions, jwt_token)
            return await _apply_targeted(db, actions, jwt_token)
        except (_Conflict, _ExecutionFailure) as exc:
            _record_failure(db, actions, str(exc))
            return False
    except BaseException:
        db.rollback()
        raise
