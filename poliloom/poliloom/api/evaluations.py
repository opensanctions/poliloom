"""Evaluations API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_engine
from ..models import Property, Evaluation
from .schemas import EvaluationRequest, EvaluationResponse
from .auth import get_current_user, User
from ..wikidata_statement import push_evaluation

router = APIRouter()


@router.post("", response_model=EvaluationResponse)
async def evaluate_extracted_data(
    request: EvaluationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate extracted properties, positions, and birthplaces.

    This endpoint allows authenticated users to evaluate extracted data,
    marking it as confirmed or discarded. Creates evaluation records
    that can be used for threshold-based evaluation workflows.

    For confirmed evaluations, attempts to push statements to Wikidata.
    """
    with Session(get_engine()) as db:
        evaluation_count = 0
        errors = []
        all_evaluations = []

        # Simplified - single loop instead of three
        for eval_item in request.evaluations:
            try:
                property_entity = db.get(Property, eval_item.id)
                if not property_entity:
                    errors.append(f"Property {eval_item.id} not found")
                    continue

                evaluation = Evaluation(
                    user_id=str(current_user.user_id),
                    is_confirmed=eval_item.is_confirmed,
                    property_id=eval_item.id,
                )
                db.add(evaluation)
                evaluation_count += 1

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

        return EvaluationResponse(
            success=True,
            message=f"Successfully processed {evaluation_count} evaluations"
            + (f" ({len(wikidata_errors)} Wikidata errors)" if wikidata_errors else ""),
            evaluation_count=evaluation_count,
            errors=errors,
        )
