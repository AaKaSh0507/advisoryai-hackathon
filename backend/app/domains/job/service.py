from typing import Optional, Sequence
from uuid import UUID

from backend.app.domains.job.models import Job, JobStatus, JobType
from backend.app.domains.job.schemas import JobCreate
from backend.app.domains.job.repository import JobRepository

class JobService:
    def __init__(self, repo: JobRepository):
        self.repo = repo

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        return await self.repo.get_by_id(job_id)

    async def list_jobs(
        self, status: Optional[JobStatus] = None, skip: int = 0, limit: int = 100
    ) -> Sequence[Job]:
        return await self.repo.list_all(status_filter=status, skip=skip, limit=limit)

    async def create_job(self, data: JobCreate) -> Job:
        job = Job(
            job_type=data.job_type,
            payload=data.payload,
            status=JobStatus.PENDING,
        )
        return await self.repo.create(job)

    async def get_job_status(self, job_id: UUID) -> Optional[Job]:
        return await self.repo.get_by_id(job_id)

    async def cancel_job(self, job_id: UUID) -> bool:
        # Business logic: can only cancel if PENDING or RUNNING
        job = await self.repo.get_by_id(job_id)
        if not job:
            return False
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            return False
        
        job.status = JobStatus.FAILED
        job.error = "Cancelled by user"
        await self.repo.session.flush()
        return True
