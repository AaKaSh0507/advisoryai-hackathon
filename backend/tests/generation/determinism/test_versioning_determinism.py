from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from backend.app.domains.versioning.schemas import VersionCreateRequest
from backend.app.domains.versioning.service import DocumentVersioningService


class MockVersioningRepo:
    def __init__(self):
        self.get_document = AsyncMock()
        self.get_version_by_content_hash = AsyncMock()
        self.get_next_version_number = AsyncMock()
        self.create_version = AsyncMock()
        self.update_current_version = AsyncMock()


class MockStorageService:
    def __init__(self):
        self.upload_document_output = MagicMock()
        self.file_exists = MagicMock()


class MockAuditRepo:
    def __init__(self):
        self.create = AsyncMock()


@pytest.fixture
def fixed_document_id() -> UUID:
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def fixed_version_id() -> UUID:
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def sample_content() -> bytes:
    return b"Sample document content for testing"


@pytest.fixture
def sample_document(fixed_document_id):
    doc = MagicMock()
    doc.id = fixed_document_id
    doc.current_version = 0
    return doc


@pytest.fixture
def sample_version(fixed_version_id, fixed_document_id):
    version = MagicMock()
    version.id = fixed_version_id
    version.document_id = fixed_document_id
    version.version_number = 1
    version.output_doc_path = "documents/test/1/output.docx"
    version.created_at = datetime(2025, 1, 15, 10, 0, 0)
    return version


class TestVersioningDeterminism:

    @pytest.mark.asyncio
    async def test_identical_content_returns_same_version(
        self,
        fixed_document_id,
        fixed_version_id,
        sample_content,
        sample_document,
        sample_version,
    ):
        repo = MockVersioningRepo()
        storage = MockStorageService()
        audit = MockAuditRepo()

        repo.get_document = AsyncMock(return_value=sample_document)
        repo.get_version_by_content_hash = AsyncMock(return_value=sample_version)

        service = DocumentVersioningService(
            repository=repo,
            storage=storage,
            audit_repo=audit,
        )

        request = VersionCreateRequest(
            document_id=fixed_document_id,
            content=sample_content,
            generation_metadata={"test": "data"},
        )

        result = await service.create_version(request)

        assert result.success is True
        assert result.is_duplicate is True
        assert result.version_id == fixed_version_id
        assert result.existing_version_number == 1

    @pytest.mark.asyncio
    async def test_duplicate_detection_uses_content_hash(
        self,
        fixed_document_id,
        sample_content,
        sample_document,
    ):
        repo = MockVersioningRepo()
        storage = MockStorageService()
        audit = MockAuditRepo()

        repo.get_document = AsyncMock(return_value=sample_document)
        repo.get_version_by_content_hash = AsyncMock(return_value=None)
        repo.get_next_version_number = AsyncMock(return_value=1)
        repo.create_version = AsyncMock(
            side_effect=lambda **kwargs: MagicMock(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                version_number=kwargs.get("version_number"),
                created_at=datetime(2025, 1, 15, 10, 0, 0),
            )
        )
        repo.update_current_version = AsyncMock()
        storage.upload_document_output = MagicMock(return_value="documents/test/1/output.docx")
        storage.file_exists = MagicMock(return_value=True)
        audit.create = AsyncMock(return_value=MagicMock())

        service = DocumentVersioningService(
            repository=repo,
            storage=storage,
            audit_repo=audit,
        )

        request = VersionCreateRequest(
            document_id=fixed_document_id,
            content=sample_content,
            generation_metadata={"test": "data"},
        )

        await service.create_version(request)

        content_hash = request.get_content_hash()
        repo.get_version_by_content_hash.assert_called_once_with(fixed_document_id, content_hash)

    @pytest.mark.asyncio
    async def test_content_hash_is_deterministic(
        self,
        fixed_document_id,
        sample_content,
    ):
        request1 = VersionCreateRequest(
            document_id=fixed_document_id,
            content=sample_content,
            generation_metadata={"test": "data"},
        )

        request2 = VersionCreateRequest(
            document_id=fixed_document_id,
            content=sample_content,
            generation_metadata={"test": "data"},
        )

        hash1 = request1.get_content_hash()
        hash2 = request2.get_content_hash()

        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_different_content_produces_different_hash(
        self,
        fixed_document_id,
    ):
        request1 = VersionCreateRequest(
            document_id=fixed_document_id,
            content=b"Content A",
            generation_metadata={"test": "data"},
        )

        request2 = VersionCreateRequest(
            document_id=fixed_document_id,
            content=b"Content B",
            generation_metadata={"test": "data"},
        )

        hash1 = request1.get_content_hash()
        hash2 = request2.get_content_hash()

        assert hash1 != hash2


class TestVersionNumberDeterminism:

    @pytest.mark.asyncio
    async def test_version_numbers_are_sequential(
        self,
        fixed_document_id,
        sample_document,
    ):
        repo = MockVersioningRepo()
        storage = MockStorageService()
        audit = MockAuditRepo()

        version_numbers_created = []

        repo.get_document = AsyncMock(return_value=sample_document)
        repo.get_version_by_content_hash = AsyncMock(return_value=None)

        call_count = 0

        async def mock_next_version(doc_id):
            nonlocal call_count
            call_count += 1
            return call_count

        repo.get_next_version_number = mock_next_version
        repo.create_version = AsyncMock(
            side_effect=lambda **kwargs: MagicMock(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                version_number=kwargs.get("version_number"),
                created_at=datetime(2025, 1, 15, 10, 0, 0),
            )
        )
        repo.update_current_version = AsyncMock()
        storage.upload_document_output = MagicMock(return_value="documents/test/1/output.docx")
        storage.file_exists = MagicMock(return_value=True)
        audit.create = AsyncMock(return_value=MagicMock())

        service = DocumentVersioningService(
            repository=repo,
            storage=storage,
            audit_repo=audit,
        )

        for i in range(3):
            request = VersionCreateRequest(
                document_id=fixed_document_id,
                content=f"Content {i}".encode(),
                generation_metadata={"iteration": i},
            )
            result = await service.create_version(request)
            if result.success and not result.is_duplicate:
                version_numbers_created.append(result.version_number)

        assert version_numbers_created == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_duplicate_content_does_not_increment_version(
        self,
        fixed_document_id,
        fixed_version_id,
        sample_content,
        sample_document,
        sample_version,
    ):
        repo = MockVersioningRepo()
        storage = MockStorageService()
        audit = MockAuditRepo()

        repo.get_document = AsyncMock(return_value=sample_document)
        repo.get_version_by_content_hash = AsyncMock(return_value=sample_version)

        service = DocumentVersioningService(
            repository=repo,
            storage=storage,
            audit_repo=audit,
        )

        request = VersionCreateRequest(
            document_id=fixed_document_id,
            content=sample_content,
            generation_metadata={"test": "data"},
        )

        result = await service.create_version(request)

        assert result.success is True
        assert result.is_duplicate is True
        repo.get_next_version_number.assert_not_called()
        repo.create_version.assert_not_called()


class TestStorageDeterminism:

    @pytest.mark.asyncio
    async def test_storage_path_is_deterministic(
        self,
        fixed_document_id,
        sample_content,
        sample_document,
    ):
        repo = MockVersioningRepo()
        storage = MockStorageService()
        audit = MockAuditRepo()

        upload_paths = []

        def capture_upload(document_id, version, file_obj):
            path = f"documents/{document_id}/{version}/output.docx"
            upload_paths.append(path)
            return path

        repo.get_document = AsyncMock(return_value=sample_document)
        repo.get_version_by_content_hash = AsyncMock(return_value=None)
        repo.get_next_version_number = AsyncMock(return_value=1)
        repo.create_version = AsyncMock(
            side_effect=lambda **kwargs: MagicMock(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                version_number=kwargs.get("version_number"),
                created_at=datetime(2025, 1, 15, 10, 0, 0),
            )
        )
        repo.update_current_version = AsyncMock()
        storage.upload_document_output = capture_upload
        storage.file_exists = MagicMock(return_value=True)
        audit.create = AsyncMock(return_value=MagicMock())

        service = DocumentVersioningService(
            repository=repo,
            storage=storage,
            audit_repo=audit,
        )

        request = VersionCreateRequest(
            document_id=fixed_document_id,
            content=sample_content,
            generation_metadata={"test": "data"},
        )

        await service.create_version(request)

        assert len(upload_paths) == 1
        expected_path = f"documents/{fixed_document_id}/1/output.docx"
        assert upload_paths[0] == expected_path
