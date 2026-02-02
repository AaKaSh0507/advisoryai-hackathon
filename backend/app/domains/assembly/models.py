import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database import Base


class AssemblyStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VALIDATED = "VALIDATED"


class AssembledDocument(Base):
    __tablename__ = "assembled_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template_versions.id"), nullable=False
    )
    version_intent: Mapped[int] = mapped_column(Integer, nullable=False)
    section_output_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("section_output_batches.id"), nullable=False
    )
    status: Mapped[AssemblyStatus] = mapped_column(
        SQLEnum(AssemblyStatus, name="assembly_status_enum"),
        nullable=False,
        default=AssemblyStatus.PENDING,
    )
    assembly_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total_blocks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dynamic_blocks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    static_blocks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    injected_sections_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assembled_structure: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    injection_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    document_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    headers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    footers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    assembly_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    assembled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_assembled_documents_document", "document_id"),
        Index("ix_assembled_documents_template_version", "template_version_id"),
        Index("ix_assembled_documents_section_output_batch", "section_output_batch_id"),
        Index("ix_assembled_documents_document_version", "document_id", "version_intent"),
        Index("ix_assembled_documents_status", "status"),
        Index("ix_assembled_documents_assembly_hash", "assembly_hash"),
    )

    @property
    def is_complete(self) -> bool:
        return bool(self.status in (AssemblyStatus.COMPLETED, AssemblyStatus.VALIDATED))

    @property
    def is_failed(self) -> bool:
        return bool(self.status == AssemblyStatus.FAILED)

    @property
    def is_validated(self) -> bool:
        return bool(self.status == AssemblyStatus.VALIDATED)

    @property
    def can_be_rendered(self) -> bool:
        return bool(
            self.is_immutable
            and self.status == AssemblyStatus.VALIDATED
            and self.assembled_structure
        )
