"""
Error handling infrastructure for observability and demo hardening.

Provides:
- Structured error models with codes and contexts
- Error persistence for queryability
- Error classification and categorization
- Recovery and retry guidance
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.infrastructure.datetime_utils import utc_now


class ErrorCategory(str, PyEnum):
    """High-level error categories for classification."""

    VALIDATION = "VALIDATION"
    PARSING = "PARSING"
    CLASSIFICATION = "CLASSIFICATION"
    GENERATION = "GENERATION"
    ASSEMBLY = "ASSEMBLY"
    RENDERING = "RENDERING"
    VERSIONING = "VERSIONING"
    REGENERATION = "REGENERATION"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN = "UNKNOWN"


class ErrorSeverity(str, PyEnum):
    """Error severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecoveryAction(str, PyEnum):
    """Suggested recovery actions."""

    RETRY = "RETRY"
    SKIP = "SKIP"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    ROLLBACK = "ROLLBACK"
    RESTART = "RESTART"
    CONTACT_SUPPORT = "CONTACT_SUPPORT"
    NONE = "NONE"


class StructuredError(BaseModel):
    """
    Structured error with full context for debugging and observability.

    Designed to be:
    - Understandable without reading code
    - Queryable for patterns
    - Actionable with recovery guidance
    """

    code: str = Field(description="Unique error code for identification")
    category: ErrorCategory
    severity: ErrorSeverity
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error context")

    correlation_id: str | None = None
    job_id: UUID | None = None
    document_id: UUID | None = None
    template_version_id: UUID | None = None

    recovery_action: RecoveryAction = RecoveryAction.NONE
    recovery_hint: str | None = None
    is_retryable: bool = False
    retry_count: int = 0
    max_retries: int = 3

    occurred_at: datetime = Field(default_factory=utc_now)

    model_config = ConfigDict(from_attributes=True)

    def to_log_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for logging."""
        return {
            "error_code": self.code,
            "error_category": self.category.value,
            "error_severity": self.severity.value,
            "error_message": self.message,
            "error_details": self.details,
            "correlation_id": self.correlation_id,
            "job_id": str(self.job_id) if self.job_id else None,
            "document_id": str(self.document_id) if self.document_id else None,
            "template_version_id": (
                str(self.template_version_id) if self.template_version_id else None
            ),
            "recovery_action": self.recovery_action.value,
            "is_retryable": self.is_retryable,
        }


class InvalidWordUploadError(StructuredError):
    """Error when Word document upload is invalid."""

    def __init__(
        self,
        reason: str,
        file_name: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="VALIDATION_INVALID_WORD_UPLOAD",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            message=f"Invalid Word document upload: {reason}",
            details={
                "reason": reason,
                "file_name": file_name,
            },
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint="Ensure the file is a valid .docx format and not corrupted",
            is_retryable=True,
        )


class InvalidClientDataError(StructuredError):
    """Error when client data is invalid."""

    def __init__(
        self,
        field: str,
        reason: str,
        value: Any = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="VALIDATION_INVALID_CLIENT_DATA",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            message=f"Invalid client data for field '{field}': {reason}",
            details={
                "field": field,
                "reason": reason,
                "value": str(value) if value is not None else None,
            },
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint=f"Correct the value for field '{field}' and retry",
            is_retryable=True,
        )


class ParsingFailureError(StructuredError):
    """Error when document parsing fails."""

    def __init__(
        self,
        template_version_id: UUID,
        reason: str,
        stage: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="PARSING_FAILURE",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.MEDIUM,
            message=f"Failed to parse document: {reason}",
            details={
                "reason": reason,
                "stage": stage,
            },
            template_version_id=template_version_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint="Check document format and structure, then retry",
            is_retryable=True,
        )


class MalformedDocumentError(StructuredError):
    """Error when document structure is malformed."""

    def __init__(
        self,
        template_version_id: UUID,
        issue: str,
        location: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="PARSING_MALFORMED_DOCUMENT",
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.MEDIUM,
            message=f"Malformed document structure: {issue}",
            details={
                "issue": issue,
                "location": location,
            },
            template_version_id=template_version_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.MANUAL_INTERVENTION,
            recovery_hint="Review and fix document structure at the specified location",
            is_retryable=False,
        )


class ClassificationFailureError(StructuredError):
    """Error when section classification fails."""

    def __init__(
        self,
        template_version_id: UUID,
        section_path: str | None = None,
        reason: str = "Unknown",
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="CLASSIFICATION_FAILURE",
            category=ErrorCategory.CLASSIFICATION,
            severity=ErrorSeverity.MEDIUM,
            message=f"Failed to classify section: {reason}",
            details={
                "section_path": section_path,
                "reason": reason,
            },
            template_version_id=template_version_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint="Verify section structure and retry classification",
            is_retryable=True,
        )


class GenerationFailureError(StructuredError):
    """Error when content generation fails."""

    def __init__(
        self,
        document_id: UUID,
        section_id: int | None = None,
        reason: str = "Unknown",
        llm_error: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="GENERATION_FAILURE",
            category=ErrorCategory.GENERATION,
            severity=ErrorSeverity.MEDIUM,
            message=f"Content generation failed: {reason}",
            details={
                "section_id": section_id,
                "reason": reason,
                "llm_error": llm_error,
            },
            document_id=document_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint="Check input data and prompt configuration, then retry",
            is_retryable=True,
            max_retries=3,
        )


class ValidationRejectionError(StructuredError):
    """Error when generated content fails validation."""

    def __init__(
        self,
        document_id: UUID,
        section_id: int,
        validation_errors: list[str],
        content_hash: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="GENERATION_VALIDATION_REJECTION",
            category=ErrorCategory.GENERATION,
            severity=ErrorSeverity.LOW,
            message=f"Generated content failed validation for section {section_id}",
            details={
                "section_id": section_id,
                "validation_errors": validation_errors,
                "content_hash": content_hash,
            },
            document_id=document_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint="Content will be automatically regenerated with adjusted parameters",
            is_retryable=True,
            max_retries=3,
        )


class JobCrashError(StructuredError):
    """Error when a job crashes unexpectedly."""

    def __init__(
        self,
        job_id: UUID,
        job_type: str,
        exception: str,
        stack_trace: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="JOB_CRASH",
            category=ErrorCategory.INFRASTRUCTURE,
            severity=ErrorSeverity.HIGH,
            message=f"Job {job_type} crashed unexpectedly",
            details={
                "job_type": job_type,
                "exception": exception,
                "stack_trace": stack_trace,
            },
            job_id=job_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RESTART,
            recovery_hint="Job will be automatically restarted by worker recovery",
            is_retryable=True,
        )


class JobTimeoutError(StructuredError):
    """Error when a job times out."""

    def __init__(
        self,
        job_id: UUID,
        job_type: str,
        timeout_minutes: int,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="JOB_TIMEOUT",
            category=ErrorCategory.INFRASTRUCTURE,
            severity=ErrorSeverity.MEDIUM,
            message=f"Job {job_type} timed out after {timeout_minutes} minutes",
            details={
                "job_type": job_type,
                "timeout_minutes": timeout_minutes,
            },
            job_id=job_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RESTART,
            recovery_hint="Job will be reset and can be retried",
            is_retryable=True,
        )


class RegenerationConflictError(StructuredError):
    """Error when regeneration conflicts with existing operation."""

    def __init__(
        self,
        document_id: UUID,
        conflict_reason: str,
        conflicting_job_id: UUID | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(
            code="REGENERATION_CONFLICT",
            category=ErrorCategory.REGENERATION,
            severity=ErrorSeverity.LOW,
            message=f"Regeneration conflict: {conflict_reason}",
            details={
                "conflict_reason": conflict_reason,
                "conflicting_job_id": str(conflicting_job_id) if conflicting_job_id else None,
            },
            document_id=document_id,
            correlation_id=correlation_id,
            recovery_action=RecoveryAction.RETRY,
            recovery_hint="Wait for existing operation to complete, then retry",
            is_retryable=True,
        )


ERROR_CODE_MAP: dict[str, type[StructuredError]] = {
    "VALIDATION_INVALID_WORD_UPLOAD": InvalidWordUploadError,
    "VALIDATION_INVALID_CLIENT_DATA": InvalidClientDataError,
    "PARSING_FAILURE": ParsingFailureError,
    "PARSING_MALFORMED_DOCUMENT": MalformedDocumentError,
    "CLASSIFICATION_FAILURE": ClassificationFailureError,
    "GENERATION_FAILURE": GenerationFailureError,
    "GENERATION_VALIDATION_REJECTION": ValidationRejectionError,
    "JOB_CRASH": JobCrashError,
    "JOB_TIMEOUT": JobTimeoutError,
    "REGENERATION_CONFLICT": RegenerationConflictError,
}


def get_error_by_code(code: str) -> type[StructuredError] | None:
    """Get error class by code."""
    return ERROR_CODE_MAP.get(code)
