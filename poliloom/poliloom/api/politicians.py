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
    PropertyEvaluation,
    PositionEvaluation,
    BirthplaceEvaluation,
)
from .schemas import (
    UnconfirmedPoliticianResponse,
    UnconfirmedPropertyResponse,
    UnconfirmedPositionResponse,
    UnconfirmedBirthplaceResponse,
    WikidataPropertyResponse,
    WikidataPositionResponse,
    WikidataBirthplaceResponse,
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
    Retrieve politicians that have unevaluated extracted data.

    Returns a list of politicians with their unevaluated data for review and evaluation.
    """
    # Query for politicians that have either unevaluated properties or positions
    query = (
        select(Politician)
        .options(
            selectinload(Politician.properties).selectinload(Property.evaluations),
            selectinload(Politician.properties).selectinload(Property.archived_page),
            selectinload(Politician.positions_held).selectinload(
                HoldsPosition.position
            ),
            selectinload(Politician.positions_held).selectinload(
                HoldsPosition.evaluations
            ),
            selectinload(Politician.positions_held).selectinload(
                HoldsPosition.archived_page
            ),
            selectinload(Politician.birthplaces).selectinload(BornAt.location),
            selectinload(Politician.birthplaces).selectinload(BornAt.evaluations),
            selectinload(Politician.birthplaces).selectinload(BornAt.archived_page),
            selectinload(Politician.wikipedia_links),
        )
        .where(
            (Politician.properties.any(Property.is_extracted))
            | (Politician.positions_held.any(HoldsPosition.is_extracted))
            | (Politician.birthplaces.any(BornAt.is_extracted))
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
            if prop.is_extracted and not prop.evaluations
        ]

        # Filter unevaluated positions (extracted but not evaluated)
        unevaluated_positions = [
            pos
            for pos in politician.positions_held
            if pos.is_extracted and not pos.evaluations
        ]

        # Filter unevaluated birthplaces (extracted but not evaluated)
        unevaluated_birthplaces = [
            birthplace
            for birthplace in politician.birthplaces
            if birthplace.is_extracted and not birthplace.evaluations
        ]

        # Filter Wikidata properties (not extracted from web sources)
        wikidata_properties = [
            prop for prop in politician.properties if not prop.is_extracted
        ]

        # Filter Wikidata positions (not extracted from web sources)
        wikidata_positions = [
            pos for pos in politician.positions_held if not pos.is_extracted
        ]

        # Filter Wikidata birthplaces (not extracted from web sources)
        wikidata_birthplaces = [
            birthplace
            for birthplace in politician.birthplaces
            if not birthplace.is_extracted
        ]

        # Only include politicians that actually have unevaluated data
        if unevaluated_properties or unevaluated_positions or unevaluated_birthplaces:
            politician_response = UnconfirmedPoliticianResponse(
                id=politician.id,
                name=politician.name,
                wikidata_id=politician.wikidata_id,
                wikidata_properties=[
                    WikidataPropertyResponse(
                        id=prop.id,
                        type=prop.type,
                        value=prop.value,
                        value_precision=prop.value_precision,
                    )
                    for prop in wikidata_properties
                ],
                wikidata_positions=[
                    WikidataPositionResponse(
                        id=pos.id,
                        position_name=pos.position.name,
                        start_date=pos.start_date,
                        start_date_precision=pos.start_date_precision,
                        end_date=pos.end_date,
                        end_date_precision=pos.end_date_precision,
                    )
                    for pos in wikidata_positions
                ],
                wikidata_birthplaces=[
                    WikidataBirthplaceResponse(
                        id=birthplace.id,
                        location_name=birthplace.location.name,
                        location_wikidata_id=birthplace.location.wikidata_id,
                    )
                    for birthplace in wikidata_birthplaces
                ],
                unconfirmed_properties=[
                    UnconfirmedPropertyResponse(
                        id=prop.id,
                        type=prop.type,
                        value=prop.value,
                        proof_line=prop.proof_line,
                        archived_page=prop.archived_page,
                    )
                    for prop in unevaluated_properties
                ],
                unconfirmed_positions=[
                    UnconfirmedPositionResponse(
                        id=pos.id,
                        position_name=pos.position.name,
                        start_date=pos.start_date,
                        end_date=pos.end_date,
                        proof_line=pos.proof_line,
                        archived_page=pos.archived_page,
                    )
                    for pos in unevaluated_positions
                ],
                unconfirmed_birthplaces=[
                    UnconfirmedBirthplaceResponse(
                        id=birthplace.id,
                        location_name=birthplace.location.name,
                        location_wikidata_id=birthplace.location.wikidata_id,
                        proof_line=birthplace.proof_line,
                        archived_page=birthplace.archived_page,
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
    property_count = 0
    position_count = 0
    birthplace_count = 0
    errors = []

    # Process property evaluations
    for eval_item in request.property_evaluations:
        try:
            property_entity = db.get(Property, eval_item.id)
            if not property_entity:
                errors.append(f"Property {eval_item.id} not found")
                continue

            # Create property evaluation record
            evaluation = PropertyEvaluation(
                user_id=current_user.username,
                is_confirmed=eval_item.is_confirmed,
                property_id=eval_item.id,
            )
            db.add(evaluation)
            property_count += 1

            # If not confirmed, remove the original entity
            if not eval_item.is_confirmed:
                db.delete(property_entity)

        except Exception as e:
            errors.append(f"Error processing property {eval_item.id}: {str(e)}")
            continue

    # Process position evaluations
    for eval_item in request.position_evaluations:
        try:
            position_entity = db.get(HoldsPosition, eval_item.id)
            if not position_entity:
                errors.append(f"Position {eval_item.id} not found")
                continue

            # Create position evaluation record
            evaluation = PositionEvaluation(
                user_id=current_user.username,
                is_confirmed=eval_item.is_confirmed,
                holds_position_id=eval_item.id,
            )
            db.add(evaluation)
            position_count += 1

            # If not confirmed, remove the original entity
            if not eval_item.is_confirmed:
                db.delete(position_entity)

        except Exception as e:
            errors.append(f"Error processing position {eval_item.id}: {str(e)}")
            continue

    # Process birthplace evaluations
    for eval_item in request.birthplace_evaluations:
        try:
            birthplace_entity = db.get(BornAt, eval_item.id)
            if not birthplace_entity:
                errors.append(f"Birthplace {eval_item.id} not found")
                continue

            # Create birthplace evaluation record
            evaluation = BirthplaceEvaluation(
                user_id=current_user.username,
                is_confirmed=eval_item.is_confirmed,
                born_at_id=eval_item.id,
            )
            db.add(evaluation)
            birthplace_count += 1

            # If not confirmed, remove the original entity
            if not eval_item.is_confirmed:
                db.delete(birthplace_entity)

        except Exception as e:
            errors.append(f"Error processing birthplace {eval_item.id}: {str(e)}")
            continue

    total_processed = property_count + position_count + birthplace_count

    try:
        db.commit()
        return EvaluationResponse(
            success=True,
            message=f"Successfully processed {total_processed} evaluations",
            property_count=property_count,
            position_count=position_count,
            birthplace_count=birthplace_count,
            errors=errors,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
