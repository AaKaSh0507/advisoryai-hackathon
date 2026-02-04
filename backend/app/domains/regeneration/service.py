import hashlib
import json
from typing import Any
from uuid import UUID

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.document.models import Document
from backend.app.domains.document.repository import DocumentRepository
from backend.app.domains.generation.repository import GenerationInputRepository
from backend.app.domains.generation.section_output_models import SectionOutputBatch
from backend.app.domains.generation.section_output_repository import SectionOutputRepository
from backend.app.domains.regeneration.schemas import (
    FullRegenerationRequest,
    RegenerationIntent,
    RegenerationResult,
    RegenerationScope,
    RegenerationSectionResult,
    RegenerationStatus,
    RegenerationStrategy,
    SectionRegenerationRequest,
    SectionRegenerationTarget,
    TemplateUpdateRegenerationRequest,
    VersionTransition,
)
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository
from backend.app.domains.template.repository import TemplateRepository
from backend.app.infrastructure.datetime_utils import utc_now
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.regeneration.service")


class RegenerationError(Exception):

    def __init__(self, message: str, code: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class DocumentNotFoundError(RegenerationError):

    def __init__(self, document_id: UUID):
        super().__init__(
            message=f"Document {document_id} not found",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": str(document_id)},
        )


class NoVersionExistsError(RegenerationError):

    def __init__(self, document_id: UUID):
        super().__init__(
            message=f"Document {document_id} has no versions to regenerate from",
            code="NO_VERSION_EXISTS",
            details={"document_id": str(document_id)},
        )


class SectionNotFoundError(RegenerationError):

    def __init__(self, section_id: int, document_id: UUID):
        super().__init__(
            message=f"Section {section_id} not found for document {document_id}",
            code="SECTION_NOT_FOUND",
            details={"section_id": section_id, "document_id": str(document_id)},
        )


class StaticSectionError(RegenerationError):

    def __init__(self, section_id: int):
        super().__init__(
            message=f"Section {section_id} is STATIC and cannot be regenerated",
            code="STATIC_SECTION",
            details={"section_id": section_id},
        )


class TemplateVersionMismatchError(RegenerationError):

    def __init__(self, document_id: UUID, expected: UUID, actual: UUID):
        super().__init__(
            message=f"Template version mismatch for document {document_id}",
            code="TEMPLATE_VERSION_MISMATCH",
            details={
                "document_id": str(document_id),
                "expected_template_version_id": str(expected),
                "actual_template_version_id": str(actual),
            },
        )


class RegenerationService:

    def __init__(
        self,
        document_repo: DocumentRepository,
        section_repo: SectionRepository,
        template_repo: TemplateRepository,
        generation_input_repo: GenerationInputRepository,
        section_output_repo: SectionOutputRepository,
        audit_repo: AuditRepository,
    ):
        self.document_repo = document_repo
        self.section_repo = section_repo
        self.template_repo = template_repo
        self.generation_input_repo = generation_input_repo
        self.section_output_repo = section_output_repo
        self.audit_repo = audit_repo

    async def regenerate_sections(
        self,
        request: SectionRegenerationRequest,
    ) -> RegenerationResult:
        started_at = utc_now()
        correlation_id = request.correlation_id or self._generate_correlation_id()

        logger.info(
            f"Starting section regeneration for document {request.document_id}, "
            f"sections: {[t.section_id for t in request.target_sections]}, "
            f"correlation_id: {correlation_id}"
        )

        try:
            document = await self._get_document(request.document_id)

            current_version = await self.document_repo.get_latest_version(request.document_id)
            if not current_version:
                raise NoVersionExistsError(request.document_id)

            previous_version_number = current_version.version_number

            template_version_id = document.template_version_id

            all_sections = await self.section_repo.get_by_template_version_id(template_version_id)
            section_map = {s.id: s for s in all_sections}

            validated_targets = await self._validate_regeneration_targets(
                request.target_sections,
                section_map,
                request.document_id,
            )

            previous_output_batch = await self._get_latest_output_batch(
                request.document_id,
                previous_version_number,
            )

            sections_to_regenerate: list[int] = []
            sections_to_reuse: list[int] = []

            target_section_ids = {t.section_id for t in validated_targets}
            dynamic_sections = [s for s in all_sections if s.section_type == SectionType.DYNAMIC]

            for section in dynamic_sections:
                if section.id in target_section_ids:
                    target = next(t for t in validated_targets if t.section_id == section.id)
                    if target.force or request.strategy == RegenerationStrategy.FORCE_ALL:
                        sections_to_regenerate.append(section.id)
                    else:
                        would_change = await self._would_section_change(
                            section,
                            request.client_data,
                            target.client_data_override,
                            previous_output_batch,
                        )
                        if would_change:
                            sections_to_regenerate.append(section.id)
                        else:
                            sections_to_reuse.append(section.id)
                else:
                    sections_to_reuse.append(section.id)

            new_version_number = previous_version_number + 1

            section_results = await self._process_section_regeneration(
                document=document,
                sections_to_regenerate=sections_to_regenerate,
                sections_to_reuse=sections_to_reuse,
                section_map=section_map,
                previous_output_batch=previous_output_batch,
                client_data=request.client_data,
                target_overrides={
                    t.section_id: t.client_data_override
                    for t in validated_targets
                    if t.client_data_override
                },
                new_version_intent=new_version_number,
            )

            regenerated_count = sum(1 for r in section_results if r.was_regenerated)
            reused_count = sum(1 for r in section_results if r.was_reused)
            failed_count = sum(1 for r in section_results if r.error is not None)

            audit_log_ids = await self._create_regeneration_audit_log(
                document_id=request.document_id,
                scope=RegenerationScope.SECTION,
                intent=request.intent,
                strategy=request.strategy,
                old_version=previous_version_number,
                new_version=new_version_number,
                template_version_id=template_version_id,
                regenerated_sections=sections_to_regenerate,
                reused_sections=sections_to_reuse,
                correlation_id=correlation_id,
            )

            completed_at = utc_now()

            status = RegenerationStatus.COMPLETED
            if failed_count > 0:
                status = (
                    RegenerationStatus.PARTIALLY_COMPLETED
                    if regenerated_count > 0
                    else RegenerationStatus.FAILED
                )

            logger.info(
                f"Section regeneration completed for document {request.document_id}, "
                f"regenerated: {regenerated_count}, reused: {reused_count}, failed: {failed_count}, "
                f"correlation_id: {correlation_id}"
            )

            return RegenerationResult(
                success=failed_count == 0,
                document_id=request.document_id,
                previous_version_number=previous_version_number,
                new_version_number=new_version_number,
                scope=RegenerationScope.SECTION,
                intent=request.intent,
                strategy=request.strategy,
                status=status,
                section_results=section_results,
                sections_regenerated=regenerated_count,
                sections_reused=reused_count,
                sections_failed=failed_count,
                started_at=started_at,
                completed_at=completed_at,
                audit_log_ids=audit_log_ids,
                correlation_id=correlation_id,
            )

        except RegenerationError as e:
            logger.error(
                f"Regeneration failed for document {request.document_id}: {e.message}, "
                f"code: {e.code}, correlation_id: {correlation_id}"
            )
            return RegenerationResult(
                success=False,
                document_id=request.document_id,
                scope=RegenerationScope.SECTION,
                intent=request.intent,
                strategy=request.strategy,
                status=RegenerationStatus.FAILED,
                error=e.message,
                error_details=e.details,
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during regeneration for document {request.document_id}: {e}, "
                f"correlation_id: {correlation_id}",
                exc_info=True,
            )
            return RegenerationResult(
                success=False,
                document_id=request.document_id,
                scope=RegenerationScope.SECTION,
                intent=request.intent,
                strategy=request.strategy,
                status=RegenerationStatus.FAILED,
                error=f"Unexpected error: {str(e)}",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation_id,
            )

    async def regenerate_full_document(
        self,
        request: FullRegenerationRequest,
    ) -> RegenerationResult:
        started_at = utc_now()
        correlation_id = request.correlation_id or self._generate_correlation_id()

        logger.info(
            f"Starting full regeneration for document {request.document_id}, "
            f"correlation_id: {correlation_id}"
        )

        try:
            document = await self._get_document(request.document_id)

            current_version = await self.document_repo.get_latest_version(request.document_id)
            previous_version_number = current_version.version_number if current_version else None

            template_version_id = document.template_version_id

            all_sections = await self.section_repo.get_by_template_version_id(template_version_id)
            dynamic_sections = [s for s in all_sections if s.section_type == SectionType.DYNAMIC]

            new_version_number = (previous_version_number + 1) if previous_version_number else 1

            sections_to_regenerate = [s.id for s in dynamic_sections]

            section_results = [
                RegenerationSectionResult(
                    section_id=s.id,
                    was_regenerated=True,
                    was_reused=False,
                )
                for s in dynamic_sections
            ]

            audit_log_ids = await self._create_regeneration_audit_log(
                document_id=request.document_id,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                strategy=None,
                old_version=previous_version_number,
                new_version=new_version_number,
                template_version_id=template_version_id,
                regenerated_sections=sections_to_regenerate,
                reused_sections=[],
                correlation_id=correlation_id,
            )

            completed_at = utc_now()

            logger.info(
                f"Full regeneration prepared for document {request.document_id}, "
                f"sections: {len(sections_to_regenerate)}, "
                f"correlation_id: {correlation_id}"
            )

            return RegenerationResult(
                success=True,
                document_id=request.document_id,
                previous_version_number=previous_version_number,
                new_version_number=new_version_number,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                status=RegenerationStatus.COMPLETED,
                section_results=section_results,
                sections_regenerated=len(sections_to_regenerate),
                sections_reused=0,
                sections_failed=0,
                started_at=started_at,
                completed_at=completed_at,
                audit_log_ids=audit_log_ids,
                correlation_id=correlation_id,
            )

        except RegenerationError as e:
            logger.error(
                f"Full regeneration failed for document {request.document_id}: {e.message}, "
                f"correlation_id: {correlation_id}"
            )
            return RegenerationResult(
                success=False,
                document_id=request.document_id,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                status=RegenerationStatus.FAILED,
                error=e.message,
                error_details=e.details,
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during full regeneration for document {request.document_id}: {e}",
                exc_info=True,
            )
            return RegenerationResult(
                success=False,
                document_id=request.document_id,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                status=RegenerationStatus.FAILED,
                error=f"Unexpected error: {str(e)}",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation_id,
            )

    async def regenerate_for_template_update(
        self,
        request: TemplateUpdateRegenerationRequest,
    ) -> RegenerationResult:
        started_at = utc_now()
        correlation_id = request.correlation_id or self._generate_correlation_id()

        logger.info(
            f"Starting template update regeneration for document {request.document_id}, "
            f"new_template_version: {request.new_template_version_id}, "
            f"correlation_id: {correlation_id}"
        )

        try:
            document = await self._get_document(request.document_id)
            old_template_version_id = document.template_version_id

            new_template_version = await self.template_repo.get_version_by_id(
                request.new_template_version_id
            )
            if not new_template_version:
                raise RegenerationError(
                    message=f"Template version {request.new_template_version_id} not found",
                    code="TEMPLATE_VERSION_NOT_FOUND",
                    details={"template_version_id": str(request.new_template_version_id)},
                )

            current_version = await self.document_repo.get_latest_version(request.document_id)
            previous_version_number = current_version.version_number if current_version else None

            new_sections = await self.section_repo.get_by_template_version_id(
                request.new_template_version_id
            )
            dynamic_sections = [s for s in new_sections if s.section_type == SectionType.DYNAMIC]

            new_version_number = (previous_version_number + 1) if previous_version_number else 1

            sections_to_regenerate = [s.id for s in dynamic_sections]

            section_results = [
                RegenerationSectionResult(
                    section_id=s.id,
                    was_regenerated=True,
                    was_reused=False,
                )
                for s in dynamic_sections
            ]

            audit_log_ids = await self._create_template_transition_audit_log(
                document_id=request.document_id,
                old_template_version_id=old_template_version_id,
                new_template_version_id=request.new_template_version_id,
                old_version=previous_version_number,
                new_version=new_version_number,
                regenerated_sections=sections_to_regenerate,
                correlation_id=correlation_id,
            )

            completed_at = utc_now()

            logger.info(
                f"Template update regeneration prepared for document {request.document_id}, "
                f"template: {old_template_version_id} -> {request.new_template_version_id}, "
                f"correlation_id: {correlation_id}"
            )

            return RegenerationResult(
                success=True,
                document_id=request.document_id,
                previous_version_number=previous_version_number,
                new_version_number=new_version_number,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                status=RegenerationStatus.COMPLETED,
                section_results=section_results,
                sections_regenerated=len(sections_to_regenerate),
                sections_reused=0,
                sections_failed=0,
                started_at=started_at,
                completed_at=completed_at,
                audit_log_ids=audit_log_ids,
                correlation_id=correlation_id,
            )

        except RegenerationError as e:
            logger.error(
                f"Template update regeneration failed for document {request.document_id}: {e.message}, "
                f"correlation_id: {correlation_id}"
            )
            return RegenerationResult(
                success=False,
                document_id=request.document_id,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                status=RegenerationStatus.FAILED,
                error=e.message,
                error_details=e.details,
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during template update regeneration: {e}",
                exc_info=True,
            )
            return RegenerationResult(
                success=False,
                document_id=request.document_id,
                scope=RegenerationScope.FULL,
                intent=request.intent,
                status=RegenerationStatus.FAILED,
                error=f"Unexpected error: {str(e)}",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation_id,
            )

    async def get_regeneration_history(
        self,
        document_id: UUID,
        limit: int = 100,
    ) -> list[VersionTransition]:
        logs = await self.audit_repo.query(
            entity_type="DOCUMENT",
            entity_id=document_id,
            action="REGENERATE",
            limit=limit,
        )

        transitions = []
        for log in logs:
            metadata = log.metadata_
            transitions.append(
                VersionTransition(
                    document_id=document_id,
                    old_version_number=metadata.get("old_version"),
                    old_version_id=(
                        UUID(metadata["old_version_id"]) if metadata.get("old_version_id") else None
                    ),
                    new_version_number=metadata["new_version"],
                    new_version_id=(
                        UUID(metadata["new_version_id"])
                        if metadata.get("new_version_id")
                        else UUID("00000000-0000-0000-0000-000000000000")
                    ),
                    scope=RegenerationScope(metadata.get("scope", "FULL")),
                    intent=RegenerationIntent(metadata.get("intent", "CONTENT_UPDATE")),
                    regenerated_section_ids=metadata.get("regenerated_sections", []),
                    reused_section_ids=metadata.get("reused_sections", []),
                    template_version_id=UUID(metadata["template_version_id"]),
                    timestamp=log.timestamp,
                )
            )

        return transitions

    async def _get_document(self, document_id: UUID) -> Document:
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        return document

    async def _validate_regeneration_targets(
        self,
        targets: list[SectionRegenerationTarget],
        section_map: dict[int, Section],
        document_id: UUID,
    ) -> list[SectionRegenerationTarget]:
        validated = []
        for target in targets:
            section = section_map.get(target.section_id)
            if not section:
                raise SectionNotFoundError(target.section_id, document_id)
            if section.section_type == SectionType.STATIC:
                raise StaticSectionError(target.section_id)
            validated.append(target)
        return validated

    async def _get_latest_output_batch(
        self,
        document_id: UUID,
        version_intent: int,
    ) -> SectionOutputBatch | None:
        return await self.section_output_repo.get_batch_by_document_version(
            document_id,
            version_intent,
            include_outputs=True,
        )

    async def _would_section_change(
        self,
        section: Section,
        client_data: dict[str, Any],
        override: dict[str, Any] | None,
        previous_batch: SectionOutputBatch | None,
    ) -> bool:
        if not previous_batch or not previous_batch.outputs:
            return True

        previous_output = next(
            (o for o in previous_batch.outputs if o.section_id == section.id),
            None,
        )
        if not previous_output:
            return True

        merged_data = {**client_data, **(override or {})}
        new_input_hash = self._compute_input_hash(section.id, merged_data)

        previous_input_hash = (
            previous_output.generation_metadata.get("input_hash")
            if previous_output.generation_metadata
            else None
        )

        return new_input_hash != previous_input_hash

    async def _process_section_regeneration(
        self,
        document: Document,
        sections_to_regenerate: list[int],
        sections_to_reuse: list[int],
        section_map: dict[int, Section],
        previous_output_batch: SectionOutputBatch | None,
        client_data: dict[str, Any],
        target_overrides: dict[int, dict[str, Any] | None],
        new_version_intent: int,
    ) -> list[RegenerationSectionResult]:
        results = []

        for section_id in sections_to_regenerate:
            section = section_map.get(section_id)
            if not section:
                results.append(
                    RegenerationSectionResult(
                        section_id=section_id,
                        was_regenerated=False,
                        error=f"Section {section_id} not found",
                    )
                )
                continue

            previous_hash = None
            if previous_output_batch and previous_output_batch.outputs:
                prev_output = next(
                    (o for o in previous_output_batch.outputs if o.section_id == section_id),
                    None,
                )
                if prev_output:
                    previous_hash = prev_output.content_hash

            results.append(
                RegenerationSectionResult(
                    section_id=section_id,
                    was_regenerated=True,
                    was_reused=False,
                    previous_content_hash=previous_hash,
                )
            )

        for section_id in sections_to_reuse:
            previous_hash = None
            if previous_output_batch and previous_output_batch.outputs:
                prev_output = next(
                    (o for o in previous_output_batch.outputs if o.section_id == section_id),
                    None,
                )
                if prev_output:
                    previous_hash = prev_output.content_hash

            results.append(
                RegenerationSectionResult(
                    section_id=section_id,
                    was_regenerated=False,
                    was_reused=True,
                    previous_content_hash=previous_hash,
                    new_content_hash=previous_hash,
                )
            )

        return results

    async def _create_regeneration_audit_log(
        self,
        document_id: UUID,
        scope: RegenerationScope,
        intent: RegenerationIntent,
        strategy: RegenerationStrategy | None,
        old_version: int | None,
        new_version: int,
        template_version_id: UUID,
        regenerated_sections: list[int],
        reused_sections: list[int],
        correlation_id: str,
    ) -> list[UUID]:
        metadata = {
            "scope": scope.value,
            "intent": intent.value,
            "strategy": strategy.value if strategy else None,
            "old_version": old_version,
            "new_version": new_version,
            "template_version_id": str(template_version_id),
            "regenerated_sections": regenerated_sections,
            "reused_sections": reused_sections,
            "correlation_id": correlation_id,
        }

        audit_log = AuditLog(
            entity_type="DOCUMENT",
            entity_id=document_id,
            action="REGENERATE",
            metadata_=metadata,
        )
        created_log = await self.audit_repo.create(audit_log)

        return [created_log.id]

    async def _create_template_transition_audit_log(
        self,
        document_id: UUID,
        old_template_version_id: UUID,
        new_template_version_id: UUID,
        old_version: int | None,
        new_version: int,
        regenerated_sections: list[int],
        correlation_id: str,
    ) -> list[UUID]:
        metadata = {
            "scope": RegenerationScope.FULL.value,
            "intent": RegenerationIntent.TEMPLATE_UPDATE.value,
            "old_version": old_version,
            "new_version": new_version,
            "old_template_version_id": str(old_template_version_id),
            "new_template_version_id": str(new_template_version_id),
            "template_version_id": str(new_template_version_id),
            "regenerated_sections": regenerated_sections,
            "reused_sections": [],
            "correlation_id": correlation_id,
            "is_template_transition": True,
        }

        audit_log = AuditLog(
            entity_type="DOCUMENT",
            entity_id=document_id,
            action="REGENERATE_TEMPLATE_UPDATE",
            metadata_=metadata,
        )
        created_log = await self.audit_repo.create(audit_log)

        return [created_log.id]

    def _generate_correlation_id(self) -> str:
        import uuid

        return f"regen-{uuid.uuid4().hex[:12]}"

    def _compute_input_hash(self, section_id: int, client_data: dict[str, Any]) -> str:
        data = {
            "section_id": section_id,
            "client_data": client_data,
        }
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()
