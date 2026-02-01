from typing import Optional
from uuid import UUID

from backend.app.domains.job.models import Job, JobStatus, JobType
from backend.app.domains.job.schemas import JobCreate


class JobService:
    async def get_job(self, job_id: UUID) -> Optional[Job]:
        return None

    async def list_jobs(
        self, status: Optional[JobStatus] = None, skip: int = 0, limit: int = 100
    ) -> list[Job]:
        return []

    async def create_job(self, data: JobCreate) -> Job:
        return Job(
            job_type=data.job_type,
            payload=data.payload,
            status=JobStatus.PENDING,
        )

    async def get_job_status(self, job_id: UUID) -> Optional[Job]:
        return None

    async def cancel_job(self, job_id: UUID) -> bool:
        return False
