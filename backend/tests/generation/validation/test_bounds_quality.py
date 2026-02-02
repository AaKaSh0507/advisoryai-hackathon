from backend.app.domains.generation.validation_schemas import (
    FailureType,
    QualityCheckConfig,
    ValidationErrorCode,
)
from backend.app.domains.generation.validation_service import (
    BoundsValidator,
    ContentValidationService,
    QualityValidator,
)


class TestEmptyOutputRejected:
    def test_empty_string_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("")
        assert not result.is_valid
        assert result.is_empty
        assert ValidationErrorCode.EMPTY_CONTENT in result.error_codes

    def test_whitespace_only_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("   \n\t  ")
        assert not result.is_valid
        assert result.is_empty
        assert ValidationErrorCode.EMPTY_CONTENT in result.error_codes

    def test_newlines_only_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("\n\n\n")
        assert not result.is_valid
        assert result.is_empty

    def test_tabs_only_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("\t\t\t")
        assert not result.is_valid
        assert result.is_empty


class TestNearEmptyOutputRejected:
    def test_single_character_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("x")
        assert not result.is_valid
        assert result.is_near_empty
        assert ValidationErrorCode.NEAR_EMPTY_CONTENT in result.error_codes

    def test_few_characters_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("hello")
        assert not result.is_valid
        assert result.is_near_empty

    def test_nine_chars_rejected(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("123456789")
        assert not result.is_valid
        assert result.is_near_empty

    def test_ten_chars_passes(self, bounds_validator: BoundsValidator):
        result = bounds_validator.validate("1234567890")
        assert result.is_valid
        assert not result.is_near_empty


class TestExcessivelyLongOutputRejected:
    def test_content_exceeding_max_length_rejected(self):
        validator = BoundsValidator(min_length=1, max_length=100)
        long_content = "x" * 101
        result = validator.validate(long_content)
        assert not result.is_valid
        assert result.is_too_long
        assert ValidationErrorCode.CONTENT_TOO_LONG in result.error_codes

    def test_content_at_max_length_passes(self):
        validator = BoundsValidator(min_length=1, max_length=100)
        content = "x" * 100
        result = validator.validate(content)
        assert result.is_valid
        assert not result.is_too_long

    def test_very_long_content_rejected(self):
        validator = BoundsValidator(min_length=1, max_length=50000)
        content = "word " * 15000
        result = validator.validate(content)
        assert not result.is_valid
        assert result.is_too_long


class TestContentTooShortRejected:
    def test_content_below_min_length_rejected(self):
        validator = BoundsValidator(min_length=20, max_length=50000)
        content = "Short text."
        result = validator.validate(content)
        assert not result.is_valid
        assert result.is_too_short
        assert ValidationErrorCode.CONTENT_TOO_SHORT in result.error_codes

    def test_content_at_min_length_passes(self):
        validator = BoundsValidator(min_length=10, max_length=50000)
        content = "1234567890"
        result = validator.validate(content)
        assert result.is_valid
        assert not result.is_too_short


class TestMinimalAcceptableOutputPasses:
    def test_minimal_valid_content_passes(self, bounds_validator: BoundsValidator):
        content = "This is valid content."
        result = bounds_validator.validate(content)
        assert result.is_valid
        assert result.content_length == 22

    def test_ten_char_content_passes(self, bounds_validator: BoundsValidator):
        content = "1234567890"
        result = bounds_validator.validate(content)
        assert result.is_valid
        assert result.content_length == 10


class TestQualityChecks:
    def test_repetitive_content_rejected(self, quality_validator: QualityValidator):
        content = "word word word word word word word word word word word word"
        result = quality_validator.validate(content)
        assert not result.is_valid
        assert result.is_repetitive
        assert ValidationErrorCode.REPETITIVE_CONTENT in result.error_codes

    def test_non_repetitive_content_passes(self, quality_validator: QualityValidator):
        content = "The quick brown fox jumps over the lazy dog."
        result = quality_validator.validate(content)
        assert result.is_valid
        assert not result.is_repetitive

    def test_boilerplate_lorem_ipsum_rejected(self, quality_validator: QualityValidator):
        content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
        result = quality_validator.validate(content)
        assert not result.is_valid
        assert result.is_boilerplate
        assert ValidationErrorCode.BOILERPLATE_ONLY in result.error_codes

    def test_boilerplate_placeholder_rejected(self, quality_validator: QualityValidator):
        content = "Placeholder text here for now."
        result = quality_validator.validate(content)
        assert not result.is_valid
        assert result.is_boilerplate

    def test_boilerplate_todo_rejected(self, quality_validator: QualityValidator):
        content = "TODO:"
        result = quality_validator.validate(content)
        assert not result.is_valid
        assert result.is_boilerplate

    def test_boilerplate_insert_bracket_rejected(self, quality_validator: QualityValidator):
        content = "[Insert client name here]"
        result = quality_validator.validate(content)
        assert not result.is_valid
        assert result.is_boilerplate

    def test_real_content_passes_quality(self, quality_validator: QualityValidator):
        content = """
        Our analysis indicates that the market conditions are favorable for
        expansion into the northern region. Revenue projections suggest a
        15% growth opportunity over the next fiscal year.
        """
        result = quality_validator.validate(content)
        assert result.is_valid
        assert not result.is_boilerplate
        assert not result.is_repetitive


class TestComprehensiveBoundsValidation:
    def test_empty_fails_comprehensive(
        self,
        content_validation_service: ContentValidationService,
    ):
        result = content_validation_service.validate("")
        assert not result.is_valid
        assert result.failure_type == FailureType.BOUNDS_VIOLATION
        assert result.is_retryable

    def test_too_long_fails_comprehensive(self):
        service = ContentValidationService(max_length=100)
        content = "x" * 150
        result = service.validate(content)
        assert not result.is_valid
        assert result.failure_type == FailureType.BOUNDS_VIOLATION
        assert result.is_retryable

    def test_quality_failure_not_retryable(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "Lorem ipsum dolor sit amet."
        result = content_validation_service.validate(content)
        assert not result.is_valid
        assert result.failure_type == FailureType.QUALITY_FAILURE
        assert not result.is_retryable


class TestCustomQualityConfig:
    def test_custom_min_unique_words(self):
        config = QualityCheckConfig(min_unique_words=10)
        validator = QualityValidator(config)
        content = "This is a short sentence with few words."
        result = validator.validate(content)
        assert result.unique_word_count < 10

    def test_custom_boilerplate_pattern(self):
        config = QualityCheckConfig(
            boilerplate_patterns=[r"DRAFT ONLY", r"NOT FOR DISTRIBUTION"],
        )
        validator = QualityValidator(config)
        content = "This document is DRAFT ONLY and should not be shared."
        result = validator.validate(content)
        assert not result.is_valid
        assert result.is_boilerplate
