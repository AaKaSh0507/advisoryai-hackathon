"""
Document validation for Word documents.

Validates file integrity and format before parsing.
"""

import io
import zipfile
from dataclasses import dataclass
from enum import Enum

from backend.app.logging_config import get_logger

logger = get_logger("app.domains.parsing.validator")


class ValidationErrorType(str, Enum):
    """Types of validation errors."""

    EMPTY_FILE = "empty_file"
    INVALID_FORMAT = "invalid_format"
    CORRUPTED_FILE = "corrupted_file"
    UNSUPPORTED_VERSION = "unsupported_version"
    MISSING_CONTENT = "missing_content"
    FILE_TOO_LARGE = "file_too_large"


@dataclass
class ValidationResult:
    """Result of document validation."""

    valid: bool
    error_type: ValidationErrorType | None = None
    error_message: str | None = None
    file_size: int = 0

    @classmethod
    def success(cls, file_size: int) -> "ValidationResult":
        return cls(valid=True, file_size=file_size)

    @classmethod
    def failure(
        cls, error_type: ValidationErrorType, message: str, file_size: int = 0
    ) -> "ValidationResult":
        return cls(valid=False, error_type=error_type, error_message=message, file_size=file_size)


class DocumentValidator:
    """
    Validates Word documents before parsing.

    Checks:
    - File is not empty
    - File is a valid ZIP archive (docx format)
    - Required DOCX components are present
    - File is not too large
    """

    # Maximum file size: 50MB
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # Required files in a valid DOCX
    REQUIRED_DOCX_FILES = [
        "[Content_Types].xml",
    ]

    # Files that indicate document content
    CONTENT_INDICATORS = [
        "word/document.xml",
    ]

    def validate(self, file_content: bytes) -> ValidationResult:
        """
        Validate a Word document.

        Args:
            file_content: Raw bytes of the document file.

        Returns:
            ValidationResult indicating success or failure details.
        """
        file_size = len(file_content)

        # Check for empty file
        if file_size == 0:
            logger.warning("Validation failed: empty file")
            return ValidationResult.failure(
                ValidationErrorType.EMPTY_FILE, "File is empty", file_size
            )

        # Check file size limit
        if file_size > self.MAX_FILE_SIZE:
            logger.warning(f"Validation failed: file too large ({file_size} bytes)")
            return ValidationResult.failure(
                ValidationErrorType.FILE_TOO_LARGE,
                f"File size ({file_size} bytes) exceeds maximum ({self.MAX_FILE_SIZE} bytes)",
                file_size,
            )

        # Check if it's a valid ZIP archive
        if not self._is_valid_zip(file_content):
            logger.warning("Validation failed: not a valid ZIP archive")
            return ValidationResult.failure(
                ValidationErrorType.INVALID_FORMAT,
                "File is not a valid DOCX format (not a ZIP archive)",
                file_size,
            )

        # Check for required DOCX components
        validation = self._validate_docx_structure(file_content)
        if not validation.valid:
            logger.warning(f"Validation failed: {validation.error_message}")
            return validation

        logger.info(f"Document validation passed ({file_size} bytes)")
        return ValidationResult.success(file_size)

    def _is_valid_zip(self, content: bytes) -> bool:
        """Check if content is a valid ZIP archive."""
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                # Try to read the file list to verify integrity
                zf.namelist()
                return True
        except (zipfile.BadZipFile, Exception):
            return False

    def _validate_docx_structure(self, content: bytes) -> ValidationResult:
        """Validate the internal structure of a DOCX file."""
        file_size = len(content)

        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                file_list = zf.namelist()

                # Check for required files
                for required in self.REQUIRED_DOCX_FILES:
                    if required not in file_list:
                        return ValidationResult.failure(
                            ValidationErrorType.INVALID_FORMAT,
                            f"Missing required DOCX component: {required}",
                            file_size,
                        )

                # Check for content indicators
                has_content = any(indicator in file_list for indicator in self.CONTENT_INDICATORS)
                if not has_content:
                    return ValidationResult.failure(
                        ValidationErrorType.MISSING_CONTENT,
                        "Document appears to have no content",
                        file_size,
                    )

                # Try to read the main document to check for corruption
                try:
                    zf.read("word/document.xml")
                except (KeyError, Exception) as e:
                    return ValidationResult.failure(
                        ValidationErrorType.CORRUPTED_FILE,
                        f"Failed to read document content: {str(e)}",
                        file_size,
                    )

                return ValidationResult.success(file_size)

        except zipfile.BadZipFile:
            return ValidationResult.failure(
                ValidationErrorType.CORRUPTED_FILE, "DOCX file is corrupted", file_size
            )
        except Exception as e:
            return ValidationResult.failure(
                ValidationErrorType.CORRUPTED_FILE,
                f"Unexpected error during validation: {str(e)}",
                file_size,
            )
