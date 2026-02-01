from typing import Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends

from backend.app.domains.job.models import JobStatus
from backend.app.domains.job.schemas import (
    JobCreate,
    JobResponse,
    JobStatusResponse,
)
from backend.app.domains.job.service import JobService
from backend.app.api.deps import get_job_service

router = APIRouter()
JobServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    service: JobServiceDep,
    status_filter: Optional[JobStatus] = None, 
    skip: int = 0, 
    limit: int = 100
) -> list[JobResponse]:
    jobs = await service.list_jobs(status=status_filter, skip=skip, limit=limit)
    return [JobResponse.model_validate(j) for j in jobs]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    service: JobServiceDep
) -> JobResponse:
    job = await service.create_job(data)
    await service.repo.session.commit()
    await service.repo.session.refresh(job)
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    service: JobServiceDep
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
    service: JobServiceDep
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
    service: JobServiceDep
) -> dict:
    cancelled = await service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} cannot be cancelled",
        )
    await service.repo.session.commit()
    return {"message": f"Job {job_id} cancelled"}
