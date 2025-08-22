"""Database batch insertion operations for dump processing."""

import logging
from datetime import datetime, timezone
from typing import List, Union

from sqlalchemy.dialects.postgresql import insert
from .worker_manager import get_worker_session
from ..models import (
    Position,
    Location,
    Country,
    Politician,
    Property,
    HoldsPosition,
    HasCitizenship,
    BornAt,
    WikipediaLink,
)
from ..entities import (
    WikidataPolitician,
    WikidataPosition,
    WikidataLocation,
    WikidataCountry,
)

logger = logging.getLogger(__name__)


class DatabaseInserter:
    """Handles batch database insertions for dump processing."""

    def insert_entity(
        self,
        entity: Union[
            WikidataPolitician, WikidataPosition, WikidataLocation, WikidataCountry
        ],
    ) -> None:
        """Insert a single entity into the database based on its type."""
        if isinstance(entity, WikidataPolitician):
            self.insert_politicians_batch([entity])
        elif isinstance(entity, WikidataPosition):
            self.insert_positions_batch([entity])
        elif isinstance(entity, WikidataLocation):
            self.insert_locations_batch([entity])
        elif isinstance(entity, WikidataCountry):
            self.insert_countries_batch([entity])
        else:
            raise ValueError(f"Unknown entity type: {type(entity)}")

    def insert_positions_batch(
        self, positions: List[Union[dict, WikidataPosition]]
    ) -> None:
        """Insert a batch of positions into the database."""
        if not positions:
            return

        # Convert entity objects to database dicts
        position_dicts = []
        for p in positions:
            if isinstance(p, WikidataPosition):
                position_dicts.append(p.to_database_dict())
            else:
                position_dicts.append(p)

        session = get_worker_session()
        try:
            # Use PostgreSQL UPSERT for positions
            stmt = insert(Position).values(
                [
                    {
                        "wikidata_id": p["wikidata_id"],
                        "name": p["name"],
                        "embedding": None,  # Will be generated later
                        "class_id": p.get("class_id"),  # May be None if not found
                    }
                    for p in position_dicts
                ]
            )

            # On conflict, update the name and class_id (in case it changed in Wikidata)
            stmt = stmt.on_conflict_do_update(
                index_elements=["wikidata_id"],
                set_={
                    "name": stmt.excluded.name,
                    "class_id": stmt.excluded.class_id,
                    "updated_at": stmt.excluded.updated_at,
                },
            )

            session.execute(stmt)
            session.commit()
            logger.debug(f"Processed {len(position_dicts)} positions (upserted)")
            # Skip logging when no new positions - this is normal

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def insert_locations_batch(
        self, locations: List[Union[dict, WikidataLocation]]
    ) -> None:
        """Insert a batch of locations into the database."""
        if not locations:
            return

        # Convert entity objects to database dicts
        location_dicts = []
        for loc in locations:
            if isinstance(loc, WikidataLocation):
                location_dicts.append(loc.to_database_dict())
            else:
                location_dicts.append(loc)

        session = get_worker_session()
        try:
            # Use PostgreSQL UPSERT for locations
            stmt = insert(Location).values(
                [
                    {
                        "wikidata_id": loc["wikidata_id"],
                        "name": loc["name"],
                        "embedding": None,  # Will be generated later
                        "class_id": loc.get("class_id"),  # May be None if not found
                    }
                    for loc in location_dicts
                ]
            )

            # On conflict, update the name and class_id (in case it changed in Wikidata)
            stmt = stmt.on_conflict_do_update(
                index_elements=["wikidata_id"],
                set_={
                    "name": stmt.excluded.name,
                    "class_id": stmt.excluded.class_id,
                    "updated_at": stmt.excluded.updated_at,
                },
            )

            session.execute(stmt)
            session.commit()
            logger.debug(f"Processed {len(location_dicts)} locations (upserted)")
            # Skip logging when no new locations - this is normal

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def insert_countries_batch(
        self, countries: List[Union[dict, WikidataCountry]]
    ) -> None:
        """Insert a batch of countries into the database using ON CONFLICT."""
        if not countries:
            return

        # Convert entity objects to database dicts
        country_dicts = []
        for c in countries:
            if isinstance(c, WikidataCountry):
                country_dicts.append(c.to_database_dict())
            else:
                country_dicts.append(c)

        session = get_worker_session()
        try:
            # Prepare data for bulk insert
            country_data = [
                {
                    "wikidata_id": c["wikidata_id"],
                    "name": c["name"],
                    "iso_code": c["iso_code"],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                for c in country_dicts
            ]

            # Use PostgreSQL's ON CONFLICT to handle duplicates
            # We need to handle both wikidata_id and iso_code constraints
            # Use ON CONFLICT DO UPDATE for wikidata_id to allow name updates
            stmt = insert(Country).values(country_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["wikidata_id"],
                set_={
                    "name": stmt.excluded.name,
                    "iso_code": stmt.excluded.iso_code,
                    "updated_at": stmt.excluded.updated_at,
                },
            )

            session.execute(stmt)
            session.commit()

            logger.debug(f"Processed {len(country_dicts)} countries (upserted)")

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def insert_politicians_batch(
        self, politicians: List[Union[dict, WikidataPolitician]]
    ) -> None:
        """Insert a batch of politicians into the database."""
        if not politicians:
            return

        # Convert entity objects to database dicts
        politician_dicts = []
        for p in politicians:
            if isinstance(p, WikidataPolitician):
                politician_dicts.append(p.to_database_dict())
            else:
                politician_dicts.append(p)

        session = get_worker_session()
        try:
            # Use PostgreSQL UPSERT for politicians
            stmt = insert(Politician).values(
                [
                    {
                        "wikidata_id": p["wikidata_id"],
                        "name": p["name"],
                    }
                    for p in politician_dicts
                ]
            )

            # On conflict, update the name (in case it changed in Wikidata)
            stmt = stmt.on_conflict_do_update(
                index_elements=["wikidata_id"],
                set_={
                    "name": stmt.excluded.name,
                    "updated_at": stmt.excluded.updated_at,
                },
            )

            session.execute(stmt)
            session.flush()

            # Get all politician objects (both new and existing)
            politician_objects = (
                session.query(Politician)
                .filter(
                    Politician.wikidata_id.in_(
                        [p["wikidata_id"] for p in politician_dicts]
                    )
                )
                .all()
            )

            # Create mapping for easy lookup
            politician_map = {pol.wikidata_id: pol for pol in politician_objects}

            # Now process related data for each politician
            for politician_data in politician_dicts:
                politician_obj = politician_map[politician_data["wikidata_id"]]

                # Handle relationships: need to check if they already exist to avoid duplicates
                # For re-imports, we want to add new relationships but not duplicate existing ones

                # Add properties using UPSERT - update only if NOT extracted (preserve user evaluations)
                for prop in politician_data.get("properties", []):
                    prop_stmt = insert(Property).values(
                        politician_id=politician_obj.id,
                        type=prop["type"],
                        value=prop["value"],
                        value_precision=prop.get("value_precision"),
                        archived_page_id=None,
                    )

                    # Update only if archived_page_id is None (preserve extracted data)
                    prop_stmt = prop_stmt.on_conflict_do_update(
                        index_elements=["politician_id", "type"],
                        set_={
                            "value": prop_stmt.excluded.value,
                            "value_precision": prop_stmt.excluded.value_precision,
                            "updated_at": prop_stmt.excluded.updated_at,
                        },
                        where=Property.archived_page_id.is_(None),
                    )

                    session.execute(prop_stmt)

                # Add positions - only link to existing positions
                for pos in politician_data.get("positions", []):
                    position_obj = (
                        session.query(Position)
                        .filter_by(wikidata_id=pos["wikidata_id"])
                        .first()
                    )

                    if position_obj:
                        # Check if this exact relationship already exists
                        existing_position = (
                            session.query(HoldsPosition)
                            .filter_by(
                                politician_id=politician_obj.id,
                                position_id=position_obj.id,
                                start_date=pos.get("start_date"),
                                end_date=pos.get("end_date"),
                            )
                            .first()
                        )

                        if existing_position:
                            # Update precision if this is NOT extracted data (preserve user evaluations)
                            if existing_position.archived_page_id is None:
                                existing_position.start_date_precision = pos.get(
                                    "start_date_precision"
                                )
                                existing_position.end_date_precision = pos.get(
                                    "end_date_precision"
                                )
                        else:
                            # Insert new position relationship
                            holds_position = HoldsPosition(
                                politician_id=politician_obj.id,
                                position_id=position_obj.id,
                                start_date=pos.get("start_date"),
                                start_date_precision=pos.get("start_date_precision"),
                                end_date=pos.get("end_date"),
                                end_date_precision=pos.get("end_date_precision"),
                                archived_page_id=None,
                            )
                            session.add(holds_position)

                # Add citizenships - only link to existing countries
                for citizenship_id in politician_data.get("citizenships", []):
                    country_obj = (
                        session.query(Country)
                        .filter_by(wikidata_id=citizenship_id)
                        .first()
                    )

                    if country_obj:
                        # Check if this citizenship already exists
                        existing_citizenship = (
                            session.query(HasCitizenship)
                            .filter_by(
                                politician_id=politician_obj.id,
                                country_id=country_obj.id,
                            )
                            .first()
                        )

                        if not existing_citizenship:
                            has_citizenship = HasCitizenship(
                                politician_id=politician_obj.id,
                                country_id=country_obj.id,
                            )
                            session.add(has_citizenship)

                # Add birthplace - only link to existing locations
                birthplace_id = politician_data.get("birthplace")
                if birthplace_id:
                    location_obj = (
                        session.query(Location)
                        .filter_by(wikidata_id=birthplace_id)
                        .first()
                    )

                    if location_obj:
                        # Check if this birthplace already exists
                        existing_birthplace = (
                            session.query(BornAt)
                            .filter_by(
                                politician_id=politician_obj.id,
                                location_id=location_obj.id,
                            )
                            .first()
                        )

                        if not existing_birthplace:
                            born_at = BornAt(
                                politician_id=politician_obj.id,
                                location_id=location_obj.id,
                                archived_page_id=None,
                            )
                            session.add(born_at)

                # Add Wikipedia links
                for wiki_link in politician_data.get("wikipedia_links", []):
                    # Check if this Wikipedia link already exists
                    existing_link = (
                        session.query(WikipediaLink)
                        .filter_by(
                            politician_id=politician_obj.id,
                            url=wiki_link["url"],
                        )
                        .first()
                    )

                    if not existing_link:
                        wikipedia_link = WikipediaLink(
                            politician_id=politician_obj.id,
                            url=wiki_link["url"],
                            language_code=wiki_link.get("language", "en"),
                        )
                        session.add(wikipedia_link)

            session.commit()
            logger.debug(f"Processed {len(politician_dicts)} politicians (upserted)")

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
