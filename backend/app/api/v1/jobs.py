from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_job_service
from backend.app.domains.job.models import JobStatus, JobType
from backend.app.domains.job.schemas import (
    JobCountResponse,
    JobCreate,
    JobResponse,
    JobStatusResponse,
    PipelineStatusResponse,
)
from backend.app.domains.job.service import JobService, PipelineError

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
    if entity_type and entity_id:
        jobs = await service.list_jobs_by_entity(entity_type, entity_id, skip, limit)
    else:
        jobs = await service.list_jobs(
            status=status_filter, job_type=job_type, skip=skip, limit=limit
        )

    return [JobResponse.model_validate(j) for j in jobs]


@router.get("/counts", response_model=JobCountResponse)
async def get_job_counts(service: JobServiceDep) -> JobCountResponse:
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
    job = await service.create_job(data)
    await service.repo.session.commit()
    await service.repo.session.refresh(job)
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    service: JobServiceDep,
) -> JobResponse:
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
    return await service.get_pipeline_status(template_version_id)


@router.post(
    "/pipeline/{template_version_id}/start",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_pipeline(
    template_version_id: UUID,
    service: JobServiceDep,
) -> JobResponse:
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
