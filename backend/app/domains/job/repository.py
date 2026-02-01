from typing import Sequence, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.job.models import Job, JobStatus

class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Optional[Job]:
        stmt = select(Job).where(Job.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
        
    async def list_all(
        self, 
        status_filter: Optional[JobStatus] = None, 
        skip: int = 0, 
        limit: int = 100
    ) -> Sequence[Job]:
        stmt = select(Job)
        if status_filter:
            stmt = stmt.where(Job.status == status_filter)
        stmt = stmt.offset(skip).limit(limit).order_by(Job.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, job_id: uuid.UUID, status: JobStatus, error: Optional[str] = None) -> Optional[Job]:
        job = await self.get_by_id(job_id)
        if job:
            job.status = status
            if error:
                job.error = error
            await self.session.flush()
        return job
