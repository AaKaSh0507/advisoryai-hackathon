from typing import Any
from uuid import UUID

from backend.app.domains.audit.generation_schemas import (
    GenerationAuditAction,
    GenerationAuditEntityType,
)
from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.repository import AuditRepository
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.audit.generation_audit_service")


class GenerationAuditService:
    def __init__(self, audit_repo: AuditRepository):
        self.audit_repo = audit_repo

    async def log_generation_initiated(
        self,
        batch_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        version_intent: int,
        total_sections: int,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "template_version_id": str(template_version_id),
            "version_intent": version_intent,
            "total_sections": total_sections,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.GENERATION_BATCH,
            entity_id=batch_id,
            action=GenerationAuditAction.GENERATION_INITIATED,
            metadata=metadata,
        )

    async def log_section_generation_completed(
        self,
        section_output_id: UUID,
        batch_id: UUID,
        section_id: int,
        document_id: UUID,
        content_hash: str,
        content_length: int,
        generation_duration_ms: float | None = None,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "batch_id": str(batch_id),
            "section_id": section_id,
            "document_id": str(document_id),
            "content_hash": content_hash,
            "content_length": content_length,
        }
        if generation_duration_ms is not None:
            metadata["generation_duration_ms"] = generation_duration_ms
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.SECTION_OUTPUT,
            entity_id=section_output_id,
            action=GenerationAuditAction.SECTION_GENERATION_COMPLETED,
            metadata=metadata,
        )

    async def log_section_generation_failed(
        self,
        section_output_id: UUID,
        batch_id: UUID,
        section_id: int,
        document_id: UUID,
        error_code: str,
        error_message: str,
        retry_count: int = 0,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "batch_id": str(batch_id),
            "section_id": section_id,
            "document_id": str(document_id),
            "error_code": error_code,
            "error_message": error_message,
            "retry_count": retry_count,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.SECTION_OUTPUT,
            entity_id=section_output_id,
            action=GenerationAuditAction.SECTION_GENERATION_FAILED,
            metadata=metadata,
        )

    async def log_batch_generation_completed(
        self,
        batch_id: UUID,
        document_id: UUID,
        completed_sections: int,
        failed_sections: int,
        total_sections: int,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "completed_sections": completed_sections,
            "failed_sections": failed_sections,
            "total_sections": total_sections,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.SECTION_OUTPUT_BATCH,
            entity_id=batch_id,
            action=GenerationAuditAction.BATCH_GENERATION_COMPLETED,
            metadata=metadata,
        )

    async def log_batch_generation_failed(
        self,
        batch_id: UUID,
        document_id: UUID,
        error_code: str,
        error_message: str,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "error_code": error_code,
            "error_message": error_message,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.SECTION_OUTPUT_BATCH,
            entity_id=batch_id,
            action=GenerationAuditAction.BATCH_GENERATION_FAILED,
            metadata=metadata,
        )

    async def log_document_assembly_completed(
        self,
        assembled_document_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        version_intent: int,
        total_blocks: int,
        dynamic_blocks_count: int,
        static_blocks_count: int,
        injected_sections_count: int,
        assembly_hash: str,
        assembly_duration_ms: float | None = None,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "template_version_id": str(template_version_id),
            "version_intent": version_intent,
            "total_blocks": total_blocks,
            "dynamic_blocks_count": dynamic_blocks_count,
            "static_blocks_count": static_blocks_count,
            "injected_sections_count": injected_sections_count,
            "assembly_hash": assembly_hash,
        }
        if assembly_duration_ms is not None:
            metadata["assembly_duration_ms"] = assembly_duration_ms
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.ASSEMBLED_DOCUMENT,
            entity_id=assembled_document_id,
            action=GenerationAuditAction.DOCUMENT_ASSEMBLY_COMPLETED,
            metadata=metadata,
        )

    async def log_document_assembly_failed(
        self,
        assembled_document_id: UUID,
        document_id: UUID,
        template_version_id: UUID,
        version_intent: int,
        error_code: str,
        error_message: str,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "template_version_id": str(template_version_id),
            "version_intent": version_intent,
            "error_code": error_code,
            "error_message": error_message,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.ASSEMBLED_DOCUMENT,
            entity_id=assembled_document_id,
            action=GenerationAuditAction.DOCUMENT_ASSEMBLY_FAILED,
            metadata=metadata,
        )

    async def log_document_rendering_completed(
        self,
        rendered_document_id: UUID,
        document_id: UUID,
        version: int,
        output_path: str,
        content_hash: str,
        file_size_bytes: int,
        total_blocks_rendered: int,
        rendering_duration_ms: float | None = None,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "version": version,
            "output_path": output_path,
            "content_hash": content_hash,
            "file_size_bytes": file_size_bytes,
            "total_blocks_rendered": total_blocks_rendered,
        }
        if rendering_duration_ms is not None:
            metadata["rendering_duration_ms"] = rendering_duration_ms
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.RENDERED_DOCUMENT,
            entity_id=rendered_document_id,
            action=GenerationAuditAction.DOCUMENT_RENDERING_COMPLETED,
            metadata=metadata,
        )

    async def log_document_rendering_failed(
        self,
        rendered_document_id: UUID,
        document_id: UUID,
        version: int,
        error_code: str,
        error_message: str,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "version": version,
            "error_code": error_code,
            "error_message": error_message,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.RENDERED_DOCUMENT,
            entity_id=rendered_document_id,
            action=GenerationAuditAction.DOCUMENT_RENDERING_FAILED,
            metadata=metadata,
        )

    async def log_document_version_created(
        self,
        version_id: UUID,
        document_id: UUID,
        version_number: int,
        output_path: str,
        content_hash: str,
        job_id: UUID | None = None,
    ) -> AuditLog:
        metadata = {
            "document_id": str(document_id),
            "version_number": version_number,
            "output_path": output_path,
            "content_hash": content_hash,
        }
        if job_id:
            metadata["job_id"] = str(job_id)

        return await self._create_audit_log(
            entity_type=GenerationAuditEntityType.DOCUMENT_VERSION,
            entity_id=version_id,
            action=GenerationAuditAction.DOCUMENT_VERSION_CREATED,
            metadata=metadata,
        )

    async def query_by_document_id(
        self,
        document_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        all_logs = await self.audit_repo.query(skip=0, limit=10000)
        filtered = [log for log in all_logs if log.metadata_.get("document_id") == str(document_id)]
        return list(filtered[skip : skip + limit])

    async def query_by_template_id(
        self,
        template_version_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        all_logs = await self.audit_repo.query(skip=0, limit=10000)
        filtered = [
            log
            for log in all_logs
            if log.metadata_.get("template_version_id") == str(template_version_id)
        ]
        return list(filtered[skip : skip + limit])

    async def query_by_version_number(
        self,
        document_id: UUID,
        version_number: int,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        all_logs = await self.audit_repo.query(skip=0, limit=10000)
        filtered = [
            log
            for log in all_logs
            if (
                log.metadata_.get("document_id") == str(document_id)
                and (
                    log.metadata_.get("version_number") == version_number
                    or log.metadata_.get("version") == version_number
                    or log.metadata_.get("version_intent") == version_number
                )
            )
        ]
        return list(filtered[skip : skip + limit])

    async def query_by_job_id(
        self,
        job_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        all_logs = await self.audit_repo.query(skip=0, limit=10000)
        filtered = [log for log in all_logs if log.metadata_.get("job_id") == str(job_id)]
        return list(filtered[skip : skip + limit])

    async def _create_audit_log(
        self,
        entity_type: GenerationAuditEntityType,
        entity_id: UUID,
        action: GenerationAuditAction,
        metadata: dict[str, Any],
    ) -> AuditLog:
        audit_log = AuditLog(
            entity_type=entity_type.value,
            entity_id=entity_id,
            action=action.value,
            metadata_=metadata,
        )
        return await self.audit_repo.create(audit_log)
