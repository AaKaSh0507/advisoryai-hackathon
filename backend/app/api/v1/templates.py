from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Depends
from backend.app.domains.template.schemas import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateVersionResponse,
)
from backend.app.domains.template.service import TemplateService
from backend.app.api.deps import get_template_service
from fastapi import UploadFile, File

router = APIRouter()

TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]

@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    service: TemplateServiceDep,
    skip: int = 0, 
    limit: int = 100
) -> list[TemplateResponse]:
    templates = await service.list_templates(skip=skip, limit=limit)
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    service: TemplateServiceDep
) -> TemplateResponse:
    template = await service.create_template(data)
    # Commit happens in middleware or should happen here?
    # Usually one commit per request.
    # But we don't have middleware for commit yet.
    # References say "Repositories must not call other repositories".
    # Transaction management is usually in Service or Controller or Middleware.
    # Simple approach: commit in controller or service.
    # Since I exposed session in repo, I can commit here or in service.
    # Service calls flush.
    # I should probably commit in the endpoint or have a dependency that auto-commits.
    # For now, let's explicitly commit in the endpoint to be safe, or add a commit to service.
    # OR better: use a UnitOfWork. But for now, direct session usage.
    # I'll rely on the fact that if I don't commit, it rolls back?
    # I NEED TO COMMIT.
    # I'll modify Service to commit? Or Endpoint?
    # Endpoint seems easier to control.
    # But service needs to be atomic?
    # Let's add commit in service methods for now, or use `commit=True` flag?
    # Or just `await service.repo.session.commit()`.
    await service.repo.session.commit()
    await service.repo.session.refresh(template)
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    service: TemplateServiceDep
) -> TemplateResponse:
    template = await service.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    return TemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID, 
    data: TemplateUpdate,
    service: TemplateServiceDep
) -> TemplateResponse:
    template = await service.update_template(template_id, data)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    await service.repo.session.commit()
    await service.repo.session.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    service: TemplateServiceDep
) -> None:
    deleted = await service.delete_template(template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    await service.repo.session.commit()

@router.post("/{template_id}/versions", response_model=TemplateVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    template_id: UUID,
    service: TemplateServiceDep,
    file: UploadFile = File(...)
) -> TemplateVersionResponse:
    version = await service.create_template_version(template_id, file.file)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    await service.repo.session.commit()
    await service.repo.session.refresh(version)
    return TemplateVersionResponse.model_validate(version)

@router.get("/{template_id}/versions", response_model=list[TemplateVersionResponse])
async def list_template_versions(
    template_id: UUID,
    service: TemplateServiceDep
) -> list[TemplateVersionResponse]:
    versions = await service.repo.list_versions(template_id)
    return [TemplateVersionResponse.model_validate(v) for v in versions]

@router.get("/{template_id}/versions/{version_number}", response_model=TemplateVersionResponse)
async def get_template_version(
    template_id: UUID,
    version_number: int,
    service: TemplateServiceDep
) -> TemplateVersionResponse:
    version = await service.repo.get_version(template_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for template {template_id}",
        )
    return TemplateVersionResponse.model_validate(version)
