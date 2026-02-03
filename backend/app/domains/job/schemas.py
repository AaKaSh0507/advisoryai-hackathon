from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.job.models import JobStatus, JobType


class JobCreate(BaseModel):
    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)


class ParseJobCreate(BaseModel):
    template_version_id: UUID


class ClassifyJobCreate(BaseModel):
    template_version_id: UUID


class GenerateJobCreate(BaseModel):
    template_version_id: UUID
    document_id: UUID
    version_intent: int = Field(default=1, ge=1)
    client_data: dict[str, Any] = Field(default_factory=dict)
    force_regenerate: bool = False


class RegenerateJobCreate(BaseModel):
    """Request to create a full regeneration job."""

    document_id: UUID
    version_intent: int = Field(ge=1)
    client_data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class RegenerateSectionsJobCreate(BaseModel):
    """Request to create a section-level regeneration job."""

    document_id: UUID
    template_version_id: UUID
    version_intent: int = Field(ge=1)
    section_ids: list[int] = Field(min_length=1)
    reuse_section_ids: list[int] = Field(default_factory=list)
    client_data: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class JobResponse(BaseModel):
    id: UUID
    job_type: JobType
    status: JobStatus
    payload: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    id: UUID
    job_type: JobType
    status: JobStatus
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListQuery(BaseModel):
    status: Optional[JobStatus] = None
    job_type: Optional[JobType] = None
    entity_type: Optional[str] = Field(None, pattern="^(template_version|document)$")
    entity_id: Optional[UUID] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class PipelineStatusResponse(BaseModel):
    template_version_id: UUID
    parse_job: Optional[JobStatusResponse] = None
    classify_job: Optional[JobStatusResponse] = None
    generate_job: Optional[JobStatusResponse] = None
    current_stage: Optional[str] = None
    is_complete: bool = False
    has_failed: bool = False

    model_config = ConfigDict(from_attributes=True)


class JobCountResponse(BaseModel):
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
