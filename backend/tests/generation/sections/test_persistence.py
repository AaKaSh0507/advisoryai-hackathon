from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.domains.generation.models import GenerationInputBatch, GenerationInputStatus
from backend.app.domains.generation.section_output_errors import (
    BatchNotFoundError,
    BatchNotValidatedError,
    DuplicateOutputBatchError,
)
from backend.app.domains.generation.section_output_models import SectionGenerationStatus
from backend.app.domains.generation.section_output_schemas import ExecuteSectionGenerationRequest
from backend.app.domains.generation.section_output_service import SectionGenerationService


class TestPersistence:
    @pytest.mark.asyncio
    async def test_output_batch_created_with_correct_fields(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        created_batch = None

        def capture_batch(batch):
            nonlocal created_batch
            batch.id = uuid4()
            created_batch = batch
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)
        mock_output_repository.mark_output_validated = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 3
        final_batch.failed_sections = 0
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        await generation_service.execute_section_generation(execute_request)

        assert created_batch is not None
        assert created_batch.input_batch_id == sample_input_batch_with_inputs.id
        assert created_batch.document_id == sample_input_batch_with_inputs.document_id
        assert created_batch.version_intent == sample_input_batch_with_inputs.version_intent
        assert created_batch.total_sections == 3

    @pytest.mark.asyncio
    async def test_outputs_created_for_each_input(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        created_outputs = []

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            created_outputs.extend(outputs)
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)
        mock_output_repository.mark_output_validated = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 3
        final_batch.failed_sections = 0
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        await generation_service.execute_section_generation(execute_request)

        assert len(created_outputs) == 3

    @pytest.mark.asyncio
    async def test_content_persisted_with_metadata(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)

        persisted_metadata = []

        async def capture_content(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            persisted_metadata.append(metadata)
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=capture_content)

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 3
        final_batch.failed_sections = 0
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        await generation_service.execute_section_generation(execute_request)

        assert len(persisted_metadata) == 3
        for metadata in persisted_metadata:
            assert "input_hash" in metadata
            assert "structural_path" in metadata
            assert "invocation" in metadata

    @pytest.mark.asyncio
    async def test_batch_progress_updated_correctly(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)
        mock_output_repository.mark_output_validated = AsyncMock(return_value=MagicMock())

        progress_updates = []

        async def track_progress(batch_id, completed_sections, failed_sections):
            progress_updates.append(
                {
                    "completed": completed_sections,
                    "failed": failed_sections,
                }
            )
            return MagicMock()

        mock_output_repository.update_batch_progress = AsyncMock(side_effect=track_progress)

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 3
        final_batch.failed_sections = 0
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        await generation_service.execute_section_generation(execute_request)

        assert len(progress_updates) == 1
        assert progress_updates[0]["completed"] == 3
        assert progress_updates[0]["failed"] == 0


class TestBatchValidation:
    @pytest.mark.asyncio
    async def test_batch_not_found_raises_error(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(return_value=None)

        with pytest.raises(BatchNotFoundError):
            await generation_service.execute_section_generation(execute_request)

    @pytest.mark.asyncio
    async def test_unvalidated_batch_raises_error(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        sample_input_batch_with_inputs.status = GenerationInputStatus.PENDING
        sample_input_batch_with_inputs.is_immutable = False

        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )

        with pytest.raises(BatchNotValidatedError):
            await generation_service.execute_section_generation(execute_request)

    @pytest.mark.asyncio
    async def test_duplicate_output_batch_raises_error(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )

        existing_batch = MagicMock()
        existing_batch.id = uuid4()
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=existing_batch)

        with pytest.raises(DuplicateOutputBatchError):
            await generation_service.execute_section_generation(execute_request)


class TestOutputImmutability:
    @pytest.mark.asyncio
    async def test_completed_outputs_marked_immutable(
        self,
        generation_service: SectionGenerationService,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)

        update_calls = []

        async def track_update(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            update_calls.append(output_id)
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=track_update)

        final_outputs = [
            MagicMock(
                id=uuid4(),
                batch_id=uuid4(),
                generation_input_id=inp.id,
                section_id=inp.section_id,
                sequence_order=inp.sequence_order,
                status=SectionGenerationStatus.COMPLETED,
                generated_content="Content",
                content_length=7,
                content_hash="hash",
                error_message=None,
                error_code=None,
                generation_metadata={},
                is_immutable=True,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            for inp in sample_input_batch_with_inputs.inputs
        ]

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 3
        final_batch.failed_sections = 0
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = final_outputs
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        response = await generation_service.execute_section_generation(execute_request)

        assert len(update_calls) == 3
        for output in response.outputs:
            assert output.is_immutable is True
