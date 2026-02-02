import hashlib
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.parsing.schemas import (
    BlockType,
    DocumentBlock,
    DocumentMetadata,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
    TextRun,
)


class AssemblyErrorCode(str, PyEnum):
    MISSING_VALIDATED_CONTENT = "MISSING_VALIDATED_CONTENT"
    STRUCTURAL_MISMATCH = "STRUCTURAL_MISMATCH"
    BLOCK_COUNT_MISMATCH = "BLOCK_COUNT_MISMATCH"
    BLOCK_ORDER_MISMATCH = "BLOCK_ORDER_MISMATCH"
    STATIC_SECTION_MODIFIED = "STATIC_SECTION_MODIFIED"
    INVALID_INJECTION_TARGET = "INVALID_INJECTION_TARGET"
    DUPLICATE_BLOCK_ID = "DUPLICATE_BLOCK_ID"
    ORPHANED_BLOCK = "ORPHANED_BLOCK"
    UNKNOWN_BLOCK_TYPE = "UNKNOWN_BLOCK_TYPE"
    HASH_MISMATCH = "HASH_MISMATCH"
    IMMUTABLE_DOCUMENT = "IMMUTABLE_DOCUMENT"
    MISSING_PARSED_TEMPLATE = "MISSING_PARSED_TEMPLATE"
    INVALID_SECTION_OUTPUT = "INVALID_SECTION_OUTPUT"
    ASSEMBLY_ALREADY_EXISTS = "ASSEMBLY_ALREADY_EXISTS"


class AssemblyStatusEnum(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VALIDATED = "VALIDATED"


class AssemblyValidationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = True
    error_codes: list[AssemblyErrorCode] = Field(default_factory=list)
    error_messages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_errors(self) -> bool:
        return len(self.error_codes) > 0

    def add_error(self, code: AssemblyErrorCode, message: str) -> None:
        self.is_valid = False
        self.error_codes.append(code)
        self.error_messages.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class SectionInjectionResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_id: int
    structural_path: str
    was_injected: bool = False
    original_content_hash: str | None = None
    injected_content_hash: str | None = None
    content_length: int = 0
    is_static: bool = False
    error_message: str | None = None


class AssembledBlockSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_id: str
    block_type: BlockType
    sequence: int
    is_dynamic: bool = False
    section_id: int | None = None
    original_content_hash: str | None = None
    assembled_content_hash: str | None = None
    was_modified: bool = False
    block_data: dict[str, Any] = Field(default_factory=dict)


class AssemblyInputSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_id: int
    structural_path: str
    generated_content: str
    content_hash: str
    is_validated: bool = True


class AssemblyRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    template_version_id: UUID
    version_intent: int
    section_output_batch_id: UUID
    force_reassembly: bool = False


class AssembledDocumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    template_version_id: UUID
    version_intent: int
    section_output_batch_id: UUID
    assembly_hash: str
    total_blocks: int = 0
    dynamic_blocks_count: int = 0
    static_blocks_count: int = 0
    injected_sections_count: int = 0
    metadata: DocumentMetadata | None = None
    blocks: list[AssembledBlockSchema] = Field(default_factory=list)
    headers: list[dict[str, Any]] = Field(default_factory=list)
    footers: list[dict[str, Any]] = Field(default_factory=list)
    injection_results: list[SectionInjectionResult] = Field(default_factory=list)
    validation_result: AssemblyValidationResult | None = None
    is_immutable: bool = False
    assembled_at: datetime = Field(default_factory=datetime.utcnow)

    def compute_assembly_hash(self) -> str:
        content_parts = [
            str(self.document_id),
            str(self.template_version_id),
            str(self.version_intent),
            str(self.section_output_batch_id),
        ]
        for block in sorted(self.blocks, key=lambda b: b.sequence):
            content_parts.append(f"{block.block_id}:{block.assembled_content_hash or ''}")
        combined = "|".join(content_parts)
        return hashlib.sha256(combined.encode()).hexdigest()


class AssemblyResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    success: bool = False
    assembled_document: AssembledDocumentSchema | None = None
    validation_result: AssemblyValidationResult | None = None
    injection_results: list[SectionInjectionResult] = Field(default_factory=list)
    error_code: AssemblyErrorCode | None = None
    error_message: str | None = None
    assembly_duration_ms: float | None = None

    @property
    def has_errors(self) -> bool:
        return not self.success or (
            self.validation_result is not None and self.validation_result.has_errors
        )


def compute_block_content_hash(block: DocumentBlock) -> str:
    if isinstance(block, (ParagraphBlock, HeadingBlock)):
        content = "".join(run.text for run in block.runs)
    elif isinstance(block, TableBlock):
        content = f"table:{block.row_count}x{block.column_count}"
    elif isinstance(block, ListBlock):
        content = "|".join(item.text for item in block.items)
    else:
        content = str(block.block_id)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def create_text_run_from_content(content: str) -> TextRun:
    return TextRun(text=content)


def create_paragraph_block_with_content(
    block_id: str,
    sequence: int,
    content: str,
    style_name: str | None = None,
    alignment: str | None = None,
) -> ParagraphBlock:
    return ParagraphBlock(
        block_id=block_id,
        sequence=sequence,
        runs=[create_text_run_from_content(content)],
        style_name=style_name,
        alignment=alignment,
    )
