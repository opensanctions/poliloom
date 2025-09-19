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
            -- Properties needing evaluation
            SELECT DISTINCT politician_id FROM properties p
            WHERE (
                -- Newly extracted statements (no statement_id, has archived_page_id, no negative evaluations)
                (p.archived_page_id IS NOT NULL AND p.statement_id IS NULL AND NOT EXISTS (
                    SELECT 1 FROM property_evaluations
                    WHERE property_id = p.id AND is_confirmed = false
                ))
                OR
                -- Failed deletion (has statement_id, no archived_page_id, has negative evaluations)
                (p.statement_id IS NOT NULL AND p.archived_page_id IS NULL AND EXISTS (
                    SELECT 1 FROM property_evaluations
                    WHERE property_id = p.id AND is_confirmed = false
                ))
            )

            UNION

            -- Positions needing evaluation
            SELECT DISTINCT politician_id FROM holds_position hp
            WHERE (
                -- Newly extracted statements
                (hp.archived_page_id IS NOT NULL AND hp.statement_id IS NULL AND NOT EXISTS (
                    SELECT 1 FROM position_evaluations
                    WHERE holds_position_id = hp.id AND is_confirmed = false
                ))
                OR
                -- Failed deletion
                (hp.statement_id IS NOT NULL AND hp.archived_page_id IS NULL AND EXISTS (
                    SELECT 1 FROM position_evaluations
                    WHERE holds_position_id = hp.id AND is_confirmed = false
                ))
            )

            UNION

            -- Birthplaces needing evaluation
            SELECT DISTINCT politician_id FROM born_at ba
            WHERE (
                -- Newly extracted statements
                (ba.archived_page_id IS NOT NULL AND ba.statement_id IS NULL AND NOT EXISTS (
                    SELECT 1 FROM birthplace_evaluations
                    WHERE born_at_id = ba.id AND is_confirmed = false
                ))
                OR
                -- Failed deletion
                (ba.statement_id IS NOT NULL AND ba.archived_page_id IS NULL AND EXISTS (
                    SELECT 1 FROM birthplace_evaluations
                    WHERE born_at_id = ba.id AND is_confirmed = false
                ))
            )
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

        # Now fetch the full politician objects with ALL their relationships
        # We load everything since we want to show all statements for context
        query = (
            select(Politician)
            .options(
                selectinload(Politician.properties).selectinload(Property.evaluations),
                selectinload(Politician.properties).selectinload(
                    Property.archived_page
                ),
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
            .where(Politician.id.in_(politician_ids))
        )

        politicians = db.execute(query).scalars().all()

        result = []
        for politician in politicians:
            # Group properties by type (sorted by value for chronological order)
            # Only include properties that haven't been successfully processed
            properties_by_type = {}
            for prop in sorted(politician.properties, key=lambda x: x.value):
                # The SQL query already filters for statements needing evaluation
                # No need to filter again in Python
                if prop.type not in properties_by_type:
                    properties_by_type[prop.type] = []
                statement = PropertyStatementResponse(
                    id=prop.id,
                    value=prop.value,
                    value_precision=prop.value_precision,
                    proof_line=prop.proof_line,
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

            # Group positions by entity (sorted by start_date for chronological order)
            # Only include positions that haven't been successfully processed
            positions_by_entity = {}
            for pos in sorted(
                politician.positions_held,
                key=lambda x: (x.start_date or "", x.end_date or ""),
            ):
                # The SQL query already filters for statements needing evaluation
                # No need to filter again in Python
                key = (pos.position.wikidata_id, pos.position.name)
                if key not in positions_by_entity:
                    positions_by_entity[key] = []
                statement = PositionStatementResponse(
                    id=pos.id,
                    start_date=pos.start_date,
                    start_date_precision=pos.start_date_precision,
                    end_date=pos.end_date,
                    end_date_precision=pos.end_date_precision,
                    proof_line=pos.proof_line,
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
            # Only include birthplaces that haven't been successfully processed
            birthplaces_by_entity = {}
            for bp in sorted(politician.birthplaces, key=lambda x: x.location.name):
                # The SQL query already filters for statements needing evaluation
                # No need to filter again in Python
                key = (bp.location.wikidata_id, bp.location.name)
                if key not in birthplaces_by_entity:
                    birthplaces_by_entity[key] = []
                statement = BirthplaceStatementResponse(
                    id=bp.id,
                    proof_line=bp.proof_line,
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
                user_id=str(current_user.user_id),
                is_confirmed=eval_item.is_confirmed,
                holds_position_id=eval_item.id,
            )
            db.add(evaluation)
            position_count += 1

            # Track all evaluations for Wikidata operations
            all_evaluations.append(evaluation)

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
                user_id=str(current_user.user_id),
                is_confirmed=eval_item.is_confirmed,
                born_at_id=eval_item.id,
            )
            db.add(evaluation)
            birthplace_count += 1

            # Track all evaluations for Wikidata operations
            all_evaluations.append(evaluation)

            # If not confirmed, remove the original entity
            if not eval_item.is_confirmed:
                db.delete(birthplace_entity)

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
