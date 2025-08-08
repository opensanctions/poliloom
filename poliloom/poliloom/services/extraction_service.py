"""Generic two-stage LLM extraction service for consolidating position and birthplace extraction patterns."""

import logging
from typing import List, Optional, TypeVar, Generic, Protocol
from sqlalchemy.orm import Session
from pydantic import BaseModel, create_model
from typing import Literal
from openai import OpenAI

from ..models import Position, Location, Politician

logger = logging.getLogger(__name__)

# Type variables for generic extraction
ExtractedT = TypeVar("ExtractedT", bound=BaseModel)
FreeFormT = TypeVar("FreeFormT", bound=BaseModel)
MappingResultT = TypeVar("MappingResultT", bound=BaseModel)
EntityT = TypeVar("EntityT")


class EntityRepository(Protocol[EntityT]):
    """Protocol for entity repositories that support similarity search."""

    def find_similar_entities(
        self, db: Session, query_text: str, max_results: int = 100
    ) -> List[str]:
        """Find similar entities using embedding similarity search."""
        ...

    def find_exact_entity(self, db: Session, entity_name: str) -> Optional[EntityT]:
        """Find exact entity match by name."""
        ...


class PositionRepository:
    """Repository for position-related operations."""

    def find_similar_entities(
        self, db: Session, query_text: str, max_results: int = 100
    ) -> List[str]:
        """Find similar positions using embedding similarity search."""
        from ..embeddings import generate_embedding

        query_embedding = generate_embedding(query_text)

        positions = (
            db.query(Position)
            .filter(Position.embedding.isnot(None))
            .order_by(Position.embedding.cosine_distance(query_embedding))
            .limit(max_results)
            .all()
        )

        return [position.name for position in positions]

    def find_exact_entity(self, db: Session, entity_name: str) -> Optional[Position]:
        """Find exact position match by name."""
        return db.query(Position).filter_by(name=entity_name).first()


class LocationRepository:
    """Repository for location-related operations."""

    def find_similar_entities(
        self, db: Session, query_text: str, max_results: int = 100
    ) -> List[str]:
        """Find similar locations using embedding similarity search."""
        from ..embeddings import generate_embedding

        query_embedding = generate_embedding(query_text)

        locations = (
            db.query(Location)
            .filter(Location.embedding.isnot(None))
            .order_by(Location.embedding.cosine_distance(query_embedding))
            .limit(max_results)
            .all()
        )

        return [location.name for location in locations]

    def find_exact_entity(self, db: Session, entity_name: str) -> Optional[Location]:
        """Find exact location match by name."""
        return db.query(Location).filter_by(name=entity_name).first()


class ExtractionPromptConfig(BaseModel):
    """Configuration for extraction prompts."""

    stage1_system_prompt: str
    stage1_user_prompt_template: str
    stage2_system_prompt: str
    stage2_user_prompt_template: str


class TwoStageExtractionService(
    Generic[ExtractedT, FreeFormT, MappingResultT, EntityT]
):
    """Generic service for two-stage LLM extraction with similarity search and mapping."""

    def __init__(
        self,
        openai_client: OpenAI,
        repository: EntityRepository[EntityT],
        prompt_config: ExtractionPromptConfig,
        free_form_response_model: type[BaseModel],
        mapping_result_factory: callable,
        extracted_model_factory: callable,
    ):
        self.openai_client = openai_client
        self.repository = repository
        self.prompt_config = prompt_config
        self.free_form_response_model = free_form_response_model
        self.mapping_result_factory = mapping_result_factory
        self.extracted_model_factory = extracted_model_factory

    def extract_and_map(
        self,
        db: Session,
        content: str,
        politician_name: str,
        country: str,
        politician: Politician,
        entity_name: str,
        source_url: str = None,
    ) -> Optional[List[ExtractedT]]:
        """
        Perform two-stage extraction: free-form extraction + Wikidata mapping.

        Args:
            db: Database session
            content: Text content to extract from
            politician_name: Name of the politician
            country: Country of the politician
            politician: Politician entity
            entity_name: Name of the entity type being extracted (for logging)
            source_url: URL of the content source (for source type detection)

        Returns:
            List of extracted and mapped entities
        """
        try:
            # Stage 1: Free-form extraction
            free_form_entities = self._extract_free_form(
                content, politician_name, country, entity_name, source_url
            )

            if free_form_entities is None:
                # LLM extraction failed
                return None

            if not free_form_entities:
                logger.warning(
                    f"No free-form {entity_name} extracted for {politician_name}"
                )
                return []

            # Stage 2: Map each entity to Wikidata
            mapped_entities = []
            for free_entity in free_form_entities:
                mapped_entity = self._map_to_wikidata(
                    db, free_entity, politician, entity_name
                )
                if mapped_entity:
                    mapped_entities.append(mapped_entity)

            logger.info(
                f"Mapped {len(mapped_entities)} out of {len(free_form_entities)} "
                f"extracted {entity_name} for {politician_name}"
            )

            return mapped_entities

        except Exception as e:
            logger.error(f"Error extracting {entity_name} with two-stage approach: {e}")
            return None

    def _extract_free_form(
        self,
        content: str,
        politician_name: str,
        country: str,
        entity_name: str,
        source_url: str,
    ) -> Optional[List[FreeFormT]]:
        """Stage 1: Extract entities in free-form without constraints."""
        try:
            user_prompt = self.prompt_config.stage1_user_prompt_template.format(
                politician_name=politician_name,
                content=content,
                country=country or "Unknown",
                source_url=source_url or "Unknown",
            )

            logger.debug(
                f"Stage 1: Free-form {entity_name} extraction for {politician_name}"
            )

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_config.stage1_system_prompt,
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format=self.free_form_response_model,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error(f"OpenAI free-form {entity_name} extraction returned None")
                logger.error(f"Response content: {message.content}")
                logger.error(f"Response refusal: {getattr(message, 'refusal', None)}")
                return None

            # Extract entities from the response based on the model structure
            entities = getattr(message.parsed, self._get_entities_field_name(), [])

            logger.info(
                f"Stage 1: Extracted {len(entities)} free-form {entity_name} for {politician_name}"
            )

            return entities

        except Exception as e:
            logger.error(f"Error in Stage 1 free-form {entity_name} extraction: {e}")
            return None

    def _map_to_wikidata(
        self,
        db: Session,
        free_entity: FreeFormT,
        politician: Politician,
        entity_name: str,
    ) -> Optional[ExtractedT]:
        """Stage 2: Map a free-form entity to Wikidata using similarity search + LLM mapping."""
        try:
            # Get entity name from free-form entity
            entity_text = self._get_entity_text(free_entity)

            # Use similarity search + LLM mapping
            similar_entities = self.repository.find_similar_entities(db, entity_text)

            if not similar_entities:
                logger.debug(f"No similar {entity_name} found for '{entity_text}'")
                return None

            # Use LLM to map to correct Wikidata entity
            mapped_entity_name = self._llm_map_to_wikidata(
                entity_text,
                similar_entities,
                self._get_proof_text(free_entity),
                entity_name,
            )

            if not mapped_entity_name:
                logger.debug(
                    f"LLM could not map '{entity_text}' to Wikidata {entity_name}"
                )
                return None

            # Verify the mapped entity exists in our database
            final_entity = self.repository.find_exact_entity(db, mapped_entity_name)
            if not final_entity:
                logger.warning(
                    f"LLM mapped to non-existent {entity_name}: '{mapped_entity_name}'"
                )
                return None

            logger.debug(f"LLM mapped '{entity_text}' -> '{mapped_entity_name}'")

            # Create the extracted entity using the factory
            return self.extracted_model_factory(free_entity, final_entity)

        except Exception as e:
            logger.error(
                f"Error mapping {entity_name} '{self._get_entity_text(free_entity)}' to Wikidata: {e}"
            )
            return None

    def _llm_map_to_wikidata(
        self,
        extracted_text: str,
        candidate_entities: List[str],
        proof_text: str,
        entity_name: str,
    ) -> Optional[str]:
        """Use LLM to map extracted entity to correct Wikidata entity."""
        try:
            # Create dynamic model with candidate entities
            DynamicMappingResult = self.mapping_result_factory(candidate_entities)

            user_prompt = self.prompt_config.stage2_user_prompt_template.format(
                extracted_text=extracted_text,
                proof_text=proof_text,
                candidate_entities=chr(10).join(
                    [f"- {entity}" for entity in candidate_entities]
                ),
            )

            response = self.openai_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_config.stage2_system_prompt,
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format=DynamicMappingResult,
                temperature=0.1,
            )

            message = response.choices[0].message

            if message.parsed is None:
                logger.error(f"OpenAI {entity_name} mapping returned None")
                return None

            # Extract the mapped entity name from the response
            return self._get_mapped_entity_name(message.parsed)

        except Exception as e:
            logger.error(f"Error mapping {entity_name} with LLM: {e}")
            return None

    def _get_entity_text(self, free_entity: FreeFormT) -> str:
        """Extract the entity text from a free-form entity. Override in subclasses."""
        if hasattr(free_entity, "name"):
            return free_entity.name
        elif hasattr(free_entity, "location_name"):
            return free_entity.location_name
        else:
            raise NotImplementedError("Subclasses must implement _get_entity_text")

    def _get_proof_text(self, free_entity: FreeFormT) -> str:
        """Extract the proof text from a free-form entity."""
        return free_entity.proof

    def _get_entities_field_name(self) -> str:
        """Get the field name that contains the list of entities. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _get_entities_field_name")

    def _get_mapped_entity_name(self, mapping_result: MappingResultT) -> Optional[str]:
        """Extract the mapped entity name from mapping result. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement _get_mapped_entity_name")


def create_dynamic_mapping_model(allowed_entities: List[str], field_name: str):
    """Create dynamic Pydantic model for entity mapping with None option."""
    # Create union type with entities + None
    if allowed_entities:
        # Filter out None values and add None as separate option
        entity_names = [entity for entity in allowed_entities if entity is not None]
        EntityNameType = Optional[Literal[tuple(entity_names)]]
    else:
        EntityNameType = Optional[str]  # Fallback

    # Create dynamic mapping result model
    DynamicMappingResult = create_model(
        f"Dynamic{field_name.title()}MappingResult",
        **{field_name: (EntityNameType, None)},
    )

    return DynamicMappingResult
