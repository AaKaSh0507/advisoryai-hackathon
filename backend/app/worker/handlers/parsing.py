from uuid import UUID

from backend.app.config import get_settings
from backend.app.domains.parsing import (
    DocumentValidator,
    LLMConfig,
    StructureInferenceService,
    WordDocumentParser,
)
from backend.app.domains.template.repository import TemplateRepository
from backend.app.infrastructure.storage import StorageService
from backend.app.logging_config import get_logger
from backend.app.worker.handlers.base import HandlerContext, HandlerResult, JobHandler

logger = get_logger("worker.handlers.parsing")


class ParsingHandler(JobHandler):
    @property
    def name(self) -> str:
        return "ParsingHandler"

    async def handle(self, context: HandlerContext) -> HandlerResult:
        job = context.job
        template_version_id_str = job.payload.get("template_version_id")

        logger.info(
            f"Parsing handler started for job {job.id}, template_version {template_version_id_str}"
        )

        if not template_version_id_str:
            return HandlerResult(
                success=False,
                error="Missing template_version_id in job payload",
                should_advance_pipeline=False,
            )

        try:
            template_version_id = UUID(template_version_id_str)
        except ValueError:
            return HandlerResult(
                success=False,
                error=f"Invalid template_version_id format: {template_version_id_str}",
                should_advance_pipeline=False,
            )
        settings = get_settings()
        storage = StorageService(settings)
        template_repo = TemplateRepository(context.session)
        version = await template_repo.get_version_by_id(template_version_id)
        if not version:
            return HandlerResult(
                success=False,
                error=f"Template version {template_version_id} not found",
                should_advance_pipeline=False,
            )
        await template_repo.mark_parsing_in_progress(template_version_id)
        await context.session.flush()

        try:
            logger.info(f"Retrieving source document from {version.source_doc_path}")
            source_content = storage.get_file(version.source_doc_path)

            if source_content is None:
                error_msg = f"Source document not found at {version.source_doc_path}"
                await template_repo.mark_parsing_failed(template_version_id, error_msg)
                return HandlerResult(
                    success=False,
                    error=error_msg,
                    should_advance_pipeline=False,
                )
            logger.info("Validating document format")
            validator = DocumentValidator()
            validation_result = validator.validate(source_content)

            if not validation_result.valid:
                error_msg = f"Document validation failed: {validation_result.error_message}"
                await template_repo.mark_parsing_failed(template_version_id, error_msg)
                return HandlerResult(
                    success=False,
                    error=error_msg,
                    should_advance_pipeline=False,
                )

            logger.info(f"Document validated: {validation_result.file_size} bytes")
            logger.info("Parsing document structure")
            parser = WordDocumentParser()
            parsing_result = parser.parse(
                content=source_content,
                template_id=version.template_id,
                template_version_id=template_version_id,
                version_number=version.version_number,
            )

            if not parsing_result.success or not parsing_result.document:
                error_details = "; ".join(e.message for e in parsing_result.errors)
                error_msg = f"Parsing failed: {error_details}"
                await template_repo.mark_parsing_failed(template_version_id, error_msg)
                return HandlerResult(
                    success=False,
                    error=error_msg,
                    should_advance_pipeline=False,
                )

            parsed_doc = parsing_result.document
            logger.info(
                f"Document parsed: {parsed_doc.total_blocks} blocks "
                f"({parsed_doc.heading_count} headings, {parsed_doc.paragraph_count} paragraphs, "
                f"{parsed_doc.table_count} tables, {parsed_doc.list_count} lists)"
            )
            inference_result = None
            if settings.llm_inference_enabled and settings.openai_api_key:
                logger.info("Applying LLM-assisted structure inference")
                try:
                    llm_config = LLMConfig(
                        api_key=settings.openai_api_key,
                        api_base_url=settings.openai_api_base_url,
                        model=settings.openai_model,
                        enabled=True,
                        confidence_threshold=settings.llm_confidence_threshold,
                    )
                    inference_service = StructureInferenceService(llm_config)
                    inference_result = inference_service.infer_structure(parsed_doc)

                    if inference_result.applied_count > 0:
                        logger.info(
                            f"LLM inference applied {inference_result.applied_count} suggestions "
                            f"(skipped {inference_result.skipped_count}) in {inference_result.duration_ms:.2f}ms"
                        )
                    else:
                        logger.info("LLM inference: no changes applied")

                    inference_service.close()
                except Exception as e:
                    logger.warning(f"LLM inference failed (continuing without): {e}")
            else:
                logger.info("LLM inference disabled, skipping")

            logger.info("Persisting parsed representation to storage")
            parsed_path = storage.upload_template_parsed_json(
                template_id=version.template_id,
                version=version.version_number,
                parsed_data=parsed_doc.model_dump(mode="json"),
            )

            await template_repo.mark_parsing_completed(
                version_id=template_version_id,
                parsed_path=parsed_path,
                content_hash=parsed_doc.content_hash,
            )

            result_data = {
                "template_version_id": str(template_version_id),
                "template_id": str(version.template_id),
                "version_number": version.version_number,
                "content_hash": parsed_doc.content_hash,
                "parsed_path": parsed_path,
                "statistics": {
                    "total_blocks": parsed_doc.total_blocks,
                    "headings": parsed_doc.heading_count,
                    "paragraphs": parsed_doc.paragraph_count,
                    "tables": parsed_doc.table_count,
                    "lists": parsed_doc.list_count,
                    "headers": len(parsed_doc.headers),
                    "footers": len(parsed_doc.footers),
                },
                "timing": {
                    "parse_duration_ms": parsing_result.parse_duration_ms,
                    "inference_duration_ms": (
                        inference_result.duration_ms if inference_result else None
                    ),
                    "total_duration_ms": parsing_result.total_duration_ms,
                },
            }

            if inference_result:
                result_data["inference"] = {
                    "suggestions_count": len(inference_result.suggestions),
                    "applied_count": inference_result.applied_count,
                    "skipped_count": inference_result.skipped_count,
                }

            if parsing_result.warnings:
                result_data["warnings"] = parsing_result.warnings

            logger.info(f"Parsing completed successfully for job {job.id}")

            return HandlerResult(
                success=True,
                data=result_data,
                should_advance_pipeline=True,
            )

        except Exception as e:
            logger.error(f"Parsing failed for job {job.id}: {e}", exc_info=True)
            await template_repo.mark_parsing_failed(template_version_id, str(e))
            return HandlerResult(
                success=False,
                error=str(e),
                should_advance_pipeline=False,
            )
