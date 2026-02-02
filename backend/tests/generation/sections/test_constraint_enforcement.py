from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.generation.llm_client import MockLLMClient
from backend.app.domains.generation.models import GenerationInputBatch
from backend.app.domains.generation.section_output_models import SectionGenerationStatus
from backend.app.domains.generation.section_output_schemas import (
    ContentConstraints,
    ContentValidator,
    ExecuteSectionGenerationRequest,
)
from backend.app.domains.generation.section_output_service import SectionGenerationService


class TestStructuralModificationRejection:
    @pytest.mark.asyncio
    async def test_markdown_headers_rejected(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        content_with_headers = "# This is a header\nSome content below."
        result = validator.validate(content_with_headers)

        assert not result.is_valid
        assert result.rejection_code == "CONSTRAINT_VIOLATION"
        assert any("structural pattern" in v for v in result.constraint_violations)

    @pytest.mark.asyncio
    async def test_markdown_horizontal_rules_rejected(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        content_with_hr = "Some content\n---\nMore content"
        result = validator.validate(content_with_hr)

        assert not result.is_valid
        assert any("structural pattern" in v for v in result.constraint_violations)

    @pytest.mark.asyncio
    async def test_html_tags_rejected(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        content_with_html = "Some content <div>with html</div> inside."
        result = validator.validate(content_with_html)

        assert not result.is_valid
        assert result.rejection_code == "CONSTRAINT_VIOLATION"

    @pytest.mark.asyncio
    async def test_markdown_links_rejected(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        content_with_links = "Click [here](https://example.com) for more info."
        result = validator.validate(content_with_links)

        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_code_blocks_rejected(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        content_with_code = "Some code:\n```python\nprint('hello')\n```"
        result = validator.validate(content_with_code)

        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_table_syntax_rejected(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        content_with_table = "| Column 1 | Column 2 |\n| --- | --- |"
        result = validator.validate(content_with_table)

        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_plain_text_accepted(
        self,
        default_constraints: ContentConstraints,
    ):
        validator = ContentValidator(default_constraints)

        plain_content = "This is a simple paragraph of text without any special formatting. It contains normal sentences and punctuation."
        result = validator.validate(plain_content)

        assert result.is_valid
        assert result.validated_content is not None


class TestLengthConstraints:
    @pytest.mark.asyncio
    async def test_content_exceeding_max_length_rejected(self):
        constraints = ContentConstraints(max_length=100)
        validator = ContentValidator(constraints)

        long_content = "A" * 200
        result = validator.validate(long_content)

        assert not result.is_valid
        assert "exceeds maximum" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_content_below_min_length_rejected(self):
        constraints = ContentConstraints(min_length=50)
        validator = ContentValidator(constraints)

        short_content = "Too short"
        result = validator.validate(short_content)

        assert not result.is_valid
        assert "below minimum" in result.rejection_reason

    @pytest.mark.asyncio
    async def test_content_within_bounds_accepted(self):
        constraints = ContentConstraints(min_length=5, max_length=100)
        validator = ContentValidator(constraints)

        valid_content = "This content has an appropriate length."
        result = validator.validate(valid_content)

        assert result.is_valid

    @pytest.mark.asyncio
    async def test_empty_content_rejected(self):
        validator = ContentValidator(ContentConstraints())

        result = validator.validate("")

        assert not result.is_valid
        assert result.rejection_code == "EMPTY_CONTENT"

    @pytest.mark.asyncio
    async def test_whitespace_only_content_rejected(self):
        validator = ContentValidator(ContentConstraints())

        result = validator.validate("   \n\t  ")

        assert not result.is_valid
        assert result.rejection_code == "EMPTY_CONTENT"


class TestConstraintEnforcementInService:
    @pytest.mark.asyncio
    async def test_structural_output_causes_section_failure(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            response_map={
                1: "# Markdown Header\nThis tries to add structure",
                2: "Normal valid content for section two.",
                3: "Normal valid content for section three.",
            }
        )

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        created_outputs = []

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            created_outputs.extend(outputs)
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)

        successful_updates = []
        failed_updates = []

        async def track_success(
            output_id,
            generated_content,
            content_length,
            content_hash,
            validation_result,
            metadata,
            completed_at,
        ):
            successful_updates.append(output_id)
            return MagicMock()

        async def track_failure(output_id, error_message, error_code, metadata, completed_at):
            failed_updates.append({"output_id": output_id, "error_code": error_code})
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(side_effect=track_success)
        mock_output_repository.mark_output_failed = AsyncMock(side_effect=track_failure)

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 2
        final_batch.failed_sections = 1
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(),
        )

        await service.execute_section_generation(request)

        assert len(successful_updates) == 2
        assert len(failed_updates) == 1
        assert failed_updates[0]["error_code"] in [
            "CONSTRAINT_VIOLATION",
            "CONTAINS_HEADERS",
            "STRUCTURAL_VIOLATION",
        ]

    @pytest.mark.asyncio
    async def test_length_violation_causes_section_failure(
        self,
        mock_input_repository: MagicMock,
        mock_output_repository: MagicMock,
        sample_input_batch_with_inputs: GenerationInputBatch,
        fixed_input_batch_id: UUID,
    ):
        llm_client = MockLLMClient(
            response_map={
                1: "A" * 200,
                2: "Valid content",
                3: "Also valid",
            }
        )

        service = SectionGenerationService(
            output_repo=mock_output_repository,
            input_repo=mock_input_repository,
            llm_client=llm_client,
        )

        mock_input_repository.get_batch_by_id = AsyncMock(
            return_value=sample_input_batch_with_inputs
        )
        mock_output_repository.get_batch_by_input_batch_id = AsyncMock(return_value=None)

        def capture_batch(batch):
            batch.id = uuid4()
            return batch

        def capture_outputs(outputs):
            for out in outputs:
                out.id = uuid4()
            return outputs

        mock_output_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_output_repository.create_outputs = AsyncMock(side_effect=capture_outputs)

        failed_updates = []

        async def track_failure(output_id, error_message, error_code, metadata, completed_at):
            failed_updates.append({"error_message": error_message})
            return MagicMock()

        mock_output_repository.mark_output_validated = AsyncMock(return_value=MagicMock())
        mock_output_repository.mark_output_failed = AsyncMock(side_effect=track_failure)

        final_batch = MagicMock()
        final_batch.id = uuid4()
        final_batch.input_batch_id = sample_input_batch_with_inputs.id
        final_batch.document_id = sample_input_batch_with_inputs.document_id
        final_batch.version_intent = 1
        final_batch.status = SectionGenerationStatus.COMPLETED
        final_batch.total_sections = 3
        final_batch.completed_sections = 2
        final_batch.failed_sections = 1
        final_batch.is_immutable = True
        final_batch.created_at = datetime.utcnow()
        final_batch.completed_at = datetime.utcnow()
        final_batch.outputs = []
        mock_output_repository.get_batch_by_id = AsyncMock(return_value=final_batch)

        request = ExecuteSectionGenerationRequest(
            input_batch_id=fixed_input_batch_id,
            constraints=ContentConstraints(max_length=100),
        )

        await service.execute_section_generation(request)

        assert len(failed_updates) == 1
        assert "too long" in failed_updates[0]["error_message"].lower()
