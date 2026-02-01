from datetime import datetime, timedelta
from typing import Sequence, Optional
import uuid

from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.job.models import Job, JobStatus, JobType


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
        job_type: Optional[JobType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Job]:
        stmt = select(Job)
        if status_filter:
            stmt = stmt.where(Job.status == status_filter)
        if job_type:
            stmt = stmt.where(Job.job_type == job_type)
        stmt = stmt.offset(skip).limit(limit).order_by(Job.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_entity(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Job]:
        """List jobs for a specific entity (template_version or document)."""
        key = f"{entity_type}_id"
        stmt = (
            select(Job)
            .where(Job.payload[key].astext == str(entity_id))
            .offset(skip)
            .limit(limit)
            .order_by(Job.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def claim_pending_job(
        self, worker_id: str, job_types: Optional[list[JobType]] = None
    ) -> Optional[Job]:
        """
        Atomically claim the oldest pending job for the given worker.
        Uses SELECT FOR UPDATE SKIP LOCKED for atomic claiming.
        Returns the claimed job or None if no jobs available.
        """
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.PENDING)
            .order_by(Job.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job_types:
            stmt = stmt.where(Job.job_type.in_(job_types))

        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if job:
            job.status = JobStatus.RUNNING
            job.worker_id = worker_id
            job.started_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            await self.session.flush()

        return job

    async def complete_job(
        self, job_id: uuid.UUID, result: Optional[dict] = None
    ) -> Optional[Job]:
        """Mark a job as completed with optional result data."""
        job = await self.get_by_id(job_id)
        if not job or job.status != JobStatus.RUNNING:
            return None

        job.status = JobStatus.COMPLETED
        job.result = result
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def fail_job(
        self, job_id: uuid.UUID, error: str
    ) -> Optional[Job]:
        """Mark a job as failed with error information."""
        job = await self.get_by_id(job_id)
        if not job or job.is_terminal:
            return None

        job.status = JobStatus.FAILED
        job.error = error
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def find_stuck_jobs(self, timeout_minutes: int = 30) -> Sequence[Job]:
        """
        Find jobs that have been RUNNING longer than the timeout.
        These may be from crashed workers.
        """
        threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        stmt = select(Job).where(
            and_(
                Job.status == JobStatus.RUNNING,
                Job.started_at < threshold,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def reset_stuck_job(self, job_id: uuid.UUID, reason: str) -> Optional[Job]:
        """
        Reset a stuck job back to PENDING status for retry.
        Records the reset reason in the error field.
        """
        job = await self.get_by_id(job_id)
        if not job or job.status != JobStatus.RUNNING:
            return None

        job.status = JobStatus.PENDING
        job.worker_id = None
        job.started_at = None
        job.error = f"Reset: {reason}"
        job.updated_at = datetime.utcnow()
        await self.session.flush()
        return job

    async def get_pipeline_jobs(self, template_version_id: uuid.UUID) -> dict[JobType, Optional[Job]]:
        """
        Get all jobs in the pipeline for a template version.
        Returns a dict mapping JobType to the most recent job of that type.
        """
        stmt = (
            select(Job)
            .where(Job.payload["template_version_id"].astext == str(template_version_id))
            .order_by(Job.created_at.desc())
        )
        result = await self.session.execute(stmt)
        jobs = result.scalars().all()

        pipeline: dict[JobType, Optional[Job]] = {
            JobType.PARSE: None,
            JobType.CLASSIFY: None,
            JobType.GENERATE: None,
        }
        for job in jobs:
            if pipeline[job.job_type] is None:
                pipeline[job.job_type] = job

        return pipeline

    async def count_by_status(self) -> dict[JobStatus, int]:
        """Get count of jobs by status."""
        from sqlalchemy import func

        stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
