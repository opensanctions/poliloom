"""Politicians API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_engine
from ..models import (
    Politician,
    Property,
    Evaluation,
)
from .schemas import (
    PoliticianResponse,
    PropertyResponse,
    ArchivedPageResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from .auth import get_current_user, User
# from ..wikidata_statement import push_evaluation  # TODO: Fix after unified model migration

router = APIRouter()


@router.get("/", response_model=List[PoliticianResponse])
async def get_politicians(
    limit: int = Query(
        default=50, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve politicians that have unevaluated extracted data.

    Returns a list of politicians with their Wikidata properties, positions, birthplaces
    and unevaluated extracted data for review and evaluation.
    """
    with Session(get_engine()) as db:
        # Use a raw SQL query for better performance
        # This identifies all politician IDs that have properties needing evaluation
        from sqlalchemy import text

        politicians_needing_eval_sql = text("""
            SELECT politician_id
            FROM (
                SELECT DISTINCT politician_id
                FROM properties
                WHERE statement_id IS NULL
            ) t
            ORDER BY RANDOM()
            LIMIT :limit OFFSET :offset
        """)

        # Get politician IDs that need evaluation
        result = db.execute(
            politicians_needing_eval_sql, {"limit": limit, "offset": offset}
        )
        politician_ids = [row[0] for row in result]

        if not politician_ids:
            return []

        # Now fetch the full politician objects with relationships
        query = (
            select(Politician)
            .options(
                selectinload(Politician.properties).options(
                    selectinload(Property.entity),
                    selectinload(Property.archived_page),
                ),
                selectinload(Politician.wikipedia_links),
            )
            .where(Politician.id.in_(politician_ids))
        )

        politicians = db.execute(query).scalars().all()

        result = []
        for politician in politicians:
            # Simplified response building - no grouping
            property_responses = []
            for prop in politician.properties:
                # Add entity name if applicable
                entity_name = None
                if prop.entity and prop.entity_id:
                    entity_name = prop.entity.name

                property_responses.append(
                    PropertyResponse(
                        id=prop.id,
                        type=prop.type,
                        value=prop.value,
                        value_precision=prop.value_precision,
                        entity_id=prop.entity_id,
                        entity_name=entity_name,
                        proof_line=prop.proof_line,
                        statement_id=prop.statement_id,
                        qualifiers=prop.qualifiers_json,
                        references=prop.references_json,
                        archived_page=(
                            ArchivedPageResponse(
                                id=prop.archived_page.id,
                                url=prop.archived_page.url,
                                content_hash=prop.archived_page.content_hash,
                                fetch_timestamp=prop.archived_page.fetch_timestamp,
                            )
                            if prop.archived_page
                            else None
                        ),
                    )
                )

            result.append(
                PoliticianResponse(
                    id=politician.id,
                    name=politician.name,
                    wikidata_id=politician.wikidata_id,
                    properties=property_responses,
                )
            )

    return result


@router.post("/evaluate", response_model=EvaluationResponse)
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

        # TODO: Re-enable Wikidata push after unified model migration
        wikidata_errors = []
        # Push evaluations to Wikidata (don't rollback local changes on failure)
        # wikidata_errors = []

        # # Extract JWT token from authenticated user for Wikidata API calls
        # jwt_token = current_user.jwt_token
        # if not jwt_token:
        #     wikidata_errors.append("No JWT token available for Wikidata API calls")
        # else:
        #     try:
        #         for evaluation in all_evaluations:
        #             try:
        #                 success = await push_evaluation(evaluation, jwt_token, db)
        #                 if not success:
        #                     wikidata_errors.append(
        #                         f"Failed to process evaluation {evaluation.id} in Wikidata"
        #                     )
        #             except Exception as e:
        #                 wikidata_errors.append(
        #                     f"Error processing evaluation {evaluation.id} in Wikidata: {str(e)}"
        #                 )

        #     except Exception as e:
        #         wikidata_errors.append(
        #             f"Error setting up Wikidata operations: {str(e)}"
        #         )

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
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
