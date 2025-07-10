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
            stage1_system_prompt="""You are a data extraction assistant. Extract ALL political positions from Wikipedia article text.

Extract any political offices, government roles, elected positions, or political appointments mentioned in the text. Use natural language descriptions as they appear in the text.

Rules:
- Extract ALL political positions mentioned in the text, even if informal
- Use the exact position names as they appear in Wikipedia 
- Include start/end dates in YYYY-MM-DD, YYYY-MM, or YYYY format if available
- Leave end_date null if position is current or dates are unknown
- For each position, provide a 'proof' field with the exact quote that mentions this position
- Do not worry about exact Wikidata position names - extract naturally""",
            stage1_user_prompt_template="""Extract ALL political positions held by {politician_name} from this Wikipedia article:

{content}

Politician name: {politician_name}
Country: {country}""",
            stage2_system_prompt="""You are a position mapping assistant. Given an extracted political position and a list of candidate Wikidata positions, select the most accurate match.

Rules:
- Choose the Wikidata position that best matches the extracted position
- Consider the context provided in the proof text
- PREFER country-specific positions over generic ones (e.g., "Minister of Foreign Affairs (Myanmar)" over "Minister of Foreign Affairs")
- If no candidate position is a good match, return None
- Be precise - only match if you're confident the positions refer to the same role""",
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
