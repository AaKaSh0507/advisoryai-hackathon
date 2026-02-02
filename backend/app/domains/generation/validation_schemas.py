import hashlib
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FailureType(str, PyEnum):
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    RETRY_EXHAUSTION = "RETRY_EXHAUSTION"
    STRUCTURAL_VIOLATION = "STRUCTURAL_VIOLATION"
    BOUNDS_VIOLATION = "BOUNDS_VIOLATION"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


class ValidationErrorCode(str, PyEnum):
    EMPTY_CONTENT = "EMPTY_CONTENT"
    NEAR_EMPTY_CONTENT = "NEAR_EMPTY_CONTENT"
    CONTENT_TOO_LONG = "CONTENT_TOO_LONG"
    CONTENT_TOO_SHORT = "CONTENT_TOO_SHORT"
    CONTAINS_MARKUP = "CONTAINS_MARKUP"
    CONTAINS_TAGS = "CONTAINS_TAGS"
    CONTAINS_HEADERS = "CONTAINS_HEADERS"
    CONTAINS_FORMATTING = "CONTAINS_FORMATTING"
    STRUCTURAL_MODIFICATION = "STRUCTURAL_MODIFICATION"
    REPETITIVE_CONTENT = "REPETITIVE_CONTENT"
    BOILERPLATE_ONLY = "BOILERPLATE_ONLY"
    INVALID_CHARACTERS = "INVALID_CHARACTERS"


class RetryEligibility(str, PyEnum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    EXHAUSTED = "EXHAUSTED"


class RetryPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts",
    )
    eligible_failure_types: frozenset[FailureType] = Field(
        default=frozenset(
            {
                FailureType.GENERATION_FAILURE,
                FailureType.BOUNDS_VIOLATION,
            }
        ),
        description="Failure types that are eligible for retry",
    )
    ineligible_failure_types: frozenset[FailureType] = Field(
        default=frozenset(
            {
                FailureType.VALIDATION_FAILURE,
                FailureType.STRUCTURAL_VIOLATION,
                FailureType.QUALITY_FAILURE,
                FailureType.RETRY_EXHAUSTION,
            }
        ),
        description="Failure types that are NOT eligible for retry",
    )


class StructuralValidationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    reject_html_tags: bool = Field(default=True)
    reject_markdown_headers: bool = Field(default=True)
    reject_markdown_formatting: bool = Field(default=True)
    reject_markdown_links: bool = Field(default=True)
    reject_code_blocks: bool = Field(default=True)
    reject_horizontal_rules: bool = Field(default=True)
    reject_tables: bool = Field(default=True)
    reject_section_numbering: bool = Field(default=True)
    custom_forbidden_patterns: list[str] = Field(default_factory=list)


class QualityCheckConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_unique_words: int = Field(
        default=5,
        ge=1,
        description="Minimum number of unique words required",
    )
    max_repetition_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Max ratio of repeated phrases to total content",
    )
    min_meaningful_length: int = Field(
        default=10,
        ge=1,
        description="Min length to not be considered near-empty",
    )
    boilerplate_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^lorem ipsum",
            r"^placeholder",
            r"^todo:?\s*$",
            r"^tbd:?\s*$",
            r"^\[insert.*\]$",
            r"^content goes here",
            r"^sample text",
        ],
        description="Patterns indicating boilerplate content",
    )


class StructuralValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool
    is_plain_text: bool = True
    detected_markup: list[str] = Field(default_factory=list)
    detected_tags: list[str] = Field(default_factory=list)
    detected_headers: list[str] = Field(default_factory=list)
    detected_formatting: list[str] = Field(default_factory=list)
    error_codes: list[ValidationErrorCode] = Field(default_factory=list)
    error_message: str | None = None


class BoundsValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool
    content_length: int = 0
    min_length: int = 0
    max_length: int = 50000
    is_empty: bool = False
    is_near_empty: bool = False
    is_too_long: bool = False
    is_too_short: bool = False
    error_codes: list[ValidationErrorCode] = Field(default_factory=list)
    error_message: str | None = None


class QualityCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool
    unique_word_count: int = 0
    total_word_count: int = 0
    repetition_ratio: float = 0.0
    is_repetitive: bool = False
    is_boilerplate: bool = False
    detected_boilerplate_patterns: list[str] = Field(default_factory=list)
    error_codes: list[ValidationErrorCode] = Field(default_factory=list)
    error_message: str | None = None


class ComprehensiveValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_valid: bool
    validated_content: str | None = None
    content_hash: str | None = None
    structural_result: StructuralValidationResult
    bounds_result: BoundsValidationResult
    quality_result: QualityCheckResult
    failure_type: FailureType | None = None
    all_error_codes: list[ValidationErrorCode] = Field(default_factory=list)
    all_violations: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    is_retryable: bool = False
    validation_metadata: dict[str, Any] = Field(default_factory=dict)

    def compute_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class RetryAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)

    attempt_number: int
    failure_type: FailureType
    error_codes: list[ValidationErrorCode] = Field(default_factory=list)
    error_message: str | None = None
    raw_output: str | None = None
    timestamp: Any = None


class RetryState(BaseModel):
    model_config = ConfigDict(frozen=True)

    output_id: UUID
    section_id: int
    current_attempt: int = 0
    max_retries: int = 3
    is_exhausted: bool = False
    is_successful: bool = False
    attempts: list[RetryAttempt] = Field(default_factory=list)
    final_failure_type: FailureType | None = None


class ValidationOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    output_id: UUID
    section_id: int
    generation_input_id: UUID
    is_valid: bool
    is_immutable: bool = False
    validation_result: ComprehensiveValidationResult | None = None
    retry_state: RetryState | None = None
    failure_type: FailureType | None = None
    validated_content: str | None = None
    content_hash: str | None = None


class FailureQueryFilter(BaseModel):
    batch_id: UUID | None = None
    section_id: int | None = None
    failure_type: FailureType | None = None
    error_code: ValidationErrorCode | None = None
    include_retried: bool = True
    only_exhausted: bool = False


class FailureRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    output_id: UUID
    batch_id: UUID
    section_id: int
    generation_input_id: UUID
    failure_type: FailureType
    error_codes: list[str] = Field(default_factory=list)
    error_message: str | None = None
    retry_count: int = 0
    is_exhausted: bool = False
    validation_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Any = None


class ValidatedOutputQueryFilter(BaseModel):
    batch_id: UUID | None = None
    section_id: int | None = None
    only_validated: bool = True
    only_immutable: bool = True
