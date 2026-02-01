from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Depends
from backend.app.domains.section.schemas import (
    SectionCreate,
    SectionResponse,
)
from backend.app.domains.section.service import SectionService
from backend.app.api.deps import get_section_service

router = APIRouter()
SectionServiceDep = Annotated[SectionService, Depends(get_section_service)]

@router.post("", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(
    data: SectionCreate,
    service: SectionServiceDep
) -> SectionResponse:
    section = await service.create_section(data)
    await service.repo.session.commit()
    # No refresh needed for auto-increment usually if returning object, but safe to refresh.
    # However, create_batch might attach them.
    await service.repo.session.refresh(section)
    return SectionResponse.model_validate(section)

@router.get("/template-version/{template_version_id}", response_model=list[SectionResponse])
async def list_sections(
    template_version_id: UUID,
    service: SectionServiceDep
) -> list[SectionResponse]:
    sections = await service.get_sections_by_template_version(template_version_id)
    return [SectionResponse.model_validate(s) for s in sections]
