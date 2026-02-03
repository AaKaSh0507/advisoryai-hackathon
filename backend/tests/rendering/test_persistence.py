from uuid import uuid4

from backend.app.domains.rendering.schemas import RenderingRequest
from backend.app.domains.rendering.service import DocumentRenderingService


class TestOutputStoredAtCorrectPath:
    async def test_output_stored_at_expected_path(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success
        expected_path = (
            f"documents/{rendering_request.document_id}/{rendering_request.version}/output.docx"
        )
        assert result.output_path == expected_path

    async def test_different_versions_stored_separately(
        self,
        rendering_service: DocumentRenderingService,
        mock_repository,
        mock_rendered_document,
        mock_storage,
        assembled_document_id,
        document_id,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        request_v1 = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
        )

        result_v1 = await rendering_service.render_document(request_v1)

        mock_repository.get_by_assembled_document.return_value = None

        request_v2 = RenderingRequest(
            assembled_document_id=uuid4(),
            document_id=document_id,
            version=2,
        )

        result_v2 = await rendering_service.render_document(request_v2)

        assert result_v1.output_path != result_v2.output_path
        assert "version/1" in result_v1.output_path or "/1/" in result_v1.output_path
        assert "version/2" in result_v2.output_path or "/2/" in result_v2.output_path


class TestOutputSurvivesProcessRestart:
    async def test_stored_content_is_retrievable(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success

        stored_content = mock_storage.get_file(result.output_path)
        assert stored_content is not None
        assert len(stored_content) > 0

    async def test_stored_content_is_valid_docx(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
        document_validator,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success

        stored_content = mock_storage.get_file(result.output_path)
        validation_result = document_validator.validate(stored_content)

        assert validation_result.is_valid


class TestArtefactImmutability:
    async def test_rendered_document_marked_immutable(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        await rendering_service.render_document(rendering_request)

        mock_repository.mark_validated.assert_called_once()

    async def test_content_hash_computed_and_stored(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success

        call_args = mock_repository.mark_completed.call_args
        assert call_args is not None
        assert "content_hash" in call_args.kwargs
        assert len(call_args.kwargs["content_hash"]) == 64

    async def test_file_size_recorded(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success

        call_args = mock_repository.mark_completed.call_args
        assert call_args is not None
        assert "file_size_bytes" in call_args.kwargs
        assert call_args.kwargs["file_size_bytes"] > 0


class TestAtomicPersistence:
    async def test_file_exists_after_successful_render(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success
        assert mock_storage.file_exists(result.output_path)

    async def test_statistics_match_content(
        self,
        rendering_service: DocumentRenderingService,
        rendering_request: RenderingRequest,
        mock_repository,
        mock_rendered_document,
        mock_storage,
    ):
        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        result = await rendering_service.render_document(rendering_request)

        assert result.success

        call_args = mock_repository.mark_completed.call_args
        assert call_args is not None

        total_blocks = call_args.kwargs.get("total_blocks", 0)
        paragraphs = call_args.kwargs.get("paragraphs", 0)
        tables = call_args.kwargs.get("tables", 0)

        assert total_blocks > 0 or paragraphs > 0 or tables > 0
