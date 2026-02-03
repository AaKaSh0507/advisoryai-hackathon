from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

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


class TestSuccessfulPipelineExecution:

    @pytest.mark.asyncio
    async def test_pipeline_completes_all_stages_in_order(
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

        mock_input_response = MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)
        mock_gen_response = MockSectionGenerationResponse(batch_id=fixed_output_batch_id)
        mock_assembly = MockAssemblyResult(
            success=True, assembled_document=sample_assembled_document
        )
        mock_rendering = MockRenderingResult(
            success=True,
            rendered_document=sample_rendered_document,
            output_path=sample_rendered_document.output_path,
        )
        mock_version = MockVersionResult(
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
                return_value=mock_input_response
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                return_value=mock_gen_response
            )
            mock_services["assembly_service"].assemble_document = AsyncMock(
                return_value=mock_assembly
            )
            mock_services["rendering_service"].render_document = AsyncMock(
                return_value=mock_rendering
            )
            mock_services["versioning_service"].create_version = AsyncMock(
                return_value=mock_version
            )
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is True
        assert result.data["pipeline_stage"] == PipelineStage.COMPLETED.value
        assert result.data["input_batch_id"] == str(fixed_input_batch_id)
        assert result.data["output_batch_id"] == str(fixed_output_batch_id)
        assert result.data["assembled_document_id"] == str(sample_assembled_document.id)
        assert result.data["rendered_document_id"] == str(sample_rendered_document.id)
        assert result.data["version_id"] == str(fixed_version_id)
        assert result.data["version_number"] == 1
        assert result.should_advance_pipeline is False

    @pytest.mark.asyncio
    async def test_all_stages_execute_in_correct_sequence(
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

        call_order = []

        async def track_input(*args, **kwargs):
            call_order.append("INPUT_PREPARATION")
            return MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)

        async def track_generation(*args, **kwargs):
            call_order.append("SECTION_GENERATION")
            return MockSectionGenerationResponse(batch_id=fixed_output_batch_id)

        async def track_assembly(*args, **kwargs):
            call_order.append("DOCUMENT_ASSEMBLY")
            return MockAssemblyResult(success=True, assembled_document=sample_assembled_document)

        async def track_rendering(*args, **kwargs):
            call_order.append("DOCUMENT_RENDERING")
            return MockRenderingResult(
                success=True,
                rendered_document=sample_rendered_document,
                output_path=sample_rendered_document.output_path,
            )

        async def track_versioning(*args, **kwargs):
            call_order.append("VERSIONING")
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

            result = await handler.handle(context)

        assert result.success is True
        expected_order = [
            "INPUT_PREPARATION",
            "SECTION_GENERATION",
            "DOCUMENT_ASSEMBLY",
            "DOCUMENT_RENDERING",
            "VERSIONING",
        ]
        assert call_order == expected_order

    @pytest.mark.asyncio
    async def test_final_document_version_is_created(
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

        mock_input_response = MockPrepareGenerationInputsResponse(batch_id=fixed_input_batch_id)
        mock_gen_response = MockSectionGenerationResponse(batch_id=fixed_output_batch_id)
        mock_assembly = MockAssemblyResult(
            success=True, assembled_document=sample_assembled_document
        )
        mock_rendering = MockRenderingResult(
            success=True,
            rendered_document=sample_rendered_document,
            output_path=sample_rendered_document.output_path,
        )
        mock_version = MockVersionResult(
            success=True,
            version_id=fixed_version_id,
            version_number=2,
            output_path="documents/test/versions/2/final.docx",
        )

        versioning_call_args = []

        async def capture_versioning(request):
            versioning_call_args.append(request)
            return mock_version

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
                return_value=mock_input_response
            )
            mock_services["section_generation_service"].execute_section_generation = AsyncMock(
                return_value=mock_gen_response
            )
            mock_services["assembly_service"].assemble_document = AsyncMock(
                return_value=mock_assembly
            )
            mock_services["rendering_service"].render_document = AsyncMock(
                return_value=mock_rendering
            )
            mock_services["versioning_service"].create_version = capture_versioning
            mock_services["storage_service"].get_file = MagicMock(
                return_value=sample_docx_content()
            )
            mock_create_services.return_value = mock_services

            result = await handler.handle(context)

        assert result.success is True
        assert result.data["version_number"] == 2
        assert len(versioning_call_args) == 1
        version_request = versioning_call_args[0]
        assert version_request.document_id == UUID(sample_job.payload["document_id"])
        assert version_request.content is not None
        assert "input_batch_id" in version_request.generation_metadata
        assert "output_batch_id" in version_request.generation_metadata
        assert "assembled_document_id" in version_request.generation_metadata
        assert "rendered_document_id" in version_request.generation_metadata

    @pytest.mark.asyncio
    async def test_pipeline_result_contains_all_artifact_ids(
        self,
        db_session,
        sample_job,
        fixed_input_batch_id,
        fixed_output_batch_id,
        sample_assembled_document,
        sample_rendered_document,
        fixed_version_id,
        fixed_document_id,
        fixed_template_version_id,
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
        data = result.data
        assert data["document_id"] == str(fixed_document_id)
        assert data["template_version_id"] == str(fixed_template_version_id)
        assert data["version_intent"] == 1
        assert data["input_batch_id"] is not None
        assert data["output_batch_id"] is not None
        assert data["assembled_document_id"] is not None
        assert data["rendered_document_id"] is not None
        assert data["version_id"] is not None
        assert data["version_number"] is not None
        assert data["output_path"] is not None


class TestPipelineInputValidation:

    @pytest.mark.asyncio
    async def test_missing_template_version_id_fails(self, db_session, sample_job):
        handler = GenerationPipelineHandler()
        sample_job.payload = {"document_id": str(sample_job.payload["document_id"])}
        context = create_handler_context(db_session, sample_job)

        result = await handler.handle(context)

        assert result.success is False
        assert "template_version_id" in result.error.lower()
        assert result.should_advance_pipeline is False

    @pytest.mark.asyncio
    async def test_missing_document_id_fails(self, db_session, sample_job):
        handler = GenerationPipelineHandler()
        sample_job.payload = {"template_version_id": str(sample_job.payload["template_version_id"])}
        context = create_handler_context(db_session, sample_job)

        result = await handler.handle(context)

        assert result.success is False
        assert "document_id" in result.error.lower()
        assert result.should_advance_pipeline is False

    @pytest.mark.asyncio
    async def test_invalid_uuid_format_fails(self, db_session, sample_job):
        handler = GenerationPipelineHandler()
        sample_job.payload = {
            "template_version_id": "not-a-valid-uuid",
            "document_id": str(sample_job.payload["document_id"]),
        }
        context = create_handler_context(db_session, sample_job)

        result = await handler.handle(context)

        assert result.success is False
        assert "uuid" in result.error.lower() or "invalid" in result.error.lower()
        assert result.should_advance_pipeline is False

    @pytest.mark.asyncio
    async def test_default_values_used_when_optional_fields_missing(
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
        sample_job.payload = {
            "template_version_id": str(sample_job.payload["template_version_id"]),
            "document_id": str(sample_job.payload["document_id"]),
        }
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
        assert result.data["version_intent"] == 1


class TestHandlerProperties:

    def test_handler_name_is_correct(self, pipeline_handler):
        assert pipeline_handler.name == "GenerationPipelineHandler"
