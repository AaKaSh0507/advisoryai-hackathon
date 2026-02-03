import hashlib
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RenderErrorCode(str, PyEnum):
    INVALID_ASSEMBLED_DOCUMENT = "INVALID_ASSEMBLED_DOCUMENT"
    MISSING_ASSEMBLED_STRUCTURE = "MISSING_ASSEMBLED_STRUCTURE"
    DOCUMENT_NOT_IMMUTABLE = "DOCUMENT_NOT_IMMUTABLE"
    DOCUMENT_NOT_VALIDATED = "DOCUMENT_NOT_VALIDATED"
    RENDERING_FAILED = "RENDERING_FAILED"
    BLOCK_RENDERING_FAILED = "BLOCK_RENDERING_FAILED"
    TABLE_RENDERING_FAILED = "TABLE_RENDERING_FAILED"
    LIST_RENDERING_FAILED = "LIST_RENDERING_FAILED"
    HEADER_FOOTER_RENDERING_FAILED = "HEADER_FOOTER_RENDERING_FAILED"
    STYLE_APPLICATION_FAILED = "STYLE_APPLICATION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    FILE_CORRUPTION_DETECTED = "FILE_CORRUPTION_DETECTED"
    CONTENT_MISSING = "CONTENT_MISSING"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    ALREADY_RENDERED = "ALREADY_RENDERED"


class RenderingStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VALIDATED = "VALIDATED"


class RenderingValidationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = True
    file_exists: bool = False
    file_opens_cleanly: bool = False
    content_present: bool = False
    structure_intact: bool = False
    no_corruption: bool = False
    error_codes: list[RenderErrorCode] = Field(default_factory=list)
    error_messages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    file_size_bytes: int = 0
    block_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    heading_count: int = 0

    @property
    def has_errors(self) -> bool:
        return len(self.error_codes) > 0

    def add_error(self, code: RenderErrorCode, message: str) -> None:
        self.is_valid = False
        self.error_codes.append(code)
        self.error_messages.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class RenderingRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assembled_document_id: UUID
    document_id: UUID
    version: int
    force_rerender: bool = False


class RenderedDocumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assembled_document_id: UUID
    document_id: UUID
    version: int
    status: RenderingStatus = RenderingStatus.PENDING
    output_path: str | None = None
    content_hash: str | None = None
    file_size_bytes: int = 0
    total_blocks_rendered: int = 0
    paragraphs_rendered: int = 0
    tables_rendered: int = 0
    lists_rendered: int = 0
    headings_rendered: int = 0
    headers_rendered: int = 0
    footers_rendered: int = 0
    validation_result: RenderingValidationResult | None = None
    is_immutable: bool = False
    rendered_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def compute_content_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


class RenderingResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool = False
    rendered_document: RenderedDocumentSchema | None = None
    validation_result: RenderingValidationResult | None = None
    output_path: str | None = None
    error_code: RenderErrorCode | None = None
    error_message: str | None = None
    rendering_duration_ms: float | None = None

    @property
    def has_errors(self) -> bool:
        return not self.success or (
            self.validation_result is not None and self.validation_result.has_errors
        )


class BlockRenderContext(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_id: str
    block_type: str
    sequence: int
    block_data: dict[str, Any]
    was_modified: bool = False
    is_dynamic: bool = False


class RenderingStatistics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_blocks: int = 0
    paragraphs: int = 0
    headings: int = 0
    tables: int = 0
    lists: int = 0
    headers: int = 0
    footers: int = 0
    page_breaks: int = 0
    section_breaks: int = 0


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
