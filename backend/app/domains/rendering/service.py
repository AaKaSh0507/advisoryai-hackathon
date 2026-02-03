import io
import time
from typing import Any
from uuid import UUID

from backend.app.domains.assembly.models import AssembledDocument, AssemblyStatus
from backend.app.domains.assembly.repository import AssembledDocumentRepository
from backend.app.domains.rendering.engine import DocumentRenderer
from backend.app.domains.rendering.models import RenderedDocument
from backend.app.domains.rendering.repository import RenderedDocumentRepository
from backend.app.domains.rendering.schemas import (
    RenderedDocumentSchema,
    RenderErrorCode,
    RenderingRequest,
    RenderingResult,
    RenderingValidationResult,
    compute_file_hash,
)
from backend.app.domains.rendering.validator import RenderedDocumentValidator
from backend.app.infrastructure.storage import StorageService
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.rendering.service")


class DocumentRenderingService:
    def __init__(
        self,
        repository: RenderedDocumentRepository,
        assembled_document_repository: AssembledDocumentRepository,
        storage: StorageService,
    ):
        self.repository = repository
        self.assembled_document_repository = assembled_document_repository
        self.storage = storage
        self.renderer = DocumentRenderer()
        self.validator = RenderedDocumentValidator()

    async def render_document(self, request: RenderingRequest) -> RenderingResult:
        start_time = time.time()

        try:
            assembled_doc = await self.assembled_document_repository.get_by_id(
                request.assembled_document_id
            )

            if not assembled_doc:
                return self._create_error_result(
                    RenderErrorCode.INVALID_ASSEMBLED_DOCUMENT,
                    f"Assembled document {request.assembled_document_id} not found",
                    start_time,
                )

            validation_error = self._validate_assembled_document(assembled_doc)
            if validation_error:
                return validation_error

            existing = await self.repository.get_by_assembled_document(
                request.assembled_document_id
            )
            if existing and existing.is_immutable and not request.force_rerender:
                return self._create_error_result(
                    RenderErrorCode.ALREADY_RENDERED,
                    "Document already rendered and immutable",
                    start_time,
                )

            rendered_doc = await self.repository.create(
                assembled_document_id=request.assembled_document_id,
                document_id=request.document_id,
                version=request.version,
            )

            await self.repository.mark_in_progress(rendered_doc)

            assembled_structure = self._extract_assembled_structure(assembled_doc)

            content, statistics = self.renderer.render(assembled_structure)

            if content is None:
                errors = self.renderer.errors
                error_msg = errors[0][1] if errors else "Unknown rendering error"
                await self.repository.mark_failed(
                    rendered_doc,
                    RenderErrorCode.RENDERING_FAILED.value,
                    error_msg,
                )
                return self._create_error_result(
                    RenderErrorCode.RENDERING_FAILED,
                    error_msg,
                    start_time,
                )

            validation_result = self.validator.validate(
                content,
                expected_blocks=statistics.total_blocks,
                expected_paragraphs=statistics.paragraphs,
                expected_tables=statistics.tables,
                expected_headings=statistics.headings,
            )

            if not validation_result.is_valid:
                await self.repository.mark_failed(
                    rendered_doc,
                    RenderErrorCode.VALIDATION_FAILED.value,
                    "; ".join(validation_result.error_messages),
                )
                return RenderingResult(
                    success=False,
                    validation_result=validation_result,
                    error_code=RenderErrorCode.VALIDATION_FAILED,
                    error_message="; ".join(validation_result.error_messages),
                    rendering_duration_ms=(time.time() - start_time) * 1000,
                )

            content_hash = compute_file_hash(content)
            file_obj = io.BytesIO(content)

            output_path = self.storage.upload_document_output(
                document_id=request.document_id,
                version=request.version,
                file_obj=file_obj,
            )

            if not self.storage.file_exists(output_path):
                await self.repository.mark_failed(
                    rendered_doc,
                    RenderErrorCode.PERSISTENCE_FAILED.value,
                    f"Failed to persist document to {output_path}",
                )
                return self._create_error_result(
                    RenderErrorCode.PERSISTENCE_FAILED,
                    "Failed to persist document to storage",
                    start_time,
                )

            rendering_duration = (time.time() - start_time) * 1000

            rendered_doc = await self.repository.mark_completed(
                rendered_doc,
                output_path=output_path,
                content_hash=content_hash,
                file_size_bytes=len(content),
                total_blocks=statistics.total_blocks,
                paragraphs=statistics.paragraphs,
                tables=statistics.tables,
                lists=statistics.lists,
                headings=statistics.headings,
                headers=statistics.headers,
                footers=statistics.footers,
                rendering_duration_ms=rendering_duration,
            )

            rendered_doc = await self.repository.mark_validated(
                rendered_doc,
                validation_result=validation_result.model_dump(),
            )

            return RenderingResult(
                success=True,
                rendered_document=self._to_schema(rendered_doc),
                validation_result=validation_result,
                output_path=output_path,
                rendering_duration_ms=rendering_duration,
            )

        except Exception as e:
            logger.error(f"Rendering failed with exception: {e}")
            return self._create_error_result(
                RenderErrorCode.RENDERING_FAILED,
                str(e),
                start_time,
            )

    async def get_rendered_document(self, rendered_doc_id: UUID) -> RenderedDocument | None:
        return await self.repository.get_by_id(rendered_doc_id)

    async def get_rendered_by_document_version(
        self, document_id: UUID, version: int
    ) -> RenderedDocument | None:
        return await self.repository.get_by_document_and_version(document_id, version)

    async def get_rendered_content(self, document_id: UUID, version: int) -> bytes | None:
        rendered = await self.repository.get_by_document_and_version(document_id, version)
        if not rendered or not rendered.output_path:
            return None
        return self.storage.get_file(rendered.output_path)

    async def validate_existing_render(
        self, rendered_doc_id: UUID
    ) -> RenderingValidationResult | None:
        rendered = await self.repository.get_by_id(rendered_doc_id)
        if not rendered or not rendered.output_path:
            return None

        content = self.storage.get_file(rendered.output_path)
        if not content:
            return None

        return self.validator.validate(content)

    async def verify_determinism(self, assembled_document_id: UUID) -> tuple[bool, str]:
        assembled_doc = await self.assembled_document_repository.get_by_id(assembled_document_id)
        if not assembled_doc:
            return False, "Assembled document not found"

        assembled_structure = self._extract_assembled_structure(assembled_doc)

        content1, _ = self.renderer.render(assembled_structure)
        if not content1:
            return False, "First render failed"

        self.renderer = DocumentRenderer()

        content2, _ = self.renderer.render(assembled_structure)
        if not content2:
            return False, "Second render failed"

        return self.validator.validate_determinism(content1, content2)

    def _validate_assembled_document(
        self, assembled_doc: AssembledDocument
    ) -> RenderingResult | None:
        if not assembled_doc.is_immutable:
            return self._create_error_result(
                RenderErrorCode.DOCUMENT_NOT_IMMUTABLE,
                "Assembled document must be immutable before rendering",
                time.time(),
            )

        if assembled_doc.status != AssemblyStatus.VALIDATED:
            return self._create_error_result(
                RenderErrorCode.DOCUMENT_NOT_VALIDATED,
                f"Assembled document status is {assembled_doc.status}, expected VALIDATED",
                time.time(),
            )

        if not assembled_doc.assembled_structure:
            return self._create_error_result(
                RenderErrorCode.MISSING_ASSEMBLED_STRUCTURE,
                "Assembled document has no structure",
                time.time(),
            )

        return None

    def _extract_assembled_structure(self, assembled_doc: AssembledDocument) -> dict[str, Any]:
        structure = assembled_doc.assembled_structure or {}

        if assembled_doc.document_metadata:
            structure["metadata"] = assembled_doc.document_metadata

        if assembled_doc.headers:
            structure["headers"] = assembled_doc.headers

        if assembled_doc.footers:
            structure["footers"] = assembled_doc.footers

        return structure

    def _create_error_result(
        self,
        error_code: RenderErrorCode,
        error_message: str,
        start_time: float,
    ) -> RenderingResult:
        return RenderingResult(
            success=False,
            error_code=error_code,
            error_message=error_message,
            rendering_duration_ms=(time.time() - start_time) * 1000,
        )

    def _to_schema(self, rendered_doc: RenderedDocument) -> RenderedDocumentSchema:
        return RenderedDocumentSchema(
            id=rendered_doc.id,
            assembled_document_id=rendered_doc.assembled_document_id,
            document_id=rendered_doc.document_id,
            version=rendered_doc.version,
            status=rendered_doc.status.value,
            output_path=rendered_doc.output_path,
            content_hash=rendered_doc.content_hash,
            file_size_bytes=rendered_doc.file_size_bytes,
            total_blocks_rendered=rendered_doc.total_blocks_rendered,
            paragraphs_rendered=rendered_doc.paragraphs_rendered,
            tables_rendered=rendered_doc.tables_rendered,
            lists_rendered=rendered_doc.lists_rendered,
            headings_rendered=rendered_doc.headings_rendered,
            headers_rendered=rendered_doc.headers_rendered,
            footers_rendered=rendered_doc.footers_rendered,
            is_immutable=rendered_doc.is_immutable,
            rendered_at=rendered_doc.rendered_at,
            created_at=rendered_doc.created_at,
        )
