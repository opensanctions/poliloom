"""Politicians API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_db
from ..models import (
    Politician,
    Property,
    HoldsPosition,
    BornAt,
    Evaluation,
    EvaluationResult,
)
from .schemas import (
    UnconfirmedPoliticianResponse,
    UnconfirmedPropertyResponse,
    UnconfirmedPositionResponse,
    UnconfirmedBirthplaceResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from .auth import get_current_user, User

router = APIRouter()


@router.get("/", response_model=List[UnconfirmedPoliticianResponse])
async def get_unconfirmed_politicians(
    limit: int = Query(
        default=50, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve politicians that have unevaluated extracted data (archived_page_id is not null).

    Returns a list of politicians with their unevaluated data for review and evaluation.
    """
    # Query for politicians that have either unevaluated properties or positions
    query = (
        select(Politician)
        .options(
            selectinload(Politician.properties).selectinload(Property.evaluations),
            selectinload(Politician.positions_held).selectinload(
                HoldsPosition.position
            ),
            selectinload(Politician.positions_held).selectinload(
                HoldsPosition.evaluations
            ),
            selectinload(Politician.birthplaces).selectinload(BornAt.location),
            selectinload(Politician.birthplaces).selectinload(BornAt.evaluations),
            selectinload(Politician.wikipedia_links),
        )
        .where(
            (Politician.properties.any(Property.archived_page_id.isnot(None)))
            | (
                Politician.positions_held.any(
                    HoldsPosition.archived_page_id.isnot(None)
                )
            )
            | (Politician.birthplaces.any(BornAt.archived_page_id.isnot(None)))
        )
        .offset(offset)
        .limit(limit)
    )

    politicians = db.execute(query).scalars().all()

    result = []
    for politician in politicians:
        # Filter unevaluated properties (extracted but not evaluated)
        unevaluated_properties = [
            prop
            for prop in politician.properties
            if prop.archived_page_id is not None and not prop.evaluations
        ]

        # Filter unevaluated positions (extracted but not evaluated)
        unevaluated_positions = [
            pos
            for pos in politician.positions_held
            if pos.archived_page_id is not None and not pos.evaluations
        ]

        # Filter unevaluated birthplaces (extracted but not evaluated)
        unevaluated_birthplaces = [
            birthplace
            for birthplace in politician.birthplaces
            if birthplace.archived_page_id is not None and not birthplace.evaluations
        ]

        # Only include politicians that actually have unevaluated data
        if unevaluated_properties or unevaluated_positions or unevaluated_birthplaces:
            politician_response = UnconfirmedPoliticianResponse(
                id=str(politician.id),
                name=politician.name,
                wikidata_id=politician.wikidata_id,
                unconfirmed_properties=[
                    UnconfirmedPropertyResponse(
                        id=str(prop.id),
                        type=prop.type,
                        value=prop.value,
                    )
                    for prop in unevaluated_properties
                ],
                unconfirmed_positions=[
                    UnconfirmedPositionResponse(
                        id=str(pos.id),
                        position_name=pos.position.name,
                        start_date=pos.start_date,
                        end_date=pos.end_date,
                    )
                    for pos in unevaluated_positions
                ],
                unconfirmed_birthplaces=[
                    UnconfirmedBirthplaceResponse(
                        id=str(birthplace.id),
                        location_name=birthplace.location.name,
                        location_wikidata_id=birthplace.location.wikidata_id,
                    )
                    for birthplace in unevaluated_birthplaces
                ],
            )
            result.append(politician_response)

    return result


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_extracted_data(
    request: EvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Evaluate extracted properties, positions, and birthplaces.

    This endpoint allows authenticated users to evaluate extracted data,
    marking it as confirmed or discarded. Creates evaluation records
    that can be used for threshold-based evaluation workflows.
    """
    processed_count = 0
    errors = []

    for eval_item in request.evaluations:
        try:
            # Determine entity type and get the entity
            entity = None
            if eval_item.entity_type == "property":
                entity = db.get(Property, eval_item.entity_id)
                if not entity:
                    errors.append(f"Property {eval_item.entity_id} not found")
                    continue
            elif eval_item.entity_type == "position":
                entity = db.get(HoldsPosition, eval_item.entity_id)
                if not entity:
                    errors.append(f"Position {eval_item.entity_id} not found")
                    continue
            elif eval_item.entity_type == "birthplace":
                entity = db.get(BornAt, eval_item.entity_id)
                if not entity:
                    errors.append(f"Birthplace {eval_item.entity_id} not found")
                    continue
            else:
                errors.append(f"Invalid entity type: {eval_item.entity_type}")
                continue

            # Convert pydantic enum to database enum
            result = (
                EvaluationResult.CONFIRMED
                if eval_item.result.value == "confirmed"
                else EvaluationResult.DISCARDED
            )

            # Create evaluation record
            evaluation = Evaluation(
                user_id=current_user.username,
                result=result,
            )

            # Set the appropriate foreign key based on entity type
            if eval_item.entity_type == "property":
                evaluation.property_id = eval_item.entity_id
            elif eval_item.entity_type == "position":
                evaluation.holds_position_id = eval_item.entity_id
            elif eval_item.entity_type == "birthplace":
                evaluation.born_at_id = eval_item.entity_id
            db.add(evaluation)
            processed_count += 1

            # If discarded, remove the original entity
            if result == EvaluationResult.DISCARDED:
                db.delete(entity)

        except Exception as e:
            errors.append(
                f"Error processing {eval_item.entity_type} {eval_item.entity_id}: {str(e)}"
            )
            continue

    try:
        db.commit()
        return EvaluationResponse(
            success=True,
            message=f"Successfully processed {processed_count} evaluations",
            processed_count=processed_count,
            errors=errors,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
