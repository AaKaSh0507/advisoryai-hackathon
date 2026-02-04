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
from backend.app.infrastructure.datetime_utils import utc_now


class SectionGenerationStatus(str, PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    VALIDATED = "VALIDATED"


class FailureCategory(str, PyEnum):
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    RETRY_EXHAUSTION = "RETRY_EXHAUSTION"
    STRUCTURAL_VIOLATION = "STRUCTURAL_VIOLATION"
    BOUNDS_VIOLATION = "BOUNDS_VIOLATION"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    failure_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_history: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped["SectionOutputBatch"] = relationship(
        "SectionOutputBatch", back_populates="outputs"
    )

    __table_args__ = (
        Index("ix_section_outputs_batch", "batch_id"),
        Index("ix_section_outputs_section", "section_id"),
        Index("ix_section_outputs_generation_input", "generation_input_id"),
        Index("ix_section_outputs_batch_sequence", "batch_id", "sequence_order"),
        Index("ix_section_outputs_failure_category", "failure_category"),
        Index("ix_section_outputs_status", "status"),
    )

    @property
    def is_successful(self) -> bool:
        return bool(
            self.status in (SectionGenerationStatus.COMPLETED, SectionGenerationStatus.VALIDATED)
            and self.generated_content
        )

    @property
    def is_failed(self) -> bool:
        return bool(self.status == SectionGenerationStatus.FAILED)

    @property
    def is_retry_exhausted(self) -> bool:
        return bool(self.retry_count >= self.max_retries)

    @property
    def can_retry(self) -> bool:
        return bool(
            not self.is_immutable
            and self.retry_count < self.max_retries
            and self.failure_category
            in (
                FailureCategory.GENERATION_FAILURE.value,
                FailureCategory.BOUNDS_VIOLATION.value,
            )
        )

    @property
    def is_ready_for_assembly(self) -> bool:
        return bool(
            self.is_validated
            and self.is_immutable
            and self.generated_content
            and self.status == SectionGenerationStatus.VALIDATED
        )
