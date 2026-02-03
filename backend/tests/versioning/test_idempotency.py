import pytest

from backend.app.domains.document.models import Document
from backend.app.domains.versioning.schemas import VersionCreateRequest
from backend.app.domains.versioning.service import DocumentVersioningService


@pytest.mark.asyncio
class TestIdempotency:
    async def test_identical_content_returns_existing_version(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
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
        assert result1.is_duplicate is False

        request2 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )
        result2 = await versioning_service.create_version(request2)

        assert result2.success is True
        assert result2.is_duplicate is True
        assert result2.version_number == 1
        assert result2.existing_version_number == 1
        assert result2.version_id == result1.version_id

    async def test_duplicate_content_does_not_create_new_version(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
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
            content=sample_content,
            generation_metadata={"different": "metadata"},
        )
        result2 = await versioning_service.create_version(request2)

        assert result2.is_duplicate is True

        history = await versioning_service.get_version_history(sample_document.id)
        assert history.total_versions == 1

    async def test_different_content_creates_new_version(
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
        assert result2.is_duplicate is False
        assert result2.version_number == 2
        assert result1.content_hash != result2.content_hash

    async def test_content_hash_consistency(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
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
            content=sample_content,
            generation_metadata=sample_metadata,
        )
        result2 = await versioning_service.create_version(request2)

        assert result1.content_hash == result2.content_hash

    async def test_idempotency_across_multiple_requests(
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

        results = []
        for _ in range(5):
            result = await versioning_service.create_version(request)
            results.append(result)

        assert results[0].is_duplicate is False
        assert all(r.is_duplicate is True for r in results[1:])

        assert all(r.version_id == results[0].version_id for r in results)

        history = await versioning_service.get_version_history(sample_document.id)
        assert history.total_versions == 1

    async def test_safe_rerun_after_successful_creation(
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

        result1 = await versioning_service.create_version(request)
        assert result1.success is True

        result2 = await versioning_service.create_version(request)

        assert result2.success is True
        assert result2.is_duplicate is True
        assert result2.version_number == result1.version_number
        assert result2.output_path == result1.output_path

    async def test_precomputed_content_hash_is_used(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
    ):
        import hashlib

        precomputed_hash = hashlib.sha256(sample_content).hexdigest()

        request1 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
            content_hash=precomputed_hash,
        )
        result1 = await versioning_service.create_version(request1)

        assert result1.success is True
        assert result1.content_hash == precomputed_hash

        request2 = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
            content_hash=precomputed_hash,
        )
        result2 = await versioning_service.create_version(request2)

        assert result2.is_duplicate is True
        assert result2.content_hash == precomputed_hash

    async def test_version_uniqueness_constraint_enforced(
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

        assert result1.version_number == 1
        assert result2.version_number == 2
        assert result1.version_id != result2.version_id
