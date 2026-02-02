import hashlib
import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SectionHierarchyContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    parent_heading: str | None = Field(
        default=None,
        description="The text of the parent heading this section falls under",
    )
    parent_level: int | None = Field(
        default=None,
        description="The heading level of the parent (1-6)",
    )
    sibling_index: int = Field(
        default=0,
        description="Zero-based index among sibling sections",
    )
    total_siblings: int = Field(
        default=1,
        description="Total number of sibling sections",
    )
    depth: int = Field(
        default=0,
        description="Nesting depth in the document structure",
    )
    path_segments: list[str] = Field(
        default_factory=list,
        description="Ordered list of heading texts from root to this section",
    )


class PromptConfigMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)
    classification_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score from classification (0.0 to 1.0)",
    )
    classification_method: str = Field(
        ...,
        description="Method used for classification (RULE_BASED, LLM, FALLBACK)",
    )
    justification: str = Field(
        ...,
        description="Justification for the DYNAMIC classification",
    )
    prompt_template: str | None = Field(
        default=None,
        description="Optional custom prompt template for this section",
    )
    generation_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional hints for content generation",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional classification metadata",
    )


class ClientDataPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    client_id: str | None = Field(
        default=None,
        description="Unique identifier for the client",
    )
    client_name: str | None = Field(
        default=None,
        description="Display name of the client",
    )
    data_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs of client data for template substitution",
    )
    custom_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional custom context for generation",
    )


class SurroundingContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    preceding_content: str | None = Field(
        default=None,
        description="Content from the immediately preceding section",
    )
    preceding_type: str | None = Field(
        default=None,
        description="Type of the preceding block (STATIC/DYNAMIC)",
    )
    following_content: str | None = Field(
        default=None,
        description="Content from the immediately following section",
    )
    following_type: str | None = Field(
        default=None,
        description="Type of the following block (STATIC/DYNAMIC)",
    )
    section_boundary_hint: str | None = Field(
        default=None,
        description="Hint about section boundaries for coherent generation",
    )


class GenerationInputData(BaseModel):
    model_config = ConfigDict(frozen=True)
    section_id: int = Field(
        ...,
        description="Database ID of the section",
    )
    template_id: str = Field(
        ...,
        description="UUID of the template (as string for deterministic serialization)",
    )
    template_version_id: str = Field(
        ...,
        description="UUID of the template version (as string for deterministic serialization)",
    )
    structural_path: str = Field(
        ...,
        description="Unique structural path of the section in the document",
    )
    hierarchy_context: SectionHierarchyContext = Field(
        ...,
        description="Hierarchical context of the section",
    )
    prompt_config: PromptConfigMetadata = Field(
        ...,
        description="Prompt configuration metadata",
    )
    client_data: ClientDataPayload = Field(
        ...,
        description="Client data payload for personalization",
    )
    surrounding_context: SurroundingContext = Field(
        ...,
        description="Static surrounding context",
    )

    def compute_hash(self) -> str:
        json_str = json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


class GenerationInputCreate(BaseModel):
    section_id: int
    sequence_order: int
    template_id: UUID
    template_version_id: UUID
    structural_path: str
    hierarchy_context: dict[str, Any]
    prompt_config: dict[str, Any]
    client_data: dict[str, Any]
    surrounding_context: dict[str, Any]

    @field_validator("structural_path")
    @classmethod
    def validate_structural_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("structural_path cannot be empty")
        return v

    @field_validator("prompt_config")
    @classmethod
    def validate_prompt_config(cls, v: dict[str, Any]) -> dict[str, Any]:
        required_fields = ["classification_confidence", "classification_method", "justification"]
        missing = [f for f in required_fields if f not in v]
        if missing:
            raise ValueError(f"prompt_config missing required fields: {missing}")
        return v


class GenerationInputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    section_id: int
    sequence_order: int
    template_id: UUID
    template_version_id: UUID
    structural_path: str
    hierarchy_context: dict[str, Any]
    prompt_config: dict[str, Any]
    client_data: dict[str, Any]
    surrounding_context: dict[str, Any]
    input_hash: str
    created_at: Any


class GenerationInputBatchCreate(BaseModel):
    document_id: UUID
    template_version_id: UUID
    version_intent: int
    client_data: ClientDataPayload = Field(default_factory=ClientDataPayload)

    @field_validator("version_intent")
    @classmethod
    def validate_version_intent(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version_intent must be >= 1")
        return v


class GenerationInputBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    template_version_id: UUID
    version_intent: int
    status: str
    content_hash: str
    total_inputs: int
    is_immutable: bool
    created_at: Any
    validated_at: Any | None
    error_message: str | None
    inputs: list[GenerationInputResponse] = Field(default_factory=list)


class PrepareGenerationInputsRequest(BaseModel):
    document_id: UUID
    template_version_id: UUID
    version_intent: int
    client_data: ClientDataPayload = Field(default_factory=ClientDataPayload)

    @field_validator("version_intent")
    @classmethod
    def validate_version_intent(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version_intent must be >= 1")
        return v


class PrepareGenerationInputsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    batch_id: UUID
    document_id: UUID
    template_version_id: UUID
    version_intent: int
    status: str
    total_dynamic_sections: int
    content_hash: str
    is_immutable: bool
    inputs: list[GenerationInputResponse]
