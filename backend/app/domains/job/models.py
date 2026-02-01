import uuid
from datetime import datetime
from typing import Optional, Any
from enum import Enum as PyEnum

from sqlalchemy import String, DateTime, Enum as SQLEnum, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from backend.app.infrastructure.database import Base


class JobType(str, PyEnum):
    PARSE = "PARSE"
    CLASSIFY = "CLASSIFY"
    GENERATE = "GENERATE"


class JobStatus(str, PyEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.FAILED: set(),
    JobStatus.COMPLETED: set(),
}


class InvalidJobTransitionError(Exception):

    def __init__(self, job_id: uuid.UUID, from_status: JobStatus, to_status: JobStatus):
        self.job_id = job_id
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(
            f"Invalid job transition for {job_id}: {from_status.value} -> {to_status.value}"
        )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[JobType] = mapped_column(SQLEnum(JobType, name="job_type_enum"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status_enum"), nullable=False, default=JobStatus.PENDING
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    worker_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_payload_entity", "payload", postgresql_using="gin"),
    )

    def can_transition_to(self, new_status: JobStatus) -> bool:
        return new_status in VALID_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status: JobStatus) -> None:
        if not self.can_transition_to(new_status):
            raise InvalidJobTransitionError(self.id, self.status, new_status)
        self.status = new_status
        self.updated_at = datetime.utcnow()

    @property
    def is_terminal(self) -> bool:
        return self.status in {JobStatus.COMPLETED, JobStatus.FAILED}

    @property
    def entity_id(self) -> Optional[uuid.UUID]:
        entity_id = self.payload.get("template_version_id") or self.payload.get("document_id")
        if entity_id:
            return uuid.UUID(entity_id) if isinstance(entity_id, str) else entity_id
        return None
