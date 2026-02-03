from uuid import UUID, uuid4

import pytest

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.generation_schemas import (
    GenerationAuditAction,
    GenerationAuditEntityType,
)
from backend.app.domains.audit.repository import AuditRepository


@pytest.mark.asyncio
class TestAtomicity:
    async def test_audit_log_persisted_with_unique_id(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        assert log.id is not None

        retrieved_logs = await audit_repository.query(entity_id=batch_id)
        assert len(retrieved_logs) == 1
        assert retrieved_logs[0].id == log.id

    async def test_multiple_audit_logs_have_unique_ids(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log1 = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        section_output_id = uuid4()
        log2 = await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        assert log1.id != log2.id

    async def test_failure_audit_log_reflects_failure_accurately(
        self,
        generation_audit_service: GenerationAuditService,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
    ):
        error_code = "VALIDATION_FAILED"
        error_message = "Content validation failed: too short"

        log = await generation_audit_service.log_section_generation_failed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=42,
            document_id=document_id,
            error_code=error_code,
            error_message=error_message,
            retry_count=2,
        )

        assert log.action == GenerationAuditAction.SECTION_GENERATION_FAILED.value
        assert log.metadata_["error_code"] == error_code
        assert log.metadata_["error_message"] == error_message
        assert log.metadata_["retry_count"] == 2

    async def test_no_orphan_audit_records(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=1,
        )

        section_output_id = uuid4()
        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        all_logs = await audit_repository.query(limit=1000)

        for log in all_logs:
            assert log.entity_id is not None
            assert log.entity_type is not None
            assert log.action is not None
            assert log.metadata_ is not None
            assert log.timestamp is not None

    async def test_audit_log_entity_id_matches_operation(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        assert log.entity_id == batch_id
        assert log.entity_type == GenerationAuditEntityType.GENERATION_BATCH.value

    async def test_audit_metadata_document_id_matches(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
        )

        assert log.metadata_["document_id"] == str(document_id)

    async def test_sequential_operations_all_logged(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        document_id: UUID,
        template_version_id: UUID,
    ):
        batch_id = uuid4()
        section_output_id = uuid4()
        assembled_id = uuid4()
        rendered_id = uuid4()
        version_id = uuid4()

        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=1,
        )

        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        await generation_audit_service.log_batch_generation_completed(
            batch_id=batch_id,
            document_id=document_id,
            completed_sections=1,
            failed_sections=0,
            total_sections=1,
        )

        await generation_audit_service.log_document_assembly_completed(
            assembled_document_id=assembled_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_blocks=5,
            dynamic_blocks_count=1,
            static_blocks_count=4,
            injected_sections_count=1,
            assembly_hash="assemblyhash",
        )

        await generation_audit_service.log_document_rendering_completed(
            rendered_document_id=rendered_id,
            document_id=document_id,
            version=1,
            output_path="path/to/output.docx",
            content_hash="renderhash",
            file_size_bytes=5000,
            total_blocks_rendered=5,
        )

        await generation_audit_service.log_document_version_created(
            version_id=version_id,
            document_id=document_id,
            version_number=1,
            output_path="path/to/output.docx",
            content_hash="versionhash",
        )

        logs = await generation_audit_service.query_by_document_id(document_id)

        assert len(logs) == 6

        expected_actions = [
            GenerationAuditAction.GENERATION_INITIATED.value,
            GenerationAuditAction.SECTION_GENERATION_COMPLETED.value,
            GenerationAuditAction.BATCH_GENERATION_COMPLETED.value,
            GenerationAuditAction.DOCUMENT_ASSEMBLY_COMPLETED.value,
            GenerationAuditAction.DOCUMENT_RENDERING_COMPLETED.value,
            GenerationAuditAction.DOCUMENT_VERSION_CREATED.value,
        ]

        logged_actions = [log.action for log in logs]
        for action in expected_actions:
            assert action in logged_actions
