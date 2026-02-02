import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import Boolean, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.infrastructure.database import Base


class SectionGenerationStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SectionOutputBatch(Base):
    __tablename__ = "section_output_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_input_batches.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    version_intent: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SectionGenerationStatus] = mapped_column(
        SQLEnum(SectionGenerationStatus, name="section_generation_status_enum"),
        nullable=False,
        default=SectionGenerationStatus.PENDING,
    )
    total_sections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_sections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_sections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    outputs: Mapped[list["SectionOutput"]] = relationship(
        "SectionOutput",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="SectionOutput.sequence_order",
    )

    __table_args__ = (
        Index("ix_section_output_batches_input_batch", "input_batch_id"),
        Index("ix_section_output_batches_document", "document_id"),
        Index(
            "ix_section_output_batches_document_version",
            "document_id",
            "version_intent",
        ),
    )

    @property
    def is_complete(self) -> bool:
        return bool(self.status == SectionGenerationStatus.COMPLETED)

    @property
    def has_failures(self) -> bool:
        return bool(self.failed_sections > 0)


class SectionOutput(Base):
    __tablename__ = "section_outputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("section_output_batches.id"), nullable=False
    )
    generation_input_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generation_inputs.id"), nullable=False
    )
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.id"), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SectionGenerationStatus] = mapped_column(
        SQLEnum(SectionGenerationStatus, name="section_generation_status_enum", create_type=False),
        nullable=False,
        default=SectionGenerationStatus.PENDING,
    )
    generated_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    batch: Mapped["SectionOutputBatch"] = relationship(
        "SectionOutputBatch", back_populates="outputs"
    )

    __table_args__ = (
        Index("ix_section_outputs_batch", "batch_id"),
        Index("ix_section_outputs_section", "section_id"),
        Index("ix_section_outputs_generation_input", "generation_input_id"),
        Index("ix_section_outputs_batch_sequence", "batch_id", "sequence_order"),
    )

    @property
    def is_successful(self) -> bool:
        return bool(self.status == SectionGenerationStatus.COMPLETED and self.generated_content)

    @property
    def is_failed(self) -> bool:
        return bool(self.status == SectionGenerationStatus.FAILED)
