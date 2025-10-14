"""Politicians API endpoints."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_, or_, func

from ..database import get_engine
from ..models import (
    Politician,
    Property,
    PropertyType,
    ArchivedPage,
    Language,
    WikidataEntity,
)
from .schemas import (
    PoliticianResponse,
    PropertyResponse,
    ArchivedPageResponse,
    PoliticianCreateRequest,
    PoliticianCreateResponse,
    PropertyAddRequest,
    PropertyAddResponse,
)
from .auth import get_current_user, User
from ..enrichment import enrich_until_target
from ..wikidata_statement import (
    create_entity,
    create_statement,
    prepare_property_for_statement,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Thread pool for background enrichment tasks (4 concurrent workers)
_enrichment_executor = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="enrichment"
)


@router.get("", response_model=List[PoliticianResponse])
async def get_politicians(
    limit: int = Query(
        default=2, le=100, description="Maximum number of politicians to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of politicians to skip"),
    search: Optional[str] = Query(
        default=None,
        description="Search politicians by name/label using fuzzy matching",
    ),
    has_unevaluated: Optional[bool] = Query(
        default=None,
        description="Filter to only politicians with unevaluated properties. If not specified, returns all politicians.",
    ),
    languages: Optional[List[str]] = Query(
        default=None,
        description="Filter by language QIDs - politicians with properties from archived pages with matching iso1_code or iso3_code",
    ),
    countries: Optional[List[str]] = Query(
        default=None,
        description="Filter by country QIDs - politicians with citizenship for these countries",
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve politicians that have unevaluated extracted data.

    Returns a list of politicians with their Wikidata properties, positions, birthplaces
    and unevaluated extracted data for review and evaluation.

    Automatically triggers background enrichment if the number of politicians with
    unevaluated properties falls below MIN_UNEVALUATED_POLITICIANS (default: 10).
    """
    with Session(get_engine()) as db:
        # Build composable politician query
        query = Politician.query_base()

        # Apply filters
        if search:
            query = Politician.search_by_label(query, search)

        if has_unevaluated is True:
            query = Politician.filter_by_unevaluated_properties(
                query, languages=languages
            )
        elif has_unevaluated is False:
            # Explicitly filter for politicians WITH evaluated properties
            # (inverse of unevaluated filter) - currently not implemented
            # For now, has_unevaluated=false returns all politicians
            pass

        if countries:
            query = Politician.filter_by_countries(query, countries)

        # Load related data with selectinload
        if languages:
            # When language filter is active, we need to filter properties
            query = query.options(
                selectinload(
                    Politician.properties.and_(
                        and_(
                            Property.deleted_at.is_(
                                None
                            ),  # Exclude soft-deleted properties
                            or_(
                                Property.archived_page_id.is_(
                                    None
                                ),  # Include Wikidata properties
                                Property.archived_page.has(
                                    ArchivedPage.iso1_code.in_(
                                        select(Language.iso1_code).where(
                                            Language.wikidata_id.in_(languages)
                                        )
                                    )
                                )
                                | Property.archived_page.has(
                                    ArchivedPage.iso3_code.in_(
                                        select(Language.iso3_code).where(
                                            Language.wikidata_id.in_(languages)
                                        )
                                    )
                                ),
                            ),
                        )
                    )
                ).options(
                    selectinload(Property.entity),
                    selectinload(Property.archived_page),
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
                    selectinload(Property.archived_page),
                ),
                selectinload(Politician.wikipedia_links),
            )

        # Apply random ordering if not searching (search already orders by similarity)
        if not search:
            query = query.order_by(func.random())

        # Apply offset and limit
        query = query.offset(offset).limit(limit)

        # Execute query
        politicians = db.execute(query).scalars().all()

        # Trigger background enrichment when filtering for unevaluated
        if has_unevaluated is True:
            min_unevaluated = int(os.getenv("MIN_UNEVALUATED_POLITICIANS", "10"))
            # Always queue enrichment job - executor handles concurrent workers and queue
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
                _enrichment_executor,
                enrich_until_target,
                min_unevaluated,
                languages,
                countries,
            )

        if not politicians:
            return []

        result = []
        for politician in politicians:
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


@router.post("", response_model=PoliticianCreateResponse, status_code=201)
async def create_politician(
    request: PoliticianCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create multiple politicians with associated properties in batch.

    This endpoint creates new politician entries without wikidata_id initially.
    The wikidata_id will be assigned later when the politicians are created in Wikidata.

    Returns PoliticianCreateResponse with success status and full politician data.
    """
    with Session(get_engine()) as db:
        created_politician_ids = []
        errors = []

        for politician_data in request.politicians:
            try:
                # Create politician directly (without wikidata_id)
                politician = Politician(
                    name=politician_data.name,
                    wikidata_id=None,  # Will be assigned later when created in Wikidata
                )
                db.add(politician)
                db.flush()  # Flush to get the politician ID

                # Create properties
                for prop_data in politician_data.properties:
                    # Validate property type
                    try:
                        prop_type = PropertyType(prop_data.type)
                    except ValueError:
                        errors.append(
                            f"Politician '{politician_data.name}': Invalid property type {prop_data.type}"
                        )
                        continue

                    # Create property
                    new_property = Property(
                        politician_id=politician.id,
                        type=prop_type,
                        value=prop_data.value,
                        value_precision=prop_data.value_precision,
                        entity_id=prop_data.entity_id,
                        qualifiers_json=prop_data.qualifiers_json,
                        references_json=prop_data.references_json,
                    )

                    db.add(new_property)

                created_politician_ids.append(politician.id)

            except Exception as e:
                errors.append(
                    f"Error creating politician '{politician_data.name}': {str(e)}"
                )
                continue

        try:
            # Commit all changes
            db.commit()
        except Exception as e:
            db.rollback()
            return PoliticianCreateResponse(
                success=False,
                message=f"Database error: {str(e)}",
                politicians=[],
                errors=errors,
            )

        # Reload politicians with properties to return full data
        politicians = (
            db.query(Politician).filter(Politician.id.in_(created_politician_ids)).all()
        )

        # Create entities and statements in Wikidata
        # Get JWT token from current_user
        jwt_token = current_user.jwt_token

        for politician in politicians:
            try:
                # Create entity in Wikidata
                logger.info(
                    f"Creating Wikidata entity for politician: {politician.name}"
                )
                entity_id = await create_entity(
                    label=politician.name,
                    description=None,
                    jwt_token=jwt_token,
                )

                # Create WikidataEntity in database
                wikidata_entity = WikidataEntity(
                    wikidata_id=entity_id,
                    name=politician.name,
                    description=None,
                )
                db.add(wikidata_entity)
                db.flush()

                # Update politician with wikidata_id
                politician.wikidata_id = entity_id

                # Create P31 (instance of) → Q5 (human) statement
                logger.info(f"Creating P31→Q5 statement for {entity_id}")
                await create_statement(
                    entity_id=entity_id,
                    property_id="P31",
                    value={"type": "value", "content": "Q5"},
                    jwt_token=jwt_token,
                )

                # Create P106 (occupation) → Q82955 (politician) statement
                logger.info(f"Creating P106→Q82955 statement for {entity_id}")
                await create_statement(
                    entity_id=entity_id,
                    property_id="P106",
                    value={"type": "value", "content": "Q82955"},
                    jwt_token=jwt_token,
                )

                # Create statements for all properties
                properties = (
                    db.query(Property)
                    .filter(Property.politician_id == politician.id)
                    .filter(Property.deleted_at.is_(None))
                    .all()
                )

                for prop in properties:
                    try:
                        # Prepare property for statement creation
                        value, qualifiers = prepare_property_for_statement(prop)

                        # Create statement
                        logger.info(
                            f"Creating statement for {entity_id} with property {prop.type.value}"
                        )
                        statement_id = await create_statement(
                            entity_id=entity_id,
                            property_id=prop.type.value,
                            value=value,
                            qualifiers=qualifiers,
                            references=prop.references_json,
                            jwt_token=jwt_token,
                        )

                        # Update property with statement_id
                        prop.statement_id = statement_id

                    except Exception as e:
                        logger.error(
                            f"Failed to create statement for property {prop.id}: {e}"
                        )
                        errors.append(
                            f"Politician '{politician.name}': Failed to create statement for {prop.type.value} - {str(e)}"
                        )
                        continue

                # Commit updates for this politician
                db.commit()
                logger.info(
                    f"Successfully created Wikidata entity {entity_id} for politician {politician.name}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to create Wikidata entity for {politician.name}: {e}"
                )
                errors.append(
                    f"Politician '{politician.name}': Wikidata creation failed - {str(e)}"
                )
                # Rollback changes for this politician
                db.rollback()
                # Reload politician state after rollback
                db.refresh(politician)
                continue

        # Build response with full politician data
        result = []
        for politician in politicians:
            properties = (
                db.query(Property)
                .filter(Property.politician_id == politician.id)
                .filter(Property.deleted_at.is_(None))
                .all()
            )

            property_responses = []
            for prop in properties:
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
                        archived_page=None,  # New properties don't have archived pages
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

        return PoliticianCreateResponse(
            success=True,
            message=f"Successfully created {len(result)} politician(s)"
            + (f" ({len(errors)} errors)" if errors else ""),
            politicians=result,
            errors=errors,
        )


@router.post(
    "/{politician_id}/properties", response_model=PropertyAddResponse, status_code=201
)
async def add_properties(
    request: PropertyAddRequest,
    politician_id: str = Path(
        ..., description="UUID of the politician to add properties to"
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Add multiple properties to an existing politician.

    This endpoint allows adding new properties to a politician that already exists
    in the database. The properties will be created without statement_id initially
    and can be evaluated later.

    Returns PropertyAddResponse with success status and full property data.
    """
    with Session(get_engine()) as db:
        # Validate politician exists
        try:
            politician_uuid = UUID(politician_id)
        except ValueError:
            return PropertyAddResponse(
                success=False,
                message=f"Invalid politician ID format: {politician_id}",
                properties=[],
                errors=[],
            )

        politician = db.get(Politician, politician_uuid)
        if not politician:
            return PropertyAddResponse(
                success=False,
                message=f"Politician not found: {politician_id}",
                properties=[],
                errors=[],
            )

        created_property_ids = []
        errors = []

        for prop_data in request.properties:
            try:
                # Validate property type
                try:
                    prop_type = PropertyType(prop_data.type)
                except ValueError:
                    errors.append(f"Invalid property type {prop_data.type}")
                    continue

                # Create property
                new_property = Property(
                    politician_id=politician_uuid,
                    type=prop_type,
                    value=prop_data.value,
                    value_precision=prop_data.value_precision,
                    entity_id=prop_data.entity_id,
                    qualifiers_json=prop_data.qualifiers_json,
                    references_json=prop_data.references_json,
                )

                db.add(new_property)
                db.flush()  # Flush to get the property ID
                created_property_ids.append(new_property.id)

            except Exception as e:
                errors.append(f"Error creating property: {str(e)}")
                continue

        try:
            # Commit all changes
            db.commit()
        except Exception as e:
            db.rollback()
            return PropertyAddResponse(
                success=False,
                message=f"Database error: {str(e)}",
                properties=[],
                errors=errors,
            )

        # Reload properties with related data to return full data
        properties = (
            db.query(Property)
            .filter(Property.id.in_(created_property_ids))
            .filter(Property.deleted_at.is_(None))
            .all()
        )

        # Create statements in Wikidata if politician has wikidata_id
        if politician.wikidata_id:
            # Get JWT token from current_user
            jwt_token = current_user.jwt_token

            for prop in properties:
                try:
                    # Prepare property for statement creation
                    value, qualifiers = prepare_property_for_statement(prop)

                    # Create statement
                    logger.info(
                        f"Creating statement for {politician.wikidata_id} with property {prop.type.value}"
                    )
                    statement_id = await create_statement(
                        entity_id=politician.wikidata_id,
                        property_id=prop.type.value,
                        value=value,
                        qualifiers=qualifiers,
                        references=prop.references_json,
                        jwt_token=jwt_token,
                    )

                    # Update property with statement_id
                    prop.statement_id = statement_id

                except Exception as e:
                    logger.error(
                        f"Failed to create statement for property {prop.id}: {e}"
                    )
                    errors.append(
                        f"Failed to create statement for {prop.type.value} - {str(e)}"
                    )
                    continue

            # Commit statement_id updates
            try:
                db.commit()
                logger.info(
                    f"Successfully created {len(properties)} statement(s) for politician {politician.wikidata_id}"
                )
            except Exception as e:
                logger.error(f"Failed to commit statement IDs: {e}")
                errors.append(f"Failed to save statement IDs - {str(e)}")
                db.rollback()
        else:
            logger.warning(
                f"Politician {politician.id} has no wikidata_id - statements will be pushed when entity is created"
            )

        # Build response with full property data
        property_responses = []
        for prop in properties:
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
                    archived_page=None,  # New properties don't have archived pages
                )
            )

        return PropertyAddResponse(
            success=True,
            message=f"Successfully added {len(property_responses)} property/properties"
            + (f" ({len(errors)} errors)" if errors else ""),
            properties=property_responses,
            errors=errors,
        )
