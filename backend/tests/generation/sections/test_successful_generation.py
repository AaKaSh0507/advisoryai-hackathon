from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.domains.generation.llm_client import MockLLMClient
from backend.app.domains.generation.models import GenerationInputBatch
from backend.app.domains.generation.section_output_models import SectionGenerationStatus
from backend.app.domains.generation.section_output_schemas import ExecuteSectionGenerationRequest
from backend.app.domains.generation.section_output_service import SectionGenerationService


class TestSuccessfulGeneration:
    @pytest.mark.asyncio
    async def test_generated_content_exists_for_each_dynamic_section(
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

        created_batch = None
        created_outputs = []

        def capture_batch(batch):
            nonlocal created_batch
            batch.id = uuid4()
            created_batch = batch
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            created_outputs.extend(outputs)
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        completed_outputs = []

        async def track_completion(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            completed_outputs.append(
                {
                    "output_id": output_id,
                    "content": generated_content,
                    "length": content_length,
                }
            )
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=track_completion)

        def build_final_batch(*args, **kwargs):
            final_batch = MagicMock()
            final_batch.id = created_batch.id
            final_batch.input_batch_id = sample_input_batch_with_inputs.id
            final_batch.document_id = sample_input_batch_with_inputs.document_id
            final_batch.version_intent = sample_input_batch_with_inputs.version_intent
            final_batch.status = SectionGenerationStatus.COMPLETED
            final_batch.total_sections = 3
            final_batch.completed_sections = 3
            final_batch.failed_sections = 0
            final_batch.is_immutable = True
            final_batch.created_at = datetime.utcnow()
            final_batch.completed_at = datetime.utcnow()
            final_batch.outputs = [
                MagicMock(
                    id=out.id,
                    batch_id=created_batch.id,
                    generation_input_id=out.generation_input_id,
                    section_id=out.section_id,
                    sequence_order=out.sequence_order,
                    status=SectionGenerationStatus.COMPLETED,
                    generated_content="This is generated content for the advisory section.",
                    content_length=50,
                    content_hash="somehash",
                    error_message=None,
                    error_code=None,
                    generation_metadata={},
                    is_immutable=True,
                    created_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                )
                for out in created_outputs
            ]
            return final_batch

        mock_output_repository.get_batch_by_id = AsyncMock(side_effect=build_final_batch)

        response = await generation_service.execute_section_generation(execute_request)

        assert response.total_sections == 3
        assert response.completed_sections == 3
        assert len(completed_outputs) == 3
        for completed in completed_outputs:
            assert completed["content"] is not None
            assert completed["length"] > 0

    @pytest.mark.asyncio
    async def test_content_persisted_correctly(
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

        created_batch = MagicMock()
        created_batch.id = uuid4()
        mock_output_repository.create_batch = AsyncMock(return_value=created_batch)

        persisted_data = []

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)

        async def capture_persistence(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            persisted_data.append(
                {
                    "output_id": output_id,
                    "content": generated_content,
                    "length": content_length,
                    "hash": content_hash,
                    "metadata": metadata,
                }
            )
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=capture_persistence)

        final_batch = MagicMock()
        final_batch.id = created_batch.id
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

        assert len(persisted_data) == 3
        for data in persisted_data:
            assert data["content"] is not None
            assert data["length"] > 0
            assert data["hash"] is not None
            assert len(data["hash"]) == 64

    @pytest.mark.asyncio
    async def test_content_associated_with_correct_section(
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
        final_batch.outputs = [
            MagicMock(
                id=out.id,
                batch_id=final_batch.id,
                generation_input_id=out.generation_input_id,
                section_id=out.section_id,
                sequence_order=out.sequence_order,
                status=SectionGenerationStatus.COMPLETED,
                generated_content="Generated content",
                content_length=17,
                content_hash="hash",
                error_message=None,
                error_code=None,
                generation_metadata={},
                is_immutable=True,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            for out in created_outputs
        ]
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        await generation_service.execute_section_generation(execute_request)

        expected_section_ids = {1, 2, 3}
        actual_section_ids = {out.section_id for out in created_outputs}
        assert actual_section_ids == expected_section_ids

        for out in created_outputs:
            matching_inputs = [
                inp
                for inp in sample_input_batch_with_inputs.inputs
                if inp.section_id == out.section_id
            ]
            assert len(matching_inputs) == 1
            assert out.generation_input_id == matching_inputs[0].id

    @pytest.mark.asyncio
    async def test_llm_invoked_once_per_section(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        execute_request: ExecuteSectionGenerationRequest,
    ):
        llm_client = MockLLMClient(default_response="Generated content")

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

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

        await service.execute_section_generation(execute_request)

        assert llm_client.invocation_count == 3
        invoked_section_ids = {inv.section_id for inv in llm_client.invocations}
        assert invoked_section_ids == {1, 2, 3}
