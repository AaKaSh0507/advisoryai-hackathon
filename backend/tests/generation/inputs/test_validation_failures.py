from datetime import datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from backend.app.domains.generation.errors import (
    InputValidationError,
    MalformedSectionMetadataError,
    MissingPromptConfigError,
)
from backend.app.domains.generation.schemas import (
    ClientDataPayload,
    GenerationInputCreate,
    GenerationInputData,
    PrepareGenerationInputsRequest,
    PromptConfigMetadata,
    SectionHierarchyContext,
    SurroundingContext,
)
from backend.app.domains.generation.service import GenerationInputService
from backend.app.domains.section.models import Section, SectionType


class TestMissingPromptConfigValidation:
    @pytest.mark.asyncio
    async def test_missing_prompt_config_raises_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        section_missing_prompt_config: Section,
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[section_missing_prompt_config]
        )
        with pytest.raises(MissingPromptConfigError) as exc_info:
            await generation_service.prepare_generation_inputs(prepare_request)
        error = exc_info.value
        assert error.section_id == section_missing_prompt_config.id
        assert error.structural_path == section_missing_prompt_config.structural_path

    @pytest.mark.asyncio
    async def test_incomplete_prompt_config_raises_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        section_incomplete_prompt_config: Section,
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[section_incomplete_prompt_config]
        )
        with pytest.raises(MissingPromptConfigError) as exc_info:
            await generation_service.prepare_generation_inputs(prepare_request)

        error = exc_info.value
        assert (
            "classification_method" in error.missing_fields
            or "justification" in error.missing_fields
        )

    def test_missing_prompt_config_error_is_traceable(
        self,
        fixed_template_version_id: UUID,
    ):
        error = MissingPromptConfigError(
            section_id=42,
            structural_path="body/problem_section",
            missing_fields=["classification_method", "justification"],
        )
        assert "42" in str(error)
        assert "body/problem_section" in str(error)
        assert "classification_method" in str(error)
        error_dict = error.to_dict()
        assert error_dict["details"]["section_id"] == 42
        assert error_dict["details"]["structural_path"] == "body/problem_section"
        assert "classification_method" in error_dict["details"]["missing_fields"]


class TestMalformedMetadataValidation:
    @pytest.mark.asyncio
    async def test_non_dict_prompt_config_raises_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        section_malformed_prompt_config: Section,
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[section_malformed_prompt_config]
        )
        with pytest.raises(MalformedSectionMetadataError) as exc_info:
            await generation_service.prepare_generation_inputs(prepare_request)

        error = exc_info.value
        assert error.section_id == section_malformed_prompt_config.id

    @pytest.mark.asyncio
    async def test_invalid_confidence_type_raises_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        fixed_template_version_id: UUID,
        prepare_request: PrepareGenerationInputsRequest,
    ):
        section = Section(
            id=200,
            template_version_id=fixed_template_version_id,
            section_type=SectionType.DYNAMIC,
            structural_path="body/invalid_confidence",
            prompt_config={
                "classification_confidence": "not_a_number",  # Should be float!
                "classification_method": "RULE_BASED",
                "justification": "Test",
            },
        )
        section.created_at = datetime(2026, 1, 1, 12, 0, 0)

        mock_section_repository.get_by_template_version_id = AsyncMock(return_value=[section])

        with pytest.raises((MalformedSectionMetadataError, ValueError)):
            await generation_service.prepare_generation_inputs(prepare_request)

    def test_malformed_metadata_error_is_traceable(self):
        error = MalformedSectionMetadataError(
            section_id=42,
            structural_path="body/malformed",
            reason="Expected dict, got str",
            invalid_data="not a dict",
        )
        assert "42" in str(error)
        assert "body/malformed" in str(error)
        assert "Expected dict, got str" in str(error)
        error_dict = error.to_dict()
        assert error_dict["details"]["section_id"] == 42
        assert error_dict["details"]["reason"] == "Expected dict, got str"


class TestInputValidationErrors:
    def test_invalid_section_id_validation(self, generation_service: GenerationInputService):
        input_data = GenerationInputData(
            section_id=0,
            template_id="22222222-2222-2222-2222-222222222222",
            template_version_id="22222222-2222-2222-2222-222222222222",
            structural_path="body/test",
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )

        with pytest.raises(InputValidationError) as exc_info:
            generation_service._validate_input(input_data)

        error = exc_info.value
        assert error.field == "section_id"
        assert "positive" in error.reason.lower()

    def test_invalid_template_id_validation(self, generation_service: GenerationInputService):
        input_data = GenerationInputData(
            section_id=1,
            template_id="not-a-valid-uuid",  # Invalid UUID
            template_version_id="22222222-2222-2222-2222-222222222222",
            structural_path="body/test",
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )

        with pytest.raises(InputValidationError) as exc_info:
            generation_service._validate_input(input_data)

        error = exc_info.value
        assert error.field == "template_id"
        assert "UUID" in error.reason

    def test_empty_structural_path_validation(self, generation_service: GenerationInputService):
        input_data = GenerationInputData(
            section_id=1,
            template_id="22222222-2222-2222-2222-222222222222",
            template_version_id="22222222-2222-2222-2222-222222222222",
            structural_path="   ",  # Empty/whitespace only
            hierarchy_context=SectionHierarchyContext(),
            prompt_config=PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
                justification="Test",
            ),
            client_data=ClientDataPayload(),
            surrounding_context=SurroundingContext(),
        )

        with pytest.raises(InputValidationError) as exc_info:
            generation_service._validate_input(input_data)

        error = exc_info.value
        assert error.field == "structural_path"
        assert "empty" in error.reason.lower()

    def test_invalid_confidence_range_validation(self, generation_service: GenerationInputService):
        with pytest.raises(Exception):
            GenerationInputData(
                section_id=1,
                template_id="22222222-2222-2222-2222-222222222222",
                template_version_id="22222222-2222-2222-2222-222222222222",
                structural_path="body/test",
                hierarchy_context=SectionHierarchyContext(),
                prompt_config=PromptConfigMetadata(
                    classification_confidence=1.5,  # Invalid: > 1.0
                    classification_method="RULE_BASED",
                    justification="Test",
                ),
                client_data=ClientDataPayload(),
                surrounding_context=SurroundingContext(),
            )

    def test_validation_error_is_traceable(self):
        error = InputValidationError(
            field="prompt_config.classification_confidence",
            reason="must be between 0.0 and 1.0",
            section_id=42,
            invalid_value=1.5,
        )
        assert "42" in str(error)
        assert "prompt_config.classification_confidence" in str(error)
        error_dict = error.to_dict()
        assert error_dict["details"]["field"] == "prompt_config.classification_confidence"
        assert error_dict["details"]["section_id"] == 42
        assert error_dict["details"]["invalid_value"] == "1.5"


class TestSchemaValidationErrors:
    def test_prompt_config_metadata_requires_confidence(self):
        with pytest.raises(Exception):
            PromptConfigMetadata(
                classification_method="RULE_BASED",
                justification="Test",
            )

    def test_prompt_config_metadata_requires_method(self):
        with pytest.raises(Exception):
            PromptConfigMetadata(
                classification_confidence=0.9,
                justification="Test",
            )

    def test_prompt_config_metadata_requires_justification(self):
        with pytest.raises(Exception):
            PromptConfigMetadata(
                classification_confidence=0.9,
                classification_method="RULE_BASED",
            )

    def test_prompt_config_confidence_range_validation(self):
        with pytest.raises(Exception):
            PromptConfigMetadata(
                classification_confidence=2.0,
                classification_method="RULE_BASED",
                justification="Test",
            )

        with pytest.raises(Exception):
            PromptConfigMetadata(
                classification_confidence=-0.5,
                classification_method="RULE_BASED",
                justification="Test",
            )

    def test_generation_input_create_validates_structural_path(self):
        with pytest.raises(Exception):
            GenerationInputCreate(
                section_id=1,
                sequence_order=0,
                template_id=UUID("22222222-2222-2222-2222-222222222222"),
                template_version_id=UUID("22222222-2222-2222-2222-222222222222"),
                structural_path="",
                hierarchy_context={},
                prompt_config={
                    "classification_confidence": 0.9,
                    "classification_method": "RULE_BASED",
                    "justification": "Test",
                },
                client_data={},
                surrounding_context={},
            )

    def test_generation_input_create_validates_prompt_config(self):
        with pytest.raises(Exception):
            GenerationInputCreate(
                section_id=1,
                sequence_order=0,
                template_id=UUID("22222222-2222-2222-2222-222222222222"),
                template_version_id=UUID("22222222-2222-2222-2222-222222222222"),
                structural_path="body/test",
                hierarchy_context={},
                prompt_config={},  # Missing required fields
                client_data={},
                surrounding_context={},
            )


class TestErrorDeterminism:
    @pytest.mark.asyncio
    async def test_same_invalid_input_same_error(
        self,
        generation_service: GenerationInputService,
        mock_section_repository,
        mock_generation_repository,
        section_missing_prompt_config: Section,
        prepare_request: PrepareGenerationInputsRequest,
    ):
        mock_section_repository.get_by_template_version_id = AsyncMock(
            return_value=[section_missing_prompt_config]
        )

        errors = []
        for _ in range(5):
            try:
                await generation_service.prepare_generation_inputs(prepare_request)
            except MissingPromptConfigError as e:
                errors.append(e.to_dict())
        assert len(errors) == 5
        first_error = errors[0]
        for error in errors[1:]:
            assert error == first_error

    def test_error_message_deterministic(self):
        error1 = MissingPromptConfigError(
            section_id=42,
            structural_path="body/test",
            missing_fields=["field_a", "field_b"],
        )

        error2 = MissingPromptConfigError(
            section_id=42,
            structural_path="body/test",
            missing_fields=["field_a", "field_b"],
        )

        assert str(error1) == str(error2)
        assert error1.to_dict() == error2.to_dict()
