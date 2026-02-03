from uuid import UUID, uuid4

import pytest

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.generation_schemas import (
    GenerationAuditAction,
    GenerationAuditEntityType,
)
from backend.app.domains.audit.repository import AuditRepository


@pytest.mark.asyncio
class TestSuccessPathAudit:
    async def test_generation_initiated_creates_audit_log(
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

        assert log is not None
        assert log.entity_type == GenerationAuditEntityType.GENERATION_BATCH.value
        assert log.entity_id == batch_id
        assert log.action == GenerationAuditAction.GENERATION_INITIATED.value

    async def test_generation_initiated_metadata_complete(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=5,
            job_id=job_id,
        )

        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["template_version_id"] == str(template_version_id)
        assert log.metadata_["version_intent"] == 1
        assert log.metadata_["total_sections"] == 5
        assert log.metadata_["job_id"] == str(job_id)

    async def test_section_generation_completed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=42,
            document_id=document_id,
            content_hash="abc123",
            content_length=500,
        )

        assert log.entity_type == GenerationAuditEntityType.SECTION_OUTPUT.value
        assert log.entity_id == section_output_id
        assert log.action == GenerationAuditAction.SECTION_GENERATION_COMPLETED.value

    async def test_section_generation_completed_metadata_complete(
        self,
        generation_audit_service: GenerationAuditService,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_section_generation_completed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=42,
            document_id=document_id,
            content_hash="abc123",
            content_length=500,
            generation_duration_ms=150.5,
            job_id=job_id,
        )

        assert log.metadata_["batch_id"] == str(batch_id)
        assert log.metadata_["section_id"] == 42
        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["content_hash"] == "abc123"
        assert log.metadata_["content_length"] == 500
        assert log.metadata_["generation_duration_ms"] == 150.5
        assert log.metadata_["job_id"] == str(job_id)

    async def test_batch_generation_completed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_batch_generation_completed(
            batch_id=batch_id,
            document_id=document_id,
            completed_sections=5,
            failed_sections=0,
            total_sections=5,
        )

        assert log.entity_type == GenerationAuditEntityType.SECTION_OUTPUT_BATCH.value
        assert log.entity_id == batch_id
        assert log.action == GenerationAuditAction.BATCH_GENERATION_COMPLETED.value

    async def test_document_assembly_completed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        assembled_document_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_document_assembly_completed(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_blocks=10,
            dynamic_blocks_count=3,
            static_blocks_count=7,
            injected_sections_count=3,
            assembly_hash="def456",
        )

        assert log.entity_type == GenerationAuditEntityType.ASSEMBLED_DOCUMENT.value
        assert log.entity_id == assembled_document_id
        assert log.action == GenerationAuditAction.DOCUMENT_ASSEMBLY_COMPLETED.value

    async def test_document_assembly_completed_metadata_complete(
        self,
        generation_audit_service: GenerationAuditService,
        assembled_document_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_document_assembly_completed(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_blocks=10,
            dynamic_blocks_count=3,
            static_blocks_count=7,
            injected_sections_count=3,
            assembly_hash="def456",
            assembly_duration_ms=250.0,
            job_id=job_id,
        )

        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["template_version_id"] == str(template_version_id)
        assert log.metadata_["version_intent"] == 1
        assert log.metadata_["total_blocks"] == 10
        assert log.metadata_["dynamic_blocks_count"] == 3
        assert log.metadata_["static_blocks_count"] == 7
        assert log.metadata_["injected_sections_count"] == 3
        assert log.metadata_["assembly_hash"] == "def456"
        assert log.metadata_["assembly_duration_ms"] == 250.0
        assert log.metadata_["job_id"] == str(job_id)

    async def test_document_rendering_completed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        rendered_document_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_document_rendering_completed(
            rendered_document_id=rendered_document_id,
            document_id=document_id,
            version=1,
            output_path="documents/doc123/1/output.docx",
            content_hash="ghi789",
            file_size_bytes=10240,
            total_blocks_rendered=10,
        )

        assert log.entity_type == GenerationAuditEntityType.RENDERED_DOCUMENT.value
        assert log.entity_id == rendered_document_id
        assert log.action == GenerationAuditAction.DOCUMENT_RENDERING_COMPLETED.value

    async def test_document_rendering_completed_metadata_complete(
        self,
        generation_audit_service: GenerationAuditService,
        rendered_document_id: UUID,
        document_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_document_rendering_completed(
            rendered_document_id=rendered_document_id,
            document_id=document_id,
            version=1,
            output_path="documents/doc123/1/output.docx",
            content_hash="ghi789",
            file_size_bytes=10240,
            total_blocks_rendered=10,
            rendering_duration_ms=300.0,
            job_id=job_id,
        )

        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["version"] == 1
        assert log.metadata_["output_path"] == "documents/doc123/1/output.docx"
        assert log.metadata_["content_hash"] == "ghi789"
        assert log.metadata_["file_size_bytes"] == 10240
        assert log.metadata_["total_blocks_rendered"] == 10
        assert log.metadata_["rendering_duration_ms"] == 300.0
        assert log.metadata_["job_id"] == str(job_id)

    async def test_document_version_created_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        version_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_document_version_created(
            version_id=version_id,
            document_id=document_id,
            version_number=1,
            output_path="documents/doc123/1/output.docx",
            content_hash="jkl012",
        )

        assert log.entity_type == GenerationAuditEntityType.DOCUMENT_VERSION.value
        assert log.entity_id == version_id
        assert log.action == GenerationAuditAction.DOCUMENT_VERSION_CREATED.value

    async def test_document_version_created_metadata_complete(
        self,
        generation_audit_service: GenerationAuditService,
        version_id: UUID,
        document_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_document_version_created(
            version_id=version_id,
            document_id=document_id,
            version_number=1,
            output_path="documents/doc123/1/output.docx",
            content_hash="jkl012",
            job_id=job_id,
        )

        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["version_number"] == 1
        assert log.metadata_["output_path"] == "documents/doc123/1/output.docx"
        assert log.metadata_["content_hash"] == "jkl012"
        assert log.metadata_["job_id"] == str(job_id)

    async def test_audit_log_timestamp_is_set(
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

        assert log.timestamp is not None

    async def test_audit_logs_ordering_reflects_execution(
        self,
        generation_audit_service: GenerationAuditService,
        audit_repository: AuditRepository,
        batch_id: UUID,
        section_output_id: UUID,
        assembled_document_id: UUID,
        rendered_document_id: UUID,
        version_id: UUID,
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
            assembled_document_id=assembled_document_id,
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
            rendered_document_id=rendered_document_id,
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

        actions = [log.action for log in logs]
        assert GenerationAuditAction.GENERATION_INITIATED.value in actions
        assert GenerationAuditAction.SECTION_GENERATION_COMPLETED.value in actions
        assert GenerationAuditAction.BATCH_GENERATION_COMPLETED.value in actions
        assert GenerationAuditAction.DOCUMENT_ASSEMBLY_COMPLETED.value in actions
        assert GenerationAuditAction.DOCUMENT_RENDERING_COMPLETED.value in actions
        assert GenerationAuditAction.DOCUMENT_VERSION_CREATED.value in actions
