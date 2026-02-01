from typing import Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from backend.app.domains.template.schemas import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
)
from backend.app.domains.template.service import TemplateService

router = APIRouter()
service = TemplateService()


@router.get("", response_model=list[TemplateResponse])
async def list_templates(skip: int = 0, limit: int = 100) -> list[TemplateResponse]:
    templates = await service.list_templates(skip=skip, limit=limit)
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(data: TemplateCreate) -> TemplateResponse:
    template = await service.create_template(data)
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: UUID) -> TemplateResponse:
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    return TemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: UUID, data: TemplateUpdate) -> TemplateResponse:
    template = await service.update_template(template_id, data)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: UUID) -> None:
    deleted = await service.delete_template(template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
