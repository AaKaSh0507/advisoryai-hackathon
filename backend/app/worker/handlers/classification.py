from uuid import UUID

from backend.app.config import get_settings
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.audit.service import AuditService
from backend.app.domains.parsing.repository import ParsedDocumentRepository
from backend.app.domains.section.classification_service import create_classification_service
from backend.app.domains.section.llm_classifier import LLMClassifierConfig
from backend.app.domains.section.repository import SectionRepository
from backend.app.infrastructure.storage import StorageService
from backend.app.logging_config import get_logger
from backend.app.worker.handlers.base import HandlerContext, HandlerResult, JobHandler

logger = get_logger("worker.handlers.classification")


class ClassificationHandler(JobHandler):
    @property
    def name(self) -> str:
        return "ClassificationHandler"

    async def handle(self, context: HandlerContext) -> HandlerResult:
        job = context.job
        template_version_id_str = job.payload.get("template_version_id")

        logger.info(
            f"Classification handler started for job {job.id}, template_version {template_version_id_str}"
        )

        if not template_version_id_str:
            return HandlerResult(
                success=False,
                error="Missing template_version_id in job payload",
                should_advance_pipeline=False,
            )

        try:
            template_version_id = UUID(template_version_id_str)
            settings = get_settings()
            storage = StorageService(settings)
            parsed_doc_repo = ParsedDocumentRepository(context.session, storage)
            parsed_document = await parsed_doc_repo.get_by_template_version_id(template_version_id)

            if not parsed_document:
                return HandlerResult(
                    success=False,
                    error=f"No parsed document found for template version {template_version_id}",
                    should_advance_pipeline=False,
                )

            logger.info(f"Found parsed document with {len(parsed_document.blocks)} blocks")
            llm_config = None
            if settings.llm_inference_enabled and settings.openai_api_key:
                llm_config = LLMClassifierConfig(
                    api_key=settings.openai_api_key,
                    api_base_url=settings.openai_api_base_url,
                    model=settings.openai_model,
                    enabled=True,
                )

            classification_service = create_classification_service(
                llm_config=llm_config,
                confidence_threshold=settings.llm_confidence_threshold,
            )
            section_repo = SectionRepository(context.session)
            result = await classification_service.classify_template_sections(
                parsed_document=parsed_document,
                section_repo=section_repo,
            )
            audit_repo = AuditRepository(context.session)
            audit_service = AuditService(audit_repo)
            await audit_service.log_action(
                entity_type="template_version",
                entity_id=template_version_id,
                action="sections_classified",
                metadata={
                    "total_sections": result.total_sections,
                    "static_sections": result.static_sections,
                    "dynamic_sections": result.dynamic_sections,
                    "high_confidence_count": result.high_confidence_count,
                    "rule_based_count": result.rule_based_count,
                    "llm_assisted_count": result.llm_assisted_count,
                    "fallback_count": result.fallback_count,
                    "duration_ms": result.duration_ms,
                    "success_rate": result.success_rate,
                },
            )
            result_data = {
                "template_version_id": template_version_id_str,
                "total_sections": result.total_sections,
                "static_sections": result.static_sections,
                "dynamic_sections": result.dynamic_sections,
                "high_confidence_count": result.high_confidence_count,
                "medium_confidence_count": result.medium_confidence_count,
                "low_confidence_count": result.low_confidence_count,
                "rule_based_count": result.rule_based_count,
                "llm_assisted_count": result.llm_assisted_count,
                "fallback_count": result.fallback_count,
                "duration_ms": result.duration_ms,
                "success_rate": result.success_rate,
            }

            logger.info(
                f"Classification completed for job {job.id}: "
                f"{result.total_sections} sections classified "
                f"({result.static_sections} STATIC, {result.dynamic_sections} DYNAMIC)"
            )

            return HandlerResult(
                success=True,
                data=result_data,
                should_advance_pipeline=True,
            )

        except Exception as e:
            logger.error(f"Classification failed for job {job.id}: {e}", exc_info=True)
            return HandlerResult(
                success=False,
                error=str(e),
                should_advance_pipeline=False,
            )
