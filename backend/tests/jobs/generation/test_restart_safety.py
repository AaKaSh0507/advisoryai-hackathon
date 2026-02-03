from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from backend.app.worker.handlers.generation_pipeline import (
    GenerationPipelineHandler,
    PipelineStage,
    PipelineState,
)
from tests.jobs.generation.conftest import (
    MockAssemblyResult,
    MockPrepareGenerationInputsResponse,
    MockRenderingResult,
    MockSectionGenerationResponse,
    MockVersionResult,
    create_handler_context,
)


class TestJobStateNotCorrupted:

    @pytest.mark.asyncio
    async def test_handler_does_not_modify_job_status_directly(
        self,
        db_session,
        sample_job,
    ):
        handler = GenerationPipelineHandler()
        original_status = sample_job.status
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                side_effect=Exception("Simulated failure")
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        assert sample_job.status == original_status

    @pytest.mark.asyncio
    async def test_handler_returns_result_for_worker_to_update_status(
        self,
        db_session,
        sample_job,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                side_effect=Exception("Simulated failure")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result is not None
        assert hasattr(result, "success")
        assert hasattr(result, "error")
        assert hasattr(result, "data")
        assert hasattr(result, "should_advance_pipeline")

    @pytest.mark.asyncio
    async def test_partial_completion_returns_artifacts_created_so_far(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                return_value=MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                return_value=MockSectionGenerationResponse(batch_id=fixed_output_batch_id)
            )
            mock_services["assembly_service"].assemble_document = AsyncMock(
                return_value=MockAssemblyResult(
                    success=True, assembled_document=sample_assembled_document
                )
            )
            mock_services["rendering_service"].render_document = AsyncMock(
                side_effect=Exception("Worker killed")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)
        assert result.data["assembled_document_id"] == str(sample_assembled_document.id)


class TestDeterministicRestartBehavior:

    @pytest.mark.asyncio
    async def test_same_input_produces_same_failure_stage(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                return_value=MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                side_effect=ValueError("Consistent error")
            )
            mock_create_services.return_value = mock_services

            result1 = await handler.handle(context)
            result2 = await handler.handle(context)

        assert result1.success == result2.success
        assert result1.data["failed_stage"] == result2.data["failed_stage"]
        assert "Consistent error" in result1.error
        assert "Consistent error" in result2.error

    @pytest.mark.asyncio
    async def test_handler_is_stateless_between_calls(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
        sample_rendered_document,
        fixed_version_id,
        sample_docx_content,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                side_effect=[
                    Exception("First run fails"),
                    MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id),
                ]
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                return_value=MockSectionGenerationResponse(batch_id=fixed_output_batch_id)
            )
            mock_services["assembly_service"].assemble_document = AsyncMock(
                return_value=MockAssemblyResult(
                    success=True, assembled_document=sample_assembled_document
                )
            )
            mock_services["rendering_service"].render_document = AsyncMock(
                return_value=MockRenderingResult(
                    success=True,
                    rendered_document=sample_rendered_document,
                    output_path=sample_rendered_document.output_path,
                )
            )
            mock_services["versioning_service"].create_version = AsyncMock(
                return_value=MockVersionResult(
                    success=True,
                    version_id=fixed_version_id,
                    version_number=1,
                    output_path="documents/test/versions/1/final.docx",
                )
            )
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            result1 = await handler.handle(context)
            result2 = await handler.handle(context)

        assert result1.success is False
        assert result2.success is True


class TestNoVersionDuplication:

    @pytest.mark.asyncio
    async def test_versioning_called_once_per_successful_pipeline(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
        sample_rendered_document,
        fixed_version_id,
        sample_docx_content,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        versioning_call_count = 0

        async def track_versioning_calls(request):
            nonlocal versioning_call_count
            versioning_call_count += 1
            return MockVersionResult(
                success=True,
                version_id=fixed_version_id,
                version_number=1,
                output_path="documents/test/versions/1/final.docx",
            )

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                return_value=MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                return_value=MockSectionGenerationResponse(batch_id=fixed_output_batch_id)
            )
            mock_services["assembly_service"].assemble_document = AsyncMock(
                return_value=MockAssemblyResult(
                    success=True, assembled_document=sample_assembled_document
                )
            )
            mock_services["rendering_service"].render_document = AsyncMock(
                return_value=MockRenderingResult(
                    success=True,
                    rendered_document=sample_rendered_document,
                    output_path=sample_rendered_document.output_path,
                )
            )
            mock_services["versioning_service"].create_version = track_versioning_calls
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        assert versioning_call_count == 1

    @pytest.mark.asyncio
    async def test_versioning_not_called_on_earlier_stage_failure(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        versioning_called = False

        async def track_versioning(*args, **kwargs):
            nonlocal versioning_called
            versioning_called = True

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_services = {
                "generation_input_service": MagicMock(),
                "section_generation_service": MagicMock(),
                "assembly_service": MagicMock(),
                "rendering_service": MagicMock(),
                "versioning_service": MagicMock(),
                "generation_audit_service": MagicMock(),
                "storage_service": MagicMock(),
            }
            mock_services["generation_input_service"].prepare_generation_inputs = AsyncMock(
                return_value=MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                return_value=MockSectionGenerationResponse(
                    batch_id=fixed_output_batch_id,
                    total_sections=3,
                    completed_count=1,
                    failed_count=2,
                )
            )
            mock_services["versioning_service"].create_version = track_versioning
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert versioning_called is False


class TestPipelineStateManagement:

    def test_pipeline_state_initialization(self):
        state = PipelineState(current_stage=PipelineStage.INPUT_PREPARATION)

        assert state.current_stage == PipelineStage.INPUT_PREPARATION
        assert state.input_batch_id is None
        assert state.output_batch_id is None
        assert state.assembled_document_id is None
        assert state.rendered_document_id is None
        assert state.version_id is None
        assert state.version_number is None
        assert state.output_path is None
        assert state.error is None
        assert state.error_stage is None

    def test_pipeline_state_tracks_progress(self):
        state = PipelineState(current_stage=PipelineStage.INPUT_PREPARATION)

        state.input_batch_id = UUID("11111111-1111-1111-1111-111111111111")
        state.current_stage = PipelineStage.SECTION_GENERATION

        assert state.input_batch_id is not None
        assert state.current_stage == PipelineStage.SECTION_GENERATION

    def test_pipeline_state_captures_error_context(self):
        state = PipelineState(current_stage=PipelineStage.DOCUMENT_ASSEMBLY)
        state.input_batch_id = UUID("11111111-1111-1111-1111-111111111111")
        state.output_batch_id = UUID("22222222-2222-2222-2222-222222222222")

        state.error = "Assembly failed: missing blocks"
        state.error_stage = PipelineStage.DOCUMENT_ASSEMBLY

        assert state.error is not None
        assert state.error_stage == PipelineStage.DOCUMENT_ASSEMBLY
        assert state.input_batch_id is not None
        assert state.output_batch_id is not None
        assert state.assembled_document_id is None


class TestExceptionHandling:

    @pytest.mark.asyncio
    async def test_unexpected_exception_is_caught(
        self,
        db_session,
        sample_job,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_create_services.side_effect = RuntimeError("Unexpected system error")

            result = await handler.handle(context)

        assert result.success is False
        assert "INPUT_PREPARATION" in result.error
        assert "Unexpected system error" in result.error

    @pytest.mark.asyncio
    async def test_exception_does_not_crash_worker(
        self,
        db_session,
        sample_job,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        with patch.object(handler, "_create_services") as mock_create_services:
            mock_create_services.side_effect = MemoryError("Out of memory")

            try:
                result = await handler.handle(context)
                exception_raised = False
            except MemoryError:
                exception_raised = True

        assert exception_raised is False or (result is not None and result.success is False)
