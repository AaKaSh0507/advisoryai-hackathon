from typing import Any
from uuid import UUID


class GenerationInputError(Exception):
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


class NoDynamicSectionsError(GenerationInputError):
    def __init__(self, template_version_id: UUID):
        super().__init__(
            message=f"No DYNAMIC sections found for template version {template_version_id}. "
            "Generation cannot proceed without dynamic sections.",
            details={"template_version_id": str(template_version_id)},
        )
        self.template_version_id = template_version_id


class MissingPromptConfigError(GenerationInputError):
    def __init__(
        self,
        section_id: int,
        structural_path: str,
        missing_fields: list[str] | None = None,
    ):
        fields_detail = f" Missing fields: {missing_fields}" if missing_fields else ""
        super().__init__(
            message=f"Section {section_id} at path '{structural_path}' is DYNAMIC but has "
            f"missing or incomplete prompt configuration.{fields_detail}",
            details={
                "section_id": section_id,
                "structural_path": structural_path,
                "missing_fields": missing_fields or [],
            },
        )
        self.section_id = section_id
        self.structural_path = structural_path
        self.missing_fields = missing_fields or []


class MalformedSectionMetadataError(GenerationInputError):
    def __init__(
        self,
        section_id: int,
        structural_path: str,
        reason: str,
        invalid_data: Any = None,
    ):
        super().__init__(
            message=f"Section {section_id} at path '{structural_path}' has malformed metadata: {reason}",
            details={
                "section_id": section_id,
                "structural_path": structural_path,
                "reason": reason,
                "invalid_data": str(invalid_data) if invalid_data is not None else None,
            },
        )
        self.section_id = section_id
        self.structural_path = structural_path
        self.reason = reason
        self.invalid_data = invalid_data


class InputValidationError(GenerationInputError):
    def __init__(
        self,
        field: str,
        reason: str,
        section_id: int | None = None,
        invalid_value: Any = None,
    ):
        section_context = f" for section {section_id}" if section_id else ""
        super().__init__(
            message=f"Validation failed{section_context}: field '{field}' - {reason}",
            details={
                "field": field,
                "reason": reason,
                "section_id": section_id,
                "invalid_value": str(invalid_value) if invalid_value is not None else None,
            },
        )
        self.field = field
        self.reason = reason
        self.section_id = section_id
        self.invalid_value = invalid_value


class ImmutabilityViolationError(GenerationInputError):
    def __init__(
        self,
        batch_id: UUID,
        operation: str,
    ):
        super().__init__(
            message=f"Cannot {operation} generation input batch {batch_id}: "
            "generation inputs are immutable once persisted.",
            details={
                "batch_id": str(batch_id),
                "operation": operation,
            },
        )
        self.batch_id = batch_id
        self.operation = operation
