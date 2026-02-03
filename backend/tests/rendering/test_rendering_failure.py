from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.domains.assembly.models import AssemblyStatus
from backend.app.domains.rendering.schemas import RenderErrorCode, RenderingRequest
from backend.app.domains.rendering.service import DocumentRenderingService


class TestInvalidAssembledInputFailsExplicitly:
    async def test_missing_assembled_document_fails(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
    ):
        mock_assembled_repository.get_by_id.return_value = None

        request = RenderingRequest(
            assembled_document_id=uuid4(),
            document_id=uuid4(),
            version=1,
        )

        result = await rendering_service.render_document(request)

        assert not result.success
        assert result.error_code == RenderErrorCode.INVALID_ASSEMBLED_DOCUMENT

    async def test_non_immutable_assembled_document_fails(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        assembled_document_id,
        document_id,
    ):
        mock_assembled = MagicMock()
        mock_assembled.id = assembled_document_id
        mock_assembled.is_immutable = False
        mock_assembled.status = AssemblyStatus.VALIDATED
        mock_assembled.assembled_structure = {"blocks": []}
        mock_assembled_repository.get_by_id.return_value = mock_assembled

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
        )

        result = await rendering_service.render_document(request)

        assert not result.success
        assert result.error_code == RenderErrorCode.DOCUMENT_NOT_IMMUTABLE

    async def test_non_validated_assembled_document_fails(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        assembled_document_id,
        document_id,
    ):
        mock_assembled = MagicMock()
        mock_assembled.id = assembled_document_id
        mock_assembled.is_immutable = True
        mock_assembled.status = AssemblyStatus.COMPLETED
        mock_assembled.assembled_structure = {"blocks": []}
        mock_assembled_repository.get_by_id.return_value = mock_assembled

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
        )

        result = await rendering_service.render_document(request)

        assert not result.success
        assert result.error_code == RenderErrorCode.DOCUMENT_NOT_VALIDATED

    async def test_empty_assembled_structure_fails(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        assembled_document_id,
        document_id,
    ):
        mock_assembled = MagicMock()
        mock_assembled.id = assembled_document_id
        mock_assembled.is_immutable = True
        mock_assembled.status = AssemblyStatus.VALIDATED
        mock_assembled.assembled_structure = None
        mock_assembled_repository.get_by_id.return_value = mock_assembled

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
        )

        result = await rendering_service.render_document(request)

        assert not result.success
        assert result.error_code == RenderErrorCode.MISSING_ASSEMBLED_STRUCTURE


class TestPartialRendersNotPersisted:
    async def test_failed_render_does_not_persist(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        mock_storage,
        assembled_document_id,
        document_id,
    ):
        mock_assembled = MagicMock()
        mock_assembled.id = assembled_document_id
        mock_assembled.is_immutable = True
        mock_assembled.status = AssemblyStatus.VALIDATED
        mock_assembled.assembled_structure = None
        mock_assembled_repository.get_by_id.return_value = mock_assembled

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
        )

        result = await rendering_service.render_document(request)

        assert not result.success

        output_key = f"documents/{document_id}/1/output.docx"
        assert not mock_storage.file_exists(output_key)

    async def test_validation_failure_does_not_persist_invalid_document(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        mock_repository,
        mock_rendered_document,
        mock_storage,
        assembled_document_id,
        document_id,
    ):
        mock_assembled_repository.get_by_id.return_value = None

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
        )

        result = await rendering_service.render_document(request)

        assert not result.success

        output_key = f"documents/{document_id}/1/output.docx"
        assert not mock_storage.file_exists(output_key)


class TestAlreadyRenderedDocumentHandled:
    async def test_already_rendered_immutable_returns_error(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        mock_repository,
        mock_assembled_document,
        assembled_document_id,
        document_id,
    ):
        existing_rendered = MagicMock()
        existing_rendered.is_immutable = True
        mock_repository.get_by_assembled_document.return_value = existing_rendered

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
            force_rerender=False,
        )

        result = await rendering_service.render_document(request)

        assert not result.success
        assert result.error_code == RenderErrorCode.ALREADY_RENDERED

    async def test_force_rerender_bypasses_immutable_check(
        self,
        rendering_service: DocumentRenderingService,
        mock_assembled_repository,
        mock_repository,
        mock_assembled_document,
        mock_rendered_document,
        assembled_document_id,
        document_id,
    ):
        existing_rendered = MagicMock()
        existing_rendered.is_immutable = True
        mock_repository.get_by_assembled_document.return_value = existing_rendered

        mock_repository.create.return_value = mock_rendered_document
        mock_repository.mark_in_progress.return_value = mock_rendered_document
        mock_repository.mark_completed.return_value = mock_rendered_document
        mock_repository.mark_validated.return_value = mock_rendered_document

        request = RenderingRequest(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            version=1,
            force_rerender=True,
        )

        result = await rendering_service.render_document(request)

        assert result.success


class TestRenderingErrorsHandled:
    def test_invalid_content_validation_fails(
        self,
        document_validator,
    ):
        invalid_content = b"This is not a valid docx file"

        result = document_validator.validate(invalid_content)

        assert not result.is_valid
        assert result.has_errors

    def test_empty_content_validation_fails(
        self,
        document_validator,
    ):
        result = document_validator.validate(b"")

        assert not result.is_valid
        assert result.has_errors

    def test_none_content_validation_fails(
        self,
        document_validator,
    ):
        result = document_validator.validate(None)

        assert not result.is_valid
        assert result.has_errors
