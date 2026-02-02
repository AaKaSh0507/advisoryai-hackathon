from backend.app.domains.generation.validation_schemas import FailureType, ValidationErrorCode
from backend.app.domains.generation.validation_service import (
    ContentValidationService,
    GenerationValidationService,
)


class TestFailuresClassifiedCorrectly:
    def test_empty_content_classified_as_bounds_violation(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content("")
        failure_type = generation_validation_service.get_failure_classification(
            validation_result,
            llm_failed=False,
            unexpected_error=False,
        )
        assert failure_type == FailureType.BOUNDS_VIOLATION

    def test_html_classified_as_structural_violation(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content("<p>HTML</p>")
        failure_type = generation_validation_service.get_failure_classification(
            validation_result,
        )
        assert failure_type == FailureType.STRUCTURAL_VIOLATION

    def test_markdown_header_classified_as_structural(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content("# Header\nContent")
        failure_type = generation_validation_service.get_failure_classification(
            validation_result,
        )
        assert failure_type == FailureType.STRUCTURAL_VIOLATION

    def test_boilerplate_classified_as_quality_failure(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content(
            "Lorem ipsum dolor sit amet."
        )
        failure_type = generation_validation_service.get_failure_classification(
            validation_result,
        )
        assert failure_type == FailureType.QUALITY_FAILURE

    def test_llm_failure_classified_as_generation_failure(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        failure_type = generation_validation_service.get_failure_classification(
            validation_result=None,
            llm_failed=True,
        )
        assert failure_type == FailureType.GENERATION_FAILURE

    def test_unexpected_error_classification(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        failure_type = generation_validation_service.get_failure_classification(
            validation_result=None,
            unexpected_error=True,
        )
        assert failure_type == FailureType.UNEXPECTED_ERROR

    def test_too_long_classified_as_bounds_violation(
        self,
    ):
        service = GenerationValidationService(max_length=100)
        validation_result = service.validate_content("x" * 150)
        failure_type = service.get_failure_classification(validation_result)
        assert failure_type == FailureType.BOUNDS_VIOLATION


class TestFailureMetadataPersisted:
    def test_validation_metadata_created(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content("<div>HTML</div>")
        metadata = generation_validation_service.create_validation_metadata(
            validation_result=validation_result,
            attempt_number=1,
            input_hash="test_hash_123",
            structural_path="body/introduction",
        )
        assert "input_hash" in metadata
        assert metadata["input_hash"] == "test_hash_123"
        assert "structural_path" in metadata
        assert metadata["attempt_number"] == 1
        assert "validation" in metadata
        assert metadata["validation"]["is_valid"] is False

    def test_metadata_includes_error_codes(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content("<p>test</p>")
        metadata = generation_validation_service.create_validation_metadata(
            validation_result=validation_result,
            attempt_number=0,
            input_hash="hash",
            structural_path="path",
        )
        assert "error_codes" in metadata["validation"]
        assert len(metadata["validation"]["error_codes"]) > 0

    def test_metadata_includes_violation_details(
        self,
        generation_validation_service: GenerationValidationService,
    ):
        validation_result = generation_validation_service.validate_content("# Header\nText")
        metadata = generation_validation_service.create_validation_metadata(
            validation_result=validation_result,
            attempt_number=0,
            input_hash="hash",
            structural_path="path",
        )
        assert "violations" in metadata["validation"]
        assert len(metadata["validation"]["violations"]) > 0


class TestFailureStatesQueryable:
    def test_validation_result_has_all_error_codes(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("<strong>Bold</strong>")
        assert len(result.all_error_codes) > 0
        assert all(isinstance(c, ValidationErrorCode) for c in result.all_error_codes)

    def test_validation_result_has_all_violations(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("# Header\n<div>HTML</div>")
        assert len(result.all_violations) > 0

    def test_failure_type_queryable_from_result(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("")
        assert result.failure_type is not None
        assert result.failure_type == FailureType.BOUNDS_VIOLATION

    def test_is_retryable_flag_queryable(
        self,
        content_validation_service: ContentValidationService,
    ):
        empty_result = content_validation_service.validate("")
        assert empty_result.is_retryable is True

        html_result = content_validation_service.validate("<p>HTML</p>")
        assert html_result.is_retryable is False


class TestComprehensiveValidationResultStructure:
    def test_result_has_structural_result(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("Valid content here.")
        assert result.structural_result is not None
        assert result.structural_result.is_valid is True

    def test_result_has_bounds_result(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("Valid content here.")
        assert result.bounds_result is not None
        assert result.bounds_result.is_valid is True

    def test_result_has_quality_result(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate(
            "This is a properly written piece of content for the advisory document."
        )
        assert result.quality_result is not None
        assert result.quality_result.is_valid is True

    def test_result_has_validation_metadata(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("Some content.")
        assert result.validation_metadata is not None
        assert "content_length" in result.validation_metadata
        assert "structural_checks" in result.validation_metadata
        assert "bounds_checks" in result.validation_metadata
        assert "quality_checks" in result.validation_metadata
