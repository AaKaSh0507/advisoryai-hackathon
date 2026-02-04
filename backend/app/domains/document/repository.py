import uuid
from typing import Optional, Sequence, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.document.models import Document, DocumentVersion


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_all(self) -> Sequence[Document]:
        """List all documents ordered by creation date descending."""
        stmt = select(Document).order_by(Document.created_at.desc())
        result = await self.session.execute(stmt)
        return cast(Sequence[Document], result.scalars().all())

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        return cast(Optional[Document], result.scalar_one_or_none())

    async def create_version(self, version: DocumentVersion) -> DocumentVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_version(
        self, document_id: uuid.UUID, version_number: int
    ) -> Optional[DocumentVersion]:
        stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number,
        )
        result = await self.session.execute(stmt)
        return cast(Optional[DocumentVersion], result.scalar_one_or_none())

    async def get_latest_version(self, document_id: uuid.UUID) -> Optional[DocumentVersion]:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return cast(Optional[DocumentVersion], result.scalar_one_or_none())

    async def list_versions(self, document_id: uuid.UUID) -> Sequence[DocumentVersion]:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await self.session.execute(stmt)
        return cast(Sequence[DocumentVersion], result.scalars().all())
