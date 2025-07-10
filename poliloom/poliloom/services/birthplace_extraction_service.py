"""Birthplace extraction service using the generic two-stage extraction framework."""

from typing import List, Optional
from openai import OpenAI
from pydantic import BaseModel

from .extraction_service import (
    TwoStageExtractionService,
    LocationRepository,
    ExtractionPromptConfig,
    create_dynamic_mapping_model,
)
from ..models import Location


class FreeFormExtractedBirthplace(BaseModel):
    """Schema for free-form birthplace extraction (Stage 1)."""

    location_name: str
    proof: str


class FreeFormBirthplaceExtractionResult(BaseModel):
    """Schema for free-form birthplace extraction result (Stage 1)."""

    birthplaces: List[FreeFormExtractedBirthplace]


class ExtractedBirthplace(BaseModel):
    """Schema for extracted birthplace data."""

    location_name: str
    proof: str


class BirthplaceExtractionService(TwoStageExtractionService):
    """Service for extracting birthplaces using the two-stage approach."""

    def __init__(self, openai_client: OpenAI):
        prompt_config = ExtractionPromptConfig(
            stage1_system_prompt="""You are a data extraction assistant. Extract birthplace information from Wikipedia article text.

Extract the birthplace of the politician mentioned in the text. Use natural language descriptions as they appear in the text.

Rules:
- Extract the birthplace location as mentioned in the Wikipedia article
- Include city, town, village, or region names as they appear
- For each birthplace, provide a 'proof' field with the exact quote that mentions this birthplace
- Only extract birthplace information explicitly stated in the text
- Do not worry about exact Wikidata location names - extract naturally""",
            stage1_user_prompt_template="""Extract the birthplace of {politician_name} from this Wikipedia article:

{content}

Politician name: {politician_name}
Country: {country}""",
            stage2_system_prompt="""You are a location mapping assistant. Given an extracted birthplace and a list of candidate Wikidata locations, select the most accurate match.

Rules:
- Choose the Wikidata location that best matches the extracted birthplace
- Consider the context provided in the proof text
- If no candidate location is a good match, return None
- Be precise - only match if you're confident the locations refer to the same place
- Consider that birthplaces can be cities, towns, villages, regions, or even countries""",
            stage2_user_prompt_template="""Map this extracted birthplace to the correct Wikidata location:

Extracted Birthplace: "{extracted_text}"
Proof Context: "{proof_text}"

Candidate Wikidata Locations:
{candidate_entities}

Select the best match or None if no good match exists.""",
        )

        super().__init__(
            openai_client=openai_client,
            repository=LocationRepository(),
            prompt_config=prompt_config,
            free_form_response_model=FreeFormBirthplaceExtractionResult,
            mapping_result_factory=lambda entities: create_dynamic_mapping_model(
                entities, "wikidata_location_name"
            ),
            extracted_model_factory=self._create_extracted_birthplace,
        )

    def _get_entities_field_name(self) -> str:
        """Get the field name that contains the list of entities."""
        return "birthplaces"

    def _get_entity_text(self, free_entity: FreeFormExtractedBirthplace) -> str:
        """Extract the entity text from a free-form entity."""
        return free_entity.location_name

    def _get_mapped_entity_name(self, mapping_result) -> Optional[str]:
        """Extract the mapped entity name from mapping result."""
        return mapping_result.wikidata_location_name

    def _create_extracted_birthplace(
        self, free_birthplace: FreeFormExtractedBirthplace, final_location: Location
    ) -> ExtractedBirthplace:
        """Create ExtractedBirthplace from free-form birthplace and final location."""
        return ExtractedBirthplace(
            location_name=final_location.name,
            proof=free_birthplace.proof,
        )
