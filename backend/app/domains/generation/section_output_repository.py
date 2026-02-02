from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.domains.generation.section_output_errors import OutputImmutabilityViolationError
from backend.app.domains.generation.section_output_models import (
    SectionGenerationStatus,
    SectionOutput,
    SectionOutputBatch,
)


class SectionOutputRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, batch: SectionOutputBatch) -> SectionOutputBatch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def create_output(self, output: SectionOutput) -> SectionOutput:
        self.session.add(output)
        await self.session.flush()
        return output

    async def create_outputs(self, outputs: list[SectionOutput]) -> list[SectionOutput]:
        self.session.add_all(outputs)
        await self.session.flush()
        return outputs

    async def get_batch_by_id(
        self, batch_id: UUID, include_outputs: bool = True
    ) -> SectionOutputBatch | None:
        if include_outputs:
            stmt = (
                select(SectionOutputBatch)
                .options(selectinload(SectionOutputBatch.outputs))
                .where(SectionOutputBatch.id == batch_id)
            )
        else:
            stmt = select(SectionOutputBatch).where(SectionOutputBatch.id == batch_id)

        result = await self.session.execute(stmt)
        batch: SectionOutputBatch | None = result.scalar_one_or_none()
        return batch

    async def get_batch_by_input_batch_id(
        self, input_batch_id: UUID, include_outputs: bool = True
    ) -> SectionOutputBatch | None:
        if include_outputs:
            stmt = (
                select(SectionOutputBatch)
                .options(selectinload(SectionOutputBatch.outputs))
                .where(SectionOutputBatch.input_batch_id == input_batch_id)
            )
        else:
            stmt = select(SectionOutputBatch).where(
                SectionOutputBatch.input_batch_id == input_batch_id
            )

        result = await self.session.execute(stmt)
        batch: SectionOutputBatch | None = result.scalar_one_or_none()
        return batch

    async def get_batch_by_document_version(
        self,
        document_id: UUID,
        version_intent: int,
        include_outputs: bool = True,
    ) -> SectionOutputBatch | None:
        if include_outputs:
            stmt = (
                select(SectionOutputBatch)
                .options(selectinload(SectionOutputBatch.outputs))
                .where(
                    SectionOutputBatch.document_id == document_id,
                    SectionOutputBatch.version_intent == version_intent,
                )
            )
        else:
            stmt = select(SectionOutputBatch).where(
                SectionOutputBatch.document_id == document_id,
                SectionOutputBatch.version_intent == version_intent,
            )

        result = await self.session.execute(stmt)
        batch: SectionOutputBatch | None = result.scalar_one_or_none()
        return batch

    async def get_output_by_id(self, output_id: UUID) -> SectionOutput | None:
        stmt = select(SectionOutput).where(SectionOutput.id == output_id)
        result = await self.session.execute(stmt)
        output: SectionOutput | None = result.scalar_one_or_none()
        return output

    async def get_output_by_generation_input_id(
        self, generation_input_id: UUID
    ) -> SectionOutput | None:
        stmt = select(SectionOutput).where(SectionOutput.generation_input_id == generation_input_id)
        result = await self.session.execute(stmt)
        output: SectionOutput | None = result.scalar_one_or_none()
        return output

    async def get_outputs_by_batch(self, batch_id: UUID) -> Sequence[SectionOutput]:
        stmt = (
            select(SectionOutput)
            .where(SectionOutput.batch_id == batch_id)
            .order_by(SectionOutput.sequence_order)
        )
        result = await self.session.execute(stmt)
        outputs: Sequence[SectionOutput] = result.scalars().all()
        return outputs

    async def get_outputs_by_section_id(self, section_id: int) -> Sequence[SectionOutput]:
        stmt = (
            select(SectionOutput)
            .where(SectionOutput.section_id == section_id)
            .order_by(SectionOutput.created_at.desc())
        )
        result = await self.session.execute(stmt)
        outputs: Sequence[SectionOutput] = result.scalars().all()
        return outputs

    async def update_output_content(
        self,
        output_id: UUID,
        generated_content: str,
        content_length: int,
        content_hash: str,
        metadata: dict,
        completed_at: datetime,
    ) -> SectionOutput | None:
        output = await self.get_output_by_id(output_id)
        if not output:
            return None

        if output.is_immutable:
            raise OutputImmutabilityViolationError(output_id, "update content")

        output.generated_content = generated_content
        output.content_length = content_length
        output.content_hash = content_hash
        output.generation_metadata = metadata
        output.status = SectionGenerationStatus.COMPLETED
        output.completed_at = completed_at
        output.is_immutable = True
        await self.session.flush()
        return output

    async def mark_output_failed(
        self,
        output_id: UUID,
        error_message: str,
        error_code: str,
        metadata: dict,
        completed_at: datetime,
    ) -> SectionOutput | None:
        output = await self.get_output_by_id(output_id)
        if not output:
            return None

        if output.is_immutable:
            raise OutputImmutabilityViolationError(output_id, "mark as failed")

        output.error_message = error_message
        output.error_code = error_code
        output.generation_metadata = metadata
        output.status = SectionGenerationStatus.FAILED
        output.completed_at = completed_at
        output.is_immutable = True
        await self.session.flush()
        return output

    async def update_batch_progress(
        self,
        batch_id: UUID,
        completed_sections: int,
        failed_sections: int,
    ) -> SectionOutputBatch | None:
        batch = await self.get_batch_by_id(batch_id, include_outputs=False)
        if not batch:
            return None

        batch.completed_sections = completed_sections
        batch.failed_sections = failed_sections

        if completed_sections + failed_sections >= batch.total_sections:
            batch.status = SectionGenerationStatus.COMPLETED
            batch.completed_at = datetime.utcnow()
            batch.is_immutable = True

        await self.session.flush()
        return batch

    async def mark_batch_in_progress(self, batch_id: UUID) -> SectionOutputBatch | None:
        batch = await self.get_batch_by_id(batch_id, include_outputs=False)
        if not batch:
            return None

        batch.status = SectionGenerationStatus.IN_PROGRESS
        await self.session.flush()
        return batch

    async def batch_exists_for_input(self, input_batch_id: UUID) -> bool:
        batch = await self.get_batch_by_input_batch_id(input_batch_id, include_outputs=False)
        return batch is not None

    async def output_exists_for_generation_input(self, generation_input_id: UUID) -> bool:
        output = await self.get_output_by_generation_input_id(generation_input_id)
        return output is not None
