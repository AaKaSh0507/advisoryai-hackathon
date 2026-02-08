from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.app.api.deps import get_rendering_service
from backend.app.domains.rendering.schemas import (
    RenderedDocumentSchema,
    RenderErrorCode,
    RenderingRequest,
    RenderingResult,
    RenderingValidationResult,
)
from backend.app.domains.rendering.service import DocumentRenderingService
from backend.app.logging_config import get_logger

logger = get_logger("app.api.v1.rendering")
router = APIRouter()
RenderingServiceDep = Annotated[DocumentRenderingService, Depends(get_rendering_service)]


@router.post("", response_model=RenderingResult, status_code=status.HTTP_201_CREATED)
async def render_document(
    request: RenderingRequest,
    service: RenderingServiceDep,
) -> RenderingResult:
    result = await service.render_document(request)

    if not result.success:
        if result.error_code == RenderErrorCode.ALREADY_RENDERED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.error_message,
            )
        if result.error_code == RenderErrorCode.INVALID_ASSEMBLED_DOCUMENT:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error_message,
            )
        if result.error_code in (
            RenderErrorCode.DOCUMENT_NOT_IMMUTABLE,
            RenderErrorCode.DOCUMENT_NOT_VALIDATED,
            RenderErrorCode.MISSING_ASSEMBLED_STRUCTURE,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message,
        )

    return result


@router.get("/{rendered_document_id}", response_model=RenderedDocumentSchema)
async def get_rendered_document(
    rendered_document_id: UUID,
    service: RenderingServiceDep,
) -> RenderedDocumentSchema:
    rendered = await service.get_rendered_document(rendered_document_id)
    if not rendered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rendered document {rendered_document_id} not found",
        )
    return RenderedDocumentSchema(
        id=rendered.id,
        assembled_document_id=rendered.assembled_document_id,
        document_id=rendered.document_id,
        version=rendered.version,
        status=rendered.status.value,
        output_path=rendered.output_path,
        content_hash=rendered.content_hash,
        file_size_bytes=rendered.file_size_bytes,
        total_blocks_rendered=rendered.total_blocks_rendered,
        paragraphs_rendered=rendered.paragraphs_rendered,
        tables_rendered=rendered.tables_rendered,
        lists_rendered=rendered.lists_rendered,
        headings_rendered=rendered.headings_rendered,
        headers_rendered=rendered.headers_rendered,
        footers_rendered=rendered.footers_rendered,
        is_immutable=rendered.is_immutable,
        rendered_at=rendered.rendered_at,
        created_at=rendered.created_at,
    )


@router.get("/document/{document_id}/version/{version}", response_model=RenderedDocumentSchema)
async def get_rendered_by_document_version(
    document_id: UUID,
    version: int,
    service: RenderingServiceDep,
) -> RenderedDocumentSchema:
    rendered = await service.get_rendered_by_document_version(document_id, version)
    if not rendered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rendered document not found for document {document_id} version {version}",
        )
    return RenderedDocumentSchema(
        id=rendered.id,
        assembled_document_id=rendered.assembled_document_id,
        document_id=rendered.document_id,
        version=rendered.version,
        status=rendered.status.value,
        output_path=rendered.output_path,
        content_hash=rendered.content_hash,
        file_size_bytes=rendered.file_size_bytes,
        total_blocks_rendered=rendered.total_blocks_rendered,
        paragraphs_rendered=rendered.paragraphs_rendered,
        tables_rendered=rendered.tables_rendered,
        lists_rendered=rendered.lists_rendered,
        headings_rendered=rendered.headings_rendered,
        headers_rendered=rendered.headers_rendered,
        footers_rendered=rendered.footers_rendered,
        is_immutable=rendered.is_immutable,
        rendered_at=rendered.rendered_at,
        created_at=rendered.created_at,
    )


@router.get("/document/{document_id}/version/{version}/download")
async def download_rendered_document(
    document_id: UUID,
    version: int,
    service: RenderingServiceDep,
) -> Response:
    logger.info(f"Download request for document {document_id} version {version}")

    content = await service.get_rendered_content(document_id, version)
    if not content:
        logger.error(f"Content not found for document {document_id} version {version}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rendered document not found for document {document_id} version {version}. The document may not have been rendered yet or the file may not exist in storage.",
        )

    logger.info(
        f"Successfully returning {len(content)} bytes for document {document_id} version {version}"
    )

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename=document_{document_id}_v{version}.docx",
            "Content-Length": str(len(content)),
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/{rendered_document_id}/validate", response_model=RenderingValidationResult)
async def validate_rendered_document(
    rendered_document_id: UUID,
    service: RenderingServiceDep,
) -> RenderingValidationResult:
    result = await service.validate_existing_render(rendered_document_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rendered document {rendered_document_id} not found or has no content",
        )
    return result


@router.post("/verify-determinism/{assembled_document_id}")
async def verify_rendering_determinism(
    assembled_document_id: UUID,
    service: RenderingServiceDep,
) -> dict:
    is_deterministic, message = await service.verify_determinism(assembled_document_id)
    return {
        "assembled_document_id": str(assembled_document_id),
        "is_deterministic": is_deterministic,
        "message": message,
    }
