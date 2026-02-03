from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_document_service, get_job_service
from backend.app.config import get_settings
from backend.app.domains.document.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentVersionResponse,
)
from backend.app.domains.document.service import DocumentService
from backend.app.domains.job.schemas import GenerateJobCreate
from backend.app.domains.job.service import JobService
from backend.app.infrastructure.redis import get_redis_client

router = APIRouter()
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    service: DocumentServiceDep,
    job_service: JobServiceDep,
) -> DocumentResponse:
    pipeline_status = await job_service.get_pipeline_status(data.template_version_id)
    if pipeline_status.has_failed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template version {data.template_version_id} pipeline has failed. "
            f"Current stage: {pipeline_status.current_stage}",
        )

    if pipeline_status.current_stage not in {"READY_FOR_GENERATE", "GENERATE", "COMPLETE"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template version {data.template_version_id} is not ready for document generation. "
            f"Current stage: {pipeline_status.current_stage}",
        )

    doc = await service.create_document(data)

    generate_job = await job_service.create_generate_job(
        GenerateJobCreate(
            template_version_id=data.template_version_id,
            document_id=doc.id,
        )
    )

    await service.repo.session.commit()
    await service.repo.session.refresh(doc)

    try:
        settings = get_settings()
        redis_client = get_redis_client(settings.redis_url)
        redis_client.notify_job_created(generate_job.id, generate_job.job_type.value)
    except Exception:
        pass

    return cast(DocumentResponse, DocumentResponse.model_validate(doc))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    service: DocumentServiceDep,
) -> DocumentResponse:
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return cast(DocumentResponse, DocumentResponse.model_validate(doc))


@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    service: DocumentServiceDep,
) -> list[DocumentVersionResponse]:
    versions = await service.repo.list_versions(document_id)
    return [DocumentVersionResponse.model_validate(v) for v in versions]


@router.get("/{document_id}/versions/{version_number}", response_model=DocumentVersionResponse)
async def get_document_version(
    document_id: UUID,
    version_number: int,
    service: DocumentServiceDep,
) -> DocumentVersionResponse:
    version = await service.repo.get_version(document_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for document {document_id}",
        )
    return cast(DocumentVersionResponse, DocumentVersionResponse.model_validate(version))
