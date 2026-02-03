from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from backend.app.domains.generation.schemas import ClientDataPayload


@pytest.fixture
def fixed_document_id():
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def fixed_template_id():
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def fixed_template_version_id():
    return UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def fixed_batch_id():
    return UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture
def fixed_job_id():
    return UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture
def sample_client_data():
    return ClientDataPayload(
        client_name="Test Corporation",
        client_industry="Technology",
        engagement_type="Advisory",
        custom_fields={"priority": "high"},
    )


@pytest.fixture
def mock_generation_repo():
    repo = MagicMock()
    repo.create_batch = AsyncMock()
    repo.create_inputs = AsyncMock(return_value=[])
    repo.get_batch_by_id = AsyncMock()
    repo.update_batch = AsyncMock()
    repo.mark_batch_validated = AsyncMock()
    return repo


@pytest.fixture
def mock_section_repo():
    repo = MagicMock()
    repo.get_sections_for_generation = AsyncMock(return_value=[])
    repo.get_by_template_version_id = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_audit_service():
    service = MagicMock()
    service.log_batch_created = AsyncMock()
    service.log_batch_validated = AsyncMock()
    service.log_input_prepared = AsyncMock()
    service.log_generation_initiated = AsyncMock()
    return service
