from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from backend.app.domains.job.models import JobStatus
from backend.app.domains.job.schemas import (
    JobCreate,
    JobResponse,
    JobStatusResponse,
)
from backend.app.domains.job.service import JobService

router = APIRouter()
service = JobService()


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status_filter: Optional[JobStatus] = None, skip: int = 0, limit: int = 100
) -> list[JobResponse]:
    jobs = await service.list_jobs(status=status_filter, skip=skip, limit=limit)
    return [JobResponse.model_validate(j) for j in jobs]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(data: JobCreate) -> JobResponse:
    job = await service.create_job(data)
    return JobResponse.model_validate(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID) -> JobResponse:
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return JobResponse.model_validate(job)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: UUID) -> JobStatusResponse:
    job = await service.get_job_status(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job(job_id: UUID) -> dict:
    cancelled = await service.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} cannot be cancelled",
        )
    return {"message": f"Job {job_id} cancelled"}
