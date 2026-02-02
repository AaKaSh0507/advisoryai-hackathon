from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.domains.generation.errors import ImmutabilityViolationError
from backend.app.domains.generation.models import (
    GenerationInput,
    GenerationInputBatch,
    GenerationInputStatus,
)


class GenerationInputRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, batch: GenerationInputBatch) -> GenerationInputBatch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def create_inputs(self, inputs: list[GenerationInput]) -> list[GenerationInput]:
        self.session.add_all(inputs)
        await self.session.flush()
        return inputs

    async def get_batch_by_id(
        self, batch_id: UUID, include_inputs: bool = True
    ) -> GenerationInputBatch | None:
        if include_inputs:
            stmt = (
                select(GenerationInputBatch)
                .options(selectinload(GenerationInputBatch.inputs))
                .where(GenerationInputBatch.id == batch_id)
            )
        else:
            stmt = select(GenerationInputBatch).where(GenerationInputBatch.id == batch_id)

        result = await self.session.execute(stmt)
        batch: GenerationInputBatch | None = result.scalar_one_or_none()
        return batch

    async def get_batch_by_document_version(
        self,
        document_id: UUID,
        version_intent: int,
        include_inputs: bool = True,
    ) -> GenerationInputBatch | None:
        if include_inputs:
            stmt = (
                select(GenerationInputBatch)
                .options(selectinload(GenerationInputBatch.inputs))
                .where(
                    GenerationInputBatch.document_id == document_id,
                    GenerationInputBatch.version_intent == version_intent,
                )
            )
        else:
            stmt = select(GenerationInputBatch).where(
                GenerationInputBatch.document_id == document_id,
                GenerationInputBatch.version_intent == version_intent,
            )

        result = await self.session.execute(stmt)
        batch: GenerationInputBatch | None = result.scalar_one_or_none()
        return batch

    async def get_batches_by_document(self, document_id: UUID) -> Sequence[GenerationInputBatch]:
        stmt = (
            select(GenerationInputBatch)
            .where(GenerationInputBatch.document_id == document_id)
            .order_by(GenerationInputBatch.version_intent.desc())
        )
        result = await self.session.execute(stmt)
        batches: Sequence[GenerationInputBatch] = result.scalars().all()
        return batches

    async def get_inputs_by_batch(self, batch_id: UUID) -> Sequence[GenerationInput]:
        stmt = (
            select(GenerationInput)
            .where(GenerationInput.batch_id == batch_id)
            .order_by(GenerationInput.sequence_order)
        )
        result = await self.session.execute(stmt)
        inputs: Sequence[GenerationInput] = result.scalars().all()
        return inputs

    async def mark_batch_validated(
        self, batch_id: UUID, validated_at: "datetime"
    ) -> GenerationInputBatch | None:
        batch = await self.get_batch_by_id(batch_id, include_inputs=False)
        if not batch:
            return None

        if batch.is_immutable:
            raise ImmutabilityViolationError(batch_id, "re-validate")

        batch.status = GenerationInputStatus.VALIDATED
        batch.validated_at = validated_at
        batch.is_immutable = True
        await self.session.flush()
        return batch

    async def mark_batch_failed(
        self, batch_id: UUID, error_message: str
    ) -> GenerationInputBatch | None:
        batch = await self.get_batch_by_id(batch_id, include_inputs=False)
        if not batch:
            return None

        if batch.is_immutable:
            raise ImmutabilityViolationError(batch_id, "mark as failed")

        batch.status = GenerationInputStatus.FAILED
        batch.error_message = error_message
        await self.session.flush()
        return batch

    async def batch_exists(self, document_id: UUID, version_intent: int) -> bool:
        batch = await self.get_batch_by_document_version(
            document_id, version_intent, include_inputs=False
        )
        return batch is not None

    async def get_validated_batch(
        self, document_id: UUID, version_intent: int
    ) -> GenerationInputBatch | None:
        batch = await self.get_batch_by_document_version(
            document_id, version_intent, include_inputs=True
        )
        if batch and batch.is_validated and batch.is_immutable:
            return batch
        return None
