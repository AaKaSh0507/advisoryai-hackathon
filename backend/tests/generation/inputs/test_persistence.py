from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.generation.errors import ImmutabilityViolationError
from backend.app.domains.generation.models import GenerationInputStatus
from backend.app.domains.generation.schemas import ClientDataPayload, PrepareGenerationInputsRequest
from backend.app.domains.generation.service import GenerationInputService
from backend.app.domains.section.models import Section, SectionType


class TestBatchPersistence:
    @pytest.mark.asyncio
    async def test_batch_created_with_correct_fields(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        mixed_sections: list[Section],
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)
        created_batch = None

        def capture_batch(batch):
            nonlocal created_batch
            batch.id = uuid4()
            created_batch = batch
            return batch

        mock_generation_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_generation_repository.create_inputs = AsyncMock(
            side_effect=lambda inputs: [setattr(inp, "id", uuid4()) or inp for inp in inputs]
        )
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                document_id=prepare_request.document_id,
                template_version_id=prepare_request.template_version_id,
                version_intent=prepare_request.version_intent,
                status=GenerationInputStatus.VALIDATED,
                content_hash="test_hash",
                is_immutable=True,
                inputs=[],
            )
        )
        await generation_service.prepare_generation_inputs(prepare_request)
        assert created_batch is not None
        assert created_batch.document_id == prepare_request.document_id
        assert created_batch.template_version_id == prepare_request.template_version_id
        assert created_batch.version_intent == prepare_request.version_intent
        assert created_batch.total_inputs == 3  # 3 DYNAMIC sections in mixed_sections
        assert created_batch.content_hash is not None
        assert len(created_batch.content_hash) == 64  # SHA-256

    @pytest.mark.asyncio
    async def test_inputs_created_for_each_dynamic_section(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        mixed_sections: list[Section],
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)
        created_inputs = []

        def capture_inputs(inputs):
            for inp in inputs:
                inp.id = uuid4()
            created_inputs.extend(inputs)
            return inputs

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
                document_id=prepare_request.document_id,
                template_version_id=prepare_request.template_version_id,
                version_intent=prepare_request.version_intent,
            )
        )

        await generation_service.prepare_generation_inputs(prepare_request)
        dynamic_count = sum(1 for s in mixed_sections if s.section_type == SectionType.DYNAMIC)
        assert len(created_inputs) == dynamic_count

    @pytest.mark.asyncio
    async def test_inputs_have_correct_sequence_order(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        multiple_dynamic_sections: list[Section],
        fixed_document_id: UUID,
        fixed_template_version_id: UUID,
        sample_client_data: ClientDataPayload,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=multiple_dynamic_sections
        )
        created_inputs = []

        def capture_inputs(inputs):
            for inp in inputs:
                inp.id = uuid4()
            created_inputs.extend(inputs)
            return inputs

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
                document_id=fixed_document_id,
                template_version_id=fixed_template_version_id,
                version_intent=1,
            )
        )

        request = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=sample_client_data,
        )
        await generation_service.prepare_generation_inputs(request)
        sequence_orders = [inp.sequence_order for inp in created_inputs]
        assert sequence_orders == list(range(len(created_inputs)))

    @pytest.mark.asyncio
    async def test_batch_marked_validated_after_creation(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        mixed_sections: list[Section],
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)

        batch_id = uuid4()
        validation_called = False
        validation_batch_id = None

        def track_validation(bid, validated_at):
            nonlocal validation_called, validation_batch_id
            validation_called = True
            validation_batch_id = bid
            return MagicMock(status=GenerationInputStatus.VALIDATED)

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", batch_id) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(
            side_effect=lambda inputs: [setattr(inp, "id", uuid4()) or inp for inp in inputs]
        )
        mock_generation_repository.mark_batch_validated = AsyncMock(side_effect=track_validation)
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=batch_id,
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
                document_id=prepare_request.document_id,
                template_version_id=prepare_request.template_version_id,
                version_intent=prepare_request.version_intent,
            )
        )

        await generation_service.prepare_generation_inputs(prepare_request)
        assert validation_called
        assert validation_batch_id == batch_id


class TestImmutability:
    @pytest.mark.asyncio
    async def test_validated_batch_is_immutable(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        mixed_sections: list[Section],
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(
            side_effect=lambda inputs: [setattr(inp, "id", uuid4()) or inp for inp in inputs]
        )
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
                document_id=prepare_request.document_id,
                template_version_id=prepare_request.template_version_id,
                version_intent=prepare_request.version_intent,
            )
        )

        response = await generation_service.prepare_generation_inputs(prepare_request)
        assert response.is_immutable is True

    def test_immutability_violation_on_revalidate(self):
        error = ImmutabilityViolationError(
            batch_id=UUID("12345678-1234-1234-1234-123456789abc"),
            operation="re-validate",
        )

        assert "immutable" in str(error).lower()
        assert "re-validate" in str(error)
        assert "12345678-1234-1234-1234-123456789abc" in str(error)

    def test_immutability_violation_on_modify(self):
        error = ImmutabilityViolationError(
            batch_id=UUID("12345678-1234-1234-1234-123456789abc"),
            operation="mark as failed",
        )

        assert "immutable" in str(error).lower()
        assert "mark as failed" in str(error)


class TestInputDataIntegrity:
    @pytest.mark.asyncio
    async def test_input_hash_persisted(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        sample_dynamic_section: Section,
        fixed_document_id: UUID,
        fixed_template_version_id: UUID,
        sample_client_data: ClientDataPayload,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[sample_dynamic_section]
        )

        persisted_inputs = []

        def capture_inputs(inputs):
            for inp in inputs:
                inp.id = uuid4()
            persisted_inputs.extend(inputs)
            return inputs

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
                document_id=fixed_document_id,
                template_version_id=fixed_template_version_id,
                version_intent=1,
            )
        )

        request = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=sample_client_data,
        )

        await generation_service.prepare_generation_inputs(request)
        assert len(persisted_inputs) == 1
        assert persisted_inputs[0].input_hash is not None
        assert len(persisted_inputs[0].input_hash) == 64  # SHA-256

    @pytest.mark.asyncio
    async def test_all_fields_persisted(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        sample_dynamic_section: Section,
        fixed_document_id: UUID,
        fixed_template_version_id: UUID,
        sample_client_data: ClientDataPayload,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[sample_dynamic_section]
        )

        persisted_inputs = []

        def capture_inputs(inputs):
            for inp in inputs:
                inp.id = uuid4()
            persisted_inputs.extend(inputs)
            return inputs

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
                document_id=fixed_document_id,
                template_version_id=fixed_template_version_id,
                version_intent=1,
            )
        )

        request = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=sample_client_data,
        )

        await generation_service.prepare_generation_inputs(request)
        inp = persisted_inputs[0]
        assert inp.section_id == sample_dynamic_section.id
        assert inp.template_version_id == fixed_template_version_id
        assert inp.structural_path == sample_dynamic_section.structural_path
        assert inp.hierarchy_context is not None
        assert inp.prompt_config is not None
        assert inp.client_data is not None
        assert inp.surrounding_context is not None


class TestDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_batch_survives_session_close(self, db_session, db_generation_repository):
        """Test that batches survive session close (simulating restart)."""
        # This requires proper database setup
        # Skip if tables don't exist
        pytest.skip("Requires full database schema setup")

    @pytest.mark.asyncio
    async def test_repository_creates_and_retrieves_batch(
        self, db_session, db_generation_repository
    ):
        pytest.skip("Requires full database schema setup with document/template tables")


class TestResponseStructure:
    @pytest.mark.asyncio
    async def test_response_contains_all_inputs(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        multiple_dynamic_sections: list[Section],
        fixed_document_id: UUID,
        fixed_template_version_id: UUID,
        sample_client_data: ClientDataPayload,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=multiple_dynamic_sections
        )

        created_inputs = []

        def capture_and_return_batch(b):
            b.id = uuid4()
            return b

        def capture_inputs(inputs):
            for i, inp in enumerate(inputs):
                inp.id = uuid4()
                inp.created_at = datetime.utcnow()
            created_inputs.extend(inputs)
            return inputs

        mock_generation_repository.create_batch = AsyncMock(side_effect=capture_and_return_batch)
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)
        mock_generation_repository.mark_batch_validated = AsyncMock()

        def get_batch_with_inputs(batch_id, include_inputs):
            return MagicMock(
                id=batch_id,
                document_id=fixed_document_id,
                template_version_id=fixed_template_version_id,
                version_intent=1,
                status=GenerationInputStatus.VALIDATED,
                content_hash="test_hash",
                is_immutable=True,
                inputs=created_inputs,
            )

        mock_generation_repository.get_batch_by_id = AsyncMock(side_effect=get_batch_with_inputs)

        request = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=sample_client_data,
        )

        response = await generation_service.prepare_generation_inputs(request)
        assert response.total_dynamic_sections == len(multiple_dynamic_sections)
        assert len(response.inputs) == len(multiple_dynamic_sections)

    @pytest.mark.asyncio
    async def test_response_status_is_validated(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        sample_dynamic_section: Section,
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[sample_dynamic_section]
        )

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(
            side_effect=lambda inputs: [
                setattr(inp, "id", uuid4()) or setattr(inp, "created_at", datetime.utcnow()) or inp
                for inp in inputs
            ]
        )
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            return_value=MagicMock(
                id=uuid4(),
                document_id=prepare_request.document_id,
                template_version_id=prepare_request.template_version_id,
                version_intent=prepare_request.version_intent,
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
            )
        )

        response = await generation_service.prepare_generation_inputs(prepare_request)
        assert response.status == "VALIDATED"
