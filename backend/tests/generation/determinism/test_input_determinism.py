import hashlib
import json
from unittest.mock import MagicMock
from uuid import UUID

from backend.app.domains.generation.schemas import (
    ClientDataPayload,
    GenerationInputData,
    PrepareGenerationInputsRequest,
    PromptConfigMetadata,
    SectionHierarchyContext,
    SurroundingContext,
)


def create_prompt_config():
    return PromptConfigMetadata(
        classification_confidence=0.95,
        classification_method="RULE_BASED",
        justification="Test justification",
    )


class TestInputHashDeterminism:

    def test_generation_input_data_hash_is_deterministic(self):
        input_data = GenerationInputData(
            section_id=1,
            template_id="11111111-1111-1111-1111-111111111111",
            template_version_id="22222222-2222-2222-2222-222222222222",
            structural_path="Executive Summary",
            hierarchy_context=SectionHierarchyContext(depth=0, ancestors=[]),
            prompt_config=create_prompt_config(),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )

        hash1 = input_data.compute_hash()
        hash2 = input_data.compute_hash()

        assert hash1 == hash2

    def test_different_section_id_produces_different_hash(self):
        base_data = {
            "template_id": "11111111-1111-1111-1111-111111111111",
            "template_version_id": "22222222-2222-2222-2222-222222222222",
            "structural_path": "Executive Summary",
            "hierarchy_context": SectionHierarchyContext(depth=0, ancestors=[]),
            "prompt_config": create_prompt_config(),
            "client_data": ClientDataPayload(),
            "surrounding_context": SurroundingContext(),
        }

        input1 = GenerationInputData(section_id=1, **base_data)
        input2 = GenerationInputData(section_id=2, **base_data)

        assert input1.compute_hash() != input2.compute_hash()

    def test_different_client_data_produces_different_hash(self):
        base_data = {
            "section_id": 1,
            "template_id": "11111111-1111-1111-1111-111111111111",
            "template_version_id": "22222222-2222-2222-2222-222222222222",
            "structural_path": "Executive Summary",
            "hierarchy_context": SectionHierarchyContext(depth=0, ancestors=[]),
            "prompt_config": create_prompt_config(),
            "surrounding_context": SurroundingContext(),
        }

        input1 = GenerationInputData(
            client_data=ClientDataPayload(client_name="Client A"), **base_data
        )
        input2 = GenerationInputData(
            client_data=ClientDataPayload(client_name="Client B"), **base_data
        )

        assert input1.compute_hash() != input2.compute_hash()


class TestRequestDeterminism:

    def test_prepare_request_parameters_are_consistent(self):
        fixed_document_id = UUID("11111111-1111-1111-1111-111111111111")
        fixed_template_version_id = UUID("22222222-2222-2222-2222-222222222222")

        request1 = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=ClientDataPayload(client_name="Test Corp"),
        )

        request2 = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=ClientDataPayload(client_name="Test Corp"),
        )

        assert request1.document_id == request2.document_id
        assert request1.template_version_id == request2.template_version_id
        assert request1.version_intent == request2.version_intent

    def test_different_version_intent_creates_different_request(self):
        fixed_document_id = UUID("11111111-1111-1111-1111-111111111111")
        fixed_template_version_id = UUID("22222222-2222-2222-2222-222222222222")

        request1 = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=1,
            client_data=ClientDataPayload(),
        )

        request2 = PrepareGenerationInputsRequest(
            document_id=fixed_document_id,
            template_version_id=fixed_template_version_id,
            version_intent=2,
            client_data=ClientDataPayload(),
        )

        assert request1.version_intent != request2.version_intent


class TestSectionOrderingDeterminism:

    def test_sections_sorted_by_id_are_deterministic(self):
        sections = [
            MagicMock(id=3, structural_path="C"),
            MagicMock(id=1, structural_path="A"),
            MagicMock(id=2, structural_path="B"),
        ]

        sorted1 = sorted(sections, key=lambda s: (s.id, s.structural_path))
        sorted2 = sorted(sections, key=lambda s: (s.id, s.structural_path))

        assert [s.id for s in sorted1] == [s.id for s in sorted2]
        assert [s.id for s in sorted1] == [1, 2, 3]

    def test_ordering_does_not_depend_on_input_order(self):
        sections_forward = [
            MagicMock(id=1, structural_path="A"),
            MagicMock(id=2, structural_path="B"),
            MagicMock(id=3, structural_path="C"),
        ]

        sections_reversed = [
            MagicMock(id=3, structural_path="C"),
            MagicMock(id=2, structural_path="B"),
            MagicMock(id=1, structural_path="A"),
        ]

        sorted_forward = sorted(sections_forward, key=lambda s: (s.id, s.structural_path))
        sorted_reversed = sorted(sections_reversed, key=lambda s: (s.id, s.structural_path))

        assert [s.id for s in sorted_forward] == [s.id for s in sorted_reversed]


class TestBatchHashConsistency:

    def test_batch_hash_from_inputs_is_deterministic(self):
        inputs = [
            {"section_id": 1, "content": "Content A"},
            {"section_id": 2, "content": "Content B"},
        ]

        def compute_batch_hash(input_list):
            combined = json.dumps(input_list, sort_keys=True)
            return hashlib.sha256(combined.encode()).hexdigest()

        hash1 = compute_batch_hash(inputs)
        hash2 = compute_batch_hash(inputs)

        assert hash1 == hash2

    def test_different_inputs_produce_different_batch_hash(self):
        inputs1 = [{"section_id": 1, "content": "Content A"}]
        inputs2 = [{"section_id": 1, "content": "Content B"}]

        def compute_batch_hash(input_list):
            combined = json.dumps(input_list, sort_keys=True)
            return hashlib.sha256(combined.encode()).hexdigest()

        assert compute_batch_hash(inputs1) != compute_batch_hash(inputs2)

    def test_batch_hash_format_is_hex(self):
        inputs = [{"section_id": 1}]

        def compute_batch_hash(input_list):
            combined = json.dumps(input_list, sort_keys=True)
            return hashlib.sha256(combined.encode()).hexdigest()

        hash_value = compute_batch_hash(inputs)
        assert all(c in "0123456789abcdef" for c in hash_value)
        assert len(hash_value) == 64


class TestClientDataDeterminism:

    def test_client_data_serialization_is_deterministic(self):
        client_data = ClientDataPayload(
            client_name="Test Corporation",
            client_id="test-corp-001",
            data_fields={"priority": "high", "region": "NA"},
        )

        json1 = client_data.model_dump_json(exclude_none=True)
        json2 = client_data.model_dump_json(exclude_none=True)

        assert json1 == json2

    def test_empty_client_data_is_valid(self):
        client_data = ClientDataPayload()
        assert client_data.client_name is None
        assert client_data.data_fields == {}

    def test_data_fields_order_does_not_affect_equality(self):
        client_data1 = ClientDataPayload(data_fields={"a": 1, "b": 2})
        client_data2 = ClientDataPayload(data_fields={"b": 2, "a": 1})

        assert client_data1.data_fields == client_data2.data_fields
