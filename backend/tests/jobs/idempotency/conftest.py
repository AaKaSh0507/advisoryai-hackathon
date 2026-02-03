from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest


@pytest.fixture
def fixed_job_id():
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def fixed_document_id():
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def fixed_template_version_id():
    return UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def fixed_input_batch_id():
    return UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture
def fixed_output_batch_id():
    return UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture
def fixed_assembled_id():
    return UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture
def fixed_rendered_id():
    return UUID("77777777-7777-7777-7777-777777777777")


@pytest.fixture
def fixed_version_id():
    return UUID("88888888-8888-8888-8888-888888888888")


@pytest.fixture
def sample_job_payload(fixed_document_id, fixed_template_version_id):
    return {
        "document_id": str(fixed_document_id),
        "template_version_id": str(fixed_template_version_id),
        "version_intent": 1,
        "client_data": {"client_name": "Test Corp"},
        "force_regenerate": False,
    }


@pytest.fixture
def sample_job_result(
    fixed_input_batch_id,
    fixed_output_batch_id,
    fixed_assembled_id,
    fixed_rendered_id,
    fixed_version_id,
):
    return {
        "input_batch_id": str(fixed_input_batch_id),
        "output_batch_id": str(fixed_output_batch_id),
        "assembled_document_id": str(fixed_assembled_id),
        "rendered_document_id": str(fixed_rendered_id),
        "version_id": str(fixed_version_id),
        "content_hash": "abc123hash",
    }


@pytest.fixture
def mock_job_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.create = AsyncMock()
    repo.update_status = AsyncMock()
    repo.set_result = AsyncMock()
    repo.set_error = AsyncMock()
    return repo


@pytest.fixture
def mock_generation_repo():
    repo = MagicMock()
    repo.get_batch_by_id = AsyncMock()
    repo.get_batch_by_content_hash = AsyncMock()
    repo.create_batch = AsyncMock()
    return repo


@pytest.fixture
def mock_output_repo():
    repo = MagicMock()
    repo.get_batch_by_id = AsyncMock()
    repo.get_batch_by_input_batch_id = AsyncMock()
    repo.create_batch = AsyncMock()
    return repo


@pytest.fixture
def mock_assembly_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_output_batch_id = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_rendering_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_assembled_document_id = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_versioning_repo():
    repo = MagicMock()
    repo.get_by_content_hash = AsyncMock()
    repo.get_latest_version = AsyncMock()
    repo.create_version = AsyncMock()
    return repo


@pytest.fixture
def mock_audit_service():
    service = MagicMock()
    service.log_stage_started = AsyncMock()
    service.log_stage_completed = AsyncMock()
    service.log_stage_failed = AsyncMock()
    service.get_entries_for_job = AsyncMock(return_value=[])
    return service
