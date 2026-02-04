from typing import Any, Sequence, cast
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.assembly.models import AssembledDocument, AssemblyStatus
from backend.app.infrastructure.datetime_utils import utc_now
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.assembly.repository")


class AssembledDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document_id: UUID,
        template_version_id: UUID,
        version_intent: int,
        section_output_batch_id: UUID,
        assembly_hash: str,
    ) -> AssembledDocument:
        assembled_doc = AssembledDocument(
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=version_intent,
            section_output_batch_id=section_output_batch_id,
            assembly_hash=assembly_hash,
            status=AssemblyStatus.PENDING,
        )
        self.session.add(assembled_doc)
        await self.session.flush()
        logger.info(f"Created assembled document {assembled_doc.id}")
        return assembled_doc

    async def get_by_id(self, assembled_doc_id: UUID) -> AssembledDocument | None:
        stmt = select(AssembledDocument).where(AssembledDocument.id == assembled_doc_id)
        result = await self.session.execute(stmt)
        return cast(AssembledDocument | None, result.scalar_one_or_none())

    async def get_by_document_and_version(
        self, document_id: UUID, version_intent: int
    ) -> AssembledDocument | None:
        stmt = select(AssembledDocument).where(
            and_(
                AssembledDocument.document_id == document_id,
                AssembledDocument.version_intent == version_intent,
            )
        )
        result = await self.session.execute(stmt)
        return cast(AssembledDocument | None, result.scalar_one_or_none())

    async def get_by_section_output_batch(
        self, section_output_batch_id: UUID
    ) -> AssembledDocument | None:
        stmt = select(AssembledDocument).where(
            AssembledDocument.section_output_batch_id == section_output_batch_id
        )
        result = await self.session.execute(stmt)
        return cast(AssembledDocument | None, result.scalar_one_or_none())

    async def get_by_assembly_hash(self, assembly_hash: str) -> AssembledDocument | None:
        stmt = select(AssembledDocument).where(AssembledDocument.assembly_hash == assembly_hash)
        result = await self.session.execute(stmt)
        return cast(AssembledDocument | None, result.scalar_one_or_none())

    async def get_validated_by_document(self, document_id: UUID) -> Sequence[AssembledDocument]:
        stmt = (
            select(AssembledDocument)
            .where(
                and_(
                    AssembledDocument.document_id == document_id,
                    AssembledDocument.status == AssemblyStatus.VALIDATED,
                    AssembledDocument.is_immutable.is_(True),
                )
            )
            .order_by(AssembledDocument.version_intent.desc())
        )
        result = await self.session.execute(stmt)
        return cast(Sequence[AssembledDocument], result.scalars().all())

    async def mark_in_progress(self, assembled_doc_id: UUID) -> AssembledDocument | None:
        assembled_doc = await self.get_by_id(assembled_doc_id)
        if not assembled_doc:
            return None
        if assembled_doc.is_immutable:
            logger.warning(f"Cannot modify immutable assembled document {assembled_doc_id}")
            return assembled_doc
        assembled_doc.status = AssemblyStatus.IN_PROGRESS
        await self.session.flush()
        return assembled_doc

    async def mark_completed(
        self,
        assembled_doc_id: UUID,
        assembled_structure: dict[str, Any],
        injection_results: list[dict[str, Any]],
        validation_result: dict[str, Any],
        metadata: dict[str, Any],
        headers: list[dict[str, Any]],
        footers: list[dict[str, Any]],
        total_blocks: int,
        dynamic_blocks_count: int,
        static_blocks_count: int,
        injected_sections_count: int,
        assembly_duration_ms: float,
        assembly_hash: str,
    ) -> AssembledDocument | None:
        assembled_doc = await self.get_by_id(assembled_doc_id)
        if not assembled_doc:
            return None
        if assembled_doc.is_immutable:
            logger.warning(f"Cannot modify immutable assembled document {assembled_doc_id}")
            return assembled_doc

        assembled_doc.status = AssemblyStatus.COMPLETED
        assembled_doc.assembled_structure = assembled_structure
        assembled_doc.injection_results = {"results": injection_results}
        assembled_doc.validation_result = validation_result
        assembled_doc.document_metadata = metadata
        assembled_doc.headers = headers
        assembled_doc.footers = footers
        assembled_doc.total_blocks = total_blocks
        assembled_doc.dynamic_blocks_count = dynamic_blocks_count
        assembled_doc.static_blocks_count = static_blocks_count
        assembled_doc.injected_sections_count = injected_sections_count
        assembled_doc.assembly_duration_ms = assembly_duration_ms
        assembled_doc.assembly_hash = assembly_hash
        assembled_doc.assembled_at = utc_now()
        await self.session.flush()
        logger.info(f"Marked assembled document {assembled_doc_id} as completed")
        return assembled_doc

    async def mark_validated(self, assembled_doc_id: UUID) -> AssembledDocument | None:
        assembled_doc = await self.get_by_id(assembled_doc_id)
        if not assembled_doc:
            return None
        if assembled_doc.is_immutable:
            logger.warning(f"Cannot modify immutable assembled document {assembled_doc_id}")
            return assembled_doc

        assembled_doc.status = AssemblyStatus.VALIDATED
        assembled_doc.is_immutable = True
        assembled_doc.validated_at = utc_now()
        await self.session.flush()
        logger.info(f"Marked assembled document {assembled_doc_id} as validated and immutable")
        return assembled_doc

    async def mark_failed(
        self,
        assembled_doc_id: UUID,
        error_code: str,
        error_message: str,
    ) -> AssembledDocument | None:
        assembled_doc = await self.get_by_id(assembled_doc_id)
        if not assembled_doc:
            return None
        if assembled_doc.is_immutable:
            logger.warning(f"Cannot modify immutable assembled document {assembled_doc_id}")
            return assembled_doc

        assembled_doc.status = AssemblyStatus.FAILED
        assembled_doc.error_code = error_code
        assembled_doc.error_message = error_message
        await self.session.flush()
        logger.info(f"Marked assembled document {assembled_doc_id} as failed: {error_code}")
        return assembled_doc

    async def update_assembly_hash(
        self, assembled_doc_id: UUID, assembly_hash: str
    ) -> AssembledDocument | None:
        assembled_doc = await self.get_by_id(assembled_doc_id)
        if not assembled_doc:
            return None
        if assembled_doc.is_immutable:
            return assembled_doc
        assembled_doc.assembly_hash = assembly_hash
        await self.session.flush()
        return assembled_doc

    async def get_latest_by_document(self, document_id: UUID) -> AssembledDocument | None:
        stmt = (
            select(AssembledDocument)
            .where(AssembledDocument.document_id == document_id)
            .order_by(AssembledDocument.version_intent.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return cast(AssembledDocument | None, result.scalar_one_or_none())

    async def exists_for_batch(self, section_output_batch_id: UUID) -> bool:
        stmt = select(AssembledDocument.id).where(
            AssembledDocument.section_output_batch_id == section_output_batch_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete(self, assembled_doc_id: UUID) -> bool:
        assembled_doc = await self.get_by_id(assembled_doc_id)
        if not assembled_doc:
            return False
        if assembled_doc.is_immutable:
            logger.warning(f"Cannot delete immutable assembled document {assembled_doc_id}")
            return False
        await self.session.delete(assembled_doc)
        await self.session.flush()
        logger.info(f"Deleted assembled document {assembled_doc_id}")
        return True

    async def count_by_document(self, document_id: UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).where(AssembledDocument.document_id == document_id)
        result = await self.session.execute(stmt)
        count = result.scalar()
        return int(count) if count else 0

    async def get_renderable_document(
        self, document_id: UUID, version_intent: int
    ) -> AssembledDocument | None:
        stmt = select(AssembledDocument).where(
            and_(
                AssembledDocument.document_id == document_id,
                AssembledDocument.version_intent == version_intent,
                AssembledDocument.status == AssemblyStatus.VALIDATED,
                AssembledDocument.is_immutable.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return cast(AssembledDocument | None, result.scalar_one_or_none())
