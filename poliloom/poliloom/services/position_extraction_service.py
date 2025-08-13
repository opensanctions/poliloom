"""Position extraction service using the generic two-stage extraction framework."""

from typing import List, Optional
from openai import OpenAI
from pydantic import BaseModel

from .extraction_service import (
    TwoStageExtractionService,
    PositionRepository,
    ExtractionPromptConfig,
    create_dynamic_mapping_model,
)
from ..models import Position


class FreeFormExtractedPosition(BaseModel):
    """Schema for free-form position extraction (Stage 1)."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str


class FreeFormPositionExtractionResult(BaseModel):
    """Schema for free-form position extraction result (Stage 1)."""

    positions: List[FreeFormExtractedPosition]


class ExtractedPosition(BaseModel):
    """Schema for extracted position data."""

    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof: str


class PositionExtractionService(TwoStageExtractionService):
    """Service for extracting positions using the two-stage approach."""

    def __init__(self, openai_client: OpenAI):
        prompt_config = ExtractionPromptConfig(
            stage1_system_prompt="""You are a political data analyst specializing in extracting structured information from Wikipedia articles and official government websites.

Extract ALL political positions from the provided content following these rules:

### EXTRACTION RULES:
- Extract any political offices, government roles, elected positions, or political appointments
- Include interim/acting positions and temporary appointments
- Use exact position names as they appear in the source

### DATE FORMAT:
- Use YYYY-MM-DD, YYYY-MM, or YYYY format when available
- Leave end_date null if position is current or unknown
- Include "acting" or "interim" in the position name if applicable

### PROOF REQUIREMENT:
- Each position MUST include ONE exact quote mentioning this position
- When multiple sentences support the claim, choose the MOST IMPORTANT/RELEVANT single quote
- The proof should contain sufficient context to verify the claim""",
            stage1_user_prompt_template="""Extract ALL political positions held by {politician_name} from the content below.

### CONTEXT:
Politician: {politician_name}
Source URL: {source_url}

### CONTENT:
\"\"\"
{content}
\"\"\"""",
            stage2_system_prompt="""You are a Wikidata mapping specialist with expertise in political positions and government structures.

Map the extracted position to the most accurate Wikidata position following these rules:

### MATCHING CRITERIA:
1. STRONGLY PREFER country-specific positions (e.g., "Minister of Foreign Affairs (Myanmar)" over generic "Minister of Foreign Affairs")
2. PREFER positions from the same political system/country context
4. Match only when confidence is HIGH - be precise about role equivalence

### REJECTION CRITERIA:
- Return None if no candidate is a good match
- Reject if the positions clearly refer to different roles
- Reject if geographic/jurisdictional scope differs significantly""",
            stage2_user_prompt_template="""Map this extracted position to the correct Wikidata position:

Extracted Position: "{extracted_text}"
Proof Context: "{proof_text}"

Candidate Wikidata Positions:
{candidate_entities}

Select the best match or None if no good match exists.""",
        )

        super().__init__(
            openai_client=openai_client,
            repository=PositionRepository(),
            prompt_config=prompt_config,
            free_form_response_model=FreeFormPositionExtractionResult,
            mapping_result_factory=lambda entities: create_dynamic_mapping_model(
                entities, "wikidata_position_name"
            ),
            extracted_model_factory=self._create_extracted_position,
        )

    def _get_entities_field_name(self) -> str:
        """Get the field name that contains the list of entities."""
        return "positions"

    def _get_mapped_entity_name(self, mapping_result) -> Optional[str]:
        """Extract the mapped entity name from mapping result."""
        return mapping_result.wikidata_position_name

    def _create_extracted_position(
        self, free_position: FreeFormExtractedPosition, final_position: Position
    ) -> ExtractedPosition:
        """Create ExtractedPosition from free-form position and final position."""
        return ExtractedPosition(
            name=final_position.name,
            start_date=free_position.start_date,
            end_date=free_position.end_date,
            proof=free_position.proof,
        )
