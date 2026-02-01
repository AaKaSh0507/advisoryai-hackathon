from typing import Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query

from backend.app.domains.job.models import JobStatus, JobType
from backend.app.domains.job.schemas import (
    JobCreate,
    JobResponse,
    JobStatusResponse,
    PipelineStatusResponse,
    JobCountResponse,
)
from backend.app.domains.job.service import JobService, PipelineError
from backend.app.api.deps import get_job_service

router = APIRouter()
JobServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    service: JobServiceDep,
    status_filter: Optional[JobStatus] = Query(None, alias="status"),
    job_type: Optional[JobType] = Query(None, alias="type"),
    entity_type: Optional[str] = Query(None, pattern="^(template_version|document)$"),
    entity_id: Optional[UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[JobResponse]:
    """
    List jobs with optional filtering.

    Filter by:
    - status: PENDING, RUNNING, COMPLETED, FAILED
    - type: PARSE, CLASSIFY, GENERATE
    - entity_type + entity_id: Jobs related to a specific entity
    """
    if entity_type and entity_id:
        jobs = await service.list_jobs_by_entity(entity_type, entity_id, skip, limit)
    else:
        jobs = await service.list_jobs(status=status_filter, job_type=job_type, skip=skip, limit=limit)

    return [JobResponse.model_validate(j) for j in jobs]


@router.get("/counts", response_model=JobCountResponse)
async def get_job_counts(service: JobServiceDep) -> JobCountResponse:
    """Get count of jobs by status."""
    counts = await service.get_job_counts()
    return JobCountResponse(
        pending=counts.get(JobStatus.PENDING, 0),
        running=counts.get(JobStatus.RUNNING, 0),
        completed=counts.get(JobStatus.COMPLETED, 0),
        failed=counts.get(JobStatus.FAILED, 0),
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    service: JobServiceDep,
) -> JobResponse:
    """
    Create a new job.

    For most use cases, prefer using the specialized endpoints:
    - POST /templates/{id}/versions to trigger parsing
    - Pipeline advancement is automatic
    """
    job = await service.create_job(data)
    await service.repo.session.commit()
    await service.repo.session.refresh(job)
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    service: JobServiceDep,
) -> JobResponse:
    """Get full job details including payload and result."""
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return JobResponse.model_validate(job)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    service: JobServiceDep,
) -> JobStatusResponse:
    """Get job status (lighter response without payload/result)."""
    job = await service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return JobStatusResponse.model_validate(job)


@router.post("/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job(
    job_id: UUID,
    service: JobServiceDep,
) -> dict:
    """
    Cancel a job.

    Only jobs in PENDING or RUNNING state can be cancelled.
    Completed or already failed jobs cannot be cancelled.
    """
    cancelled = await service.cancel_job(job_id)
    if not cancelled:
        job = await service.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} cannot be cancelled (status: {job.status.value})",
        )
    await service.repo.session.commit()
    return {"message": f"Job {job_id} cancelled"}


@router.get("/pipeline/{template_version_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    template_version_id: UUID,
    service: JobServiceDep,
) -> PipelineStatusResponse:
    """
    Get the status of the processing pipeline for a template version.

    Returns the status of each stage (PARSE, CLASSIFY, GENERATE) and
    indicates the current stage and overall pipeline state.
    """
    return await service.get_pipeline_status(template_version_id)


@router.post("/pipeline/{template_version_id}/start", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def start_pipeline(
    template_version_id: UUID,
    service: JobServiceDep,
) -> JobResponse:
    """
    Start the processing pipeline for a template version.

    Creates a PARSE job to begin the pipeline. Subsequent stages
    (CLASSIFY) will be created automatically upon completion.

    GENERATE jobs are created when documents are created.
    """
    try:
        job = await service.start_pipeline(template_version_id)
        await service.repo.session.commit()
        await service.repo.session.refresh(job)
        return JobResponse.model_validate(job)
    except PipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
