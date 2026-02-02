import hashlib
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.generation.models import GenerationInputStatus
from backend.app.domains.generation.schemas import (
    ClientDataPayload,
    GenerationInputData,
    PrepareGenerationInputsRequest,
    PromptConfigMetadata,
    SectionHierarchyContext,
    SurroundingContext,
)
from backend.app.domains.generation.service import GenerationInputService
from backend.app.domains.section.models import Section


class TestInputHashDeterminism:
    @pytest.fixture
    def fixed_input_data(self, fixed_template_version_id: UUID) -> GenerationInputData:
        return GenerationInputData(
            section_id=1,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/intro",
            hierarchy_context=SectionHierarchyContext(
                parent_heading="Body",
                parent_level=1,
                sibling_index=0,
                total_siblings=2,
                depth=1,
                path_segments=["body", "intro"],
            ),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.95,
                classification_method="RULE_BASED",
                justification="Contains placeholder",
            ),
            client_data=ClientDataPayload(
                client_id="c1",
                client_name="Test Client",
            ),
            surrounding_context=SurroundingContext(),
        )

    def test_same_input_produces_same_hash(self, fixed_input_data: GenerationInputData):
        hash1 = fixed_input_data.compute_hash()
        hash2 = fixed_input_data.compute_hash()
        assert hash1 == hash2

    def test_hash_consistent_across_multiple_calls(self, fixed_input_data: GenerationInputData):
        hashes = [fixed_input_data.compute_hash() for _ in range(100)]
        assert all(h == hashes[0] for h in hashes)

    def test_different_section_id_different_hash(self, fixed_template_version_id: UUID):
        input1 = GenerationInputData(
            section_id=1,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/intro",
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )

        input2 = GenerationInputData(
            section_id=2,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/intro",
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )
        assert input1.compute_hash() != input2.compute_hash()

    def test_different_structural_path_different_hash(self, fixed_template_version_id: UUID):
        base_kwargs = {
            "section_id": 1,
            "template_id": str(fixed_template_version_id),
            "template_version_id": str(fixed_template_version_id),
            "hierarchy_context": SectionHierarchyContext(),
            "prompt_config": PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            "client_data": ClientDataPayload(),
            "surrounding_context": SurroundingContext(),
        }
        input1 = GenerationInputData(**base_kwargs, structural_path="path/a")
        input2 = GenerationInputData(**base_kwargs, structural_path="path/b")
        assert input1.compute_hash() != input2.compute_hash()

    def test_different_client_data_different_hash(self, fixed_template_version_id: UUID):
        base_kwargs = {
            "section_id": 1,
            "template_id": str(fixed_template_version_id),
            "template_version_id": str(fixed_template_version_id),
            "structural_path": "body/intro",
            "hierarchy_context": SectionHierarchyContext(),
            "prompt_config": PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            "surrounding_context": SurroundingContext(),
        }
        input1 = GenerationInputData(
            **base_kwargs, client_data=ClientDataPayload(client_name="Client A")
        )
        input2 = GenerationInputData(
            **base_kwargs, client_data=ClientDataPayload(client_name="Client B")
        )
        assert input1.compute_hash() != input2.compute_hash()

    def test_hash_uses_sha256(self, fixed_input_data: GenerationInputData):
        hash_value = fixed_input_data.compute_hash()
        assert len(hash_value) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_hash_from_json_serialization(self, fixed_input_data: GenerationInputData):
        json_str = json.dumps(
            fixed_input_data.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        expected_hash = hashlib.sha256(json_str.encode("utf-8")).hexdigest()
        actual_hash = fixed_input_data.compute_hash()
        assert actual_hash == expected_hash


class TestBatchHashDeterminism:
    def test_batch_hash_same_for_same_inputs(
        self,
        generation_service: GenerationInputService,
        fixed_template_version_id: UUID,
    ):
        inputs = [
            GenerationInputData(
                section_id=i,
                template_id=str(fixed_template_version_id),
                template_version_id=str(fixed_template_version_id),
                structural_path=f"body/section_{i}",
                hierarchy_context=SectionHierarchyContext(),
                prompt_config=PromptConfigMetadata(
                    classification_confidence=0.9,
                    classification_method="RULE_BASED",
                    justification="Test",
                ),
                client_data=ClientDataPayload(),
                surrounding_context=SurroundingContext(),
            )
            for i in range(1, 4)
        ]

        hash1 = generation_service._compute_batch_hash(inputs)
        hash2 = generation_service._compute_batch_hash(inputs)
        assert hash1 == hash2

    def test_batch_hash_order_independent(
        self,
        generation_service: GenerationInputService,
        fixed_template_version_id: UUID,
    ):
        base_kwargs = {
            "template_id": str(fixed_template_version_id),
            "template_version_id": str(fixed_template_version_id),
            "hierarchy_context": SectionHierarchyContext(),
            "prompt_config": PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            "client_data": ClientDataPayload(),
            "surrounding_context": SurroundingContext(),
        }

        inputs_ordered = [
            GenerationInputData(section_id=1, structural_path="a", **base_kwargs),
            GenerationInputData(section_id=2, structural_path="b", **base_kwargs),
            GenerationInputData(section_id=3, structural_path="c", **base_kwargs),
        ]

        inputs_shuffled = [
            GenerationInputData(section_id=3, structural_path="c", **base_kwargs),
            GenerationInputData(section_id=1, structural_path="a", **base_kwargs),
            GenerationInputData(section_id=2, structural_path="b", **base_kwargs),
        ]

        hash_ordered = generation_service._compute_batch_hash(inputs_ordered)
        hash_shuffled = generation_service._compute_batch_hash(inputs_shuffled)
        assert hash_ordered == hash_shuffled

    def test_batch_hash_different_for_different_inputs(
        self,
        generation_service: GenerationInputService,
        fixed_template_version_id: UUID,
    ):
        base_kwargs = {
            "template_id": str(fixed_template_version_id),
            "template_version_id": str(fixed_template_version_id),
            "hierarchy_context": SectionHierarchyContext(),
            "prompt_config": PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            "client_data": ClientDataPayload(),
            "surrounding_context": SurroundingContext(),
        }

        inputs1 = [
            GenerationInputData(section_id=1, structural_path="a", **base_kwargs),
        ]

        inputs2 = [
            GenerationInputData(section_id=2, structural_path="b", **base_kwargs),
        ]

        hash1 = generation_service._compute_batch_hash(inputs1)
        hash2 = generation_service._compute_batch_hash(inputs2)
        assert hash1 != hash2


class TestPreparationDeterminism:
    @pytest.mark.asyncio
    async def test_same_request_same_inputs(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        mixed_sections: list[Section],
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=mixed_sections)
        created_batches = []
        created_inputs_list = []

        def capture_batch(batch):
            batch.id = uuid4()  # Simulate DB assignment
            created_batches.append(batch)
            return batch

        def capture_inputs(inputs):
            for inp in inputs:
                inp.id = uuid4()
            created_inputs_list.append(inputs)
            return inputs

        mock_generation_repository.create_batch = AsyncMock(side_effect=capture_batch)
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)

        def make_validated_batch(batch_id, validated_at):
            if created_batches:
                batch = created_batches[-1]
                batch.status = GenerationInputStatus.VALIDATED
                batch.validated_at = validated_at
                batch.is_immutable = True
                batch.inputs = created_inputs_list[-1] if created_inputs_list else []
                return batch
            return None

        mock_generation_repository.mark_batch_validated = AsyncMock(
            side_effect=make_validated_batch
        )
        mock_generation_repository.get_batch_by_id = AsyncMock(
            side_effect=lambda bid, include_inputs: created_batches[-1] if created_batches else None
        )

        response1 = await generation_service.prepare_generation_inputs(prepare_request)
        created_batches.clear()
        created_inputs_list.clear()
        response2 = await generation_service.prepare_generation_inputs(prepare_request)
        assert response1.content_hash == response2.content_hash
        assert response1.total_dynamic_sections == response2.total_dynamic_sections

    @pytest.mark.asyncio
    async def test_input_hashes_reproducible(
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
        captured_hashes = []

        def capture_inputs(inputs):
            for inp in inputs:
                inp.id = uuid4()
            captured_hashes.append([inp.input_hash for inp in inputs])
            return inputs

        mock_generation_repository.create_batch = AsyncMock(
            side_effect=lambda b: setattr(b, "id", uuid4()) or b
        )
        mock_generation_repository.create_inputs = AsyncMock(side_effect=capture_inputs)
        mock_generation_repository.mark_batch_validated = AsyncMock()
        mock_generation_repository.get_batch_by_id = AsyncMock(
            side_effect=lambda bid, include_inputs: MagicMock(
                id=bid,
                document_id=fixed_document_id,
                template_version_id=fixed_template_version_id,
                version_intent=1,
                status=GenerationInputStatus.VALIDATED,
                content_hash="test",
                is_immutable=True,
                inputs=[],
            )
        )

        request = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=sample_client_data,
        )

        await generation_service.prepare_generation_inputs(request)
        await generation_service.prepare_generation_inputs(request)
        assert len(captured_hashes) == 2
        assert captured_hashes[0] == captured_hashes[1]


class TestNoRuntimeValues:
    def test_input_data_frozen(self, fixed_template_version_id: UUID):
        """Verify GenerationInputData is immutable (frozen)."""
        input_data = GenerationInputData(
            section_id=1,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/intro",
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )
        with pytest.raises(Exception):
            input_data.section_id = 999

    def test_hash_independent_of_creation_time(self, fixed_template_version_id: UUID):
        kwargs = {
            "section_id": 1,
            "template_id": str(fixed_template_version_id),
            "template_version_id": str(fixed_template_version_id),
            "structural_path": "body/intro",
            "hierarchy_context": SectionHierarchyContext(),
            "prompt_config": PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            "client_data": ClientDataPayload(),
            "surrounding_context": SurroundingContext(),
        }
        import time

        input1 = GenerationInputData(**kwargs)
        time.sleep(0.1)
        input2 = GenerationInputData(**kwargs)

        assert input1.compute_hash() == input2.compute_hash()

    def test_serialized_json_has_no_runtime_fields(self, fixed_template_version_id: UUID):
        input_data = GenerationInputData(
            section_id=1,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/intro",
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )

        json_data = input_data.model_dump(mode="json")
        forbidden_fields = {"timestamp", "created_at", "updated_at", "uuid", "random"}

        def check_no_forbidden_fields(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    assert key not in forbidden_fields, f"Found forbidden field: {path}.{key}"
                    check_no_forbidden_fields(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_no_forbidden_fields(item, f"{path}[{i}]")

        check_no_forbidden_fields(json_data)
