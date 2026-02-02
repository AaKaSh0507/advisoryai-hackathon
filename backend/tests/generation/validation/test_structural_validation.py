from backend.app.domains.generation.validation_schemas import (
    FailureType,
    StructuralValidationConfig,
    ValidationErrorCode,
)
from backend.app.domains.generation.validation_service import (
    ContentValidationService,
    StructuralValidator,
)


class TestContentWithMarkupIsRejected:
    def test_html_tags_rejected(self, structural_validator: StructuralValidator):
        content_with_html = "This is content <strong>with bold</strong> tags."
        result = structural_validator.validate(content_with_html)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_TAGS in result.error_codes
        assert len(result.detected_tags) > 0

    def test_html_div_rejected(self, structural_validator: StructuralValidator):
        content_with_div = "<div>Some content</div>"
        result = structural_validator.validate(content_with_div)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_TAGS in result.error_codes

    def test_html_paragraph_rejected(self, structural_validator: StructuralValidator):
        content = "<p>Paragraph content</p>"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_TAGS in result.error_codes

    def test_self_closing_tags_rejected(self, structural_validator: StructuralValidator):
        content = "Line break here<br/>and more text"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_TAGS in result.error_codes

    def test_markdown_links_rejected(self, structural_validator: StructuralValidator):
        content = "Click [here](https://example.com) for more info."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_MARKUP in result.error_codes
        assert len(result.detected_markup) > 0

    def test_markdown_bold_rejected(self, structural_validator: StructuralValidator):
        content = "This has **bold text** inside."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_FORMATTING in result.error_codes

    def test_markdown_italic_rejected(self, structural_validator: StructuralValidator):
        content = "This has *italic text* inside."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_FORMATTING in result.error_codes

    def test_code_blocks_rejected(self, structural_validator: StructuralValidator):
        content = "Here is code:\n```python\nprint('hello')\n```"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_MARKUP in result.error_codes

    def test_inline_code_rejected(self, structural_validator: StructuralValidator):
        content = "Use the `print()` function."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_MARKUP in result.error_codes


class TestStructuralChangesRejected:
    def test_markdown_h1_header_rejected(self, structural_validator: StructuralValidator):
        content = "# Main Heading\nSome content below."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_HEADERS in result.error_codes
        assert len(result.detected_headers) > 0

    def test_markdown_h2_header_rejected(self, structural_validator: StructuralValidator):
        content = "## Section Title\nContent here."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_HEADERS in result.error_codes

    def test_markdown_h3_header_rejected(self, structural_validator: StructuralValidator):
        content = "### Subsection\nMore content."
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_HEADERS in result.error_codes

    def test_horizontal_rule_rejected(self, structural_validator: StructuralValidator):
        content = "Above the line\n---\nBelow the line"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.STRUCTURAL_MODIFICATION in result.error_codes

    def test_horizontal_rule_asterisks_rejected(self, structural_validator: StructuralValidator):
        content = "Above\n***\nBelow"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.STRUCTURAL_MODIFICATION in result.error_codes

    def test_table_structure_rejected(self, structural_validator: StructuralValidator):
        content = "| Column 1 | Column 2 |\n|----------|----------|\n| Data 1   | Data 2   |"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.STRUCTURAL_MODIFICATION in result.error_codes

    def test_numbered_list_rejected(self, structural_validator: StructuralValidator):
        content = "1. First item\n2. Second item"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_HEADERS in result.error_codes

    def test_lettered_list_rejected(self, structural_validator: StructuralValidator):
        content = "a. First item\nb. Second item"
        result = structural_validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.CONTAINS_HEADERS in result.error_codes


class TestPlainTextPasses:
    def test_simple_plain_text_passes(self, structural_validator: StructuralValidator):
        content = "This is simple plain text content without any markup or formatting."
        result = structural_validator.validate(content)
        assert result.is_valid
        assert result.is_plain_text
        assert len(result.error_codes) == 0

    def test_multiline_plain_text_passes(self, structural_validator: StructuralValidator):
        content = """This is the first paragraph of content.

This is the second paragraph, separated by a blank line.

And here is a third paragraph with more information."""
        result = structural_validator.validate(content)
        assert result.is_valid
        assert result.is_plain_text

    def test_plain_text_with_punctuation_passes(self, structural_validator: StructuralValidator):
        content = "Hello! How are you? I'm fine, thanks. Let's meet at 3:00 PM."
        result = structural_validator.validate(content)
        assert result.is_valid

    def test_plain_text_with_numbers_passes(self, structural_validator: StructuralValidator):
        content = "The project costs $1,500 and will take 3 weeks to complete."
        result = structural_validator.validate(content)
        assert result.is_valid

    def test_plain_text_with_quotes_passes(self, structural_validator: StructuralValidator):
        content = "She said \"Hello\" and he replied 'Hi there'."
        result = structural_validator.validate(content)
        assert result.is_valid

    def test_plain_text_with_parentheses_passes(self, structural_validator: StructuralValidator):
        content = "The company (founded in 2010) has grown significantly."
        result = structural_validator.validate(content)
        assert result.is_valid

    def test_empty_content_passes_structural(self, structural_validator: StructuralValidator):
        result = structural_validator.validate("")
        assert result.is_valid
        assert result.is_plain_text


class TestComprehensiveValidation:
    def test_plain_text_passes_comprehensive(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "This is valid plain text content for the advisory document section."
        result = content_validation_service.validate(content)
        assert result.is_valid
        assert result.validated_content == content.strip()
        assert result.content_hash is not None
        assert result.structural_result.is_valid
        assert result.bounds_result.is_valid
        assert result.quality_result.is_valid

    def test_html_fails_comprehensive(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "<p>HTML content</p>"
        result = content_validation_service.validate(content)
        assert not result.is_valid
        assert result.failure_type == FailureType.STRUCTURAL_VIOLATION
        assert not result.is_retryable

    def test_markdown_header_fails_comprehensive(
        self,
        content_validation_service: ContentValidationService,
    ):
        content = "# Header\nSome content"
        result = content_validation_service.validate(content)
        assert not result.is_valid
        assert result.failure_type == FailureType.STRUCTURAL_VIOLATION
        assert not result.structural_result.is_valid


class TestCustomForbiddenPatterns:
    def test_custom_pattern_rejected(self):
        config = StructuralValidationConfig(
            custom_forbidden_patterns=[r"CONFIDENTIAL", r"TOP SECRET"],
        )
        validator = StructuralValidator(config)
        content = "This document is CONFIDENTIAL and should not be shared."
        result = validator.validate(content)
        assert not result.is_valid
        assert ValidationErrorCode.STRUCTURAL_MODIFICATION in result.error_codes

    def test_content_without_custom_pattern_passes(self):
        config = StructuralValidationConfig(
            custom_forbidden_patterns=[r"CONFIDENTIAL"],
        )
        validator = StructuralValidator(config)
        content = "This is a normal public document."
        result = validator.validate(content)
        assert result.is_valid
