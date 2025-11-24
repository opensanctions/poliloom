"""Evaluations API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db_session
from ..models import Property, Evaluation
from .schemas import EvaluationRequest, EvaluationResponse, EvaluationObjectResponse
from .auth import get_current_user, User
from ..wikidata_statement import push_evaluation

router = APIRouter()


@router.post("", response_model=EvaluationResponse)
async def evaluate_extracted_data(
    request: EvaluationRequest,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate extracted properties, positions, and birthplaces.

    This endpoint allows authenticated users to evaluate extracted data,
    marking it as accepted or rejected. Creates evaluation records
    that can be used for threshold-based evaluation workflows.

    For accepted evaluations, attempts to push statements to Wikidata.
    For rejected existing statements, deprecates them in Wikidata.
    """
    errors = []
    all_evaluations = []

    # Process each evaluation in the request
    for eval_item in request.evaluations:
        try:
            property_entity = db.get(Property, eval_item.id)
            if not property_entity:
                errors.append(f"Property {eval_item.id} not found")
                continue

            evaluation = Evaluation(
                user_id=str(current_user.user_id),
                is_accepted=eval_item.is_accepted,
                property_id=eval_item.id,
            )
            db.add(evaluation)

            # Track all evaluations for Wikidata operations
            all_evaluations.append(evaluation)

        except Exception as e:
            errors.append(f"Error processing property {eval_item.id}: {str(e)}")
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
