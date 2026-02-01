from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from backend.app.domains.document.models import Document


class DocumentRepository(ABC):
    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Optional[Document]:
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Document]:
        ...

    @abstractmethod
    async def create(self, document: Document) -> Document:
        ...

    @abstractmethod
    async def update(self, document: Document) -> Document:
        ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> bool:
        ...
