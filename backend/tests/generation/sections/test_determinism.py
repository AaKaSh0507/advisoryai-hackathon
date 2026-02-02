from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.generation.llm_client import DeterministicLLMClient, MockLLMClient
from backend.app.domains.generation.models import GenerationInputBatch
from backend.app.domains.generation.section_output_models import SectionGenerationStatus
from backend.app.domains.generation.section_output_schemas import (
    ContentConstraints,
    ExecuteSectionGenerationRequest,
    LLMInvocationRequest,
)
from backend.app.domains.generation.section_output_service import SectionGenerationService


class TestDeterminism:
    @pytest.mark.asyncio
    async def test_same_inputs_produce_equivalent_outputs(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        def deterministic_response(request: LLMInvocationRequest) -> str:
            return f"Deterministic content for section {request.section_id} with path from prompt"

        llm_client = DeterministicLLMClient(response_generator=deterministic_response)

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )

        first_run_content = {}
        second_run_content = {}

        async def capture_first_run(
            output_id, generated_content, content_length, content_hash, metadata, completed_at
        ):
            section_id = metadata.get("structural_path", "").split("/")[-1]
            first_run_content[section_id] = {
                "content": generated_content,
                "hash": content_hash,
            }
            return MagicMock()

        async def capture_second_run(
            output_id, generated_content, content_length, content_hash, metadata, completed_at
        ):
            section_id = metadata.get("structural_path", "").split("/")[-1]
            second_run_content[section_id] = {
                "content": generated_content,
                "hash": content_hash,
            }
            return MagicMock()

        def setup_mocks_for_run(content_tracker):
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
            mock_output_repository.update_output_content = AsyncMock(side_effect=content_tracker)
            mock_output_repository.mark_output_failed = AsyncMock(return_value=MagicMock())

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

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        setup_mocks_for_run(capture_first_run)
        await service.execute_section_generation(request)

        setup_mocks_for_run(capture_second_run)
        await service.execute_section_generation(request)

        assert len(first_run_content) == len(second_run_content)
        for key in first_run_content:
            assert first_run_content[key]["content"] == second_run_content[key]["content"]
            assert first_run_content[key]["hash"] == second_run_content[key]["hash"]

    @pytest.mark.asyncio
    async def test_content_hash_deterministic_for_same_content(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        fixed_content = "This is exactly the same content every time."
        llm_client = MockLLMClient(default_response=fixed_content)

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        captured_hashes = []

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        async def capture_hash(
            output_id, generated_content, content_length, content_hash, metadata, completed_at
        ):
            captured_hashes.append(content_hash)
            return MagicMock()

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)
        mock_output_repository.update_output_content = AsyncMock(side_effect=capture_hash)

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

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        await service.execute_section_generation(request)

        assert len(captured_hashes) == 3
        assert all(h == captured_hashes[0] for h in captured_hashes)


class TestNoDuplication:
    @pytest.mark.asyncio
    async def test_rerun_rejected_when_output_batch_exists(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        from backend.app.domains.generation.section_output_errors import DuplicateOutputBatchError

        llm_client = MockLLMClient(default_response="Content")

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )

        existing_batch = MagicMock()
        existing_batch.id = uuid4()
        existing_batch.input_batch_id = fixed_input_batch_id
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=existing_batch)

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        with pytest.raises(DuplicateOutputBatchError):
            await service.execute_section_generation(request)

    @pytest.mark.asyncio
    async def test_outputs_tied_to_unique_generation_input_ids(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(default_response="Content")

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

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
        mock_output_repository.update_output_content = AsyncMock(return_value=MagicMock())

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

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        await service.execute_section_generation(request)

        generation_input_ids = [out.generation_input_id for out in created_outputs]
        assert len(generation_input_ids) == len(set(generation_input_ids))

        expected_input_ids = {inp.id for inp in sample_input_batch_with_inputs.inputs}
        actual_input_ids = set(generation_input_ids)
        assert actual_input_ids == expected_input_ids

    @pytest.mark.asyncio
    async def test_sequence_order_preserved(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(default_response="Content")

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

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
        mock_output_repository.update_output_content = AsyncMock(return_value=MagicMock())

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

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        await service.execute_section_generation(request)

        sequence_orders = [out.sequence_order for out in created_outputs]
        assert sequence_orders == sorted(sequence_orders)
        assert sequence_orders == list(range(len(created_outputs)))
