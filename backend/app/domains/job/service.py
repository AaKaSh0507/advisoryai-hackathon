from typing import Optional, Sequence
from uuid import UUID

from backend.app.domains.job.models import Job, JobStatus, JobType
from backend.app.domains.job.repository import JobRepository
from backend.app.domains.job.schemas import (
    ClassifyJobCreate,
    GenerateJobCreate,
    JobCreate,
    JobStatusResponse,
    ParseJobCreate,
    PipelineStatusResponse,
    RegenerateJobCreate,
    RegenerateSectionsJobCreate,
)
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.job.service")


class JobCreationError(Exception):
    pass


class PipelineError(Exception):
    pass


class JobService:
    def __init__(self, repo: JobRepository):
        self.repo = repo

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        return await self.repo.get_by_id(job_id)

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Job]:
        return await self.repo.list_all(
            status_filter=status, job_type=job_type, skip=skip, limit=limit
        )

    async def list_jobs_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Job]:
        return await self.repo.list_by_entity(entity_type, entity_id, skip, limit)

    async def get_job_status(self, job_id: UUID) -> Optional[Job]:
        return await self.repo.get_by_id(job_id)

    async def get_job_counts(self) -> dict[JobStatus, int]:
        return await self.repo.count_by_status()

    async def create_job(self, data: JobCreate) -> Job:
        job = Job(
            job_type=data.job_type,
            payload=data.payload,
            status=JobStatus.PENDING,
        )
        return await self.repo.create(job)

    async def create_parse_job(self, data: ParseJobCreate) -> Job:
        job = Job(
            job_type=JobType.PARSE,
            payload={"template_version_id": str(data.template_version_id)},
            status=JobStatus.PENDING,
        )
        created = await self.repo.create(job)
        logger.info(
            f"Created PARSE job {created.id} for template_version {data.template_version_id}"
        )
        return created

    async def create_classify_job(self, data: ClassifyJobCreate) -> Job:
        job = Job(
            job_type=JobType.CLASSIFY,
            payload={"template_version_id": str(data.template_version_id)},
            status=JobStatus.PENDING,
        )
        created = await self.repo.create(job)
        logger.info(
            f"Created CLASSIFY job {created.id} for template_version {data.template_version_id}"
        )
        return created

    async def create_generate_job(self, data: GenerateJobCreate) -> Job:
        job = Job(
            job_type=JobType.GENERATE,
            payload={
                "template_version_id": str(data.template_version_id),
                "document_id": str(data.document_id),
                "version_intent": data.version_intent,
                "client_data": data.client_data,
                "force_regenerate": data.force_regenerate,
            },
            status=JobStatus.PENDING,
        )
        created = await self.repo.create(job)
        logger.info(f"Created GENERATE job {created.id} for document {data.document_id}")
        return created

    async def create_regenerate_job(self, data: "RegenerateJobCreate") -> Job:
        """Create a full document regeneration job."""
        job = Job(
            job_type=JobType.REGENERATE,
            payload={
                "document_id": str(data.document_id),
                "version_intent": data.version_intent,
                "client_data": data.client_data,
                "correlation_id": data.correlation_id,
            },
            status=JobStatus.PENDING,
        )
        created = await self.repo.create(job)
        logger.info(
            f"Created REGENERATE job {created.id} for document {data.document_id}, "
            f"version_intent: {data.version_intent}"
        )
        return created

    async def create_regenerate_sections_job(self, data: "RegenerateSectionsJobCreate") -> Job:
        """Create a section-level regeneration job."""
        job = Job(
            job_type=JobType.REGENERATE_SECTIONS,
            payload={
                "document_id": str(data.document_id),
                "template_version_id": str(data.template_version_id),
                "version_intent": data.version_intent,
                "section_ids": data.section_ids,
                "reuse_section_ids": data.reuse_section_ids,
                "client_data": data.client_data,
                "correlation_id": data.correlation_id,
            },
            status=JobStatus.PENDING,
        )
        created = await self.repo.create(job)
        logger.info(
            f"Created REGENERATE_SECTIONS job {created.id} for document {data.document_id}, "
            f"sections: {data.section_ids}, reuse: {data.reuse_section_ids}"
        )
        return created

    async def claim_job(
        self, worker_id: str, job_types: Optional[list[JobType]] = None
    ) -> Optional[Job]:
        job = await self.repo.claim_pending_job(worker_id, job_types)
        if job:
            logger.info(f"Worker {worker_id} claimed job {job.id} ({job.job_type.value})")
        return job

    async def complete_job(self, job_id: UUID, result: Optional[dict] = None) -> Optional[Job]:
        job = await self.repo.complete_job(job_id, result)
        if job:
            logger.info(f"Job {job_id} completed successfully")
        return job

    async def fail_job(self, job_id: UUID, error: str) -> Optional[Job]:
        job = await self.repo.fail_job(job_id, error)
        if job:
            logger.warning(f"Job {job_id} failed: {error}")
        return job

    async def cancel_job(self, job_id: UUID) -> bool:
        job = await self.repo.get_by_id(job_id)
        if not job:
            return False
        if job.is_terminal:
            return False

        await self.repo.fail_job(job_id, "Cancelled by user")
        logger.info(f"Job {job_id} cancelled by user")
        return True

    async def recover_stuck_jobs(self, timeout_minutes: int = 30) -> list[UUID]:
        stuck_jobs = await self.repo.find_stuck_jobs(timeout_minutes)
        recovered_ids = []

        for job in stuck_jobs:
            reason = f"Worker timeout after {timeout_minutes} minutes"
            await self.repo.reset_stuck_job(job.id, reason)
            recovered_ids.append(job.id)
            logger.warning(f"Reset stuck job {job.id}: {reason}")

        return recovered_ids

    async def get_pipeline_status(self, template_version_id: UUID) -> PipelineStatusResponse:
        pipeline = await self.repo.get_pipeline_jobs(template_version_id)
        parse_job = pipeline.get(JobType.PARSE)
        classify_job = pipeline.get(JobType.CLASSIFY)
        generate_job = pipeline.get(JobType.GENERATE)
        current_stage = None
        is_complete = False
        has_failed = False

        if parse_job and parse_job.status == JobStatus.FAILED:
            has_failed = True
            current_stage = "PARSE"
        elif classify_job and classify_job.status == JobStatus.FAILED:
            has_failed = True
            current_stage = "CLASSIFY"
        elif generate_job and generate_job.status == JobStatus.FAILED:
            has_failed = True
            current_stage = "GENERATE"
        elif generate_job and generate_job.status == JobStatus.COMPLETED:
            is_complete = True
            current_stage = "COMPLETE"
        elif generate_job and generate_job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
            current_stage = "GENERATE"
        elif classify_job and classify_job.status == JobStatus.COMPLETED:
            current_stage = "READY_FOR_GENERATE"
        elif classify_job and classify_job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
            current_stage = "CLASSIFY"
        elif parse_job and parse_job.status == JobStatus.COMPLETED:
            current_stage = "READY_FOR_CLASSIFY"
        elif parse_job and parse_job.status in {JobStatus.PENDING, JobStatus.RUNNING}:
            current_stage = "PARSE"
        else:
            current_stage = "NOT_STARTED"

        return PipelineStatusResponse(
            template_version_id=template_version_id,
            parse_job=JobStatusResponse.model_validate(parse_job) if parse_job else None,
            classify_job=JobStatusResponse.model_validate(classify_job) if classify_job else None,
            generate_job=JobStatusResponse.model_validate(generate_job) if generate_job else None,
            current_stage=current_stage,
            is_complete=is_complete,
            has_failed=has_failed,
        )

    async def start_pipeline(self, template_version_id: UUID) -> Job:
        existing = await self.repo.get_pipeline_jobs(template_version_id)
        parse_job = existing.get(JobType.PARSE)

        if parse_job and not parse_job.is_terminal:
            raise PipelineError(
                f"Pipeline already in progress for template_version {template_version_id}"
            )

        return await self.create_parse_job(ParseJobCreate(template_version_id=template_version_id))

    async def advance_pipeline(self, job: Job) -> Optional[Job]:
        if job.status != JobStatus.COMPLETED:
            return None

        template_version_id = job.payload.get("template_version_id")
        if not template_version_id:
            return None

        tv_id = UUID(template_version_id)

        if job.job_type == JobType.PARSE:
            return await self.create_classify_job(ClassifyJobCreate(template_version_id=tv_id))

        elif job.job_type == JobType.CLASSIFY:
            logger.info(
                f"Classification complete for template_version {tv_id}, ready for generation"
            )
            return None

        return None
