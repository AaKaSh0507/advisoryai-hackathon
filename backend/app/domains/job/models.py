from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class JobType(str, Enum):
    PARSING = "parsing"
    CLASSIFICATION = "classification"
    GENERATION = "generation"


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: UUID = field(default_factory=uuid4)
    job_type: JobType = JobType.PARSING
    status: JobStatus = JobStatus.PENDING
    payload: dict[str, Any] = field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
