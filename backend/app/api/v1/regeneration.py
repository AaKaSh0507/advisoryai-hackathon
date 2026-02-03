"""
Regeneration API endpoints.

Provides endpoints for:
- Section-level regeneration
- Full document regeneration
- Template update regeneration
- Regeneration history retrieval
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_regeneration_service
from backend.app.domains.regeneration.schemas import (
    FullRegenerationRequest,
    RegenerationResult,
    SectionRegenerationRequest,
    TemplateUpdateRegenerationRequest,
    VersionTransition,
)
from backend.app.domains.regeneration.service import RegenerationService
from backend.app.logging_config import get_logger

router = APIRouter()
logger = get_logger("app.api.v1.regeneration")

RegenerationServiceDep = Annotated[RegenerationService, Depends(get_regeneration_service)]


@router.post(
    "/documents/{document_id}/regenerate/sections",
    response_model=RegenerationResult,
    status_code=status.HTTP_200_OK,
    summary="Regenerate specific sections",
    description="Regenerate one or more specific DYNAMIC sections without full document reprocessing.",
)
async def regenerate_sections(
    document_id: UUID,
    request: SectionRegenerationRequest,
    service: RegenerationServiceDep,
) -> RegenerationResult:
    """
    Regenerate specific sections of a document.

    - Only DYNAMIC sections can be regenerated
    - Creates a new document version
    - Unchanged sections are reused based on strategy
    - Previous versions remain untouched
    """
    if request.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID in path does not match request body",
        )

    logger.info(
        f"Section regeneration requested for document {document_id}, "
        f"sections: {[t.section_id for t in request.target_sections]}"
    )

    result = await service.regenerate_sections(request)

    if not result.success and result.error:
        logger.warning(f"Section regeneration failed for document {document_id}: {result.error}")

    return result


@router.post(
    "/documents/{document_id}/regenerate/full",
    response_model=RegenerationResult,
    status_code=status.HTTP_200_OK,
    summary="Regenerate entire document",
    description="Regenerate the entire document using the same template version.",
)
async def regenerate_full_document(
    document_id: UUID,
    request: FullRegenerationRequest,
    service: RegenerationServiceDep,
) -> RegenerationResult:
    """
    Regenerate entire document.

    - Re-executes full pipeline
    - Creates a new document version
    - Previous versions remain untouched
    - Idempotent and restart-safe
    """
    if request.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID in path does not match request body",
        )

    logger.info(f"Full regeneration requested for document {document_id}")

    result = await service.regenerate_full_document(request)

    if not result.success and result.error:
        logger.warning(f"Full regeneration failed for document {document_id}: {result.error}")

    return result


@router.post(
    "/documents/{document_id}/regenerate/template-update",
    response_model=RegenerationResult,
    status_code=status.HTTP_200_OK,
    summary="Regenerate with new template version",
    description="Regenerate document using a new template version.",
)
async def regenerate_for_template_update(
    document_id: UUID,
    request: TemplateUpdateRegenerationRequest,
    service: RegenerationServiceDep,
) -> RegenerationResult:
    """
    Regenerate document using a new template version.

    - Document is regenerated with new template structure
    - Previous versions tied to old template remain untouched
    - Audit captures template version transition
    """
    if request.document_id != document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document ID in path does not match request body",
        )

    logger.info(
        f"Template update regeneration requested for document {document_id}, "
        f"new template version: {request.new_template_version_id}"
    )

    result = await service.regenerate_for_template_update(request)

    if not result.success and result.error:
        logger.warning(
            f"Template update regeneration failed for document {document_id}: {result.error}"
        )

    return result


@router.get(
    "/documents/{document_id}/regeneration-history",
    response_model=list[VersionTransition],
    status_code=status.HTTP_200_OK,
    summary="Get regeneration history",
    description="Retrieve the history of regeneration operations for a document.",
)
async def get_regeneration_history(
    document_id: UUID,
    service: RegenerationServiceDep,
    limit: int = 100,
) -> list[VersionTransition]:
    """
    Get regeneration history for a document.

    Returns version transitions with regeneration details.
    """
    logger.info(f"Regeneration history requested for document {document_id}")

    return await service.get_regeneration_history(document_id, limit=limit)
