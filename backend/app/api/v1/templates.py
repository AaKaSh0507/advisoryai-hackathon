from typing import Annotated
from uuid import UUID

from backend.app.api.deps import get_job_service, get_template_service
from backend.app.config import get_settings
from backend.app.domains.job.schemas import ParseJobCreate
from backend.app.domains.job.service import JobService
from backend.app.domains.template.schemas import (
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
    TemplateVersionResponse,
)
from backend.app.domains.template.service import TemplateService
from backend.app.infrastructure.redis import get_redis_client
from backend.app.infrastructure.storage import StorageService
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

router = APIRouter()

TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    service: TemplateServiceDep,
    skip: int = 0,
    limit: int = 100,
) -> list[TemplateResponse]:
    templates = await service.list_templates(skip=skip, limit=limit)
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    service: TemplateServiceDep,
) -> TemplateResponse:
    template = await service.create_template(data)
    await service.repo.session.commit()
    await service.repo.session.refresh(template)
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    service: TemplateServiceDep,
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
    service: TemplateServiceDep,
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
    service: TemplateServiceDep,
) -> None:
    deleted = await service.delete_template(template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )
    await service.repo.session.commit()


@router.post(
    "/{template_id}/versions",
    response_model=TemplateVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_version(
    template_id: UUID,
    service: TemplateServiceDep,
    job_service: JobServiceDep,
    file: UploadFile = File(..., description="Word document (.docx) file to upload"),
) -> TemplateVersionResponse:
    """
    Upload a new template version.

    Accepts only .docx files. This automatically triggers the processing pipeline:
    1. Validates the uploaded file is a valid .docx
    2. Creates a PARSE job to extract template structure
    3. On PARSE completion, a CLASSIFY job is created automatically
    4. Once classified, the template is ready for document generation
    """
    # Validate file extension
    if file.filename and not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx files are accepted. Please upload a Word document.",
        )

    # Validate content type
    valid_content_types = [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",  # Some clients send this
    ]
    if file.content_type and file.content_type not in valid_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {file.content_type}. Expected .docx file.",
        )

    version = await service.create_template_version(template_id, file.file)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found",
        )

    # Create PARSE job to start the pipeline
    parse_job = await job_service.create_parse_job(ParseJobCreate(template_version_id=version.id))

    await service.repo.session.commit()
    await service.repo.session.refresh(version)

    # Notify workers about the new job
    try:
        settings = get_settings()
        redis_client = get_redis_client(settings.redis_url)
        redis_client.notify_job_created(parse_job.id, parse_job.job_type.value)
    except Exception:
        pass  # Redis notification is best-effort

    return TemplateVersionResponse.model_validate(version)


@router.get("/{template_id}/versions", response_model=list[TemplateVersionResponse])
async def list_template_versions(
    template_id: UUID,
    service: TemplateServiceDep,
) -> list[TemplateVersionResponse]:
    versions = await service.repo.list_versions(template_id)
    return [TemplateVersionResponse.model_validate(v) for v in versions]


@router.get("/{template_id}/versions/{version_number}", response_model=TemplateVersionResponse)
async def get_template_version(
    template_id: UUID,
    version_number: int,
    service: TemplateServiceDep,
) -> TemplateVersionResponse:
    version = await service.repo.get_version(template_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for template {template_id}",
        )
    return TemplateVersionResponse.model_validate(version)


@router.get("/{template_id}/versions/{version_number}/parsed")
async def get_parsed_representation(
    template_id: UUID,
    version_number: int,
    service: TemplateServiceDep,
) -> dict:
    """
    Get the parsed representation of a template version.

    Returns the full parsed JSON structure including all blocks,
    metadata, and statistics.

    Requires the template version to have been successfully parsed.
    """
    from backend.app.domains.template.models import ParsingStatus

    version = await service.repo.get_version(template_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for template {template_id}",
        )

    if version.parsing_status != ParsingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template version is not parsed. Status: {version.parsing_status.value}",
        )

    if not version.parsed_representation_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed representation path not found",
        )

    # Retrieve from storage
    settings = get_settings()
    storage = StorageService(settings)
    parsed_data = storage.get_template_parsed(template_id, version_number)

    if parsed_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parsed representation not found in storage",
        )

    return parsed_data


@router.get("/{template_id}/versions/{version_number}/status")
async def get_parsing_status(
    template_id: UUID,
    version_number: int,
    service: TemplateServiceDep,
) -> dict:
    """
    Get the parsing status of a template version.

    Returns current status, any errors, and completion timestamp.
    """
    version = await service.repo.get_version(template_id, version_number)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for template {template_id}",
        )

    return {
        "template_version_id": str(version.id),
        "parsing_status": version.parsing_status.value,
        "parsing_error": version.parsing_error,
        "parsed_at": version.parsed_at.isoformat() if version.parsed_at else None,
        "content_hash": version.content_hash,
        "is_parsed": version.is_parsed,
    }
