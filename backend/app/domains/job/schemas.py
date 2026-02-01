from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from backend.app.domains.job.models import JobStatus, JobType


class JobCreate(BaseModel):
    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    id: UUID
    job_type: JobType
    status: JobStatus
    payload: dict[str, Any]
    result: Optional[dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    id: UUID
    job_type: JobType
    status: JobStatus
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
