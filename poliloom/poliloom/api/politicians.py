"""Politicians API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_engine
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
    PoliticianResponse,
    PropertyResponse,
    PositionResponse,
    BirthplaceResponse,
    PropertyStatementResponse,
    PositionStatementResponse,
    BirthplaceStatementResponse,
    ArchivedPageResponse,
    EvaluationRequest,
    EvaluationResponse,
)
from .auth import get_current_user, User
from ..wikidata_statement import push_evaluation

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
        # Use a raw SQL query with CTEs for better performance
        # This identifies all politician IDs that have statements needing evaluation
        from sqlalchemy import text

        politicians_needing_eval_sql = text("""
        WITH politicians_to_evaluate AS (
            -- Properties needing evaluation (no statement_id means not yet processed)
            SELECT DISTINCT politician_id FROM properties p
            WHERE p.statement_id IS NULL

            UNION

            -- Positions needing evaluation (no statement_id means not yet processed)
            SELECT DISTINCT politician_id FROM holds_position hp
            WHERE hp.statement_id IS NULL

            UNION

            -- Birthplaces needing evaluation (no statement_id means not yet processed)
            SELECT DISTINCT politician_id FROM born_at ba
            WHERE ba.statement_id IS NULL
        )
        SELECT politician_id FROM politicians_to_evaluate
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
                    selectinload(Property.evaluations),
                    selectinload(Property.archived_page),
                ),
                selectinload(Politician.positions_held).options(
                    selectinload(HoldsPosition.position),
                    selectinload(HoldsPosition.evaluations),
                    selectinload(HoldsPosition.archived_page),
                ),
                selectinload(Politician.birthplaces).options(
                    selectinload(BornAt.location),
                    selectinload(BornAt.evaluations),
                    selectinload(BornAt.archived_page),
                ),
                selectinload(Politician.wikipedia_links),
            )
            .where(Politician.id.in_(politician_ids))
        )

        politicians = db.execute(query).scalars().all()

        result = []
        for politician in politicians:
            # Group properties by type (sorted by value for chronological order)
            properties_by_type = {}
            for prop in sorted(politician.properties, key=lambda x: x.value):
                if prop.type not in properties_by_type:
                    properties_by_type[prop.type] = []
                statement = PropertyStatementResponse(
                    id=prop.id,
                    value=prop.value,
                    value_precision=prop.value_precision,
                    proof_line=prop.proof_line,
                    statement_id=prop.statement_id,
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
                properties_by_type[prop.type].append(statement)

            # Group positions by entity
            positions_by_entity = {}
            for pos in politician.positions_held:
                key = (pos.position.wikidata_id, pos.position.name)
                if key not in positions_by_entity:
                    positions_by_entity[key] = []
                statement = PositionStatementResponse(
                    id=pos.id,
                    proof_line=pos.proof_line,
                    statement_id=pos.statement_id,
                    qualifiers=pos.qualifiers_json,
                    references=pos.references_json,
                    archived_page=(
                        ArchivedPageResponse(
                            id=pos.archived_page.id,
                            url=pos.archived_page.url,
                            content_hash=pos.archived_page.content_hash,
                            fetch_timestamp=pos.archived_page.fetch_timestamp,
                        )
                        if pos.archived_page
                        else None
                    ),
                )
                positions_by_entity[key].append(statement)

            # Group birthplaces by entity (sorted by location name)
            birthplaces_by_entity = {}
            for bp in sorted(politician.birthplaces, key=lambda x: x.location.name):
                key = (bp.location.wikidata_id, bp.location.name)
                if key not in birthplaces_by_entity:
                    birthplaces_by_entity[key] = []
                statement = BirthplaceStatementResponse(
                    id=bp.id,
                    proof_line=bp.proof_line,
                    statement_id=bp.statement_id,
                    qualifiers=bp.qualifiers_json,
                    references=bp.references_json,
                    archived_page=(
                        ArchivedPageResponse(
                            id=bp.archived_page.id,
                            url=bp.archived_page.url,
                            content_hash=bp.archived_page.content_hash,
                            fetch_timestamp=bp.archived_page.fetch_timestamp,
                        )
                        if bp.archived_page
                        else None
                    ),
                )
                birthplaces_by_entity[key].append(statement)

            politician_response = PoliticianResponse(
                id=politician.id,
                name=politician.name,
                wikidata_id=politician.wikidata_id,
                properties=[
                    PropertyResponse(type=prop_type, statements=statements)
                    for prop_type, statements in properties_by_type.items()
                ],
                positions=[
                    PositionResponse(qid=qid, name=name, statements=statements)
                    for (qid, name), statements in positions_by_entity.items()
                ],
                birthplaces=[
                    BirthplaceResponse(qid=qid, name=name, statements=statements)
                    for (qid, name), statements in birthplaces_by_entity.items()
                ],
            )
            result.append(politician_response)

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
        property_count = 0
        position_count = 0
        birthplace_count = 0
        errors = []
        all_evaluations = []

        # Process property evaluations
    for eval_item in request.property_evaluations:
        try:
            property_entity = db.get(Property, eval_item.id)
            if not property_entity:
                errors.append(f"Property {eval_item.id} not found")
                continue

            # Create property evaluation record
            evaluation = PropertyEvaluation(
                user_id=str(current_user.user_id),
                is_confirmed=eval_item.is_confirmed,
                property_id=eval_item.id,
            )
            db.add(evaluation)
            property_count += 1

            # Track all evaluations for Wikidata operations
            all_evaluations.append(evaluation)

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
                user_id=str(current_user.user_id),
                is_confirmed=eval_item.is_confirmed,
                holds_position_id=eval_item.id,
            )
            db.add(evaluation)
            position_count += 1

            # Track all evaluations for Wikidata operations
            all_evaluations.append(evaluation)

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
                user_id=str(current_user.user_id),
                is_confirmed=eval_item.is_confirmed,
                born_at_id=eval_item.id,
            )
            db.add(evaluation)
            birthplace_count += 1

            # Track all evaluations for Wikidata operations
            all_evaluations.append(evaluation)

        except Exception as e:
            errors.append(f"Error processing birthplace {eval_item.id}: {str(e)}")
            continue

    total_processed = property_count + position_count + birthplace_count

    try:
        # Commit local database changes first
        db.commit()

        # Push evaluations to Wikidata (don't rollback local changes on failure)
        wikidata_errors = []

        # Extract JWT token from authenticated user for Wikidata API calls
        jwt_token = current_user.jwt_token
        if not jwt_token:
            wikidata_errors.append("No JWT token available for Wikidata API calls")
        else:
            try:
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

            except Exception as e:
                wikidata_errors.append(
                    f"Error setting up Wikidata operations: {str(e)}"
                )

        # Include Wikidata errors in response but don't fail the request
        if wikidata_errors:
            errors.extend(wikidata_errors)

        return EvaluationResponse(
            success=True,
            message=f"Successfully processed {total_processed} evaluations"
            + (f" ({len(wikidata_errors)} Wikidata errors)" if wikidata_errors else ""),
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
