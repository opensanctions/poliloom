"""Evaluations API endpoints."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db_session
from ..enrichment import (
    count_politicians_with_unevaluated,
    enrich_batch,
    has_enrichable_politicians,
)
from ..models import (
    ArchivedPage,
    ArchivedPageLanguage,
    Evaluation,
    Politician,
    Property,
)
from ..wikidata_statement import push_evaluation
from .auth import User, get_current_user
from .schemas import (
    ArchivedPageResponse,
    EnrichmentMetadata,
    EvaluationObjectResponse,
    EvaluationRequest,
    EvaluationResponse,
    PoliticianResponse,
    PoliticiansListResponse,
    PropertyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Thread pool for background enrichment tasks (4 concurrent workers)
_enrichment_executor = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="enrichment"
)


@router.get("/politicians", response_model=PoliticiansListResponse)
async def get_politicians_for_evaluation(
    limit: int = Query(
        default=2, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of politicians to skip"),
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter by language QIDs - politicians with properties from archived pages with matching language",
    ),
    countries: Optional[List[str]] = Query(
        default=None,
        description="Filter by country QIDs - politicians with citizenship for these countries",
    ),
    exclude_ids: Optional[List[str]] = Query(
        default=None,
        description="Exclude politicians with these UUIDs from results (for avoiding duplicates during navigation)",
    ),
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve politicians with unevaluated extracted data for review and evaluation.

    Returns a list of politicians that have properties without statement_id (unevaluated).
    Automatically triggers background enrichment if the number of politicians with
    unevaluated properties falls below MIN_UNEVALUATED_POLITICIANS (default: 10).

    Response includes metadata about enrichment status for UI empty states.
    """
    # Build composable politician query
    query = Politician.query_base()

    # Always filter for unevaluated properties
    query = Politician.filter_by_unevaluated_properties(query, languages=languages)

    if countries:
        query = Politician.filter_by_countries(query, countries)

    # Exclude specific politician IDs (for avoiding duplicates during navigation)
    if exclude_ids:
        try:
            exclude_uuids = [UUID(id_str) for id_str in exclude_ids]
            query = query.where(Politician.id.notin_(exclude_uuids))
        except ValueError:
            # Invalid UUID format - log and ignore
            logger.warning(f"Invalid UUID format in exclude_ids: {exclude_ids}")

    # Load related data
    if languages:
        # Filter properties: include Wikidata properties OR properties with matching language
        property_filter = and_(
            Property.deleted_at.is_(None),
            or_(
                # Include Wikidata properties (no archived page)
                Property.archived_page_id.is_(None),
                # Include properties where archived page has matching language
                Property.archived_page_id.in_(
                    select(ArchivedPageLanguage.archived_page_id).where(
                        ArchivedPageLanguage.language_id.in_(languages)
                    )
                ),
            ),
        )

        query = query.options(
            selectinload(Politician.properties.and_(property_filter)).options(
                selectinload(Property.entity),
                selectinload(Property.archived_page).selectinload(
                    ArchivedPage.language_entities
                ),
            ),
            selectinload(Politician.wikipedia_links),
        )
    else:
        # No language filter, load all properties
        query = query.options(
            selectinload(
                Politician.properties.and_(Property.deleted_at.is_(None))
            ).options(
                selectinload(Property.entity),
                selectinload(Property.archived_page).selectinload(
                    ArchivedPage.language_entities
                ),
            ),
            selectinload(Politician.wikipedia_links),
        )

    # Random ordering for variety
    query = query.order_by(func.random())

    # Apply offset and limit
    query = query.offset(offset).limit(limit)

    # Apply populate_existing to ensure fresh property loads when using .and_() filters
    query = query.execution_options(populate_existing=True)

    # Execute query
    politicians = db.execute(query).scalars().all()

    # Track enrichment status for empty state UX
    min_threshold = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
    current_count = count_politicians_with_unevaluated(db, languages, countries)

    # Check if there are politicians available to enrich (for "all caught up" state)
    can_enrich = has_enrichable_politicians(db, languages, countries)

    if current_count < min_threshold and can_enrich:
        logger.info(
            f"Only {current_count} politicians with unevaluated properties (threshold: {min_threshold}), triggering enrichment batch"
        )
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            _enrichment_executor,
            enrich_batch,
            languages,
            countries,
        )

    result = []
    for politician in politicians:
        property_responses = []
        for prop in politician.properties:
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
                    supporting_quotes=prop.supporting_quotes,
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

    return PoliticiansListResponse(
        politicians=result,
        meta=EnrichmentMetadata(
            has_enrichable_politicians=can_enrich,
            total_matching_filters=current_count,
        ),
    )


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
