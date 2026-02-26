"""Evaluations API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import Evaluation, Politician, Property, PropertyType
from ..wikidata_statement import push_evaluation
from .auth import User, get_current_user
from .schemas import (
    EvaluationObjectResponse,
    EvaluationRequest,
    EvaluationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Map frontend property type strings (Wikidata P-IDs) to backend enum
PROPERTY_TYPE_MAP = {
    "P569": PropertyType.BIRTH_DATE,
    "P570": PropertyType.DEATH_DATE,
    "P19": PropertyType.BIRTHPLACE,
    "P39": PropertyType.POSITION,
    "P27": PropertyType.CITIZENSHIP,
}


@router.post("", response_model=EvaluationResponse)
async def evaluate_extracted_data(
    request: EvaluationRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate extracted properties and/or create new ones.

    Each item in the request is either:
    - An evaluation of an existing property (has `id` + `is_accepted`)
    - A new property creation (has `type` + value/entity fields)

    For accepted evaluations, attempts to push statements to Wikidata.
    For rejected existing statements, deprecates them in Wikidata.
    New properties are auto-accepted and pushed to Wikidata.
    """
    # Validate politician exists
    politician = db.get(Politician, request.politician_id)
    if not politician:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Politician {request.politician_id} not found",
        )

    errors = []
    all_evaluations = []

    for item in request.items:
        try:
            if item.id is not None:
                # Evaluation of existing property
                property_entity = db.get(Property, item.id)
                if not property_entity:
                    errors.append(f"Property {item.id} not found")
                    continue

                evaluation = Evaluation(
                    user_id=str(current_user.user_id),
                    is_accepted=item.is_accepted,
                    property_id=item.id,
                )
                db.add(evaluation)
                all_evaluations.append(evaluation)
            else:
                # New property creation
                if not item.type:
                    errors.append("New property item missing 'type'")
                    continue

                prop_type = PROPERTY_TYPE_MAP.get(item.type)
                if not prop_type:
                    errors.append(f"Unknown property type: {item.type}")
                    continue

                new_property = Property(
                    politician_id=request.politician_id,
                    type=prop_type,
                    value=item.value,
                    value_precision=item.value_precision,
                    entity_id=item.entity_id,
                    qualifiers_json=item.qualifiers_json,
                )
                db.add(new_property)
                db.flush()  # Get the ID

                # Auto-accept the new property
                evaluation = Evaluation(
                    user_id=str(current_user.user_id),
                    is_accepted=True,
                    property_id=new_property.id,
                )
                db.add(evaluation)
                all_evaluations.append(evaluation)

        except Exception as e:
            item_desc = str(item.id) if item.id else f"new {item.type}"
            errors.append(f"Error processing item {item_desc}: {str(e)}")
            continue

    try:
        # Commit local database changes first
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )

    # Push evaluations to Wikidata (don't rollback local changes on failure)
    wikidata_errors = []

    # Extract JWT token from authenticated user for Wikidata API calls
    jwt_token = current_user.jwt_token
    if not jwt_token:
        wikidata_errors.append("No JWT token available for Wikidata API calls")
    else:
        for evaluation in all_evaluations:
            try:
                success = await push_evaluation(evaluation, jwt_token, db)
                if not success:
                    wikidata_errors.append(
                        f"Failed to process evaluation {evaluation.id} in Wikidata"
                    )
            except Exception as e:
                wikidata_errors.append(
                    f"Error processing evaluation {evaluation.id} in Wikidata: {str(e)}"
                )

    # Include Wikidata errors in response but don't fail the request
    if wikidata_errors:
        errors.extend(wikidata_errors)

    # Build response with full evaluation data
    evaluation_responses = [
        EvaluationObjectResponse(
            id=evaluation.id,
            user_id=evaluation.user_id,
            is_accepted=evaluation.is_accepted,
            property_id=evaluation.property_id,
            created_at=evaluation.created_at,
        )
        for evaluation in all_evaluations
    ]

    return EvaluationResponse(
        success=True,
        message=f"Successfully processed {len(evaluation_responses)} evaluations"
        + (f" ({len(wikidata_errors)} Wikidata errors)" if wikidata_errors else ""),
        evaluations=evaluation_responses,
        errors=errors,
    )
