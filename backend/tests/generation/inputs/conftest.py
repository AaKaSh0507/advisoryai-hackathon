from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
import pytest_asyncio

from backend.app.domains.generation.repository import GenerationInputRepository
from backend.app.domains.generation.schemas import ClientDataPayload, PrepareGenerationInputsRequest
from backend.app.domains.generation.service import GenerationInputService
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository


@pytest.fixture
def fixed_template_id() -> UUID:
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def fixed_template_version_id() -> UUID:
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def fixed_document_id() -> UUID:
    return UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def sample_dynamic_section(fixed_template_version_id: UUID) -> Section:
    section = Section(
        id=1,
        template_version_id=fixed_template_version_id,
        section_type=SectionType.DYNAMIC,
        structural_path="body/introduction",
        prompt_config={
            "classification_confidence": 0.95,
            "classification_method": "RULE_BASED",
            "justification": "Contains placeholder {client_name}",
            "metadata": {"detected_placeholders": ["{client_name}"]},
        },
    )
    section.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return section


@pytest.fixture
def sample_static_section(fixed_template_version_id: UUID) -> Section:
    section = Section(
        id=2,
        template_version_id=fixed_template_version_id,
        section_type=SectionType.STATIC,
        structural_path="body/legal_notice",
        prompt_config=None,
    )
    section.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return section


@pytest.fixture
def multiple_dynamic_sections(fixed_template_version_id: UUID) -> list[Section]:
    sections = []
    paths = [
        "body/section_a/content",
        "body/section_b/content",
        "body/introduction",
    ]
    for i, path in enumerate(paths, start=1):
        section = Section(
            id=i,
            template_version_id=fixed_template_version_id,
            section_type=SectionType.DYNAMIC,
            structural_path=path,
            prompt_config={
                "classification_confidence": 0.9,
                "classification_method": "RULE_BASED",
                "justification": f"Dynamic content for {path}",
                "metadata": {},
            },
        )
        section.created_at = datetime(2026, 1, 1, 12, 0, i)
        sections.append(section)
    return sections


@pytest.fixture
def mixed_sections(fixed_template_version_id: UUID) -> list[Section]:
    sections = []
    configs = [
        (1, SectionType.STATIC, "header/logo", None),
        (
            2,
            SectionType.DYNAMIC,
            "body/greeting",
            {
                "classification_confidence": 0.92,
                "classification_method": "RULE_BASED",
                "justification": "Contains personalization placeholders",
                "metadata": {},
            },
        ),
        (3, SectionType.STATIC, "body/legal_disclaimer", None),
        (
            4,
            SectionType.DYNAMIC,
            "body/main_content",
            {
                "classification_confidence": 0.88,
                "classification_method": "LLM",
                "justification": "Context-dependent content identified",
                "metadata": {"llm_model": "gpt-4"},
            },
        ),
        (5, SectionType.STATIC, "footer/copyright", None),
        (
            6,
            SectionType.DYNAMIC,
            "body/closing",
            {
                "classification_confidence": 0.95,
                "classification_method": "RULE_BASED",
                "justification": "Contains variable closing statement",
                "metadata": {},
            },
        ),
    ]
    for section_id, section_type, path, config in configs:
        section = Section(
            id=section_id,
            template_version_id=fixed_template_version_id,
            section_type=section_type,
            structural_path=path,
            prompt_config=config,
        )
        section.created_at = datetime(2026, 1, 1, 12, 0, section_id)
        sections.append(section)
    return sections


@pytest.fixture
def section_missing_prompt_config(fixed_template_version_id: UUID) -> Section:
    section = Section(
        id=100,
        template_version_id=fixed_template_version_id,
        section_type=SectionType.DYNAMIC,
        structural_path="body/broken_section",
        prompt_config=None,  # Missing!
    )
    section.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return section


@pytest.fixture
def section_incomplete_prompt_config(fixed_template_version_id: UUID) -> Section:
    section = Section(
        id=101,
        template_version_id=fixed_template_version_id,
        section_type=SectionType.DYNAMIC,
        structural_path="body/incomplete_section",
        prompt_config={
            "classification_confidence": 0.9,
        },
    )
    section.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return section


@pytest.fixture
def section_malformed_prompt_config(fixed_template_version_id: UUID) -> Section:
    section = Section(
        id=102,
        template_version_id=fixed_template_version_id,
        section_type=SectionType.DYNAMIC,
        structural_path="body/malformed_section",
        prompt_config="not a dict",
    )
    section.created_at = datetime(2026, 1, 1, 12, 0, 0)
    return section


@pytest.fixture
def sample_client_data() -> ClientDataPayload:
    return ClientDataPayload(
        client_id="client_001",
        client_name="Acme Corporation",
        data_fields={
            "contact_name": "John Smith",
            "contact_email": "john.smith@acme.com",
            "company_address": "123 Business Ave, Suite 100",
            "project_name": "Q4 Advisory Report",
        },
        custom_context={
            "industry": "technology",
            "relationship_start": "2024-01-15",
        },
    )


@pytest.fixture
def empty_client_data() -> ClientDataPayload:
    return ClientDataPayload()


@pytest.fixture
def prepare_request(
    fixed_document_id: UUID,
    fixed_template_version_id: UUID,
    sample_client_data: ClientDataPayload,
) -> PrepareGenerationInputsRequest:
    return PrepareGenerationInputsRequest(
        document_id=fixed_document_id,
        template_version_id=fixed_template_version_id,
        version_intent=1,
        client_data=sample_client_data,
    )


@pytest.fixture
def mock_section_repository() -> MagicMock:
    mock_repo = MagicMock(spec=SectionRepository)
    mock_repo.get_by_template_version_id = AsyncMock(return_value=[])
    return mock_repo


@pytest.fixture
def mock_generation_repository() -> MagicMock:
    mock_repo = MagicMock(spec=GenerationInputRepository)
    mock_repo.create_batch = AsyncMock()
    mock_repo.create_inputs = AsyncMock()
    mock_repo.mark_batch_validated = AsyncMock()
    mock_repo.get_batch_by_id = AsyncMock()
    mock_repo.batch_exists = AsyncMock(return_value=False)
    return mock_repo


@pytest.fixture
def generation_service(
    mock_generation_repository: MagicMock,
    mock_section_repository: MagicMock,
) -> GenerationInputService:
    return GenerationInputService(
        generation_repo=mock_generation_repository,
        section_repo=mock_section_repository,
    )


@pytest_asyncio.fixture
async def db_generation_repository(db_session) -> GenerationInputRepository:
    return GenerationInputRepository(db_session)


@pytest_asyncio.fixture
async def db_section_repository(db_session) -> SectionRepository:
    return SectionRepository(db_session)


@pytest_asyncio.fixture
async def db_generation_service(
    db_generation_repository: GenerationInputRepository,
    db_section_repository: SectionRepository,
) -> GenerationInputService:
    return GenerationInputService(
        generation_repo=db_generation_repository,
        section_repo=db_section_repository,
    )
