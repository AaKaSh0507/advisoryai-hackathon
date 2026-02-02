import hashlib
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentConstraints(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_length: int = Field(
        default=50000,
        ge=100,
        le=500000,
        description="Maximum allowed content length in characters",
    )
    min_length: int = Field(
        default=1,
        ge=0,
        description="Minimum required content length in characters",
    )
    allowed_content_type: str = Field(
        default="plain_text",
        description="Type of content allowed (plain_text only for phase 6.2)",
    )
    reject_structural_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^#+\s",
            r"^\*{3,}",
            r"^-{3,}",
            r"^={3,}",
            r"^\|.*\|",
            r"^```",
            r"<[a-zA-Z][^>]*>",
            r"\[.*\]\(.*\)",
        ],
        description="Regex patterns that indicate structural modification attempts",
    )


class LLMInvocationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_input_id: UUID = Field(
        ...,
        description="ID of the generation input being processed",
    )
    section_id: int = Field(
        ...,
        description="Database ID of the section",
    )
    prompt_text: str = Field(
        ...,
        description="The assembled prompt text for LLM invocation",
    )
    constraints: ContentConstraints = Field(
        default_factory=ContentConstraints,
        description="Content constraints for validation",
    )


class LLMInvocationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_input_id: UUID = Field(
        ...,
        description="ID of the generation input that was processed",
    )
    section_id: int = Field(
        ...,
        description="Database ID of the section",
    )
    raw_output: str = Field(
        ...,
        description="Raw output from the LLM",
    )
    is_successful: bool = Field(
        default=True,
        description="Whether the LLM call succeeded",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if invocation failed",
    )
    invocation_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the LLM invocation",
    )


class ContentValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool = Field(
        ...,
        description="Whether the content passes all validation checks",
    )
    validated_content: str | None = Field(
        default=None,
        description="The validated and sanitized content if valid",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="Reason for rejection if invalid",
    )
    rejection_code: str | None = Field(
        default=None,
        description="Machine-readable rejection code",
    )
    constraint_violations: list[str] = Field(
        default_factory=list,
        description="List of specific constraint violations",
    )


class SectionGenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_input_id: UUID = Field(
        ...,
        description="ID of the generation input that was processed",
    )
    section_id: int = Field(
        ...,
        description="Database ID of the section",
    )
    status: str = Field(
        ...,
        description="Generation status (COMPLETED or FAILED)",
    )
    generated_content: str | None = Field(
        default=None,
        description="The generated content if successful",
    )
    content_length: int = Field(
        default=0,
        description="Length of generated content",
    )
    content_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of the content",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if generation failed",
    )
    error_code: str | None = Field(
        default=None,
        description="Machine-readable error code",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the generation",
    )

    def compute_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class SectionOutputCreate(BaseModel):
    batch_id: UUID
    generation_input_id: UUID
    section_id: int
    sequence_order: int
    status: str
    generated_content: str | None = None
    content_length: int = 0
    content_hash: str | None = None
    error_message: str | None = None
    error_code: str | None = None
    generation_metadata: dict[str, Any] = Field(default_factory=dict)


class SectionOutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    generation_input_id: UUID
    section_id: int
    sequence_order: int
    status: str
    generated_content: str | None
    content_length: int
    content_hash: str | None
    error_message: str | None
    error_code: str | None
    generation_metadata: dict[str, Any]
    is_immutable: bool
    created_at: Any
    completed_at: Any | None


class SectionOutputBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    input_batch_id: UUID
    document_id: UUID
    version_intent: int
    status: str
    total_sections: int
    completed_sections: int
    failed_sections: int
    is_immutable: bool
    created_at: Any
    completed_at: Any | None
    outputs: list[SectionOutputResponse] = Field(default_factory=list)


class ExecuteSectionGenerationRequest(BaseModel):
    input_batch_id: UUID = Field(
        ...,
        description="ID of the validated generation input batch",
    )
    constraints: ContentConstraints = Field(
        default_factory=ContentConstraints,
        description="Content constraints to apply",
    )

    @field_validator("input_batch_id")
    @classmethod
    def validate_batch_id(cls, v: UUID) -> UUID:
        if not v:
            raise ValueError("input_batch_id cannot be empty")
        return v


class ExecuteSectionGenerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: UUID
    input_batch_id: UUID
    document_id: UUID
    version_intent: int
    status: str
    total_sections: int
    completed_sections: int
    failed_sections: int
    outputs: list[SectionOutputResponse]


class ContentValidator:
    def __init__(self, constraints: ContentConstraints):
        self.constraints = constraints
        self._compiled_patterns = [
            re.compile(pattern, re.MULTILINE) for pattern in constraints.reject_structural_patterns
        ]

    def validate(self, content: str) -> ContentValidationResult:
        violations: list[str] = []

        if not content or not content.strip():
            return ContentValidationResult(
                is_valid=False,
                rejection_reason="Content is empty or contains only whitespace",
                rejection_code="EMPTY_CONTENT",
                constraint_violations=["empty_content"],
            )

        content_length = len(content)

        if content_length < self.constraints.min_length:
            violations.append(
                f"Content length {content_length} is below minimum {self.constraints.min_length}"
            )

        if content_length > self.constraints.max_length:
            violations.append(
                f"Content length {content_length} exceeds maximum {self.constraints.max_length}"
            )

        for i, pattern in enumerate(self._compiled_patterns):
            if pattern.search(content):
                violations.append(
                    f"Content contains forbidden structural pattern: {self.constraints.reject_structural_patterns[i]}"
                )

        if violations:
            return ContentValidationResult(
                is_valid=False,
                rejection_reason="; ".join(violations),
                rejection_code="CONSTRAINT_VIOLATION",
                constraint_violations=violations,
            )

        sanitized_content = content.strip()

        return ContentValidationResult(
            is_valid=True,
            validated_content=sanitized_content,
        )
