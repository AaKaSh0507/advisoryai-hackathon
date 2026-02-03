from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.worker.handlers.generation_pipeline import GenerationPipelineHandler, PipelineStage
from tests.jobs.generation.conftest import (
    MockAssemblyResult,
    MockPrepareGenerationInputsResponse,
    MockRenderingResult,
    MockSectionGenerationResponse,
    MockVersionResult,
    create_handler_context,
)


class TestInputPreparationFailure:

    @pytest.mark.asyncio
    async def test_input_preparation_exception_halts_pipeline(
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
                side_effect=Exception("Failed to prepare inputs")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "Input preparation failed" in result.error
        assert result.should_advance_pipeline is False
        mock_services["section_generation_service"].execute_section_generation.assert_not_called()

    @pytest.mark.asyncio
    async def test_input_preparation_failure_persists_context(
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
                side_effect=ValueError("Invalid template structure")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert result.data is not None
        assert result.data.get("failed_stage") == PipelineStage.INPUT_PREPARATION.value
        assert result.data.get("current_stage") == PipelineStage.INPUT_PREPARATION.value


class TestSectionGenerationFailure:

    @pytest.mark.asyncio
    async def test_section_generation_with_failures_halts_pipeline(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        mock_gen_response = MockSectionGenerationResponse(
            batch_id=fixed_output_batch_id,
            total_sections=3,
            completed_count=2,
            failed_count=1,
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
                return_value=mock_gen_response
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "1 failures" in result.error or "failed" in result.error.lower()
        assert result.data["failed_stage"] == PipelineStage.SECTION_GENERATION.value
        mock_services["assembly_service"].assemble_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_section_generation_exception_halts_pipeline(
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
                side_effect=RuntimeError("LLM client timeout")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "Section generation failed" in result.error
        mock_services["assembly_service"].assemble_document.assert_not_called()


class TestDocumentAssemblyFailure:

    @pytest.mark.asyncio
    async def test_assembly_failure_halts_pipeline(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        mock_assembly = MockAssemblyResult(
            success=False,
            assembled_document=None,
            error_message="Missing section content for block blk_par_002",
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
                return_value=mock_assembly
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "assembly" in result.error.lower()
        assert result.data["failed_stage"] == PipelineStage.DOCUMENT_ASSEMBLY.value
        mock_services["rendering_service"].render_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_assembly_exception_captures_context(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
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
                side_effect=KeyError("missing_block_id")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)
        assert result.data["assembled_document_id"] is None


class TestDocumentRenderingFailure:

    @pytest.mark.asyncio
    async def test_rendering_failure_halts_pipeline(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        mock_rendering = MockRenderingResult(
            success=False,
            rendered_document=None,
            error_message="Failed to render table block",
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
                return_value=mock_rendering
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "rendering" in result.error.lower()
        assert result.data["failed_stage"] == PipelineStage.DOCUMENT_RENDERING.value
        assert result.data["assembled_document_id"] == str(sample_assembled_document.id)
        mock_services["versioning_service"].create_version.assert_not_called()


class TestVersioningFailure:

    @pytest.mark.asyncio
    async def test_versioning_failure_after_rendering(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
        sample_rendered_document,
        sample_docx_content,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        mock_error = MagicMock()
        mock_error.message = "Duplicate version number"
        mock_version = MockVersionResult(
            success=False,
            error=mock_error,
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
            mock_services["versioning_service"].create_version = AsyncMock(
                return_value=mock_version
            )
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "versioning" in result.error.lower() or "version" in result.error.lower()
        assert result.data["failed_stage"] == PipelineStage.VERSIONING.value
        assert result.data["rendered_document_id"] == str(sample_rendered_document.id)

    @pytest.mark.asyncio
    async def test_versioning_missing_file_content(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
        sample_rendered_document,
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
                return_value=MockRenderingResult(
                    success=True,
                    rendered_document=sample_rendered_document,
                    output_path=sample_rendered_document.output_path,
                )
            )
            mock_services["storage_service"].get_file = MagicMock(return_value=None)
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "read" in result.error.lower() or "content" in result.error.lower()
        assert result.data["failed_stage"] == PipelineStage.VERSIONING.value


class TestFailureContextPersistence:

    @pytest.mark.asyncio
    async def test_partial_progress_preserved_on_failure(
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
                side_effect=Exception("Rendering engine crash")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)
        assert result.data["assembled_document_id"] == str(sample_assembled_document.id)
        assert result.data["rendered_document_id"] is None
        assert result.data["current_stage"] == PipelineStage.DOCUMENT_RENDERING.value

    @pytest.mark.asyncio
    async def test_error_message_includes_stage_information(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
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
                side_effect=ValueError("Structural integrity violation")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert "Document assembly" in result.error or "assembly" in result.error.lower()
        assert "Structural integrity violation" in result.error


class TestDownstreamStagesNotExecuted:

    @pytest.mark.asyncio
    async def test_no_stages_after_input_failure(
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
                side_effect=Exception("Input preparation failed")
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        mock_services["section_generation_service"].execute_section_generation.assert_not_called()
        mock_services["assembly_service"].assemble_document.assert_not_called()
        mock_services["rendering_service"].render_document.assert_not_called()
        mock_services["versioning_service"].create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_stages_after_generation_failure(
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
                side_effect=Exception("LLM unavailable")
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        mock_services["generation_input_service"].prepare_generation_inputs.assert_called_once()
        mock_services["assembly_service"].assemble_document.assert_not_called()
        mock_services["rendering_service"].render_document.assert_not_called()
        mock_services["versioning_service"].create_version.assert_not_called()
