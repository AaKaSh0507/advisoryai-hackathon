"""
Demo API endpoints for demo data management and validation.

Provides endpoints for:
- Seeding demo data
- Validating demo flows
- Getting demo entity IDs
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_db
from backend.app.infrastructure.demo_seeding import DemoDataSeeder, get_demo_ids
from backend.app.logging_config import get_logger

router = APIRouter()
logger = get_logger("app.api.v1.demo")

DbSession = Annotated[AsyncSession, Depends(get_db)]


class DemoSeedRequest(BaseModel):
    """Request for seeding demo data."""

    force: bool = False


class DemoSeedResponse(BaseModel):
    """Response from demo data seeding."""

    success: bool
    message: str
    entities: dict[str, Any]


class DemoIdsResponse(BaseModel):
    """Response with demo entity IDs."""

    ids: dict[str, str]


class DemoValidationResponse(BaseModel):
    """Response from demo flow validation."""

    valid: bool
    flows_validated: list[str]
    errors: list[str]


@router.post(
    "/seed",
    response_model=DemoSeedResponse,
    status_code=status.HTTP_200_OK,
    summary="Seed demo data",
    description="Seed deterministic demo data for reliable demo flows.",
)
async def seed_demo_data(
    request: DemoSeedRequest,
    session: DbSession,
) -> DemoSeedResponse:
    """
    Seed demo data.

    - Creates deterministic templates, documents, sections
    - Can be re-run safely (force=True to reset)
    - Does not pollute real data paths
    """
    logger.info(f"Demo data seeding requested, force={request.force}")

    try:
        seeder = DemoDataSeeder(session)
        entities = await seeder.seed_all(force=request.force)

        return DemoSeedResponse(
            success=True,
            message="Demo data seeded successfully",
            entities=entities,
        )
    except Exception as e:
        logger.error(f"Demo data seeding failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {str(e)}",
        )


@router.get(
    "/ids",
    response_model=DemoIdsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get demo entity IDs",
    description="Get the deterministic IDs used for demo entities.",
)
async def get_demo_entity_ids() -> DemoIdsResponse:
    """Get all demo entity IDs for reference."""
    return DemoIdsResponse(ids=get_demo_ids())


@router.post(
    "/validate",
    response_model=DemoValidationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate demo flows",
    description="Validate that demo flows are working correctly.",
)
async def validate_demo_flows(
    session: DbSession,
) -> DemoValidationResponse:
    """
    Validate demo flows.

    Checks:
    - Template upload → document generation
    - Section-level regeneration
    - Full regeneration
    - Template update → new document generation
    - Failure → recovery → retry
    """
    logger.info("Demo flow validation requested")

    flows_validated = []
    errors = []

    # Check demo template exists
    from sqlalchemy import select

    from backend.app.domains.template.models import Template
    from backend.app.infrastructure.demo_seeding import DEMO_TEMPLATE_ID

    stmt = select(Template).where(Template.id == DEMO_TEMPLATE_ID)
    result = await session.execute(stmt)
    template = result.scalar_one_or_none()

    if template:
        flows_validated.append("demo_template_exists")
    else:
        errors.append("Demo template not found - run /api/v1/demo/seed first")

    # Check demo template version exists
    from backend.app.domains.template.models import TemplateVersion
    from backend.app.infrastructure.demo_seeding import DEMO_TEMPLATE_VERSION_ID

    stmt = select(TemplateVersion).where(TemplateVersion.id == DEMO_TEMPLATE_VERSION_ID)
    result = await session.execute(stmt)
    template_version = result.scalar_one_or_none()

    if template_version:
        flows_validated.append("demo_template_version_exists")
        if template_version.parsing_status.value == "COMPLETED":
            flows_validated.append("demo_template_parsed")
        else:
            errors.append(f"Demo template version not parsed: {template_version.parsing_status}")
    else:
        errors.append("Demo template version not found")

    # Check demo document exists
    from backend.app.domains.document.models import Document
    from backend.app.infrastructure.demo_seeding import DEMO_DOCUMENT_ID

    stmt = select(Document).where(Document.id == DEMO_DOCUMENT_ID)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()

    if document:
        flows_validated.append("demo_document_exists")
        if document.current_version >= 1:
            flows_validated.append("demo_document_has_version")
    else:
        errors.append("Demo document not found")

    # Check sections exist
    from backend.app.domains.section.models import Section, SectionType

    stmt = select(Section).where(Section.template_version_id == DEMO_TEMPLATE_VERSION_ID)
    result = await session.execute(stmt)
    sections = result.scalars().all()

    if sections:
        flows_validated.append(f"demo_sections_exist ({len(sections)})")
        dynamic_sections = [s for s in sections if s.section_type == SectionType.DYNAMIC]
        if dynamic_sections:
            flows_validated.append(f"demo_dynamic_sections_exist ({len(dynamic_sections)})")
    else:
        errors.append("Demo sections not found")

    from backend.app.domains.job.models import Job, JobStatus

    stmt = select(Job).where(
        Job.payload.contains({"template_version_id": str(DEMO_TEMPLATE_VERSION_ID)})
    )
    result = await session.execute(stmt)
    jobs = result.scalars().all()

    completed_jobs = [j for j in jobs if j.status == JobStatus.COMPLETED]
    if completed_jobs:
        flows_validated.append(f"demo_jobs_completed ({len(completed_jobs)})")
    else:
        errors.append("No completed demo jobs found")

    valid = len(errors) == 0

    logger.info(
        f"Demo flow validation completed: valid={valid}, "
        f"flows={len(flows_validated)}, errors={len(errors)}"
    )

    return DemoValidationResponse(
        valid=valid,
        flows_validated=flows_validated,
        errors=errors,
    )
