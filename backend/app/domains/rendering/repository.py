from datetime import datetime
from typing import Sequence, cast
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.rendering.models import RenderedDocument, RenderStatus
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.rendering.repository")


class RenderedDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        assembled_document_id: UUID,
        document_id: UUID,
        version: int,
    ) -> RenderedDocument:
        rendered_doc = RenderedDocument(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=version,
            status=RenderStatus.PENDING,
        )
        self.session.add(rendered_doc)
        await self.session.flush()
        logger.info(f"Created rendered document {rendered_doc.id}")
        return rendered_doc

    async def get_by_id(self, rendered_doc_id: UUID) -> RenderedDocument | None:
        stmt = select(RenderedDocument).where(RenderedDocument.id == rendered_doc_id)
        result = await self.session.execute(stmt)
        return cast(RenderedDocument | None, result.scalar_one_or_none())

    async def get_by_assembled_document(
        self, assembled_document_id: UUID
    ) -> RenderedDocument | None:
        stmt = select(RenderedDocument).where(
            RenderedDocument.assembled_document_id == assembled_document_id
        )
        result = await self.session.execute(stmt)
        return cast(RenderedDocument | None, result.scalar_one_or_none())

    async def get_by_document_and_version(
        self, document_id: UUID, version: int
    ) -> RenderedDocument | None:
        stmt = select(RenderedDocument).where(
            and_(
                RenderedDocument.document_id == document_id,
                RenderedDocument.version == version,
            )
        )
        result = await self.session.execute(stmt)
        return cast(RenderedDocument | None, result.scalar_one_or_none())

    async def get_by_content_hash(self, content_hash: str) -> RenderedDocument | None:
        stmt = select(RenderedDocument).where(RenderedDocument.content_hash == content_hash)
        result = await self.session.execute(stmt)
        return cast(RenderedDocument | None, result.scalar_one_or_none())

    async def get_validated_by_document(self, document_id: UUID) -> Sequence[RenderedDocument]:
        stmt = (
            select(RenderedDocument)
            .where(
                and_(
                    RenderedDocument.document_id == document_id,
                    RenderedDocument.status == RenderStatus.VALIDATED,
                    RenderedDocument.is_immutable.is_(True),
                )
            )
            .order_by(RenderedDocument.version.desc())
        )
        result = await self.session.execute(stmt)
        return cast(Sequence[RenderedDocument], result.scalars().all())

    async def get_latest_by_document(self, document_id: UUID) -> RenderedDocument | None:
        stmt = (
            select(RenderedDocument)
            .where(RenderedDocument.document_id == document_id)
            .order_by(RenderedDocument.version.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return cast(RenderedDocument | None, result.scalar_one_or_none())

    async def exists_for_assembled_document(self, assembled_document_id: UUID) -> bool:
        stmt = select(RenderedDocument.id).where(
            RenderedDocument.assembled_document_id == assembled_document_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_in_progress(self, rendered_doc: RenderedDocument) -> RenderedDocument:
        rendered_doc.status = RenderStatus.IN_PROGRESS
        await self.session.flush()
        logger.info(f"Marked rendered document {rendered_doc.id} as in progress")
        return rendered_doc

    async def mark_completed(
        self,
        rendered_doc: RenderedDocument,
        output_path: str,
        content_hash: str,
        file_size_bytes: int,
        total_blocks: int,
        paragraphs: int,
        tables: int,
        lists: int,
        headings: int,
        headers: int,
        footers: int,
        rendering_duration_ms: float,
    ) -> RenderedDocument:
        rendered_doc.status = RenderStatus.COMPLETED
        rendered_doc.output_path = output_path
        rendered_doc.content_hash = content_hash
        rendered_doc.file_size_bytes = file_size_bytes
        rendered_doc.total_blocks_rendered = total_blocks
        rendered_doc.paragraphs_rendered = paragraphs
        rendered_doc.tables_rendered = tables
        rendered_doc.lists_rendered = lists
        rendered_doc.headings_rendered = headings
        rendered_doc.headers_rendered = headers
        rendered_doc.footers_rendered = footers
        rendered_doc.rendering_duration_ms = rendering_duration_ms
        rendered_doc.rendered_at = datetime.utcnow()
        await self.session.flush()
        logger.info(f"Marked rendered document {rendered_doc.id} as completed")
        return rendered_doc

    async def mark_validated(
        self,
        rendered_doc: RenderedDocument,
        validation_result: dict,
    ) -> RenderedDocument:
        rendered_doc.status = RenderStatus.VALIDATED
        rendered_doc.validation_result = validation_result
        rendered_doc.is_immutable = True
        rendered_doc.validated_at = datetime.utcnow()
        await self.session.flush()
        logger.info(f"Marked rendered document {rendered_doc.id} as validated and immutable")
        return rendered_doc

    async def mark_failed(
        self,
        rendered_doc: RenderedDocument,
        error_code: str,
        error_message: str,
    ) -> RenderedDocument:
        rendered_doc.status = RenderStatus.FAILED
        rendered_doc.error_code = error_code
        rendered_doc.error_message = error_message
        await self.session.flush()
        logger.info(f"Marked rendered document {rendered_doc.id} as failed: {error_code}")
        return rendered_doc

    async def update_rendering_metadata(
        self,
        rendered_doc: RenderedDocument,
        metadata: dict,
    ) -> RenderedDocument:
        rendered_doc.rendering_metadata = metadata
        await self.session.flush()
        return rendered_doc

    async def list_by_status(self, status: RenderStatus) -> Sequence[RenderedDocument]:
        stmt = (
            select(RenderedDocument)
            .where(RenderedDocument.status == status)
            .order_by(RenderedDocument.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return cast(Sequence[RenderedDocument], result.scalars().all())

    async def delete(self, rendered_doc_id: UUID) -> bool:
        rendered_doc = await self.get_by_id(rendered_doc_id)
        if rendered_doc and not rendered_doc.is_immutable:
            await self.session.delete(rendered_doc)
            await self.session.flush()
            logger.info(f"Deleted rendered document {rendered_doc_id}")
            return True
        return False
