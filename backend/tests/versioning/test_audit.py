import pytest

from backend.app.domains.document.models import Document
from backend.app.domains.versioning.schemas import VersionCreateRequest
from backend.app.domains.versioning.service import DocumentVersioningService


@pytest.mark.asyncio
class TestAuditLogging:
    async def test_audit_log_created_for_version_creation(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)
        assert result.success is True

        logs = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            entity_id=result.version_id,
            action="CREATE",
        )

        assert len(logs) == 1
        log = logs[0]
        assert log.entity_type == "DOCUMENT_VERSION"
        assert log.entity_id == result.version_id
        assert log.action == "CREATE"

    async def test_audit_log_metadata_is_complete(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)
        assert result.success is True

        logs = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            entity_id=result.version_id,
            action="CREATE",
        )

        assert len(logs) == 1
        log = logs[0]

        assert "document_id" in log.metadata_
        assert "version_number" in log.metadata_
        assert "output_path" in log.metadata_
        assert "content_hash" in log.metadata_

        assert log.metadata_["document_id"] == str(sample_document.id)
        assert log.metadata_["version_number"] == result.version_number
        assert log.metadata_["output_path"] == result.output_path
        assert log.metadata_["content_hash"] == result.content_hash

    async def test_audit_log_created_for_current_version_update(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)
        assert result.success is True

        logs = await audit_repository.query(
            entity_type="DOCUMENT",
            entity_id=sample_document.id,
            action="UPDATE_CURRENT_VERSION",
        )

        assert len(logs) == 1
        log = logs[0]
        assert log.entity_type == "DOCUMENT"
        assert log.entity_id == sample_document.id
        assert log.action == "UPDATE_CURRENT_VERSION"
        assert log.metadata_["new_current_version"] == result.version_number

    async def test_audit_logs_for_multiple_versions(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_metadata: dict,
        audit_repository,
    ):
        for i in range(3):
            content = f"Version {i + 1} content".encode()
            request = VersionCreateRequest(
                document_id=sample_document.id,
                content=content,
                generation_metadata={**sample_metadata, "iteration": i},
            )
            await versioning_service.create_version(request)

        version_logs = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            action="CREATE",
        )

        update_logs = await audit_repository.query(
            entity_type="DOCUMENT",
            action="UPDATE_CURRENT_VERSION",
        )

        assert len(version_logs) == 3
        assert len(update_logs) == 3

    async def test_audit_log_timestamp_is_set(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)
        assert result.success is True

        logs = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            entity_id=result.version_id,
        )

        assert len(logs) == 1
        assert logs[0].timestamp is not None

    async def test_no_audit_log_on_duplicate_detection(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result1 = await versioning_service.create_version(request)
        assert result1.success is True

        logs_after_first = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            action="CREATE",
        )
        initial_count = len(logs_after_first)

        result2 = await versioning_service.create_version(request)
        assert result2.success is True
        assert result2.is_duplicate is True

        logs_after_second = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            action="CREATE",
        )

        assert len(logs_after_second) == initial_count

    async def test_audit_log_entity_id_matches_version_id(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        request = VersionCreateRequest(
            document_id=sample_document.id,
            content=sample_content,
            generation_metadata=sample_metadata,
        )

        result = await versioning_service.create_version(request)
        assert result.success is True

        logs = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            entity_id=result.version_id,
        )

        assert len(logs) == 1
        assert logs[0].entity_id == result.version_id

    async def test_audit_logs_traceable_to_document(
        self,
        versioning_service: DocumentVersioningService,
        sample_document: Document,
        sample_content: bytes,
        sample_content_different: bytes,
        sample_metadata: dict,
        audit_repository,
    ):
        logs = await audit_repository.query(
            entity_type="DOCUMENT_VERSION",
            action="CREATE",
        )

        document_ids = [log.metadata_["document_id"] for log in logs]
        assert all(did == str(sample_document.id) for did in document_ids)
