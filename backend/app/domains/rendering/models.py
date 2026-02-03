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


class RenderStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VALIDATED = "VALIDATED"


class RenderedDocument(Base):
    __tablename__ = "rendered_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assembled_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assembled_documents.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RenderStatus] = mapped_column(
        SQLEnum(RenderStatus, name="render_status_enum"),
        nullable=False,
        default=RenderStatus.PENDING,
    )
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_blocks_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paragraphs_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tables_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lists_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    headings_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    headers_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    footers_rendered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rendering_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    rendering_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_rendered_documents_assembled", "assembled_document_id"),
        Index("ix_rendered_documents_document", "document_id"),
        Index("ix_rendered_documents_document_version", "document_id", "version"),
        Index("ix_rendered_documents_status", "status"),
        Index("ix_rendered_documents_content_hash", "content_hash"),
    )

    @property
    def is_complete(self) -> bool:
        return bool(self.status in (RenderStatus.COMPLETED, RenderStatus.VALIDATED))

    @property
    def is_failed(self) -> bool:
        return bool(self.status == RenderStatus.FAILED)

    @property
    def is_validated(self) -> bool:
        return bool(self.status == RenderStatus.VALIDATED)

    @property
    def can_be_persisted(self) -> bool:
        return bool(self.is_complete and self.output_path and self.content_hash)
