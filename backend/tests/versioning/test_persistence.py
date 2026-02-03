import pytest

from backend.app.domains.document.models import Document
from backend.app.domains.versioning.schemas import VersionCreateRequest
from backend.app.domains.versioning.service import DocumentVersioningService


@pytest.mark.asyncio
class TestPersistence:
    async def test_version_metadata_stored_correctly(
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
        assert version.document_id == sample_document.id
        assert version.version_number == result.version_number
        assert version.content_hash == result.content_hash
        assert version.file_size_bytes == len(sample_content)
        assert "template_name" in version.generation_metadata
        assert version.generation_metadata["template_name"] == "Advisory Report"

    async def test_output_document_path_matches_version(
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

        expected_path = f"documents/{sample_document.id}/{result.version_number}/output.docx"
        assert result.output_path == expected_path

        version = await versioning_service.get_version(sample_document.id, result.version_number)
        assert version.output_path == expected_path

    async def test_version_content_retrievable_from_storage(
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

        retrieved_content = await versioning_service.get_version_content(
            sample_document.id, result.version_number
        )

        assert retrieved_content is not None
        assert retrieved_content == sample_content

    async def test_version_integrity_verification(
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

        is_valid = await versioning_service.verify_version_integrity(
            sample_document.id, result.version_number
        )

        assert is_valid is True

    async def test_version_history_retrievable(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_metadata: dict,
    ):
        for i in range(3):
            content = f"Version {i + 1} content".encode()
            request = VersionCreateRequest(
                document_id=sample_document.id,
                content=content,
                generation_metadata={**sample_metadata, "version": i + 1},
            )
            await versioning_service.create_version(request)

        history = await versioning_service.get_version_history(sample_document.id)

        assert history is not None
        assert history.document_id == sample_document.id
        assert history.total_versions == 3
        assert history.current_version == 3
        assert len(history.versions) == 3

        version_numbers = [v.version_number for v in history.versions]
        assert version_numbers == [3, 2, 1]

    async def test_current_version_pointer_persisted(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_content_different: bytes,
        sample_metadata: dict,
        versioning_repository,
    ):
        request1 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )
        await versioning_service.create_version(request1)

        document = await versioning_repository.get_document(sample_document.id)
        assert document.current_version == 1

        request2 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content_different,
            generation_metadata=sample_metadata,
        )
        await versioning_service.create_version(request2)

        document = await versioning_repository.get_document(sample_document.id)
        assert document.current_version == 2

    async def test_get_current_version(
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
        await versioning_service.create_version(request1)

        request2 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content_different,
            generation_metadata=sample_metadata,
        )
        await versioning_service.create_version(request2)

        current = await versioning_service.get_current_version(sample_document.id)

        assert current is not None
        assert current.version_number == 2

    async def test_version_exists_check(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
    ):
        exists_before = await versioning_service.version_exists(sample_document.id, 1)
        assert exists_before is False

        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )
        await versioning_service.create_version(request)

        exists_after = await versioning_service.version_exists(sample_document.id, 1)
        assert exists_after is True

        exists_v2 = await versioning_service.version_exists(sample_document.id, 2)
        assert exists_v2 is False

    async def test_file_size_stored_in_metadata(
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

        assert version.file_size_bytes == len(sample_content)

    async def test_content_hash_stored_in_metadata(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
    ):
        import hashlib

        expected_hash = hashlib.sha256(sample_content).hexdigest()

        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)
        assert result.success is True

        version = await versioning_service.get_version(sample_document.id, result.version_number)

        assert version.content_hash == expected_hash
