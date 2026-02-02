import hashlib
import re
from collections import Counter
from typing import Any

from backend.app.domains.generation.validation_schemas import (
    BoundsValidationResult,
    ComprehensiveValidationResult,
    FailureType,
    QualityCheckConfig,
    QualityCheckResult,
    RetryEligibility,
    RetryPolicy,
    StructuralValidationConfig,
    StructuralValidationResult,
    ValidationErrorCode,
)


class StructuralValidator:
    DEFAULT_HTML_PATTERN = re.compile(r"<[a-zA-Z][^>]*>|</[a-zA-Z]+>", re.IGNORECASE)
    DEFAULT_HEADER_PATTERN = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)
    DEFAULT_BOLD_ITALIC_PATTERN = re.compile(r"\*{1,3}[^*]+\*{1,3}|_{1,3}[^_]+_{1,3}")
    DEFAULT_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    DEFAULT_CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```|`[^`]+`")
    DEFAULT_HR_PATTERN = re.compile(r"^[-*_]{3,}$", re.MULTILINE)
    DEFAULT_TABLE_PATTERN = re.compile(r"^\|.*\|$", re.MULTILINE)
    DEFAULT_NUMBERING_PATTERN = re.compile(
        r"^(?:\d+\.|\d+\)|\(\d+\)|[a-zA-Z]\.|\([a-zA-Z]\))\s+",
        re.MULTILINE,
    )

    def __init__(self, config: StructuralValidationConfig | None = None):
        self.config = config or StructuralValidationConfig()
        self._custom_patterns = [
            re.compile(p, re.MULTILINE | re.IGNORECASE)
            for p in self.config.custom_forbidden_patterns
        ]

    def validate(self, content: str) -> StructuralValidationResult:
        if not content:
            return StructuralValidationResult(
                is_valid=True,
                is_plain_text=True,
            )

        detected_markup: list[str] = []
        detected_tags: list[str] = []
        detected_headers: list[str] = []
        detected_formatting: list[str] = []
        error_codes: list[ValidationErrorCode] = []

        if self.config.reject_html_tags:
            html_matches = self.DEFAULT_HTML_PATTERN.findall(content)
            if html_matches:
                detected_tags.extend(html_matches[:5])
                error_codes.append(ValidationErrorCode.CONTAINS_TAGS)

        if self.config.reject_markdown_headers:
            header_matches = self.DEFAULT_HEADER_PATTERN.findall(content)
            if header_matches:
                detected_headers.extend(header_matches[:5])
                error_codes.append(ValidationErrorCode.CONTAINS_HEADERS)

        if self.config.reject_markdown_formatting:
            format_matches = self.DEFAULT_BOLD_ITALIC_PATTERN.findall(content)
            if format_matches:
                detected_formatting.extend(format_matches[:5])
                error_codes.append(ValidationErrorCode.CONTAINS_FORMATTING)

        if self.config.reject_markdown_links:
            link_matches = self.DEFAULT_LINK_PATTERN.findall(content)
            if link_matches:
                detected_markup.extend([f"[{m[0]}]({m[1]})" for m in link_matches[:3]])
                error_codes.append(ValidationErrorCode.CONTAINS_MARKUP)

        if self.config.reject_code_blocks:
            code_matches = self.DEFAULT_CODE_BLOCK_PATTERN.findall(content)
            if code_matches:
                detected_markup.extend(["code_block" for _ in code_matches[:3]])
                error_codes.append(ValidationErrorCode.CONTAINS_MARKUP)

        if self.config.reject_horizontal_rules:
            if self.DEFAULT_HR_PATTERN.search(content):
                detected_markup.append("horizontal_rule")
                error_codes.append(ValidationErrorCode.STRUCTURAL_MODIFICATION)

        if self.config.reject_tables:
            table_matches = self.DEFAULT_TABLE_PATTERN.findall(content)
            if table_matches:
                detected_markup.extend(["table_row" for _ in table_matches[:3]])
                error_codes.append(ValidationErrorCode.STRUCTURAL_MODIFICATION)

        if self.config.reject_section_numbering:
            numbering_matches = self.DEFAULT_NUMBERING_PATTERN.findall(content)
            if numbering_matches:
                detected_headers.extend(numbering_matches[:5])
                error_codes.append(ValidationErrorCode.CONTAINS_HEADERS)

        for pattern in self._custom_patterns:
            if pattern.search(content):
                detected_markup.append(f"custom_pattern:{pattern.pattern}")
                error_codes.append(ValidationErrorCode.STRUCTURAL_MODIFICATION)

        is_valid = len(error_codes) == 0
        error_message = None
        if not is_valid:
            violations = []
            if detected_tags:
                violations.append(f"HTML tags detected: {detected_tags[:3]}")
            if detected_headers:
                violations.append(f"Headers/numbering detected: {detected_headers[:3]}")
            if detected_formatting:
                violations.append(f"Formatting detected: {detected_formatting[:3]}")
            if detected_markup:
                violations.append(f"Structural markup detected: {detected_markup[:3]}")
            error_message = "; ".join(violations)

        return StructuralValidationResult(
            is_valid=is_valid,
            is_plain_text=is_valid,
            detected_markup=detected_markup,
            detected_tags=detected_tags,
            detected_headers=detected_headers,
            detected_formatting=detected_formatting,
            error_codes=list(set(error_codes)),
            error_message=error_message,
        )


class BoundsValidator:
    def __init__(self, min_length: int = 1, max_length: int = 50000, min_meaningful: int = 10):
        self.min_length = min_length
        self.max_length = max_length
        self.min_meaningful = min_meaningful

    def validate(self, content: str) -> BoundsValidationResult:
        error_codes: list[ValidationErrorCode] = []
        stripped = content.strip() if content else ""
        content_length = len(stripped)

        is_empty = content_length == 0
        is_near_empty = 0 < content_length < self.min_meaningful
        is_too_short = content_length < self.min_length and not is_empty
        is_too_long = content_length > self.max_length

        if is_empty:
            error_codes.append(ValidationErrorCode.EMPTY_CONTENT)
        elif is_near_empty:
            error_codes.append(ValidationErrorCode.NEAR_EMPTY_CONTENT)

        if is_too_short and not is_empty:
            error_codes.append(ValidationErrorCode.CONTENT_TOO_SHORT)

        if is_too_long:
            error_codes.append(ValidationErrorCode.CONTENT_TOO_LONG)

        is_valid = len(error_codes) == 0
        error_message = None
        if not is_valid:
            msgs = []
            if is_empty:
                msgs.append("Content is empty")
            elif is_near_empty:
                msgs.append(f"Content is near-empty ({content_length} chars)")
            if is_too_short and not is_empty:
                msgs.append(f"Content too short: {content_length} < {self.min_length}")
            if is_too_long:
                msgs.append(f"Content too long: {content_length} > {self.max_length}")
            error_message = "; ".join(msgs)

        return BoundsValidationResult(
            is_valid=is_valid,
            content_length=content_length,
            min_length=self.min_length,
            max_length=self.max_length,
            is_empty=is_empty,
            is_near_empty=is_near_empty,
            is_too_long=is_too_long,
            is_too_short=is_too_short,
            error_codes=error_codes,
            error_message=error_message,
        )


class QualityValidator:
    def __init__(self, config: QualityCheckConfig | None = None):
        self.config = config or QualityCheckConfig()
        self._boilerplate_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.config.boilerplate_patterns
        ]

    def validate(self, content: str) -> QualityCheckResult:
        if not content or not content.strip():
            return QualityCheckResult(
                is_valid=False,
                error_codes=[ValidationErrorCode.EMPTY_CONTENT],
                error_message="Cannot validate quality of empty content",
            )

        error_codes: list[ValidationErrorCode] = []
        words = re.findall(r"\b\w+\b", content.lower())
        total_word_count = len(words)
        unique_words = set(words)
        unique_word_count = len(unique_words)

        word_counts = Counter(words)
        if total_word_count > 0:
            most_common_count = word_counts.most_common(1)[0][1] if word_counts else 0
            repetition_ratio = most_common_count / total_word_count
        else:
            repetition_ratio = 0.0

        is_repetitive = (
            total_word_count >= 10 and repetition_ratio > self.config.max_repetition_ratio
        )
        has_few_unique = unique_word_count < self.config.min_unique_words

        detected_boilerplate: list[str] = []
        content_stripped = content.strip()
        for pattern in self._boilerplate_patterns:
            if pattern.search(content_stripped):
                detected_boilerplate.append(pattern.pattern)

        is_boilerplate = len(detected_boilerplate) > 0

        if is_repetitive:
            error_codes.append(ValidationErrorCode.REPETITIVE_CONTENT)
        if is_boilerplate:
            error_codes.append(ValidationErrorCode.BOILERPLATE_ONLY)
        if has_few_unique and total_word_count >= 5:
            error_codes.append(ValidationErrorCode.NEAR_EMPTY_CONTENT)

        is_valid = len(error_codes) == 0
        error_message = None
        if not is_valid:
            msgs = []
            if is_repetitive:
                msgs.append(f"Content is repetitive (ratio: {repetition_ratio:.2f})")
            if is_boilerplate:
                msgs.append(f"Boilerplate detected: {detected_boilerplate[:2]}")
            if has_few_unique and total_word_count >= 5:
                msgs.append(f"Too few unique words: {unique_word_count}")
            error_message = "; ".join(msgs)

        return QualityCheckResult(
            is_valid=is_valid,
            unique_word_count=unique_word_count,
            total_word_count=total_word_count,
            repetition_ratio=repetition_ratio,
            is_repetitive=is_repetitive,
            is_boilerplate=is_boilerplate,
            detected_boilerplate_patterns=detected_boilerplate,
            error_codes=error_codes,
            error_message=error_message,
        )


class ContentValidationService:
    def __init__(
        self,
        min_length: int = 1,
        max_length: int = 50000,
        structural_config: StructuralValidationConfig | None = None,
        quality_config: QualityCheckConfig | None = None,
    ):
        self.structural_validator = StructuralValidator(structural_config)
        self.bounds_validator = BoundsValidator(
            min_length=min_length,
            max_length=max_length,
            min_meaningful=quality_config.min_meaningful_length if quality_config else 10,
        )
        self.quality_validator = QualityValidator(quality_config)

    def validate(self, content: str) -> ComprehensiveValidationResult:
        bounds_result = self.bounds_validator.validate(content)
        if bounds_result.is_empty:
            return ComprehensiveValidationResult(
                is_valid=False,
                structural_result=StructuralValidationResult(is_valid=True),
                bounds_result=bounds_result,
                quality_result=QualityCheckResult(
                    is_valid=False,
                    error_codes=[ValidationErrorCode.EMPTY_CONTENT],
                ),
                failure_type=FailureType.BOUNDS_VIOLATION,
                all_error_codes=[ValidationErrorCode.EMPTY_CONTENT],
                all_violations=["Content is empty"],
                rejection_reason="Content is empty",
                is_retryable=True,
            )

        structural_result = self.structural_validator.validate(content)
        quality_result = self.quality_validator.validate(content)

        all_error_codes: list[ValidationErrorCode] = []
        all_violations: list[str] = []

        all_error_codes.extend(bounds_result.error_codes)
        all_error_codes.extend(structural_result.error_codes)
        all_error_codes.extend(quality_result.error_codes)

        if bounds_result.error_message:
            all_violations.append(bounds_result.error_message)
        if structural_result.error_message:
            all_violations.append(structural_result.error_message)
        if quality_result.error_message:
            all_violations.append(quality_result.error_message)

        is_valid = bounds_result.is_valid and structural_result.is_valid and quality_result.is_valid

        failure_type = None
        is_retryable = False

        if not is_valid:
            if not structural_result.is_valid:
                failure_type = FailureType.STRUCTURAL_VIOLATION
                is_retryable = False
            elif not bounds_result.is_valid:
                failure_type = FailureType.BOUNDS_VIOLATION
                is_retryable = True
            elif not quality_result.is_valid:
                failure_type = FailureType.QUALITY_FAILURE
                is_retryable = False

        validated_content = None
        content_hash = None
        if is_valid:
            validated_content = content.strip()
            content_hash = hashlib.sha256(validated_content.encode("utf-8")).hexdigest()

        return ComprehensiveValidationResult(
            is_valid=is_valid,
            validated_content=validated_content,
            content_hash=content_hash,
            structural_result=structural_result,
            bounds_result=bounds_result,
            quality_result=quality_result,
            failure_type=failure_type,
            all_error_codes=list(set(all_error_codes)),
            all_violations=all_violations,
            rejection_reason="; ".join(all_violations) if all_violations else None,
            is_retryable=is_retryable,
            validation_metadata={
                "content_length": len(content.strip()) if content else 0,
                "structural_checks": structural_result.is_valid,
                "bounds_checks": bounds_result.is_valid,
                "quality_checks": quality_result.is_valid,
            },
        )


class RetryManager:
    def __init__(self, policy: RetryPolicy | None = None):
        self.policy = policy or RetryPolicy()

    def determine_eligibility(
        self,
        failure_type: FailureType,
        current_attempt: int,
    ) -> RetryEligibility:
        if current_attempt >= self.policy.max_retries:
            return RetryEligibility.EXHAUSTED

        if failure_type in self.policy.ineligible_failure_types:
            return RetryEligibility.NOT_ELIGIBLE

        if failure_type in self.policy.eligible_failure_types:
            return RetryEligibility.ELIGIBLE

        return RetryEligibility.NOT_ELIGIBLE

    def is_retryable(self, failure_type: FailureType, current_attempt: int) -> bool:
        eligibility = self.determine_eligibility(failure_type, current_attempt)
        return bool(eligibility == RetryEligibility.ELIGIBLE)

    def get_failure_type_for_exhaustion(
        self,
        original_failure_type: FailureType,
    ) -> FailureType:
        return FailureType.RETRY_EXHAUSTION

    def compute_deterministic_retry_delay(self, attempt: int) -> int:
        return int(min(2**attempt, 16))


class GenerationValidationService:
    def __init__(
        self,
        min_length: int = 1,
        max_length: int = 50000,
        structural_config: StructuralValidationConfig | None = None,
        quality_config: QualityCheckConfig | None = None,
        retry_policy: RetryPolicy | None = None,
    ):
        self.content_validator = ContentValidationService(
            min_length=min_length,
            max_length=max_length,
            structural_config=structural_config,
            quality_config=quality_config,
        )
        self.retry_manager = RetryManager(retry_policy)

    def validate_content(self, content: str) -> ComprehensiveValidationResult:
        return self.content_validator.validate(content)

    def is_retryable_failure(
        self,
        failure_type: FailureType,
        current_attempt: int,
    ) -> bool:
        return self.retry_manager.is_retryable(failure_type, current_attempt)

    def get_failure_classification(
        self,
        validation_result: ComprehensiveValidationResult | None,
        llm_failed: bool = False,
        unexpected_error: bool = False,
    ) -> FailureType:
        if unexpected_error:
            return FailureType.UNEXPECTED_ERROR
        if llm_failed:
            return FailureType.GENERATION_FAILURE
        if validation_result and validation_result.failure_type:
            return validation_result.failure_type
        return FailureType.VALIDATION_FAILURE

    def create_validation_metadata(
        self,
        validation_result: ComprehensiveValidationResult,
        attempt_number: int,
        input_hash: str,
        structural_path: str,
    ) -> dict[str, Any]:
        return {
            "input_hash": input_hash,
            "structural_path": structural_path,
            "attempt_number": attempt_number,
            "validation": {
                "is_valid": validation_result.is_valid,
                "error_codes": [c.value for c in validation_result.all_error_codes],
                "violations": validation_result.all_violations,
                "structural_valid": validation_result.structural_result.is_valid,
                "bounds_valid": validation_result.bounds_result.is_valid,
                "quality_valid": validation_result.quality_result.is_valid,
                "content_length": validation_result.bounds_result.content_length,
            },
        }
