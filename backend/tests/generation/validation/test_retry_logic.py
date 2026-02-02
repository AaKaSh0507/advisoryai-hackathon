from backend.app.domains.generation.validation_schemas import (
    FailureType,
    RetryEligibility,
    RetryPolicy,
)
from backend.app.domains.generation.validation_service import RetryManager


class TestEligibleFailuresTriggerRetries:
    def test_generation_failure_is_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.GENERATION_FAILURE,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.ELIGIBLE

    def test_generation_failure_retryable_at_attempt_1(self, retry_manager: RetryManager):
        result = retry_manager.is_retryable(FailureType.GENERATION_FAILURE, current_attempt=1)
        assert result is True

    def test_generation_failure_retryable_at_attempt_2(self, retry_manager: RetryManager):
        result = retry_manager.is_retryable(FailureType.GENERATION_FAILURE, current_attempt=2)
        assert result is True

    def test_bounds_violation_is_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.BOUNDS_VIOLATION,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.ELIGIBLE

    def test_bounds_violation_retryable_method(self, retry_manager: RetryManager):
        result = retry_manager.is_retryable(FailureType.BOUNDS_VIOLATION, current_attempt=1)
        assert result is True


class TestIneligibleFailuresDoNotRetry:
    def test_validation_failure_not_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.VALIDATION_FAILURE,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.NOT_ELIGIBLE

    def test_structural_violation_not_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.STRUCTURAL_VIOLATION,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.NOT_ELIGIBLE

    def test_quality_failure_not_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.QUALITY_FAILURE,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.NOT_ELIGIBLE

    def test_retry_exhaustion_not_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.RETRY_EXHAUSTION,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.NOT_ELIGIBLE

    def test_unexpected_error_not_retryable(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.UNEXPECTED_ERROR,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.NOT_ELIGIBLE

    def test_is_retryable_returns_false_for_validation(self, retry_manager: RetryManager):
        result = retry_manager.is_retryable(FailureType.VALIDATION_FAILURE, current_attempt=0)
        assert result is False


class TestRetryLimitsEnforced:
    def test_retry_exhausted_at_max_retries(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.GENERATION_FAILURE,
            current_attempt=3,
        )
        assert eligibility == RetryEligibility.EXHAUSTED

    def test_is_retryable_false_at_max_retries(self, retry_manager: RetryManager):
        result = retry_manager.is_retryable(FailureType.GENERATION_FAILURE, current_attempt=3)
        assert result is False

    def test_retry_exhausted_beyond_max(self, retry_manager: RetryManager):
        eligibility = retry_manager.determine_eligibility(
            FailureType.GENERATION_FAILURE,
            current_attempt=5,
        )
        assert eligibility == RetryEligibility.EXHAUSTED

    def test_custom_max_retries_enforced(self, strict_retry_policy: RetryPolicy):
        manager = RetryManager(strict_retry_policy)
        eligibility = manager.determine_eligibility(
            FailureType.GENERATION_FAILURE,
            current_attempt=2,
        )
        assert eligibility == RetryEligibility.EXHAUSTED

    def test_custom_max_retries_allows_before_limit(self, strict_retry_policy: RetryPolicy):
        manager = RetryManager(strict_retry_policy)
        eligibility = manager.determine_eligibility(
            FailureType.GENERATION_FAILURE,
            current_attempt=1,
        )
        assert eligibility == RetryEligibility.ELIGIBLE


class TestRetryDelayComputation:
    def test_delay_exponential_backoff(self, retry_manager: RetryManager):
        delay_0 = retry_manager.compute_deterministic_retry_delay(0)
        delay_1 = retry_manager.compute_deterministic_retry_delay(1)
        delay_2 = retry_manager.compute_deterministic_retry_delay(2)
        assert delay_0 == 1
        assert delay_1 == 2
        assert delay_2 == 4

    def test_delay_capped_at_16(self, retry_manager: RetryManager):
        delay_10 = retry_manager.compute_deterministic_retry_delay(10)
        assert delay_10 == 16


class TestFailureTypeForExhaustion:
    def test_exhaustion_failure_type(self, retry_manager: RetryManager):
        result = retry_manager.get_failure_type_for_exhaustion(FailureType.GENERATION_FAILURE)
        assert result == FailureType.RETRY_EXHAUSTION

    def test_exhaustion_from_bounds(self, retry_manager: RetryManager):
        result = retry_manager.get_failure_type_for_exhaustion(FailureType.BOUNDS_VIOLATION)
        assert result == FailureType.RETRY_EXHAUSTION


class TestCustomRetryPolicy:
    def test_custom_eligible_failure_types(self):
        policy = RetryPolicy(
            max_retries=5,
            eligible_failure_types=frozenset(
                {
                    FailureType.GENERATION_FAILURE,
                    FailureType.UNEXPECTED_ERROR,
                }
            ),
        )
        manager = RetryManager(policy)

        gen_result = manager.is_retryable(FailureType.GENERATION_FAILURE, current_attempt=0)
        assert gen_result is True

        bounds_result = manager.is_retryable(FailureType.BOUNDS_VIOLATION, current_attempt=0)
        assert bounds_result is False

    def test_zero_retries_policy(self):
        policy = RetryPolicy(max_retries=0)
        manager = RetryManager(policy)
        eligibility = manager.determine_eligibility(
            FailureType.GENERATION_FAILURE,
            current_attempt=0,
        )
        assert eligibility == RetryEligibility.EXHAUSTED
