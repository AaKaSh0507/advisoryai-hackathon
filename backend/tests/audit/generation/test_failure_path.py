from uuid import UUID, uuid4

import pytest

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.generation_schemas import (
    GenerationAuditAction,
    GenerationAuditEntityType,
)


@pytest.mark.asyncio
class TestFailurePathAudit:
    async def test_section_generation_failed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_section_generation_failed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=42,
            document_id=document_id,
            error_code="LLM_TIMEOUT",
            error_message="LLM request timed out after 30 seconds",
        )

        assert log.entity_type == GenerationAuditEntityType.SECTION_OUTPUT.value
        assert log.entity_id == section_output_id
        assert log.action == GenerationAuditAction.SECTION_GENERATION_FAILED.value

    async def test_section_generation_failed_captures_error_context(
        self,
        generation_audit_service: GenerationAuditService,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_section_generation_failed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=42,
            document_id=document_id,
            error_code="VALIDATION_FAILED",
            error_message="Content exceeds maximum length",
            retry_count=3,
            job_id=job_id,
        )

        assert log.metadata_["error_code"] == "VALIDATION_FAILED"
        assert log.metadata_["error_message"] == "Content exceeds maximum length"
        assert log.metadata_["retry_count"] == 3
        assert log.metadata_["batch_id"] == str(batch_id)
        assert log.metadata_["section_id"] == 42
        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["job_id"] == str(job_id)

    async def test_batch_generation_failed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_batch_generation_failed(
            batch_id=batch_id,
            document_id=document_id,
            error_code="BATCH_TIMEOUT",
            error_message="Batch processing exceeded time limit",
        )

        assert log.entity_type == GenerationAuditEntityType.SECTION_OUTPUT_BATCH.value
        assert log.entity_id == batch_id
        assert log.action == GenerationAuditAction.BATCH_GENERATION_FAILED.value

    async def test_batch_generation_failed_captures_error_context(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_batch_generation_failed(
            batch_id=batch_id,
            document_id=document_id,
            error_code="BATCH_TIMEOUT",
            error_message="Batch processing exceeded time limit",
            job_id=job_id,
        )

        assert log.metadata_["error_code"] == "BATCH_TIMEOUT"
        assert log.metadata_["error_message"] == "Batch processing exceeded time limit"
        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["job_id"] == str(job_id)

    async def test_document_assembly_failed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        assembled_document_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
    ):
        log = await generation_audit_service.log_document_assembly_failed(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            error_code="STRUCTURAL_MISMATCH",
            error_message="Block order mismatch detected",
        )

        assert log.entity_type == GenerationAuditEntityType.ASSEMBLED_DOCUMENT.value
        assert log.entity_id == assembled_document_id
        assert log.action == GenerationAuditAction.DOCUMENT_ASSEMBLY_FAILED.value

    async def test_document_assembly_failed_captures_error_context(
        self,
        generation_audit_service: GenerationAuditService,
        assembled_document_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_document_assembly_failed(
            assembled_document_id=assembled_document_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            error_code="STRUCTURAL_MISMATCH",
            error_message="Block order mismatch detected",
            job_id=job_id,
        )

        assert log.metadata_["error_code"] == "STRUCTURAL_MISMATCH"
        assert log.metadata_["error_message"] == "Block order mismatch detected"
        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["template_version_id"] == str(template_version_id)
        assert log.metadata_["version_intent"] == 1
        assert log.metadata_["job_id"] == str(job_id)

    async def test_document_rendering_failed_creates_audit_log(
        self,
        generation_audit_service: GenerationAuditService,
        rendered_document_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_document_rendering_failed(
            rendered_document_id=rendered_document_id,
            document_id=document_id,
            version=1,
            error_code="RENDERING_FAILED",
            error_message="Failed to create docx file",
        )

        assert log.entity_type == GenerationAuditEntityType.RENDERED_DOCUMENT.value
        assert log.entity_id == rendered_document_id
        assert log.action == GenerationAuditAction.DOCUMENT_RENDERING_FAILED.value

    async def test_document_rendering_failed_captures_error_context(
        self,
        generation_audit_service: GenerationAuditService,
        rendered_document_id: UUID,
        document_id: UUID,
        job_id: UUID,
    ):
        log = await generation_audit_service.log_document_rendering_failed(
            rendered_document_id=rendered_document_id,
            document_id=document_id,
            version=1,
            error_code="RENDERING_FAILED",
            error_message="Failed to create docx file",
            job_id=job_id,
        )

        assert log.metadata_["error_code"] == "RENDERING_FAILED"
        assert log.metadata_["error_message"] == "Failed to create docx file"
        assert log.metadata_["document_id"] == str(document_id)
        assert log.metadata_["version"] == 1
        assert log.metadata_["job_id"] == str(job_id)

    async def test_failure_logs_have_timestamp(
        self,
        generation_audit_service: GenerationAuditService,
        section_output_id: UUID,
        batch_id: UUID,
        document_id: UUID,
    ):
        log = await generation_audit_service.log_section_generation_failed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=42,
            document_id=document_id,
            error_code="LLM_ERROR",
            error_message="LLM service unavailable",
        )

        assert log.timestamp is not None

    async def test_partial_failure_captured_accurately(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
    ):
        section_id_1 = uuid4()
        section_id_2 = uuid4()

        await generation_audit_service.log_section_generation_completed(
            section_output_id=section_id_1,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            content_hash="hash1",
            content_length=100,
        )

        await generation_audit_service.log_section_generation_failed(
            section_output_id=section_id_2,
            batch_id=batch_id,
            section_id=2,
            document_id=document_id,
            error_code="VALIDATION_FAILED",
            error_message="Content too short",
        )

        await generation_audit_service.log_batch_generation_completed(
            batch_id=batch_id,
            document_id=document_id,
            completed_sections=1,
            failed_sections=1,
            total_sections=2,
        )

        logs = await generation_audit_service.query_by_document_id(document_id)

        completed_logs = [
            log
            for log in logs
            if log.action == GenerationAuditAction.SECTION_GENERATION_COMPLETED.value
        ]
        failed_logs = [
            log
            for log in logs
            if log.action == GenerationAuditAction.SECTION_GENERATION_FAILED.value
        ]
        batch_logs = [
            log
            for log in logs
            if log.action == GenerationAuditAction.BATCH_GENERATION_COMPLETED.value
        ]

        assert len(completed_logs) == 1
        assert len(failed_logs) == 1
        assert len(batch_logs) == 1

        batch_log = batch_logs[0]
        assert batch_log.metadata_["completed_sections"] == 1
        assert batch_log.metadata_["failed_sections"] == 1
        assert batch_log.metadata_["total_sections"] == 2

    async def test_no_missing_audit_entries_on_failure(
        self,
        generation_audit_service: GenerationAuditService,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        section_output_id: UUID,
    ):
        await generation_audit_service.log_generation_initiated(
            batch_id=batch_id,
            document_id=document_id,
            template_version_id=template_version_id,
            version_intent=1,
            total_sections=1,
        )

        await generation_audit_service.log_section_generation_failed(
            section_output_id=section_output_id,
            batch_id=batch_id,
            section_id=1,
            document_id=document_id,
            error_code="LLM_ERROR",
            error_message="Service unavailable",
            retry_count=3,
        )

        await generation_audit_service.log_batch_generation_failed(
            batch_id=batch_id,
            document_id=document_id,
            error_code="ALL_SECTIONS_FAILED",
            error_message="All section generations failed",
        )

        logs = await generation_audit_service.query_by_document_id(document_id)

        assert len(logs) == 3

        actions = [log.action for log in logs]
        assert GenerationAuditAction.GENERATION_INITIATED.value in actions
        assert GenerationAuditAction.SECTION_GENERATION_FAILED.value in actions
        assert GenerationAuditAction.BATCH_GENERATION_FAILED.value in actions
