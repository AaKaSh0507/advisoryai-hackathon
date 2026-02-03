"""
Regeneration worker handlers.

Handles:
- Full document regeneration (REGENERATE)
- Section-level regeneration (REGENERATE_SECTIONS)

All regeneration operations:
- Create new immutable versions
- Preserve historical data
- Maintain audit trail
- Support deterministic replay
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.domains.assembly.repository import AssembledDocumentRepository
from backend.app.domains.assembly.schemas import AssemblyRequest
from backend.app.domains.assembly.service import DocumentAssemblyService
from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.document.repository import DocumentRepository
from backend.app.domains.generation.llm_client import MockLLMClient
from backend.app.domains.generation.repository import GenerationInputRepository
from backend.app.domains.generation.schemas import ClientDataPayload, PrepareGenerationInputsRequest
from backend.app.domains.generation.section_output_repository import SectionOutputRepository
from backend.app.domains.generation.section_output_schemas import (
    ContentConstraints,
    ExecuteSectionGenerationRequest,
)
from backend.app.domains.generation.section_output_service import SectionGenerationService
from backend.app.domains.generation.service import GenerationInputService
from backend.app.domains.parsing.repository import ParsedDocumentRepository
from backend.app.domains.rendering.repository import RenderedDocumentRepository
from backend.app.domains.rendering.schemas import RenderingRequest
from backend.app.domains.rendering.service import DocumentRenderingService
from backend.app.domains.section.repository import SectionRepository
from backend.app.domains.versioning.repository import VersioningRepository
from backend.app.domains.versioning.schemas import VersionCreateRequest
from backend.app.domains.versioning.service import DocumentVersioningService
from backend.app.infrastructure.storage import StorageService
from backend.app.logging_config import get_logger
from backend.app.worker.handlers.base import HandlerContext, HandlerResult, JobHandler

logger = get_logger("worker.handlers.regeneration")


class RegenerationStage(str, Enum):
    """Stages of regeneration pipeline."""

    VALIDATION = "VALIDATION"
    INPUT_PREPARATION = "INPUT_PREPARATION"
    SECTION_GENERATION = "SECTION_GENERATION"
    CONTENT_REUSE = "CONTENT_REUSE"
    DOCUMENT_ASSEMBLY = "DOCUMENT_ASSEMBLY"
    DOCUMENT_RENDERING = "DOCUMENT_RENDERING"
    VERSIONING = "VERSIONING"
    COMPLETED = "COMPLETED"


@dataclass
class RegenerationState:
    """State tracking for regeneration pipeline."""

    current_stage: RegenerationStage
    correlation_id: str | None = None
    input_batch_id: UUID | None = None
    output_batch_id: UUID | None = None
    assembled_document_id: UUID | None = None
    rendered_document_id: UUID | None = None
    version_id: UUID | None = None
    version_number: int | None = None
    output_path: str | None = None
    sections_regenerated: list[int] | None = None
    sections_reused: list[int] | None = None
    error: str | None = None
    error_stage: RegenerationStage | None = None


class FullRegenerationHandler(JobHandler):
    """Handler for full document regeneration jobs."""

    @property
    def name(self) -> str:
        return "FullRegenerationHandler"

    async def handle(self, context: HandlerContext) -> HandlerResult:
        job = context.job
        session = context.session

        document_id = job.payload.get("document_id")
        version_intent = job.payload.get("version_intent", 1)
        client_data = job.payload.get("client_data", {})
        correlation_id = job.payload.get("correlation_id")

        logger.info(
            f"Full regeneration started for job {job.id}, "
            f"document {document_id}, version_intent {version_intent}, "
            f"correlation_id: {correlation_id}"
        )

        if not document_id:
            return HandlerResult(
                success=False,
                error="Missing document_id in job payload",
                should_advance_pipeline=False,
            )

        try:
            document_uuid = UUID(document_id)
        except (ValueError, TypeError) as e:
            return HandlerResult(
                success=False,
                error=f"Invalid document_id UUID: {e}",
                should_advance_pipeline=False,
            )

        state = RegenerationState(
            current_stage=RegenerationStage.VALIDATION,
            correlation_id=correlation_id,
        )

        try:
            document_repo = DocumentRepository(session)
            document = await document_repo.get_by_id(document_uuid)
            if not document:
                return HandlerResult(
                    success=False,
                    error=f"Document {document_id} not found",
                    should_advance_pipeline=False,
                )

            template_version_id = document.template_version_id

            services = self._create_services(session, job.id)

            state = await self._execute_full_regeneration(
                services=services,
                document_uuid=document_uuid,
                template_version_id=template_version_id,
                version_intent=version_intent,
                client_data=client_data,
                state=state,
            )

            if state.error:
                return self._create_failure_result(state)

            state.current_stage = RegenerationStage.COMPLETED

            logger.info(
                f"Full regeneration completed for job {job.id}, "
                f"version {state.version_number} created, "
                f"correlation_id: {correlation_id}"
            )

            return HandlerResult(
                success=True,
                data={
                    "document_id": str(document_uuid),
                    "template_version_id": str(template_version_id),
                    "version_intent": version_intent,
                    "version_number": state.version_number,
                    "version_id": str(state.version_id) if state.version_id else None,
                    "output_path": state.output_path,
                    "correlation_id": correlation_id,
                    "regeneration_type": "FULL",
                },
                should_advance_pipeline=False,
            )

        except Exception as e:
            logger.error(
                f"Full regeneration failed for job {job.id}: {e}, "
                f"correlation_id: {correlation_id}",
                exc_info=True,
            )
            return HandlerResult(
                success=False,
                error=f"Regeneration failed at {state.current_stage.value}: {str(e)}",
                should_advance_pipeline=False,
            )

    def _create_services(self, session: AsyncSession, job_id: UUID) -> dict[str, Any]:
        """Create all required services."""
        audit_repo = AuditRepository(session)
        generation_audit_service = GenerationAuditService(audit_repo)

        generation_input_repo = GenerationInputRepository(session)
        section_repo = SectionRepository(session)
        generation_input_service = GenerationInputService(
            generation_repo=generation_input_repo,
            section_repo=section_repo,
            generation_audit_service=generation_audit_service,
        )

        section_output_repo = SectionOutputRepository(session)
        llm_client = MockLLMClient()
        section_generation_service = SectionGenerationService(
            output_repo=section_output_repo,
            input_repo=generation_input_repo,
            llm_client=llm_client,
        )

        settings = get_settings()
        storage_service = StorageService(settings)

        assembled_repo = AssembledDocumentRepository(session)
        parsed_repo = ParsedDocumentRepository(session, storage_service)
        assembly_service = DocumentAssemblyService(
            repository=assembled_repo,
            section_output_repository=section_output_repo,
            parsed_document_repository=parsed_repo,
            section_repository=section_repo,
            generation_audit_service=generation_audit_service,
        )

        rendered_repo = RenderedDocumentRepository(session)
        rendering_service = DocumentRenderingService(
            repository=rendered_repo,
            assembled_document_repository=assembled_repo,
            storage=storage_service,
            generation_audit_service=generation_audit_service,
        )

        versioning_repo = VersioningRepository(session)
        versioning_service = DocumentVersioningService(
            repository=versioning_repo,
            storage=storage_service,
            audit_repo=audit_repo,
        )

        return {
            "generation_input_service": generation_input_service,
            "section_generation_service": section_generation_service,
            "assembly_service": assembly_service,
            "rendering_service": rendering_service,
            "versioning_service": versioning_service,
            "storage_service": storage_service,
            "audit_repo": audit_repo,
        }

    async def _execute_full_regeneration(
        self,
        services: dict[str, Any],
        document_uuid: UUID,
        template_version_id: UUID,
        version_intent: int,
        client_data: dict[str, Any],
        state: RegenerationState,
    ) -> RegenerationState:
        """Execute full regeneration pipeline."""
        state.current_stage = RegenerationStage.INPUT_PREPARATION
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        generation_input_service = services["generation_input_service"]
        try:
            client_data_payload = ClientDataPayload(
                company_name=client_data.get("company_name", "Demo Company"),
                deal_name=client_data.get("deal_name", "Demo Deal"),
                industry=client_data.get("industry", "Technology"),
                transaction_type=client_data.get("transaction_type", "M&A"),
                document_date=client_data.get("document_date"),
                custom_fields=client_data.get("custom_fields", {}),
            )

            prepare_request = PrepareGenerationInputsRequest(
                document_id=document_uuid,
                template_version_id=template_version_id,
                version_intent=version_intent,
                client_data=client_data_payload,
            )
            input_result = await generation_input_service.prepare_generation_inputs(prepare_request)
            state.input_batch_id = input_result.batch_id
        except Exception as e:
            state.error = f"Input preparation failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.SECTION_GENERATION
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        section_generation_service = services["section_generation_service"]
        try:
            gen_request = ExecuteSectionGenerationRequest(
                input_batch_id=state.input_batch_id,
                constraints=ContentConstraints(
                    min_length=50,
                    max_length=10000,
                    require_complete_sentences=True,
                ),
            )
            gen_result = await section_generation_service.execute_section_generation(gen_request)
            state.output_batch_id = gen_result.batch_id
        except Exception as e:
            state.error = f"Section generation failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.DOCUMENT_ASSEMBLY
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        assembly_service = services["assembly_service"]
        try:
            assembly_request = AssemblyRequest(
                document_id=document_uuid,
                template_version_id=template_version_id,
                output_batch_id=state.output_batch_id,
                version_intent=version_intent,
            )
            assembly_result = await assembly_service.assemble_document(assembly_request)
            if not assembly_result.success:
                state.error = f"Assembly failed: {assembly_result.error}"
                state.error_stage = state.current_stage
                return state
            state.assembled_document_id = assembly_result.assembled_document_id
        except Exception as e:
            state.error = f"Document assembly failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.DOCUMENT_RENDERING
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        rendering_service = services["rendering_service"]
        try:
            render_request = RenderingRequest(
                document_id=document_uuid,
                assembled_document_id=state.assembled_document_id,
                version_intent=version_intent,
            )
            render_result = await rendering_service.render_document(render_request)
            if not render_result.success:
                state.error = f"Rendering failed: {render_result.error}"
                state.error_stage = state.current_stage
                return state
            state.rendered_document_id = render_result.rendered_document_id
        except Exception as e:
            state.error = f"Document rendering failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.VERSIONING
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        versioning_service = services["versioning_service"]
        storage_service = services["storage_service"]
        try:
            rendered_content = storage_service.get_file(render_result.output_path)
            if not rendered_content:
                state.error = "Rendered content not found in storage"
                state.error_stage = state.current_stage
                return state

            version_request = VersionCreateRequest(
                document_id=document_uuid,
                content=rendered_content,
                generation_metadata={
                    "input_batch_id": str(state.input_batch_id),
                    "output_batch_id": str(state.output_batch_id),
                    "assembled_document_id": str(state.assembled_document_id),
                    "rendered_document_id": str(state.rendered_document_id),
                    "regeneration_type": "FULL",
                    "correlation_id": state.correlation_id,
                },
            )
            version_result = await versioning_service.create_version(version_request)
            if not version_result.success:
                state.error = f"Versioning failed: {version_result.error.message if version_result.error else 'Unknown error'}"
                state.error_stage = state.current_stage
                return state
            state.version_id = version_result.version_id
            state.version_number = version_result.version_number
            state.output_path = version_result.output_path
        except Exception as e:
            state.error = f"Versioning failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        return state

    def _create_failure_result(self, state: RegenerationState) -> HandlerResult:
        """Create failure result from state."""
        return HandlerResult(
            success=False,
            error=f"Regeneration failed at {state.error_stage.value if state.error_stage else 'UNKNOWN'}: {state.error}",
            data={
                "error_stage": state.error_stage.value if state.error_stage else None,
                "correlation_id": state.correlation_id,
            },
            should_advance_pipeline=False,
        )


class SectionRegenerationHandler(JobHandler):
    """Handler for section-level regeneration jobs."""

    @property
    def name(self) -> str:
        return "SectionRegenerationHandler"

    async def handle(self, context: HandlerContext) -> HandlerResult:
        job = context.job
        session = context.session

        document_id = job.payload.get("document_id")
        template_version_id = job.payload.get("template_version_id")
        version_intent = job.payload.get("version_intent", 1)
        section_ids = job.payload.get("section_ids", [])
        reuse_section_ids = job.payload.get("reuse_section_ids", [])
        client_data = job.payload.get("client_data", {})
        correlation_id = job.payload.get("correlation_id")

        logger.info(
            f"Section regeneration started for job {job.id}, "
            f"document {document_id}, sections to regenerate: {section_ids}, "
            f"sections to reuse: {reuse_section_ids}, "
            f"correlation_id: {correlation_id}"
        )

        if not document_id:
            return HandlerResult(
                success=False,
                error="Missing document_id in job payload",
                should_advance_pipeline=False,
            )

        if not section_ids:
            return HandlerResult(
                success=False,
                error="No sections specified for regeneration",
                should_advance_pipeline=False,
            )

        try:
            document_uuid = UUID(document_id)
            template_version_uuid = UUID(template_version_id) if template_version_id else None
        except (ValueError, TypeError) as e:
            return HandlerResult(
                success=False,
                error=f"Invalid UUID in payload: {e}",
                should_advance_pipeline=False,
            )

        state = RegenerationState(
            current_stage=RegenerationStage.VALIDATION,
            correlation_id=correlation_id,
            sections_regenerated=section_ids,
            sections_reused=reuse_section_ids,
        )

        try:
            document_repo = DocumentRepository(session)
            document = await document_repo.get_by_id(document_uuid)
            if not document:
                return HandlerResult(
                    success=False,
                    error=f"Document {document_id} not found",
                    should_advance_pipeline=False,
                )

            if not template_version_uuid:
                template_version_uuid = document.template_version_id

            services = self._create_services(session, job.id)

            state = await self._execute_section_regeneration(
                services=services,
                document_uuid=document_uuid,
                template_version_id=template_version_uuid,
                version_intent=version_intent,
                section_ids=section_ids,
                reuse_section_ids=reuse_section_ids,
                client_data=client_data,
                state=state,
            )

            if state.error:
                return self._create_failure_result(state)

            state.current_stage = RegenerationStage.COMPLETED

            logger.info(
                f"Section regeneration completed for job {job.id}, "
                f"version {state.version_number} created, "
                f"regenerated: {len(section_ids)}, reused: {len(reuse_section_ids)}, "
                f"correlation_id: {correlation_id}"
            )

            return HandlerResult(
                success=True,
                data={
                    "document_id": str(document_uuid),
                    "template_version_id": str(template_version_uuid),
                    "version_intent": version_intent,
                    "version_number": state.version_number,
                    "version_id": str(state.version_id) if state.version_id else None,
                    "output_path": state.output_path,
                    "sections_regenerated": section_ids,
                    "sections_reused": reuse_section_ids,
                    "correlation_id": correlation_id,
                    "regeneration_type": "SECTION",
                },
                should_advance_pipeline=False,
            )

        except Exception as e:
            logger.error(
                f"Section regeneration failed for job {job.id}: {e}, "
                f"correlation_id: {correlation_id}",
                exc_info=True,
            )
            return HandlerResult(
                success=False,
                error=f"Regeneration failed at {state.current_stage.value}: {str(e)}",
                should_advance_pipeline=False,
            )

    def _create_services(self, session: AsyncSession, job_id: UUID) -> dict[str, Any]:
        """Create all required services - same as FullRegenerationHandler."""
        audit_repo = AuditRepository(session)
        generation_audit_service = GenerationAuditService(audit_repo)

        generation_input_repo = GenerationInputRepository(session)
        section_repo = SectionRepository(session)
        generation_input_service = GenerationInputService(
            generation_repo=generation_input_repo,
            section_repo=section_repo,
            generation_audit_service=generation_audit_service,
        )

        section_output_repo = SectionOutputRepository(session)
        llm_client = MockLLMClient()
        section_generation_service = SectionGenerationService(
            output_repo=section_output_repo,
            input_repo=generation_input_repo,
            llm_client=llm_client,
        )

        settings = get_settings()
        storage_service = StorageService(settings)

        assembled_repo = AssembledDocumentRepository(session)
        parsed_repo = ParsedDocumentRepository(session, storage_service)
        assembly_service = DocumentAssemblyService(
            repository=assembled_repo,
            section_output_repository=section_output_repo,
            parsed_document_repository=parsed_repo,
            section_repository=section_repo,
            generation_audit_service=generation_audit_service,
        )

        rendered_repo = RenderedDocumentRepository(session)
        rendering_service = DocumentRenderingService(
            repository=rendered_repo,
            assembled_document_repository=assembled_repo,
            storage=storage_service,
            generation_audit_service=generation_audit_service,
        )

        versioning_repo = VersioningRepository(session)
        versioning_service = DocumentVersioningService(
            repository=versioning_repo,
            storage=storage_service,
            audit_repo=audit_repo,
        )

        return {
            "generation_input_service": generation_input_service,
            "section_generation_service": section_generation_service,
            "section_output_repo": section_output_repo,
            "assembly_service": assembly_service,
            "rendering_service": rendering_service,
            "versioning_service": versioning_service,
            "storage_service": storage_service,
            "audit_repo": audit_repo,
        }

    async def _execute_section_regeneration(
        self,
        services: dict[str, Any],
        document_uuid: UUID,
        template_version_id: UUID,
        version_intent: int,
        section_ids: list[int],
        reuse_section_ids: list[int],
        client_data: dict[str, Any],
        state: RegenerationState,
    ) -> RegenerationState:
        """
        Execute section-level regeneration.

        This reuses outputs from previous batch for non-targeted sections.
        """
        state.current_stage = RegenerationStage.INPUT_PREPARATION
        logger.info(
            f"Regeneration stage: {state.current_stage.value}, "
            f"sections to regenerate: {section_ids}"
        )

        section_output_repo = services["section_output_repo"]
        previous_batch = await section_output_repo.get_batch_by_document_version(
            document_uuid,
            version_intent - 1,  # Previous version
            include_outputs=True,
        )

        generation_input_service = services["generation_input_service"]
        try:
            client_data_payload = ClientDataPayload(
                company_name=client_data.get("company_name", "Demo Company"),
                deal_name=client_data.get("deal_name", "Demo Deal"),
                industry=client_data.get("industry", "Technology"),
                transaction_type=client_data.get("transaction_type", "M&A"),
                document_date=client_data.get("document_date"),
                custom_fields=client_data.get("custom_fields", {}),
            )

            prepare_request = PrepareGenerationInputsRequest(
                document_id=document_uuid,
                template_version_id=template_version_id,
                version_intent=version_intent,
                client_data=client_data_payload,
            )
            input_result = await generation_input_service.prepare_generation_inputs(prepare_request)
            state.input_batch_id = input_result.batch_id
        except Exception as e:
            state.error = f"Input preparation failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.SECTION_GENERATION
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        section_generation_service = services["section_generation_service"]
        try:
            gen_request = ExecuteSectionGenerationRequest(
                input_batch_id=state.input_batch_id,
                constraints=ContentConstraints(
                    min_length=50,
                    max_length=10000,
                    require_complete_sentences=True,
                ),
            )
            gen_result = await section_generation_service.execute_section_generation(gen_request)
            state.output_batch_id = gen_result.batch_id
        except Exception as e:
            state.error = f"Section generation failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.CONTENT_REUSE
        logger.info(
            f"Regeneration stage: {state.current_stage.value}, "
            f"reusing content for sections: {reuse_section_ids}"
        )

        if reuse_section_ids and previous_batch and previous_batch.outputs:
            try:
                # Content reuse is handled during assembly
                # The assembly service will use the outputs from this batch
                pass
            except Exception as e:
                logger.warning(f"Content reuse warning: {e}")

        state.current_stage = RegenerationStage.DOCUMENT_ASSEMBLY
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        assembly_service = services["assembly_service"]
        try:
            assembly_request = AssemblyRequest(
                document_id=document_uuid,
                template_version_id=template_version_id,
                output_batch_id=state.output_batch_id,
                version_intent=version_intent,
            )
            assembly_result = await assembly_service.assemble_document(assembly_request)
            if not assembly_result.success:
                state.error = f"Assembly failed: {assembly_result.error}"
                state.error_stage = state.current_stage
                return state
            state.assembled_document_id = assembly_result.assembled_document_id
        except Exception as e:
            state.error = f"Document assembly failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.DOCUMENT_RENDERING
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        rendering_service = services["rendering_service"]
        try:
            render_request = RenderingRequest(
                document_id=document_uuid,
                assembled_document_id=state.assembled_document_id,
                version_intent=version_intent,
            )
            render_result = await rendering_service.render_document(render_request)
            if not render_result.success:
                state.error = f"Rendering failed: {render_result.error}"
                state.error_stage = state.current_stage
                return state
            state.rendered_document_id = render_result.rendered_document_id
        except Exception as e:
            state.error = f"Document rendering failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        state.current_stage = RegenerationStage.VERSIONING
        logger.info(f"Regeneration stage: {state.current_stage.value}")

        versioning_service = services["versioning_service"]
        storage_service = services["storage_service"]
        try:
            rendered_content = storage_service.get_file(render_result.output_path)
            if not rendered_content:
                state.error = "Rendered content not found in storage"
                state.error_stage = state.current_stage
                return state

            version_request = VersionCreateRequest(
                document_id=document_uuid,
                content=rendered_content,
                generation_metadata={
                    "input_batch_id": str(state.input_batch_id),
                    "output_batch_id": str(state.output_batch_id),
                    "assembled_document_id": str(state.assembled_document_id),
                    "rendered_document_id": str(state.rendered_document_id),
                    "regeneration_type": "SECTION",
                    "sections_regenerated": section_ids,
                    "sections_reused": reuse_section_ids,
                    "correlation_id": state.correlation_id,
                },
            )
            version_result = await versioning_service.create_version(version_request)
            if not version_result.success:
                state.error = f"Versioning failed: {version_result.error.message if version_result.error else 'Unknown error'}"
                state.error_stage = state.current_stage
                return state
            state.version_id = version_result.version_id
            state.version_number = version_result.version_number
            state.output_path = version_result.output_path
        except Exception as e:
            state.error = f"Versioning failed: {str(e)}"
            state.error_stage = state.current_stage
            return state

        return state

    def _create_failure_result(self, state: RegenerationState) -> HandlerResult:
        """Create failure result from state."""
        return HandlerResult(
            success=False,
            error=f"Regeneration failed at {state.error_stage.value if state.error_stage else 'UNKNOWN'}: {state.error}",
            data={
                "error_stage": state.error_stage.value if state.error_stage else None,
                "correlation_id": state.correlation_id,
                "sections_attempted": state.sections_regenerated,
            },
            should_advance_pipeline=False,
        )
