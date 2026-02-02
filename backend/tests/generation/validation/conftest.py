from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.generation.llm_client import MockLLMClient
from backend.app.domains.generation.models import (
    GenerationInput,
    GenerationInputBatch,
    GenerationInputStatus,
)
from backend.app.domains.generation.repository import GenerationInputRepository
from backend.app.domains.generation.section_output_repository import SectionOutputRepository
from backend.app.domains.generation.section_output_schemas import (
    ContentConstraints,
    ExecuteSectionGenerationRequest,
)
from backend.app.domains.generation.section_output_service import SectionGenerationService
from backend.app.domains.generation.validation_schemas import RetryPolicy
from backend.app.domains.generation.validation_service import (
    BoundsValidator,
    ContentValidationService,
    GenerationValidationService,
    QualityValidator,
    RetryManager,
    StructuralValidator,
)


@pytest.fixture
def fixed_document_id() -> UUID:
    return UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def fixed_template_version_id() -> UUID:
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def fixed_input_batch_id() -> UUID:
    return UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture
def sample_generation_input_batch(
    fixed_input_batch_id: UUID,
    fixed_document_id: UUID,
    fixed_template_version_id: UUID,
) -> GenerationInputBatch:
    batch = GenerationInputBatch(
        id=fixed_input_batch_id,
        document_id=fixed_document_id,
        template_version_id=fixed_template_version_id,
        version_intent=1,
        status=GenerationInputStatus.VALIDATED,
        content_hash="abc123",
        total_inputs=3,
        is_immutable=True,
    )
    batch.created_at = datetime(2026, 1, 15, 10, 0, 0)
    batch.validated_at = datetime(2026, 1, 15, 10, 0, 1)
    return batch


@pytest.fixture
def sample_generation_inputs(
    fixed_input_batch_id: UUID,
    fixed_template_version_id: UUID,
) -> list[GenerationInput]:
    inputs = []
    section_configs = [
        (1, "body/introduction", 0),
        (2, "body/main_content", 1),
        (3, "body/conclusion", 2),
    ]
    for section_id, path, seq in section_configs:
        inp = GenerationInput(
            id=uuid4(),
            batch_id=fixed_input_batch_id,
            section_id=section_id,
            sequence_order=seq,
            template_id=fixed_template_version_id,
            template_version_id=fixed_template_version_id,
            structural_path=path,
            hierarchy_context={
                "parent_heading": "body",
                "depth": 1,
                "path_segments": ["body", path.split("/")[-1]],
            },
            prompt_config={
                "classification_confidence": 0.95,
                "classification_method": "RULE_BASED",
                "justification": f"Dynamic content for {path}",
            },
            client_data={
                "client_name": "Test Corp",
                "data_fields": {"project": "Test Project"},
            },
            surrounding_context={},
            input_hash=f"hash_{section_id}",
        )
        inp.created_at = datetime(2026, 1, 15, 10, 0, 0)
        inputs.append(inp)
    return inputs


@pytest.fixture
def sample_input_batch_with_inputs(
    sample_generation_input_batch: GenerationInputBatch,
    sample_generation_inputs: list[GenerationInput],
) -> GenerationInputBatch:
    sample_generation_input_batch.inputs = sample_generation_inputs
    return sample_generation_input_batch


@pytest.fixture
def mock_input_repository() -> MagicMock:
    mock_repo = MagicMock(spec=GenerationInputRepository)
    mock_repo.get_batch_by_id = AsyncMock(return_value=None)
    return mock_repo


@pytest.fixture
def mock_output_repository() -> MagicMock:
    mock_repo = MagicMock(spec=SectionOutputRepository)
    mock_repo.create_batch = AsyncMock()
    mock_repo.create_outputs = AsyncMock()
    mock_repo.update_output_content = AsyncMock()
    mock_repo.mark_output_failed = AsyncMock()
    mock_repo.mark_output_validated = AsyncMock()
    mock_repo.increment_retry_count = AsyncMock()
    mock_repo.mark_retry_exhausted = AsyncMock()
    mock_repo.update_batch_progress = AsyncMock()
    mock_repo.mark_batch_in_progress = AsyncMock()
    mock_repo.get_batch_by_id = AsyncMock(return_value=None)
    mock_repo.get_batch_by_input_batch_id = AsyncMock(return_value=None)
    mock_repo.get_validated_outputs = AsyncMock(return_value=[])
    mock_repo.get_failed_outputs = AsyncMock(return_value=[])
    mock_repo.get_outputs_by_failure_category = AsyncMock(return_value=[])
    mock_repo.get_retryable_outputs = AsyncMock(return_value=[])
    mock_repo.batch_exists_for_input = AsyncMock(return_value=False)
    return mock_repo


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    return MockLLMClient(
        default_response="This is valid generated content for the advisory section."
    )


@pytest.fixture
def structural_validator() -> StructuralValidator:
    return StructuralValidator()


@pytest.fixture
def bounds_validator() -> BoundsValidator:
    return BoundsValidator(min_length=1, max_length=50000)


@pytest.fixture
def quality_validator() -> QualityValidator:
    return QualityValidator()


@pytest.fixture
def content_validation_service() -> ContentValidationService:
    return ContentValidationService()


@pytest.fixture
def generation_validation_service() -> GenerationValidationService:
    return GenerationValidationService()


@pytest.fixture
def retry_manager() -> RetryManager:
    return RetryManager()


@pytest.fixture
def strict_retry_policy() -> RetryPolicy:
    return RetryPolicy(max_retries=2)


@pytest.fixture
def default_constraints() -> ContentConstraints:
    return ContentConstraints()


@pytest.fixture
def strict_constraints() -> ContentConstraints:
    return ContentConstraints(
        max_length=100,
        min_length=10,
    )


@pytest.fixture
def generation_service(
    mock_output_repository: MagicMock,
    mock_input_repository: MagicMock,
    mock_llm_client: MockLLMClient,
) -> SectionGenerationService:
    return SectionGenerationService(
        output_repo=mock_output_repository,
        input_repo=mock_input_repository,
        llm_client=mock_llm_client,
    )


@pytest.fixture
def execute_request(fixed_input_batch_id: UUID) -> ExecuteSectionGenerationRequest:
    return ExecuteSectionGenerationRequest(
        input_batch_id=fixed_input_batch_id,
        constraints=ContentConstraints(),
    )
