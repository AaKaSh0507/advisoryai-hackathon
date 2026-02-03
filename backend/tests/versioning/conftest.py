from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.document.models import Document
from backend.app.domains.versioning.repository import VersioningRepository
from backend.app.domains.versioning.schemas import VersionCreateRequest
from backend.app.domains.versioning.service import DocumentVersioningService


@pytest.fixture
def document_id() -> UUID:
    return uuid4()


@pytest.fixture
def template_version_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_content() -> bytes:
    return b"Sample document content for testing versioning system"


@pytest.fixture
def sample_content_different() -> bytes:
    return b"Different document content for version 2"


@pytest.fixture
def sample_metadata() -> dict:
    return {
        "template_name": "Advisory Report",
        "generation_timestamp": "2026-02-03T10:00:00Z",
        "generation_type": "full",
    }


@pytest_asyncio.fixture
async def sample_document(db_session: AsyncSession, template_version_id: UUID) -> Document:
    from backend.app.domains.template.models import Template, TemplateVersion

    template = Template(
        id=uuid4(),
        name="Test Template",
    )
    db_session.add(template)
    await db_session.flush()

    template_version = TemplateVersion(
        id=template_version_id,
        template_id=template.id,
        version_number=1,
        source_doc_path="templates/test/1/source.docx",
        parsed_representation_path="templates/test/1/parsed.json",
    )
    db_session.add(template_version)
    await db_session.flush()

    document = Document(
        template_version_id=template_version_id,
        current_version=0,
    )
    db_session.add(document)
    await db_session.flush()
    return document


@pytest_asyncio.fixture
async def versioning_repository(db_session: AsyncSession) -> VersioningRepository:
    return VersioningRepository(db_session)


@pytest_asyncio.fixture
async def audit_repository(db_session: AsyncSession) -> AuditRepository:
    return AuditRepository(db_session)


@pytest_asyncio.fixture
async def versioning_service(
    versioning_repository: VersioningRepository,
    mock_storage,
    audit_repository: AuditRepository,
) -> DocumentVersioningService:
    return DocumentVersioningService(
        repository=versioning_repository,
        storage=mock_storage,
        audit_repo=audit_repository,
    )


@pytest.fixture
def version_create_request(
    document_id: UUID,
    sample_content: bytes,
    sample_metadata: dict,
) -> VersionCreateRequest:
    return VersionCreateRequest(
        document_id=document_id,
        content=sample_content,
        generation_metadata=sample_metadata,
    )


@pytest.fixture
def mock_versioning_repository() -> AsyncMock:
    repo = AsyncMock(spec=VersioningRepository)
    repo.get_document.return_value = None
    repo.get_next_version_number.return_value = 1
    repo.version_exists.return_value = False
    repo.get_version_by_content_hash.return_value = None
    return repo


@pytest.fixture
def mock_audit_repository() -> AsyncMock:
    repo = AsyncMock(spec=AuditRepository)
    return repo


@pytest.fixture
def mock_versioning_service(
    mock_versioning_repository: AsyncMock,
    mock_storage,
    mock_audit_repository: AsyncMock,
) -> DocumentVersioningService:
    return DocumentVersioningService(
        repository=mock_versioning_repository,
        storage=mock_storage,
        audit_repo=mock_audit_repository,
    )
