from uuid import uuid4

import pytest

from backend.app.domains.document.models import Document
from backend.app.domains.versioning.schemas import VersionCreateRequest, VersioningErrorCode
from backend.app.domains.versioning.service import DocumentVersioningService


@pytest.mark.asyncio
class TestVersionCreation:
    async def test_first_document_version_is_version_1(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        assert result.success is True
        assert result.version_number == 1
        assert result.document_id == sample_document.id
        assert result.is_duplicate is False

    async def test_subsequent_versions_increment_correctly(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_content_different: bytes,
        sample_metadata: dict,
    ):
        request1 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )
        result1 = await versioning_service.create_version(request1)
        assert result1.success is True
        assert result1.version_number == 1

        request2 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content_different,
            generation_metadata={**sample_metadata, "generation_type": "incremental"},
        )
        result2 = await versioning_service.create_version(request2)

        assert result2.success is True
        assert result2.version_number == 2
        assert result2.is_duplicate is False

    async def test_versions_are_immutable_after_creation(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        db_session,
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
        original_hash = version.content_hash
        original_path = version.output_path

        version_after = await versioning_service.get_version(
            sample_document.id, result.version_number
        )
        assert version_after is not None
        assert version_after.content_hash == original_hash
        assert version_after.output_path == original_path

    async def test_version_numbers_are_monotonically_increasing(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_metadata: dict,
    ):
        versions_created = []
        for i in range(5):
            content = f"Document content version {i + 1}".encode()
            request = VersionCreateRequest(
                document_id=sample_document.id,
                content=content,
                generation_metadata={**sample_metadata, "iteration": i},
            )
            result = await versioning_service.create_version(request)
            assert result.success is True
            versions_created.append(result.version_number)

        assert versions_created == [1, 2, 3, 4, 5]

        for i in range(len(versions_created) - 1):
            assert versions_created[i] < versions_created[i + 1]

    async def test_version_creation_for_nonexistent_document_fails(
        self,
        versioning_service: DocumentVersioningService,
        sample_content: bytes,
        sample_metadata: dict,
    ):
        nonexistent_id = uuid4()
        request = VersionCreateRequest(
            document_id=nonexistent_id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        assert result.success is False
        assert result.error is not None
        assert result.error.code == VersioningErrorCode.DOCUMENT_NOT_FOUND

    async def test_version_id_is_unique_uuid(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_content_different: bytes,
        sample_metadata: dict,
    ):
        request1 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )
        result1 = await versioning_service.create_version(request1)

        request2 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content_different,
            generation_metadata=sample_metadata,
        )
        result2 = await versioning_service.create_version(request2)

        assert result1.success is True
        assert result2.success is True
        assert result1.version_id is not None
        assert result2.version_id is not None
        assert result1.version_id != result2.version_id

    async def test_version_contains_correct_metadata(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
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
        assert version.generation_metadata["template_name"] == "Advisory Report"
        assert version.generation_metadata["generation_type"] == "full"
        assert "content_hash" in version.generation_metadata
        assert "file_size_bytes" in version.generation_metadata

    async def test_version_created_at_timestamp_is_set(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)

        assert result.success is True
        assert result.created_at is not None
