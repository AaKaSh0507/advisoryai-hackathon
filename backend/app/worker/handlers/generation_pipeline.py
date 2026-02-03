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

logger = get_logger("worker.handlers.generation_pipeline")


class PipelineStage(str, Enum):
    INPUT_PREPARATION = "INPUT_PREPARATION"
    SECTION_GENERATION = "SECTION_GENERATION"
    DOCUMENT_ASSEMBLY = "DOCUMENT_ASSEMBLY"
    DOCUMENT_RENDERING = "DOCUMENT_RENDERING"
    VERSIONING = "VERSIONING"
    COMPLETED = "COMPLETED"


@dataclass
class PipelineState:
    current_stage: PipelineStage
    input_batch_id: UUID | None = None
    output_batch_id: UUID | None = None
    assembled_document_id: UUID | None = None
    rendered_document_id: UUID | None = None
    version_id: UUID | None = None
    version_number: int | None = None
    output_path: str | None = None
    error: str | None = None
    error_stage: PipelineStage | None = None


class GenerationPipelineHandler(JobHandler):
    @property
    def name(self) -> str:
        return "GenerationPipelineHandler"

    async def handle(self, context: HandlerContext) -> HandlerResult:
        job = context.job
        session = context.session

        template_version_id = job.payload.get("template_version_id")
        document_id = job.payload.get("document_id")
        version_intent = job.payload.get("version_intent", 1)
        client_data = job.payload.get("client_data", {})
        _ = job.payload.get("force_regenerate", False)

        logger.info(
            f"Generation pipeline started for job {job.id}, "
            f"document {document_id}, template_version {template_version_id}"
        )

        if not template_version_id:
            return HandlerResult(
                success=False,
                error="Missing template_version_id in job payload",
                should_advance_pipeline=False,
            )

        if not document_id:
            return HandlerResult(
                success=False,
                error="Missing document_id in job payload",
                should_advance_pipeline=False,
            )

        try:
            template_version_uuid = UUID(template_version_id)
            document_uuid = UUID(document_id)
        except (ValueError, TypeError) as e:
            return HandlerResult(
                success=False,
                error=f"Invalid UUID in payload: {e}",
                should_advance_pipeline=False,
            )

        pipeline_state = PipelineState(current_stage=PipelineStage.INPUT_PREPARATION)

        try:
            services = self._create_services(session, job.id)

            pipeline_state = await self._execute_input_preparation(
                services,
                document_uuid,
                template_version_uuid,
                version_intent,
                client_data,
                pipeline_state,
            )
            if pipeline_state.error:
                return self._create_failure_result(pipeline_state)

            pipeline_state = await self._execute_section_generation(
                services,
                pipeline_state,
            )
            if pipeline_state.error:
                return self._create_failure_result(pipeline_state)

            pipeline_state = await self._execute_document_assembly(
                services,
                document_uuid,
                template_version_uuid,
                version_intent,
                pipeline_state,
            )
            if pipeline_state.error:
                return self._create_failure_result(pipeline_state)

            pipeline_state = await self._execute_document_rendering(
                services,
                document_uuid,
                version_intent,
                pipeline_state,
            )
            if pipeline_state.error:
                return self._create_failure_result(pipeline_state)

            pipeline_state = await self._execute_versioning(
                services,
                document_uuid,
                pipeline_state,
            )
            if pipeline_state.error:
                return self._create_failure_result(pipeline_state)

            pipeline_state.current_stage = PipelineStage.COMPLETED

            logger.info(
                f"Generation pipeline completed for job {job.id}, "
                f"version {pipeline_state.version_number} created"
            )

            return HandlerResult(
                success=True,
                data={
                    "document_id": str(document_uuid),
                    "template_version_id": str(template_version_uuid),
                    "version_intent": version_intent,
                    "input_batch_id": str(pipeline_state.input_batch_id),
                    "output_batch_id": str(pipeline_state.output_batch_id),
                    "assembled_document_id": str(pipeline_state.assembled_document_id),
                    "rendered_document_id": str(pipeline_state.rendered_document_id),
                    "version_id": str(pipeline_state.version_id),
                    "version_number": pipeline_state.version_number,
                    "output_path": pipeline_state.output_path,
                    "pipeline_stage": PipelineStage.COMPLETED.value,
                },
                should_advance_pipeline=False,
            )

        except Exception as e:
            logger.error(f"Generation pipeline failed for job {job.id}: {e}", exc_info=True)
            return HandlerResult(
                success=False,
                error=f"Pipeline failed at {pipeline_state.current_stage.value}: {str(e)}",
                should_advance_pipeline=False,
            )

    def _create_services(self, session: AsyncSession, job_id: UUID) -> dict[str, Any]:
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

        assembled_doc_repo = AssembledDocumentRepository(session)
        storage_service = StorageService(settings=get_settings())
        parsed_doc_repo = ParsedDocumentRepository(session, storage=storage_service)
        assembly_service = DocumentAssemblyService(
            repository=assembled_doc_repo,
            section_output_repository=section_output_repo,
            parsed_document_repository=parsed_doc_repo,
            section_repository=section_repo,
            generation_audit_service=generation_audit_service,
        )

        rendered_doc_repo = RenderedDocumentRepository(session)
        rendering_service = DocumentRenderingService(
            repository=rendered_doc_repo,
            assembled_document_repository=assembled_doc_repo,
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
            "generation_audit_service": generation_audit_service,
            "storage_service": storage_service,
        }

    async def _execute_input_preparation(
        self,
        services: dict[str, Any],
        document_id: UUID,
        template_version_id: UUID,
        version_intent: int,
        client_data: dict[str, Any],
        state: PipelineState,
    ) -> PipelineState:
        state.current_stage = PipelineStage.INPUT_PREPARATION
        logger.info(f"Executing input preparation for document {document_id}")

        try:
            generation_input_service: GenerationInputService = services["generation_input_service"]

            client_payload = ClientDataPayload(
                client_id=client_data.get("client_id"),
                client_name=client_data.get("client_name"),
                data_fields=client_data.get("data_fields", {}),
                custom_context=client_data.get("custom_context", {}),
            )

            request = PrepareGenerationInputsRequest(
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=version_intent,
                client_data=client_payload,
            )

            response = await generation_input_service.prepare_generation_inputs(request)
            state.input_batch_id = response.batch_id

            logger.info(
                f"Input preparation completed: batch {response.batch_id}, "
                f"{response.total_dynamic_sections} sections"
            )

        except Exception as e:
            logger.error(f"Input preparation failed: {e}", exc_info=True)
            state.error = f"Input preparation failed: {str(e)}"
            state.error_stage = PipelineStage.INPUT_PREPARATION

        return state

    async def _execute_section_generation(
        self,
        services: dict[str, Any],
        state: PipelineState,
    ) -> PipelineState:
        state.current_stage = PipelineStage.SECTION_GENERATION
        logger.info(f"Executing section generation for batch {state.input_batch_id}")

        try:
            section_generation_service: SectionGenerationService = services[
                "section_generation_service"
            ]

            request = ExecuteSectionGenerationRequest(
                input_batch_id=state.input_batch_id,
                constraints=ContentConstraints(),
            )

            response = await section_generation_service.execute_section_generation(request)
            state.output_batch_id = response.batch_id

            if response.failed_count > 0:
                state.error = (
                    f"Section generation had {response.failed_count} failures "
                    f"out of {response.total_sections} sections"
                )
                state.error_stage = PipelineStage.SECTION_GENERATION
                return state

            logger.info(
                f"Section generation completed: batch {response.batch_id}, "
                f"{response.completed_count} sections generated"
            )

        except Exception as e:
            logger.error(f"Section generation failed: {e}", exc_info=True)
            state.error = f"Section generation failed: {str(e)}"
            state.error_stage = PipelineStage.SECTION_GENERATION

        return state

    async def _execute_document_assembly(
        self,
        services: dict[str, Any],
        document_id: UUID,
        template_version_id: UUID,
        version_intent: int,
        state: PipelineState,
    ) -> PipelineState:
        state.current_stage = PipelineStage.DOCUMENT_ASSEMBLY
        logger.info(f"Executing document assembly for output batch {state.output_batch_id}")

        try:
            assembly_service: DocumentAssemblyService = services["assembly_service"]

            request = AssemblyRequest(
                document_id=document_id,
                template_version_id=template_version_id,
                version_intent=version_intent,
                section_output_batch_id=state.output_batch_id,
            )

            result = await assembly_service.assemble_document(request)

            if not result.success or result.assembled_document is None:
                state.error = f"Document assembly failed: {result.error_message}"
                state.error_stage = PipelineStage.DOCUMENT_ASSEMBLY
                return state

            state.assembled_document_id = result.assembled_document.id

            logger.info(
                f"Document assembly completed: assembled_document {state.assembled_document_id}"
            )

        except Exception as e:
            logger.error(f"Document assembly failed: {e}", exc_info=True)
            state.error = f"Document assembly failed: {str(e)}"
            state.error_stage = PipelineStage.DOCUMENT_ASSEMBLY

        return state

    async def _execute_document_rendering(
        self,
        services: dict[str, Any],
        document_id: UUID,
        version: int,
        state: PipelineState,
    ) -> PipelineState:
        state.current_stage = PipelineStage.DOCUMENT_RENDERING
        logger.info(
            f"Executing document rendering for assembled_document {state.assembled_document_id}"
        )

        try:
            rendering_service: DocumentRenderingService = services["rendering_service"]

            request = RenderingRequest(
                assembled_document_id=state.assembled_document_id,
                document_id=document_id,
                version=version,
            )

            result = await rendering_service.render_document(request)

            if not result.success or result.rendered_document is None:
                state.error = f"Document rendering failed: {result.error_message}"
                state.error_stage = PipelineStage.DOCUMENT_RENDERING
                return state

            state.rendered_document_id = result.rendered_document.id
            state.output_path = result.output_path

            logger.info(
                f"Document rendering completed: rendered_document {state.rendered_document_id}, "
                f"output_path {state.output_path}"
            )

        except Exception as e:
            logger.error(f"Document rendering failed: {e}", exc_info=True)
            state.error = f"Document rendering failed: {str(e)}"
            state.error_stage = PipelineStage.DOCUMENT_RENDERING

        return state

    async def _execute_versioning(
        self,
        services: dict[str, Any],
        document_id: UUID,
        state: PipelineState,
    ) -> PipelineState:
        state.current_stage = PipelineStage.VERSIONING
        logger.info(f"Executing versioning for document {document_id}")

        try:
            versioning_service: DocumentVersioningService = services["versioning_service"]
            storage_service: StorageService = services["storage_service"]

            if state.output_path is None:
                state.error = "No output path available from rendering stage"
                state.error_stage = PipelineStage.VERSIONING
                return state

            content = storage_service.get_file(state.output_path)
            if not content:
                state.error = f"Failed to read rendered content from {state.output_path}"
                state.error_stage = PipelineStage.VERSIONING
                return state

            request = VersionCreateRequest(
                document_id=document_id,
                content=content,
                generation_metadata={
                    "input_batch_id": str(state.input_batch_id),
                    "output_batch_id": str(state.output_batch_id),
                    "assembled_document_id": str(state.assembled_document_id),
                    "rendered_document_id": str(state.rendered_document_id),
                },
            )

            result = await versioning_service.create_version(request)

            if not result.success:
                state.error = f"Versioning failed: {result.error.message if result.error else 'Unknown error'}"
                state.error_stage = PipelineStage.VERSIONING
                return state

            state.version_id = result.version_id
            state.version_number = result.version_number
            state.output_path = result.output_path

            logger.info(
                f"Versioning completed: version {state.version_number}, "
                f"version_id {state.version_id}"
            )

        except Exception as e:
            logger.error(f"Versioning failed: {e}", exc_info=True)
            state.error = f"Versioning failed: {str(e)}"
            state.error_stage = PipelineStage.VERSIONING

        return state

    def _create_failure_result(self, state: PipelineState) -> HandlerResult:
        return HandlerResult(
            success=False,
            error=state.error,
            data={
                "failed_stage": state.error_stage.value if state.error_stage else None,
                "current_stage": state.current_stage.value,
                "input_batch_id": str(state.input_batch_id) if state.input_batch_id else None,
                "output_batch_id": str(state.output_batch_id) if state.output_batch_id else None,
                "assembled_document_id": (
                    str(state.assembled_document_id) if state.assembled_document_id else None
                ),
                "rendered_document_id": (
                    str(state.rendered_document_id) if state.rendered_document_id else None
                ),
            },
            should_advance_pipeline=False,
        )
