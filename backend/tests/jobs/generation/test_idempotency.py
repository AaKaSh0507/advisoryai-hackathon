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


class TestNoDuplicateCreation:

    @pytest.mark.asyncio
    async def test_rerun_does_not_create_duplicate_input_batch(
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

        input_call_count = 0

        async def track_input_calls(request):
            nonlocal input_call_count
            input_call_count += 1
            return MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)

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
            mock_services["generation_input_service"].prepare_generation_inputs = track_input_calls
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

            result = await handler.handle(context)

        assert result.success is True
        assert input_call_count == 1

    @pytest.mark.asyncio
    async def test_each_service_called_exactly_once(
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

        call_counts = {
            "input": 0,
            "generation": 0,
            "assembly": 0,
            "rendering": 0,
            "versioning": 0,
        }

        async def track_input(*args, **kwargs):
            call_counts["input"] += 1
            return MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)

        async def track_generation(*args, **kwargs):
            call_counts["generation"] += 1
            return MockSectionGenerationResponse(batch_id=fixed_output_batch_id)

        async def track_assembly(*args, **kwargs):
            call_counts["assembly"] += 1
            return MockAssemblyResult(success=True, assembled_document=sample_assembled_document)

        async def track_rendering(*args, **kwargs):
            call_counts["rendering"] += 1
            return MockRenderingResult(
                success=True,
                rendered_document=sample_rendered_document,
                output_path=sample_rendered_document.output_path,
            )

        async def track_versioning(*args, **kwargs):
            call_counts["versioning"] += 1
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
            mock_services["generation_input_service"].prepare_generation_inputs = track_input
            mock_services["section_generation_service"].execute_section_generation = (
                track_generation
            )
            mock_services["assembly_service"].assemble_document = track_assembly
            mock_services["rendering_service"].render_document = track_rendering
            mock_services["versioning_service"].create_version = track_versioning
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        assert call_counts["input"] == 1
        assert call_counts["generation"] == 1
        assert call_counts["assembly"] == 1
        assert call_counts["rendering"] == 1
        assert call_counts["versioning"] == 1


class TestPartialCompletionHandling:

    @pytest.mark.asyncio
    async def test_failure_after_assembly_preserves_artifacts(
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
                side_effect=Exception("Rendering engine failure")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)
        assert result.data["assembled_document_id"] == str(sample_assembled_document.id)

    @pytest.mark.asyncio
    async def test_failure_captures_last_successful_stage(
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
                side_effect=ValueError("Missing section outputs")
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is False
        assert result.data["failed_stage"] == PipelineStage.DOCUMENT_ASSEMBLY.value
        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)
        assert result.data["assembled_document_id"] is None


class TestConsistentResults:

    @pytest.mark.asyncio
    async def test_same_job_produces_consistent_result_data(
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

            result = await handler.handle(context)

        assert result.success is True
        assert result.data["document_id"] == str(sample_job.payload["document_id"])
        assert result.data["template_version_id"] == str(sample_job.payload["template_version_id"])
        assert result.data["version_intent"] == sample_job.payload["version_intent"]
        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)

    @pytest.mark.asyncio
    async def test_result_contains_all_expected_fields(
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

            result = await handler.handle(context)

        expected_fields = [
            "document_id",
            "template_version_id",
            "version_intent",
            "input_batch_id",
            "output_batch_id",
            "assembled_document_id",
            "rendered_document_id",
            "version_id",
            "version_number",
            "output_path",
            "pipeline_stage",
        ]
        for field in expected_fields:
            assert field in result.data, f"Missing field: {field}"


class TestServiceCallParameters:

    @pytest.mark.asyncio
    async def test_input_preparation_receives_correct_parameters(
        self,
        db_session,
        sample_job,
        fixed_document_id,
        fixed_template_version_id,
        sample_client_data,
        fixed_input_batch_id,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        captured_request = None

        async def capture_input_request(request):
            nonlocal captured_request
            captured_request = request
            return MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)

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
            mock_services["generation_input_service"].prepare_generation_inputs = (
                capture_input_request
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                side_effect=Exception("Stop here")
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        assert captured_request is not None
        assert captured_request.document_id == fixed_document_id
        assert captured_request.template_version_id == fixed_template_version_id
        assert captured_request.version_intent == 1
        assert captured_request.client_data.client_id == sample_client_data["client_id"]
        assert captured_request.client_data.client_name == sample_client_data["client_name"]

    @pytest.mark.asyncio
    async def test_assembly_receives_output_batch_id_from_generation(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
    ):
        handler = GenerationPipelineHandler()
        context = create_handler_context(db_session, sample_job)

        captured_request = None

        async def capture_assembly_request(request):
            nonlocal captured_request
            captured_request = request
            return MockAssemblyResult(success=True, assembled_document=sample_assembled_document)

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
            mock_services["assembly_service"].assemble_document = capture_assembly_request
            mock_services["rendering_service"].render_document = AsyncMock(
                side_effect=Exception("Stop here")
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        assert captured_request is not None
        assert captured_request.section_output_batch_id == fixed_output_batch_id

    @pytest.mark.asyncio
    async def test_versioning_receives_metadata_from_all_stages(
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

        captured_request = None

        async def capture_versioning_request(request):
            nonlocal captured_request
            captured_request = request
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
            mock_services["versioning_service"].create_version = capture_versioning_request
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            await handler.handle(context)

        assert captured_request is not None
        metadata = captured_request.generation_metadata
        assert metadata["input_batch_id"] == str(fixed_input_batch_id)
        assert metadata["output_batch_id"] == str(fixed_output_batch_id)
        assert metadata["assembled_document_id"] == str(sample_assembled_document.id)
        assert metadata["rendered_document_id"] == str(sample_rendered_document.id)
