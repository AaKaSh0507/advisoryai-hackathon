import pytest

from backend.app.domains.generation.validation_schemas import FailureType
from backend.app.domains.generation.validation_service import (
    BoundsValidator,
    ContentValidationService,
    QualityValidator,
    StructuralValidator,
)


class TestIdenticalInputsYieldIdenticalOutcomes:
    def test_structural_validation_deterministic(
        self,
        structural_validator: StructuralValidator,
    ):
        content = "This is plain text content."
        result1 = structural_validator.validate(content)
        result2 = structural_validator.validate(content)
        assert result1.is_valid == result2.is_valid
        assert result1.is_plain_text == result2.is_plain_text
        assert result1.error_codes == result2.error_codes

    def test_structural_rejection_deterministic(
        self,
        structural_validator: StructuralValidator,
    ):
        content = "<div>HTML content</div>"
        result1 = structural_validator.validate(content)
        result2 = structural_validator.validate(content)
        assert result1.is_valid == result2.is_valid is False
        assert result1.error_codes == result2.error_codes
        assert result1.detected_tags == result2.detected_tags

    def test_bounds_validation_deterministic(
        self,
        bounds_validator: BoundsValidator,
    ):
        content = "Valid content within bounds."
        result1 = bounds_validator.validate(content)
        result2 = bounds_validator.validate(content)
        assert result1.is_valid == result2.is_valid
        assert result1.content_length == result2.content_length
        assert result1.error_codes == result2.error_codes

    def test_quality_validation_deterministic(
        self,
        quality_validator: QualityValidator,
    ):
        content = "This is unique quality content for testing purposes."
        result1 = quality_validator.validate(content)
        result2 = quality_validator.validate(content)
        assert result1.is_valid == result2.is_valid
        assert result1.unique_word_count == result2.unique_word_count
        assert result1.repetition_ratio == result2.repetition_ratio

    def test_comprehensive_validation_deterministic(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "This is valid content for the advisory document section."
        result1 = content_validation_service.validate(content)
        result2 = content_validation_service.validate(content)
        assert result1.is_valid == result2.is_valid
        assert result1.content_hash == result2.content_hash
        assert result1.validated_content == result2.validated_content
        assert result1.failure_type == result2.failure_type
        assert result1.all_error_codes == result2.all_error_codes


class TestMultipleRunsProduceSameResults:
    def test_repeated_validation_consistent(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "Consistent validation testing content."
        results = [content_validation_service.validate(content) for _ in range(10)]
        first_result = results[0]
        for result in results[1:]:
            assert result.is_valid == first_result.is_valid
            assert result.content_hash == first_result.content_hash
            assert result.validated_content == first_result.validated_content

    def test_repeated_failure_validation_consistent(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "<p>Invalid HTML content</p>"
        results = [content_validation_service.validate(content) for _ in range(10)]
        first_result = results[0]
        for result in results[1:]:
            assert result.is_valid == first_result.is_valid is False
            assert result.failure_type == first_result.failure_type
            assert result.all_error_codes == first_result.all_error_codes


class TestHashConsistency:
    def test_content_hash_consistent(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "Content for hash consistency test."
        result1 = content_validation_service.validate(content)
        result2 = content_validation_service.validate(content)
        assert result1.content_hash == result2.content_hash
        assert result1.content_hash is not None

    def test_different_content_different_hash(
        self,
        content_validation_service: ContentValidationService,
    ):
        content1 = "First content for hashing."
        content2 = "Second content for hashing."
        result1 = content_validation_service.validate(content1)
        result2 = content_validation_service.validate(content2)
        assert result1.content_hash != result2.content_hash

    def test_whitespace_trimmed_consistently(
        self,
        content_validation_service: ContentValidationService,
    ):
        content1 = "  Content with whitespace  "
        content2 = "Content with whitespace"
        result1 = content_validation_service.validate(content1)
        result2 = content_validation_service.validate(content2)
        assert result1.validated_content == result2.validated_content
        assert result1.content_hash == result2.content_hash


class TestValidationOutcomesImmutable:
    def test_result_object_immutable(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("Valid content.")
        with pytest.raises(Exception):
            result.is_valid = False

    def test_structural_result_immutable(
        self,
        structural_validator: StructuralValidator,
    ):
        result = structural_validator.validate("Plain text.")
        with pytest.raises(Exception):
            result.is_valid = False

    def test_bounds_result_immutable(
        self,
        bounds_validator: BoundsValidator,
    ):
        result = bounds_validator.validate("Valid content.")
        with pytest.raises(Exception):
            result.content_length = 999


class TestFailureTypeDeterminism:
    def test_empty_always_bounds_violation(
        self,
        content_validation_service: ContentValidationService,
    ):
        for _ in range(5):
            result = content_validation_service.validate("")
            assert result.failure_type == FailureType.BOUNDS_VIOLATION

    def test_html_always_structural_violation(
        self,
        content_validation_service: ContentValidationService,
    ):
        for _ in range(5):
            result = content_validation_service.validate("<div>HTML</div>")
            assert result.failure_type == FailureType.STRUCTURAL_VIOLATION

    def test_boilerplate_always_quality_failure(
        self,
        content_validation_service: ContentValidationService,
    ):
        for _ in range(5):
            result = content_validation_service.validate("Lorem ipsum dolor sit amet.")
            assert result.failure_type == FailureType.QUALITY_FAILURE


class TestRetryabilityDeterminism:
    def test_bounds_violations_always_retryable(
        self,
        content_validation_service: ContentValidationService,
    ):
        for _ in range(5):
            result = content_validation_service.validate("")
            assert result.is_retryable is True

    def test_structural_violations_never_retryable(
        self,
        content_validation_service: ContentValidationService,
    ):
        for _ in range(5):
            result = content_validation_service.validate("# Header\nContent")
            assert result.is_retryable is False

    def test_quality_failures_never_retryable(
        self,
        content_validation_service: ContentValidationService,
    ):
        for _ in range(5):
            result = content_validation_service.validate("Lorem ipsum dolor sit amet.")
            assert result.is_retryable is False
