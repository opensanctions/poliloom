"""Politicians API endpoints."""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..database import get_engine
from ..models import (
    Politician,
    Property,
)
from .schemas import (
    PoliticianResponse,
    PropertyResponse,
    ArchivedPageResponse,
)
from .auth import get_current_user, User

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
