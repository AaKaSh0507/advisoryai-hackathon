from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.generation.llm_client import MockLLMClient
from backend.app.domains.generation.models import GenerationInputBatch
from backend.app.domains.generation.section_output_models import SectionGenerationStatus
from backend.app.domains.generation.section_output_schemas import (
    ContentConstraints,
    ExecuteSectionGenerationRequest,
)
from backend.app.domains.generation.section_output_service import SectionGenerationService


class TestFailureIsolation:
    @pytest.mark.asyncio
    async def test_one_section_failure_does_not_block_others(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            default_response="Valid generated content",
            failure_sections=[2],
        )

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

        successful_sections = []
        failed_sections = []

        async def track_success(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            successful_sections.append(output_id)
            return MagicMock()

        async def track_failure(output_id, error_message, error_code, metadata, completed_at):
            failed_sections.append(output_id)
            return MagicMock()

        async def track_retry_exhausted(output_id, error_message, metadata, completed_at):
            failed_sections.append(output_id)
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=track_success)
        mock_output_repository.mark_output_failed = AsyncMock(side_effect=track_failure)
        mock_output_repository.mark_retry_exhausted = AsyncMock(side_effect=track_retry_exhausted)
        mock_output_repository.increment_retry_count = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 2
        final_batch.failed_sections = 1
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        response = await service.execute_section_generation(request)

        assert len(successful_sections) == 2
        assert len(failed_sections) == 1
        assert response.completed_sections == 2
        assert response.failed_sections == 1

    @pytest.mark.asyncio
    async def test_multiple_failures_do_not_cascade(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            default_response="Valid content",
            failure_sections=[1, 3],
        )

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

        successful_count = 0
        failed_count = 0

        async def track_success(*args, **kwargs):
            nonlocal successful_count
            successful_count += 1
            return MagicMock()

        async def track_failure(*args, **kwargs):
            nonlocal failed_count
            failed_count += 1
            return MagicMock()

        async def track_retry_exhausted(*args, **kwargs):
            nonlocal failed_count
            failed_count += 1
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=track_success)
        mock_output_repository.mark_output_failed = AsyncMock(side_effect=track_failure)
        mock_output_repository.mark_retry_exhausted = AsyncMock(side_effect=track_retry_exhausted)
        mock_output_repository.increment_retry_count = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 1
        final_batch.failed_sections = 2
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

        assert successful_count == 1
        assert failed_count == 2

    @pytest.mark.asyncio
    async def test_failures_persisted_with_error_details(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            default_response="Valid content",
            failure_sections=[2],
        )

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

        failure_details = []

        async def capture_failure(output_id, error_message, error_code, metadata, completed_at):
            failure_details.append(
                {
                    "output_id": output_id,
                    "error_message": error_message,
                    "error_code": error_code,
                    "metadata": metadata,
                }
            )
            return MagicMock()

        async def capture_retry_exhausted(output_id, error_message, metadata, completed_at):
            failure_details.append(
                {
                    "output_id": output_id,
                    "error_message": error_message,
                    "error_code": "RETRY_EXHAUSTED",
                    "metadata": metadata,
                }
            )
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(return_value=MagicMock())
        mock_output_repository.mark_output_failed = AsyncMock(side_effect=capture_failure)
        mock_output_repository.mark_retry_exhausted = AsyncMock(side_effect=capture_retry_exhausted)
        mock_output_repository.increment_retry_count = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 2
        final_batch.failed_sections = 1
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

        assert len(failure_details) == 1
        failure = failure_details[0]
        assert failure["error_message"] is not None
        assert failure["error_code"] == "RETRY_EXHAUSTED"
        assert "failure_type" in failure["metadata"]

    @pytest.mark.asyncio
    async def test_all_sections_fail_gracefully(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            default_response="",
            failure_sections=[1, 2, 3],
        )

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
        mock_output_repository.mark_output_failed = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 0
        final_batch.failed_sections = 3
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        response = await service.execute_section_generation(request)

        assert response.completed_sections == 0
        assert response.failed_sections == 3
        assert response.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_successful_sections_unaffected_by_failures(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            response_map={
                1: "First section content that is valid",
                2: "",
                3: "Third section content that is valid",
            },
            failure_sections=[2],
        )

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

        persisted_content = {}

        async def track_success(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            persisted_content[output_id] = generated_content
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=track_success)
        mock_output_repository.mark_output_failed = AsyncMock(return_value=MagicMock())

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 2
        final_batch.failed_sections = 1
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

        assert len(persisted_content) == 2
        for content in persisted_content.values():
            assert "valid" in content.lower()
