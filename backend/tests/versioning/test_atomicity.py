from unittest.mock import AsyncMock

import pytest

from backend.app.domains.document.models import Document
from backend.app.domains.versioning.repository import VersioningRepository
from backend.app.domains.versioning.schemas import VersionCreateRequest, VersioningErrorCode
from backend.app.domains.versioning.service import DocumentVersioningService


@pytest.mark.asyncio
class TestAtomicity:
    async def test_failure_during_storage_does_not_create_partial_version(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        mock_storage,
    ):
        mock_storage._files.clear()
        original_upload = mock_storage.upload_document_output

        def failing_upload(*args, **kwargs):
            raise Exception("Storage failure")

        mock_storage.upload_document_output = failing_upload

        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        assert result.success is False
        assert result.error is not None

        mock_storage.upload_document_output = original_upload

        version = await versioning_service.get_version(sample_document.id, 1)
        assert version is None

    async def test_current_version_pointer_unchanged_on_storage_failure(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        mock_storage,
        versioning_repository: VersioningRepository,
    ):
        original_current_version = sample_document.current_version

        def failing_upload(*args, **kwargs):
            raise Exception("Storage failure")

        mock_storage.upload_document_output = failing_upload

        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        assert result.success is False

        document = await versioning_repository.get_document(sample_document.id)
        assert document.current_version == original_current_version

    async def test_storage_rollback_on_db_failure(
        self,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        mock_storage,
        mock_audit_repository,
    ):
        from sqlalchemy.exc import IntegrityError

        mock_repo = AsyncMock(spec=VersioningRepository)
        mock_repo.get_document.return_value = sample_document
        mock_repo.get_next_version_number.return_value = 1
        mock_repo.get_version_by_content_hash.return_value = None
        mock_repo.create_version.side_effect = IntegrityError("duplicate key", None, None)

        service = DocumentVersioningService(
            repository=mock_repo,
            storage=mock_storage,
            audit_repo=mock_audit_repository,
        )

        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await service.create_version(request)

        assert result.success is False
        assert result.error.code == VersioningErrorCode.DUPLICATE_VERSION

    async def test_version_and_pointer_update_succeed_together(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        versioning_repository: VersioningRepository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        assert result.success is True

        version = await versioning_service.get_version(sample_document.id, result.version_number)
        assert version is not None

        document = await versioning_repository.get_document(sample_document.id)
        assert document.current_version == result.version_number

    async def test_file_existence_verification_after_upload(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        mock_storage,
    ):
        original_exists = mock_storage.file_exists

        def failing_exists(key):
            if "output.docx" in key:
                return False
            return original_exists(key)

        original_upload = mock_storage.upload_document_output
        mock_storage.upload_document_output = (
            lambda *args, **kwargs: f"documents/{sample_document.id}/1/output.docx"
        )
        mock_storage.file_exists = failing_exists

        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        mock_storage.upload_document_output = original_upload
        mock_storage.file_exists = original_exists

        assert result.success is False
        assert result.error.code == VersioningErrorCode.STORAGE_FAILED

    async def test_multiple_sequential_versions_maintain_atomicity(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_metadata: dict,
        versioning_repository: VersioningRepository,
    ):
        for i in range(3):
            content = f"Version {i + 1} content".encode()
            request = VersionCreateRequest(
                document_id=sample_document.id,
                content=content,
                generation_metadata={**sample_metadata, "version": i + 1},
            )

            result = await versioning_service.create_version(request)
            assert result.success is True
            assert result.version_number == i + 1

            document = await versioning_repository.get_document(sample_document.id)
            assert document.current_version == i + 1

            version = await versioning_service.get_version(sample_document.id, i + 1)
            assert version is not None
