from typing import Any
from uuid import UUID


class SectionGenerationError(Exception):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class LLMInvocationError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        generation_input_id: UUID,
        reason: str,
        llm_error: str | None = None,
    ):
        super().__init__(
            message=f"LLM invocation failed for section {section_id}: {reason}",
            details={
                "section_id": section_id,
                "generation_input_id": str(generation_input_id),
                "reason": reason,
                "llm_error": llm_error,
            },
        )
        self.section_id = section_id
        self.generation_input_id = generation_input_id
        self.reason = reason
        self.llm_error = llm_error


class ContentConstraintViolationError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        generation_input_id: UUID,
        violations: list[str],
        rejection_code: str,
    ):
        super().__init__(
            message=f"Content from section {section_id} violated constraints: {'; '.join(violations)}",
            details={
                "section_id": section_id,
                "generation_input_id": str(generation_input_id),
                "violations": violations,
                "rejection_code": rejection_code,
            },
        )
        self.section_id = section_id
        self.generation_input_id = generation_input_id
        self.violations = violations
        self.rejection_code = rejection_code


class StructuralModificationAttemptError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        generation_input_id: UUID,
        detected_patterns: list[str],
    ):
        super().__init__(
            message=f"Section {section_id} output attempted structural modification",
            details={
                "section_id": section_id,
                "generation_input_id": str(generation_input_id),
                "detected_patterns": detected_patterns,
            },
        )
        self.section_id = section_id
        self.generation_input_id = generation_input_id
        self.detected_patterns = detected_patterns


class SectionIsolationError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        affected_sections: list[int],
        reason: str,
    ):
        super().__init__(
            message=f"Section {section_id} generation caused isolation breach: {reason}",
            details={
                "section_id": section_id,
                "affected_sections": affected_sections,
                "reason": reason,
            },
        )
        self.section_id = section_id
        self.affected_sections = affected_sections
        self.reason = reason


class OutputPersistenceError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        generation_input_id: UUID,
        reason: str,
    ):
        super().__init__(
            message=f"Failed to persist output for section {section_id}: {reason}",
            details={
                "section_id": section_id,
                "generation_input_id": str(generation_input_id),
                "reason": reason,
            },
        )
        self.section_id = section_id
        self.generation_input_id = generation_input_id
        self.reason = reason


class BatchNotValidatedError(SectionGenerationError):
    def __init__(self, batch_id: UUID):
        super().__init__(
            message=f"Cannot execute generation: input batch {batch_id} is not validated",
            details={"batch_id": str(batch_id)},
        )
        self.batch_id = batch_id


class BatchNotFoundError(SectionGenerationError):
    def __init__(self, batch_id: UUID):
        super().__init__(
            message=f"Generation input batch {batch_id} not found",
            details={"batch_id": str(batch_id)},
        )
        self.batch_id = batch_id


class DuplicateOutputBatchError(SectionGenerationError):
    def __init__(self, input_batch_id: UUID):
        super().__init__(
            message=f"Output batch already exists for input batch {input_batch_id}",
            details={"input_batch_id": str(input_batch_id)},
        )
        self.input_batch_id = input_batch_id


class OutputImmutabilityViolationError(SectionGenerationError):
    def __init__(
        self,
        output_id: UUID,
        operation: str,
    ):
        super().__init__(
            message=f"Cannot {operation} section output {output_id}: output is immutable",
            details={
                "output_id": str(output_id),
                "operation": operation,
            },
        )
        self.output_id = output_id
        self.operation = operation


class ContentLengthExceededError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        actual_length: int,
        max_length: int,
    ):
        super().__init__(
            message=f"Section {section_id} content length {actual_length} exceeds maximum {max_length}",
            details={
                "section_id": section_id,
                "actual_length": actual_length,
                "max_length": max_length,
            },
        )
        self.section_id = section_id
        self.actual_length = actual_length
        self.max_length = max_length


class EmptyContentError(SectionGenerationError):
    def __init__(
        self,
        section_id: int,
        generation_input_id: UUID,
    ):
        super().__init__(
            message=f"Section {section_id} generated empty content",
            details={
                "section_id": section_id,
                "generation_input_id": str(generation_input_id),
            },
        )
        self.section_id = section_id
        self.generation_input_id = generation_input_id
