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
            stage1_system_prompt="""You are a biographical data specialist extracting location information from Wikipedia articles and official government profiles.

Extract birthplace information following these rules:

### EXTRACTION RULES:
- Extract birthplace as mentioned in the source (city, town, village or region)

### PROOF REQUIREMENT:
- Provide ONE exact quote from the source content that mentions the birthplace
- When multiple sentences support the claim, choose the MOST IMPORTANT/RELEVANT single quote""",
            stage1_user_prompt_template="""Extract the birthplace of {politician_name} from the content below.

### CONTEXT:
Politician: {politician_name}
Source URL: {source_url}

### CONTENT:
\"\"\"
{content}
\"\"\"""",
            stage2_system_prompt="""You are a Wikidata location mapping specialist with expertise in geographic locations and administrative divisions.

Map the extracted birthplace to the most accurate Wikidata location following these rules:

### MATCHING CRITERIA:
1. When there's multiple candidate entities with the same name, and you have no proof for which one matches, match the least specific location level (region over city)
2. Account for different name spellings and transliterations

### REJECTION CRITERIA:
- Return None if no candidate is a good match""",
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
