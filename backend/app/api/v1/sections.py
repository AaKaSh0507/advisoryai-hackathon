from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.api.deps import get_job_service, get_section_service
from backend.app.domains.job.schemas import ClassifyJobCreate
from backend.app.domains.job.service import JobService
from backend.app.domains.section.schemas import SectionCreate, SectionResponse
from backend.app.domains.section.service import SectionService

router = APIRouter()
SectionServiceDep = Annotated[SectionService, Depends(get_section_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]


class ClassificationTriggerRequest(BaseModel):
    template_version_id: UUID = Field(..., description="Template version to classify")


class ClassificationTriggerResponse(BaseModel):
    job_id: UUID = Field(..., description="ID of the created classification job")
    template_version_id: UUID
    message: str


@router.post("", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(data: SectionCreate, service: SectionServiceDep) -> SectionResponse:
    section = await service.create_section(data)
    await service.repo.session.commit()
    await service.repo.session.refresh(section)
    return cast(SectionResponse, SectionResponse.model_validate(section))


@router.get("/template-version/{template_version_id}", response_model=list[SectionResponse])
async def list_sections(
    template_version_id: UUID, service: SectionServiceDep
) -> list[SectionResponse]:
    sections = await service.get_sections_by_template_version(template_version_id)
    return [SectionResponse.model_validate(s) for s in sections]


@router.post(
    "/classify", response_model=ClassificationTriggerResponse, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_classification(
    request: ClassificationTriggerRequest,
    job_service: JobServiceDep,
) -> ClassificationTriggerResponse:
    job = await job_service.create_classify_job(
        ClassifyJobCreate(template_version_id=request.template_version_id)
    )

    await job_service.repo.session.commit()

    return ClassificationTriggerResponse(
        job_id=job.id,
        template_version_id=request.template_version_id,
        message=f"Classification job {job.id} created. Monitor status at /api/v1/jobs/{job.id}",
    )


@router.get("/template-version/{template_version_id}/classification-stats")
async def get_classification_stats(
    template_version_id: UUID,
    service: SectionServiceDep,
):
    sections = await service.get_sections_by_template_version(template_version_id)

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sections found for template version {template_version_id}. Has classification run?",
        )

    total = len(sections)
    static_count = sum(1 for s in sections if s.section_type.value == "STATIC")
    dynamic_count = sum(1 for s in sections if s.section_type.value == "DYNAMIC")
    high_conf = 0
    medium_conf = 0
    low_conf = 0

    for section in sections:
        if section.prompt_config:
            conf = section.prompt_config.get("classification_confidence", 0.0)
            if conf >= 0.9:
                high_conf += 1
            elif conf >= 0.7:
                medium_conf += 1
            else:
                low_conf += 1
        else:
            high_conf += 1

    return {
        "template_version_id": str(template_version_id),
        "total_sections": total,
        "static_sections": static_count,
        "dynamic_sections": dynamic_count,
        "high_confidence_count": high_conf,
        "medium_confidence_count": medium_conf,
        "low_confidence_count": low_conf,
        "static_percentage": round((static_count / total) * 100, 2) if total > 0 else 0,
        "dynamic_percentage": round((dynamic_count / total) * 100, 2) if total > 0 else 0,
    }
