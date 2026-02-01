from typing import Optional
from uuid import UUID
from backend.app.domains.document.models import Document, DocumentStatus
from backend.app.domains.document.schemas import DocumentCreate


class DocumentService:
    async def get_document(self, document_id: UUID) -> Optional[Document]:
        return None

    async def list_documents(self, skip: int = 0, limit: int = 100) -> list[Document]:
        return []

    async def create_document(self, data: DocumentCreate) -> Document:
        return Document(
            name=data.name,
            content_type=data.content_type,
            status=DocumentStatus.PENDING,
        )

    async def get_document_status(self, document_id: UUID) -> Optional[Document]:
        return None

    async def delete_document(self, document_id: UUID) -> bool:
        return False
