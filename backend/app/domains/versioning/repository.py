import uuid
from typing import Optional, Sequence, cast

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.document.models import Document, DocumentVersion


class VersioningRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_document(self, document_id: uuid.UUID) -> Optional[Document]:
        stmt = select(Document).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        return cast(Optional[Document], result.scalar_one_or_none())

    async def get_next_version_number(self, document_id: uuid.UUID) -> int:
        stmt = (
            select(DocumentVersion.version_number)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        latest = result.scalar_one_or_none()
        return (latest + 1) if latest else 1

    async def version_exists(self, document_id: uuid.UUID, version_number: int) -> bool:
        stmt = select(DocumentVersion.id).where(
            and_(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_number,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_version_by_content_hash(
        self, document_id: uuid.UUID, content_hash: str
    ) -> Optional[DocumentVersion]:
        stmt = select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        result = await self.session.execute(stmt)
        versions = result.scalars().all()

        for version in versions:
            if version.generation_metadata.get("content_hash") == content_hash:
                return cast(DocumentVersion, version)
        return None

    async def create_version(
        self,
        document_id: uuid.UUID,
        version_number: int,
        output_path: str,
        generation_metadata: dict,
    ) -> DocumentVersion:
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            output_doc_path=output_path,
            generation_metadata=generation_metadata,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def update_current_version(self, document: Document, version_number: int) -> Document:
        document.current_version = version_number
        await self.session.flush()
        return document

    async def get_version(
        self, document_id: uuid.UUID, version_number: int
    ) -> Optional[DocumentVersion]:
        stmt = select(DocumentVersion).where(
            and_(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version_number == version_number,
            )
        )
        result = await self.session.execute(stmt)
        return cast(Optional[DocumentVersion], result.scalar_one_or_none())

    async def get_version_by_id(self, version_id: uuid.UUID) -> Optional[DocumentVersion]:
        stmt = select(DocumentVersion).where(DocumentVersion.id == version_id)
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

    async def count_versions(self, document_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_latest_version(self, document_id: uuid.UUID) -> Optional[DocumentVersion]:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return cast(Optional[DocumentVersion], result.scalar_one_or_none())
