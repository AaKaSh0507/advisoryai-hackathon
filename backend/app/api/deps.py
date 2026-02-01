from typing import AsyncGenerator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings, Settings
from backend.app.infrastructure.database import get_db_session
from backend.app.infrastructure.storage import StorageService

from backend.app.domains.template.repository import TemplateRepository
from backend.app.domains.template.service import TemplateService
from backend.app.domains.section.repository import SectionRepository
from backend.app.domains.section.service import SectionService
from backend.app.domains.document.repository import DocumentRepository
from backend.app.domains.document.service import DocumentService
from backend.app.domains.job.repository import JobRepository
from backend.app.domains.job.service import JobService
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.audit.service import AuditService

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db_session():
        yield session

DbSession = Annotated[AsyncSession, Depends(get_db)]

def get_storage_service() -> StorageService:
    return StorageService(get_settings())

def get_audit_repository(session: DbSession) -> AuditRepository:
    return AuditRepository(session)

def get_template_repository(session: DbSession) -> TemplateRepository:
    return TemplateRepository(session)

def get_template_service(
    repo: Annotated[TemplateRepository, Depends(get_template_repository)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)]
) -> TemplateService:
    return TemplateService(repo, storage, audit_repo)

def get_section_repository(session: DbSession) -> SectionRepository:
    return SectionRepository(session)

def get_section_service(
    repo: Annotated[SectionRepository, Depends(get_section_repository)]
) -> SectionService:
    return SectionService(repo)

def get_document_repository(session: DbSession) -> DocumentRepository:
    return DocumentRepository(session)

def get_document_service(
    repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repository)]
) -> DocumentService:
    return DocumentService(repo, storage, audit_repo)

def get_job_repository(session: DbSession) -> JobRepository:
    return JobRepository(session)

def get_job_service(
    repo: Annotated[JobRepository, Depends(get_job_repository)]
) -> JobService:
    return JobService(repo)

def get_audit_service(
    repo: Annotated[AuditRepository, Depends(get_audit_repository)]
) -> AuditService:
    return AuditService(repo)
