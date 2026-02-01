from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from backend.app.domains.section.schemas import (
    SectionCreate,
    SectionUpdate,
    SectionResponse,
    SectionReorder,
)
from backend.app.domains.section.service import SectionService

router = APIRouter()
service = SectionService()


@router.get("", response_model=list[SectionResponse])
async def list_sections(
    template_id: UUID, skip: int = 0, limit: int = 100
) -> list[SectionResponse]:
    sections = await service.list_sections_by_template(
        template_id=template_id, skip=skip, limit=limit
    )
    return [SectionResponse.model_validate(s) for s in sections]


@router.post("", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(data: SectionCreate) -> SectionResponse:
    section = await service.create_section(data)
    return SectionResponse.model_validate(section)


@router.get("/{section_id}", response_model=SectionResponse)
async def get_section(section_id: UUID) -> SectionResponse:
    section = await service.get_section(section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found",
        )
    return SectionResponse.model_validate(section)


@router.patch("/{section_id}", response_model=SectionResponse)
async def update_section(section_id: UUID, data: SectionUpdate) -> SectionResponse:
    section = await service.update_section(section_id, data)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found",
        )
    return SectionResponse.model_validate(section)


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(section_id: UUID) -> None:
    deleted = await service.delete_section(section_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Section {section_id} not found",
        )


@router.post("/reorder", status_code=status.HTTP_200_OK)
async def reorder_sections(template_id: UUID, data: SectionReorder) -> dict:
    success = await service.reorder_sections(template_id, data.section_ids)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reorder sections",
        )
    return {"message": "Sections reordered successfully"}
