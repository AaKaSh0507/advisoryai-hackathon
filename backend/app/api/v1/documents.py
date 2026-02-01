from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from backend.app.domains.document.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentStatusResponse,
)
from backend.app.domains.document.service import DocumentService

router = APIRouter()
service = DocumentService()


@router.get("", response_model=list[DocumentResponse])
async def list_documents(skip: int = 0, limit: int = 100) -> list[DocumentResponse]:
    documents = await service.list_documents(skip=skip, limit=limit)
    return [DocumentResponse.model_validate(d) for d in documents]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(data: DocumentCreate) -> DocumentResponse:
    document = await service.create_document(data)
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID) -> DocumentResponse:
    document = await service.get_document(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: UUID) -> DocumentStatusResponse:
    document = await service.get_document_status(document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentStatusResponse(
        id=document.id,
        name=document.name,
        status=document.status,
        error_message=document.error_message,
        updated_at=document.updated_at,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID) -> None:
    deleted = await service.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
