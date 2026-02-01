from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Depends
from backend.app.domains.document.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentVersionResponse,
)
from backend.app.domains.document.service import DocumentService
from backend.app.api.deps import get_document_service

router = APIRouter()
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    service: DocumentServiceDep
) -> DocumentResponse:
    doc = await service.create_document(data)
    await service.repo.session.commit()
    await service.repo.session.refresh(doc)
    return DocumentResponse.model_validate(doc)

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    service: DocumentServiceDep
) -> DocumentResponse:
    doc = await service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentResponse.model_validate(doc)

@router.get("/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    service: DocumentServiceDep
) -> list[DocumentVersionResponse]:
    versions = await service.repo.list_versions(document_id)
    return [DocumentVersionResponse.model_validate(v) for v in versions]

@router.get("/{document_id}/versions/{version_number}", response_model=DocumentVersionResponse)
async def get_document_version(
    document_id: UUID,
    version_number: int,
    service: DocumentServiceDep
) -> DocumentVersionResponse:
    version = await service.repo.get_version(document_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for document {document_id}",
        )
    return DocumentVersionResponse.model_validate(version)
