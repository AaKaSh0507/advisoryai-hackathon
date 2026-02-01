from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from backend.app.domains.job.models import JobStatus, JobType


class JobCreate(BaseModel):
    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)


class ParseJobCreate(BaseModel):
    """Schema for creating a PARSE job."""

    template_version_id: UUID


class ClassifyJobCreate(BaseModel):
    """Schema for creating a CLASSIFY job."""

    template_version_id: UUID


class GenerateJobCreate(BaseModel):
    """Schema for creating a GENERATE job."""

    template_version_id: UUID
    document_id: UUID


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
    """Query parameters for listing jobs."""

    status: Optional[JobStatus] = None
    job_type: Optional[JobType] = None
    entity_type: Optional[str] = Field(None, pattern="^(template_version|document)$")
    entity_id: Optional[UUID] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class PipelineStatusResponse(BaseModel):
    """Status of a complete processing pipeline for a template version."""

    template_version_id: UUID
    parse_job: Optional[JobStatusResponse] = None
    classify_job: Optional[JobStatusResponse] = None
    generate_job: Optional[JobStatusResponse] = None
    current_stage: Optional[str] = None
    is_complete: bool = False
    has_failed: bool = False

    model_config = ConfigDict(from_attributes=True)


class JobCountResponse(BaseModel):
    """Count of jobs by status."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
