import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.document.models import Document, DocumentVersion
from backend.app.domains.generation.models import GenerationInput, GenerationInputBatch
from backend.app.domains.generation.section_output_models import SectionOutput, SectionOutputBatch
from backend.app.domains.job.models import Job, JobStatus, JobType
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion
from backend.app.logging_config import get_logger

logger = get_logger("app.infrastructure.demo_seeding")


DEMO_TEMPLATE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEMO_TEMPLATE_VERSION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DEMO_DOCUMENT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
DEMO_DOCUMENT_VERSION_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
DEMO_GENERATION_BATCH_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")
DEMO_OUTPUT_BATCH_ID = uuid.UUID("00000000-0000-0000-0000-000000000006")

DEMO_SECTION_IDS = {
    "title": uuid.UUID("55555555-5555-5555-5555-555555555001"),
    "intro": uuid.UUID("55555555-5555-5555-5555-555555555002"),
    "scope": uuid.UUID("55555555-5555-5555-5555-555555555003"),
    "methodology": uuid.UUID("55555555-5555-5555-5555-555555555004"),
    "conclusion": uuid.UUID("55555555-5555-5555-5555-555555555005"),
}

DEMO_JOBS = {
    "parse": {"id": uuid.UUID("66666666-6666-6666-6666-666666666001"), "type": JobType.PARSE},
    "classify": {"id": uuid.UUID("66666666-6666-6666-6666-666666666002"), "type": JobType.CLASSIFY},
    "generate": {"id": uuid.UUID("66666666-6666-6666-6666-666666666003"), "type": JobType.GENERATE},
}

DEMO_PREFIX = "DEMO_"


class DemoDataSeeder:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def seed_all(self, force: bool = False) -> dict[str, Any]:
        logger.info("Starting demo data seeding")

        if force:
            await self._clear_demo_data()

        result: dict[str, Any] = {
            "template_id": None,
            "template_version_id": None,
            "document_id": None,
            "document_version_id": None,
            "sections": [],
            "jobs": [],
        }

        template = await self._seed_template()
        result["template_id"] = str(template.id)

        template_version = await self._seed_template_version(template.id)
        result["template_version_id"] = str(template_version.id)

        sections = await self._seed_sections(template_version.id)
        result["sections"] = [s.id for s in sections]

        jobs = await self._seed_completed_jobs(template_version.id)
        result["jobs"] = [str(j.id) for j in jobs]

        document = await self._seed_document(template_version.id)
        result["document_id"] = str(document.id)

        doc_version = await self._seed_document_version(document.id)
        result["document_version_id"] = str(doc_version.id) if doc_version else None

        await self._seed_audit_logs(template.id, template_version.id, document.id)

        await self.session.commit()

        logger.info(f"Demo data seeding completed: {result}")
        return result

    async def _clear_demo_data(self):
        """Clear existing demo data."""
        logger.info("Clearing existing demo data")

        from sqlalchemy import delete, or_

        await self.session.execute(
            delete(SectionOutput).where(SectionOutput.batch_id == DEMO_OUTPUT_BATCH_ID)
        )
        await self.session.execute(
            delete(SectionOutputBatch).where(SectionOutputBatch.id == DEMO_OUTPUT_BATCH_ID)
        )

        await self.session.execute(
            delete(GenerationInput).where(GenerationInput.batch_id == DEMO_GENERATION_BATCH_ID)
        )
        await self.session.execute(
            delete(GenerationInputBatch).where(GenerationInputBatch.id == DEMO_GENERATION_BATCH_ID)
        )

        await self.session.execute(
            delete(DocumentVersion).where(DocumentVersion.document_id == DEMO_DOCUMENT_ID)
        )

        await self.session.execute(delete(Document).where(Document.id == DEMO_DOCUMENT_ID))

        await self.session.execute(
            delete(Section).where(Section.template_version_id == DEMO_TEMPLATE_VERSION_ID)
        )

        await self.session.execute(
            delete(Job).where(
                Job.payload.contains({"template_version_id": str(DEMO_TEMPLATE_VERSION_ID)})
            )
        )

        await self.session.execute(
            delete(TemplateVersion).where(TemplateVersion.id == DEMO_TEMPLATE_VERSION_ID)
        )

        await self.session.execute(delete(Template).where(Template.id == DEMO_TEMPLATE_ID))

        await self.session.execute(
            delete(AuditLog).where(
                or_(
                    AuditLog.entity_id == DEMO_TEMPLATE_ID,
                    AuditLog.entity_id == DEMO_TEMPLATE_VERSION_ID,
                    AuditLog.entity_id == DEMO_DOCUMENT_ID,
                )
            )
        )

        await self.session.flush()

    async def _seed_template(self) -> Template:
        """Seed demo template."""
        template = Template(
            id=DEMO_TEMPLATE_ID,
            name=f"{DEMO_PREFIX}Advisory_Report_Template",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(template)
        await self.session.flush()
        return template

    async def _seed_template_version(self, template_id: uuid.UUID) -> TemplateVersion:
        """Seed demo template version."""
        version = TemplateVersion(
            id=DEMO_TEMPLATE_VERSION_ID,
            template_id=template_id,
            version_number=1,
            source_doc_path=f"demo/templates/{template_id}/1/source.docx",
            parsed_representation_path=f"demo/templates/{template_id}/1/parsed.json",
            parsing_status=ParsingStatus.COMPLETED,
            parsed_at=datetime.utcnow(),
            content_hash=hashlib.sha256(b"demo_content").hexdigest(),
            created_at=datetime.utcnow(),
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def _seed_sections(self, template_version_id: uuid.UUID) -> list[Section]:
        """Seed demo sections."""
        sections = [
            Section(
                id=1,
                template_version_id=template_version_id,
                section_type=SectionType.STATIC,
                structural_path="Title",
                prompt_config=None,
                created_at=datetime.utcnow(),
            ),
            Section(
                id=2,
                template_version_id=template_version_id,
                section_type=SectionType.DYNAMIC,
                structural_path="Executive Summary",
                prompt_config={
                    "classification_confidence": 0.95,
                    "classification_method": "llm",
                    "justification": "Contains placeholder text requiring generation",
                    "prompt_template": "Generate executive summary for {company_name}",
                    "generation_hints": {"tone": "professional", "length": "medium"},
                },
                created_at=datetime.utcnow(),
            ),
            Section(
                id=3,
                template_version_id=template_version_id,
                section_type=SectionType.DYNAMIC,
                structural_path="Market Analysis",
                prompt_config={
                    "classification_confidence": 0.92,
                    "classification_method": "llm",
                    "justification": "Market analysis section requires dynamic content",
                    "prompt_template": "Analyze market conditions for {industry}",
                    "generation_hints": {"tone": "analytical", "length": "long"},
                },
                created_at=datetime.utcnow(),
            ),
            Section(
                id=4,
                template_version_id=template_version_id,
                section_type=SectionType.STATIC,
                structural_path="Appendix",
                prompt_config=None,
                created_at=datetime.utcnow(),
            ),
            Section(
                id=5,
                template_version_id=template_version_id,
                section_type=SectionType.DYNAMIC,
                structural_path="Financial Projections",
                prompt_config={
                    "classification_confidence": 0.88,
                    "classification_method": "llm",
                    "justification": "Financial projections need dynamic data",
                    "prompt_template": "Project financials for {deal_name}",
                    "generation_hints": {"tone": "precise", "length": "medium"},
                },
                created_at=datetime.utcnow(),
            ),
        ]

        for section in sections:
            self.session.add(section)
        await self.session.flush()
        return sections

    async def _seed_completed_jobs(self, template_version_id: uuid.UUID) -> list[Job]:
        """Seed completed pipeline jobs."""
        jobs = [
            Job(
                id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
                job_type=JobType.PARSE,
                status=JobStatus.COMPLETED,
                payload={"template_version_id": str(template_version_id)},
                result={"parsed_blocks": 15, "content_hash": "abc123"},
                worker_id="demo-worker",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            Job(
                id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
                job_type=JobType.CLASSIFY,
                status=JobStatus.COMPLETED,
                payload={"template_version_id": str(template_version_id)},
                result={"static_sections": 2, "dynamic_sections": 3},
                worker_id="demo-worker",
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]

        for job in jobs:
            self.session.add(job)
        await self.session.flush()
        return jobs

    async def _seed_document(self, template_version_id: uuid.UUID) -> Document:
        """Seed demo document."""
        document = Document(
            id=DEMO_DOCUMENT_ID,
            template_version_id=template_version_id,
            current_version=1,
            created_at=datetime.utcnow(),
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def _seed_document_version(self, document_id: uuid.UUID) -> DocumentVersion | None:
        """Seed demo document version."""
        version = DocumentVersion(
            id=DEMO_DOCUMENT_VERSION_ID,
            document_id=document_id,
            version_number=1,
            output_doc_path=f"demo/documents/{document_id}/1/output.docx",
            generation_metadata={
                "demo": True,
                "generated_at": datetime.utcnow().isoformat(),
                "sections_generated": 3,
            },
            created_at=datetime.utcnow(),
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def _seed_audit_logs(
        self,
        template_id: uuid.UUID,
        template_version_id: uuid.UUID,
        document_id: uuid.UUID,
    ):
        """Seed demo audit logs."""
        logs = [
            AuditLog(
                entity_type="TEMPLATE",
                entity_id=template_id,
                action="CREATE",
                metadata_={"name": f"{DEMO_PREFIX}Advisory_Report_Template", "demo": True},
                timestamp=datetime.utcnow(),
            ),
            AuditLog(
                entity_type="TEMPLATE_VERSION",
                entity_id=template_version_id,
                action="CREATE",
                metadata_={
                    "template_id": str(template_id),
                    "version_number": 1,
                    "demo": True,
                },
                timestamp=datetime.utcnow(),
            ),
            AuditLog(
                entity_type="DOCUMENT",
                entity_id=document_id,
                action="CREATE",
                metadata_={
                    "template_version_id": str(template_version_id),
                    "demo": True,
                },
                timestamp=datetime.utcnow(),
            ),
        ]

        for log in logs:
            self.session.add(log)
        await self.session.flush()


def get_demo_ids() -> dict[str, Any]:
    """Get all demo entity IDs for reference."""
    return {
        "template_id": str(DEMO_TEMPLATE_ID),
        "template_version_id": str(DEMO_TEMPLATE_VERSION_ID),
        "document_id": str(DEMO_DOCUMENT_ID),
        "document_version_id": str(DEMO_DOCUMENT_VERSION_ID),
        "generation_batch_id": str(DEMO_GENERATION_BATCH_ID),
        "output_batch_id": str(DEMO_OUTPUT_BATCH_ID),
        "section_ids": {k: str(v) for k, v in DEMO_SECTION_IDS.items()},
        "job_ids": {k: str(v["id"]) for k, v in DEMO_JOBS.items()},
    }


def is_demo_entity(entity_id: uuid.UUID) -> bool:
    """Check if an entity ID is a demo entity."""
    demo_ids: set[uuid.UUID] = {
        DEMO_TEMPLATE_ID,
        DEMO_TEMPLATE_VERSION_ID,
        DEMO_DOCUMENT_ID,
        DEMO_DOCUMENT_VERSION_ID,
        DEMO_GENERATION_BATCH_ID,
        DEMO_OUTPUT_BATCH_ID,
    }
    demo_ids.update(DEMO_SECTION_IDS.values())
    for job in DEMO_JOBS.values():
        demo_ids.add(job["id"])
    return entity_id in demo_ids
