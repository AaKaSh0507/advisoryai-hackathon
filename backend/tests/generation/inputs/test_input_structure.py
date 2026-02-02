import json
from uuid import UUID

import pytest

from backend.app.domains.generation.schemas import (
    ClientDataPayload,
    GenerationInputData,
    GenerationInputResponse,
    PrepareGenerationInputsResponse,
    PromptConfigMetadata,
    SectionHierarchyContext,
    SurroundingContext,
)


class TestGenerationInputDataStructure:
    @pytest.fixture
    def valid_input_data(self, fixed_template_version_id: UUID) -> GenerationInputData:
        return GenerationInputData(
            section_id=1,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/introduction",
            hierarchy_context=SectionHierarchyContext(
                parent_heading="Body",
                parent_level=1,
                sibling_index=0,
                total_siblings=3,
                depth=1,
                path_segments=["body", "introduction"],
            ),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.95,
                classification_method="RULE_BASED",
                justification="Contains placeholder {client_name}",
                prompt_template=None,
                generation_hints={},
                metadata={"detected_placeholders": ["{client_name}"]},
            ),
            client_data=ClientDataPayload(
                client_id="client_001",
                client_name="Acme Corp",
                data_fields={"project": "Q4 Report"},
                custom_context={},
            ),
            surrounding_context=SurroundingContext(
                preceding_content="header/logo",
                preceding_type="STATIC",
                following_content="body/legal",
                following_type="STATIC",
                section_boundary_hint="Section 2 of 5",
            ),
        )

    def test_all_required_fields_present(self, valid_input_data: GenerationInputData):
        required_fields = {
            "section_id",
            "template_id",
            "template_version_id",
            "structural_path",
            "hierarchy_context",
            "prompt_config",
            "client_data",
            "surrounding_context",
        }

        data_dict = valid_input_data.model_dump()
        actual_fields = set(data_dict.keys())

        assert required_fields.issubset(actual_fields)

    def test_no_extraneous_top_level_fields(self, valid_input_data: GenerationInputData):
        expected_fields = {
            "section_id",
            "template_id",
            "template_version_id",
            "structural_path",
            "hierarchy_context",
            "prompt_config",
            "client_data",
            "surrounding_context",
        }

        data_dict = valid_input_data.model_dump()
        actual_fields = set(data_dict.keys())

        assert actual_fields == expected_fields

    def test_hierarchy_context_structure(self, valid_input_data: GenerationInputData):
        expected_fields = {
            "parent_heading",
            "parent_level",
            "sibling_index",
            "total_siblings",
            "depth",
            "path_segments",
        }

        hierarchy_dict = valid_input_data.hierarchy_context.model_dump()
        actual_fields = set(hierarchy_dict.keys())

        assert actual_fields == expected_fields

    def test_prompt_config_structure(self, valid_input_data: GenerationInputData):
        expected_fields = {
            "classification_confidence",
            "classification_method",
            "justification",
            "prompt_template",
            "generation_hints",
            "metadata",
        }

        config_dict = valid_input_data.prompt_config.model_dump()
        actual_fields = set(config_dict.keys())

        assert actual_fields == expected_fields

    def test_client_data_structure(self, valid_input_data: GenerationInputData):
        expected_fields = {
            "client_id",
            "client_name",
            "data_fields",
            "custom_context",
        }

        client_dict = valid_input_data.client_data.model_dump()
        actual_fields = set(client_dict.keys())

        assert actual_fields == expected_fields

    def test_surrounding_context_structure(self, valid_input_data: GenerationInputData):
        expected_fields = {
            "preceding_content",
            "preceding_type",
            "following_content",
            "following_type",
            "section_boundary_hint",
        }

        context_dict = valid_input_data.surrounding_context.model_dump()
        actual_fields = set(context_dict.keys())

        assert actual_fields == expected_fields


class TestSchemaStability:
    @pytest.fixture
    def stable_input_data(self, fixed_template_version_id: UUID) -> GenerationInputData:
        """Create input data with fixed values for stability testing."""
        return GenerationInputData(
            section_id=42,
            template_id=str(fixed_template_version_id),
            template_version_id=str(fixed_template_version_id),
            structural_path="body/test_section",
            hierarchy_context=SectionHierarchyContext(
                parent_heading="Body",
                parent_level=1,
                sibling_index=2,
                total_siblings=5,
                depth=1,
                path_segments=["body", "test_section"],
            ),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.87,
                classification_method="LLM",
                justification="Identified as dynamic by LLM analysis",
                prompt_template="Generate content for {section}",
                generation_hints={"tone": "formal"},
                metadata={"model_version": "v1"},
            ),
            client_data=ClientDataPayload(
                client_id="stable_client",
                client_name="Stable Corp",
                data_fields={"key1": "value1", "key2": "value2"},
                custom_context={"flag": True},
            ),
            surrounding_context=SurroundingContext(
                preceding_content="previous_section",
                preceding_type="DYNAMIC",
                following_content="next_section",
                following_type="STATIC",
                section_boundary_hint="Middle section",
            ),
        )

    def test_json_serialization_roundtrip(self, stable_input_data: GenerationInputData):
        json_str = json.dumps(stable_input_data.model_dump(mode="json"))
        data_dict = json.loads(json_str)
        restored = GenerationInputData(**data_dict)
        assert restored.section_id == stable_input_data.section_id
        assert restored.template_id == stable_input_data.template_id
        assert restored.structural_path == stable_input_data.structural_path
        assert (
            restored.prompt_config.classification_confidence
            == stable_input_data.prompt_config.classification_confidence
        )

    def test_schema_field_types_stable(self, stable_input_data: GenerationInputData):
        data_dict = stable_input_data.model_dump(mode="json")
        assert isinstance(data_dict["section_id"], int)
        assert isinstance(data_dict["template_id"], str)
        assert isinstance(data_dict["template_version_id"], str)
        assert isinstance(data_dict["structural_path"], str)
        assert isinstance(data_dict["hierarchy_context"], dict)
        assert isinstance(data_dict["prompt_config"], dict)
        assert isinstance(data_dict["client_data"], dict)
        assert isinstance(data_dict["surrounding_context"], dict)

    def test_nested_types_stable(self, stable_input_data: GenerationInputData):
        data_dict = stable_input_data.model_dump(mode="json")
        hc = data_dict["hierarchy_context"]
        assert isinstance(hc["sibling_index"], int)
        assert isinstance(hc["total_siblings"], int)
        assert isinstance(hc["depth"], int)
        assert isinstance(hc["path_segments"], list)
        pc = data_dict["prompt_config"]
        assert isinstance(pc["classification_confidence"], float)
        assert isinstance(pc["classification_method"], str)
        assert isinstance(pc["generation_hints"], dict)
        cd = data_dict["client_data"]
        assert isinstance(cd["data_fields"], dict)
        assert isinstance(cd["custom_context"], dict)


class TestGenerationInputResponseStructure:
    def test_response_includes_all_input_fields(self):
        expected_fields = {
            "id",
            "batch_id",
            "section_id",
            "sequence_order",
            "template_id",
            "template_version_id",
            "structural_path",
            "hierarchy_context",
            "prompt_config",
            "client_data",
            "surrounding_context",
            "input_hash",
            "created_at",
        }

        schema_fields = set(GenerationInputResponse.model_fields.keys())
        assert schema_fields == expected_fields


class TestPrepareGenerationInputsResponseStructure:
    def test_response_includes_batch_metadata(self):
        expected_fields = {
            "batch_id",
            "document_id",
            "template_version_id",
            "version_intent",
            "status",
            "total_dynamic_sections",
            "content_hash",
            "is_immutable",
            "inputs",
        }

        schema_fields = set(PrepareGenerationInputsResponse.model_fields.keys())
        assert schema_fields == expected_fields


class TestDefaultValues:
    def test_hierarchy_context_defaults(self):
        context = SectionHierarchyContext()
        assert context.parent_heading is None
        assert context.parent_level is None
        assert context.sibling_index == 0
        assert context.total_siblings == 1
        assert context.depth == 0
        assert context.path_segments == []

    def test_client_data_defaults(self):
        client_data = ClientDataPayload()
        assert client_data.client_id is None
        assert client_data.client_name is None
        assert client_data.data_fields == {}
        assert client_data.custom_context == {}

    def test_surrounding_context_defaults(self):
        context = SurroundingContext()
        assert context.preceding_content is None
        assert context.preceding_type is None
        assert context.following_content is None
        assert context.following_type is None
        assert context.section_boundary_hint is None

    def test_prompt_config_required_fields(self):
        with pytest.raises(Exception):
            PromptConfigMetadata()

    def test_prompt_config_with_only_required(self):
        config = PromptConfigMetadata(
            classification_confidence=0.9,
            classification_method="RULE_BASED",
            justification="Test justification",
        )

        assert config.prompt_template is None
        assert config.generation_hints == {}
        assert config.metadata == {}
