import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database import Base


class GenerationInputStatus(str, PyEnum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"


class GenerationInputBatch(Base):
    __tablename__ = "generation_input_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template_versions.id"), nullable=False
    )
    version_intent: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[GenerationInputStatus] = mapped_column(
        SQLEnum(GenerationInputStatus, name="generation_input_status_enum"),
        nullable=False,
        default=GenerationInputStatus.PENDING,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total_inputs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    inputs: Mapped[list["GenerationInput"]] = relationship(
        "GenerationInput",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="GenerationInput.sequence_order",
    )

    __table_args__ = (
        Index("ix_generation_input_batches_document", "document_id"),
        Index("ix_generation_input_batches_template_version", "template_version_id"),
        Index(
            "ix_generation_input_batches_document_version",
            "document_id",
            "version_intent",
        ),
    )

    @property
    def is_validated(self) -> bool:
        return bool(self.status == GenerationInputStatus.VALIDATED)

    @property
    def is_failed(self) -> bool:
        return bool(self.status == GenerationInputStatus.FAILED)


class GenerationInput(Base):
    __tablename__ = "generation_inputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_input_batches.id"), nullable=False
    )
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.id"), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    structural_path: Mapped[str] = mapped_column(String, nullable=False)
    hierarchy_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    prompt_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    client_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    surrounding_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    batch: Mapped["GenerationInputBatch"] = relationship(
        "GenerationInputBatch", back_populates="inputs"
    )

    __table_args__ = (
        Index("ix_generation_inputs_batch", "batch_id"),
        Index("ix_generation_inputs_section", "section_id"),
        Index("ix_generation_inputs_batch_sequence", "batch_id", "sequence_order"),
    )
