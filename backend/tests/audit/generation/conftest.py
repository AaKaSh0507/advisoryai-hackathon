from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.audit.repository import AuditRepository


@pytest.fixture
def document_id() -> UUID:
    return uuid4()


@pytest.fixture
def template_version_id() -> UUID:
    return uuid4()


@pytest.fixture
def batch_id() -> UUID:
    return uuid4()


@pytest.fixture
def section_output_id() -> UUID:
    return uuid4()


@pytest.fixture
def assembled_document_id() -> UUID:
    return uuid4()


@pytest.fixture
def rendered_document_id() -> UUID:
    return uuid4()


@pytest.fixture
def version_id() -> UUID:
    return uuid4()


@pytest.fixture
def job_id() -> UUID:
    return uuid4()


@pytest_asyncio.fixture
async def audit_repository(db_session: AsyncSession) -> AuditRepository:
    return AuditRepository(db_session)


@pytest_asyncio.fixture
async def generation_audit_service(
    audit_repository: AuditRepository,
) -> GenerationAuditService:
    return GenerationAuditService(audit_repo=audit_repository)
