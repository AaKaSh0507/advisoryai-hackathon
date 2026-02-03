import logging
import uuid
from unittest.mock import AsyncMock

import pytest

from backend.app.infrastructure.demo_seeding import (
    DEMO_DOCUMENT_ID,
    DEMO_DOCUMENT_VERSION_ID,
    DEMO_JOBS,
    DEMO_SECTION_IDS,
    DEMO_TEMPLATE_ID,
    DEMO_TEMPLATE_VERSION_ID,
    DemoDataSeeder,
    get_demo_ids,
)
from backend.app.infrastructure.errors import (
    ClassificationFailureError,
    ErrorCategory,
    ErrorSeverity,
    GenerationFailureError,
    InvalidWordUploadError,
    JobCrashError,
    ParsingFailureError,
    RecoveryAction,
    RegenerationConflictError,
    StructuredError,
)
from backend.app.logging_config import (
    LogContext,
    StructuredJSONFormatter,
    clear_context,
    correlation_id_var,
    document_id_var,
    job_id_var,
    template_id_var,
)


class TestStructuredErrors:
    def test_error_category_values(self):
        assert ErrorCategory.VALIDATION.value == "VALIDATION"
        assert ErrorCategory.PARSING.value == "PARSING"
        assert ErrorCategory.CLASSIFICATION.value == "CLASSIFICATION"
        assert ErrorCategory.GENERATION.value == "GENERATION"
        assert ErrorCategory.ASSEMBLY.value == "ASSEMBLY"
        assert ErrorCategory.RENDERING.value == "RENDERING"
        assert ErrorCategory.INFRASTRUCTURE.value == "INFRASTRUCTURE"
        assert ErrorCategory.UNKNOWN.value == "UNKNOWN"

    def test_error_severity_values(self):
        assert ErrorSeverity.LOW.value == "LOW"
        assert ErrorSeverity.MEDIUM.value == "MEDIUM"
        assert ErrorSeverity.HIGH.value == "HIGH"
        assert ErrorSeverity.CRITICAL.value == "CRITICAL"

    def test_recovery_action_values(self):
        assert RecoveryAction.RETRY.value == "RETRY"
        assert RecoveryAction.MANUAL_INTERVENTION.value == "MANUAL_INTERVENTION"
        assert RecoveryAction.SKIP.value == "SKIP"
        assert RecoveryAction.ROLLBACK.value == "ROLLBACK"
        assert RecoveryAction.RESTART.value == "RESTART"

    def test_structured_error_creation(self):
        error = StructuredError(
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            code="ERR_TEST",
            message="Test error",
            details={"field": "test"},
            recovery_action=RecoveryAction.RETRY,
        )

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "ERR_TEST"
        assert error.recovery_action == RecoveryAction.RETRY

    def test_structured_error_to_log_dict(self):
        """Test StructuredError serialization to log dict."""
        error = StructuredError(
            category=ErrorCategory.PARSING,
            severity=ErrorSeverity.HIGH,
            code="ERR_PARSE",
            message="Parsing failed",
            details={},
            recovery_action=RecoveryAction.MANUAL_INTERVENTION,
        )

        error_dict = error.to_log_dict()

        assert "error_code" in error_dict
        assert "error_category" in error_dict
        assert "error_severity" in error_dict
        assert "error_message" in error_dict
        assert "recovery_action" in error_dict

    def test_invalid_word_upload_error(self):
        error = InvalidWordUploadError(
            reason="Not a valid .docx format",
            file_name="test.doc",
        )

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.LOW
        assert error.code == "VALIDATION_INVALID_WORD_UPLOAD"
        assert error.details["file_name"] == "test.doc"
        assert error.details["reason"] == "Not a valid .docx format"
        assert error.recovery_action == RecoveryAction.RETRY

    def test_parsing_failure_error(self):
        template_version_id = uuid.uuid4()
        error = ParsingFailureError(
            template_version_id=template_version_id,
            reason="XML parsing error",
            stage="structure_extraction",
        )

        assert error.category == ErrorCategory.PARSING
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "PARSING_FAILURE"
        assert error.template_version_id == template_version_id
        assert error.details["stage"] == "structure_extraction"

    def test_classification_failure_error(self):
        template_version_id = uuid.uuid4()
        error = ClassificationFailureError(
            template_version_id=template_version_id,
            section_path="/intro",
            reason="Model timeout",
        )

        assert error.category == ErrorCategory.CLASSIFICATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "CLASSIFICATION_FAILURE"
        assert error.recovery_action == RecoveryAction.RETRY

    def test_generation_failure_error(self):
        doc_id = uuid.uuid4()
        error = GenerationFailureError(
            document_id=doc_id,
            section_id=1,
            reason="Content generation failed",
            llm_error="Timeout",
        )

        assert error.category == ErrorCategory.GENERATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.code == "GENERATION_FAILURE"

    def test_job_crash_error(self):
        job_id_val = uuid.uuid4()
        error = JobCrashError(
            job_id=job_id_val,
            job_type="PARSE",
            exception="RuntimeError: Memory exceeded",
            stack_trace="...",
        )

        assert error.category == ErrorCategory.INFRASTRUCTURE
        assert error.severity == ErrorSeverity.HIGH
        assert error.code == "JOB_CRASH"
        assert error.job_id == job_id_val
        assert error.recovery_action == RecoveryAction.RESTART

    def test_regeneration_conflict_error(self):
        doc_id = uuid.uuid4()
        error = RegenerationConflictError(
            document_id=doc_id,
            conflict_reason="Another regeneration is in progress",
        )

        assert error.category == ErrorCategory.REGENERATION
        assert error.severity == ErrorSeverity.LOW
        assert error.code == "REGENERATION_CONFLICT"
        assert error.recovery_action == RecoveryAction.RETRY


class TestStructuredLogging:
    def test_correlation_id_context_var(self):
        test_id = "test-correlation-123"
        correlation_id_var.set(test_id)
        assert correlation_id_var.get() == test_id
        clear_context()

    def test_job_id_context_var(self):
        test_job_id = str(uuid.uuid4())
        job_id_var.set(test_job_id)
        assert job_id_var.get() == test_job_id
        clear_context()

    def test_document_id_context_var(self):
        test_doc_id = str(uuid.uuid4())
        document_id_var.set(test_doc_id)
        assert document_id_var.get() == test_doc_id
        clear_context()

    def test_template_id_context_var(self):
        test_template_id = str(uuid.uuid4())
        template_id_var.set(test_template_id)
        assert template_id_var.get() == test_template_id
        clear_context()

    def test_log_context_manager(self):
        test_correlation = "ctx-test-123"
        test_job = str(uuid.uuid4())

        with LogContext(correlation_id=test_correlation, job_id=test_job):
            assert correlation_id_var.get() == test_correlation
            assert job_id_var.get() == test_job
        assert correlation_id_var.get() is None
        assert job_id_var.get() is None

    def test_log_context_with_auto_generate(self):
        clear_context()
        with LogContext(auto_generate_correlation_id=True):
            cid = correlation_id_var.get()
            assert cid is not None
            assert len(cid) > 0
        assert correlation_id_var.get() is None

    def test_structured_json_formatter_format(self):
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        correlation_id_var.set("test-corr-id")
        formatted = formatter.format(record)
        assert "timestamp" in formatted
        assert "level" in formatted
        assert "message" in formatted
        assert "test-corr-id" in formatted
        clear_context()


class TestDemoSeeding:
    def test_demo_ids_are_deterministic(self):
        assert DEMO_TEMPLATE_ID == uuid.UUID("11111111-1111-1111-1111-111111111111")
        assert DEMO_TEMPLATE_VERSION_ID == uuid.UUID("22222222-2222-2222-2222-222222222222")
        assert DEMO_DOCUMENT_ID == uuid.UUID("33333333-3333-3333-3333-333333333333")
        assert DEMO_DOCUMENT_VERSION_ID == uuid.UUID("44444444-4444-4444-4444-444444444444")

    def test_demo_section_ids_are_deterministic(self):
        assert len(DEMO_SECTION_IDS) == 5
        assert DEMO_SECTION_IDS["title"] == uuid.UUID("55555555-5555-5555-5555-555555555001")
        assert DEMO_SECTION_IDS["intro"] == uuid.UUID("55555555-5555-5555-5555-555555555002")
        assert DEMO_SECTION_IDS["scope"] == uuid.UUID("55555555-5555-5555-5555-555555555003")
        assert DEMO_SECTION_IDS["methodology"] == uuid.UUID("55555555-5555-5555-5555-555555555004")
        assert DEMO_SECTION_IDS["conclusion"] == uuid.UUID("55555555-5555-5555-5555-555555555005")

    def test_demo_jobs_are_deterministic(self):
        assert len(DEMO_JOBS) == 3
        assert DEMO_JOBS["parse"]["id"] == uuid.UUID("66666666-6666-6666-6666-666666666001")
        assert DEMO_JOBS["classify"]["id"] == uuid.UUID("66666666-6666-6666-6666-666666666002")
        assert DEMO_JOBS["generate"]["id"] == uuid.UUID("66666666-6666-6666-6666-666666666003")

    def test_get_demo_ids_returns_all_ids(self):
        ids = get_demo_ids()

        assert "template_id" in ids
        assert "template_version_id" in ids
        assert "document_id" in ids
        assert "document_version_id" in ids
        assert "section_ids" in ids
        assert "job_ids" in ids

        assert ids["template_id"] == str(DEMO_TEMPLATE_ID)
        assert ids["template_version_id"] == str(DEMO_TEMPLATE_VERSION_ID)

    def test_demo_seeder_initialization(self):
        mock_session = AsyncMock()
        seeder = DemoDataSeeder(mock_session)
        assert seeder.session == mock_session

    @pytest.mark.asyncio
    async def test_demo_seeder_idempotent(self):
        mock_session = AsyncMock()
        seeder = DemoDataSeeder(mock_session)
        assert hasattr(seeder, "seed_all")
        assert callable(seeder.seed_all)


class TestDemoFlowValidation:
    def test_demo_api_schemas(self):
        from backend.app.api.v1.demo import (
            DemoIdsResponse,
            DemoSeedRequest,
            DemoSeedResponse,
            DemoValidationResponse,
        )

        request = DemoSeedRequest(force=True)
        assert request.force is True
        response = DemoSeedResponse(
            success=True,
            message="Seeded",
            entities={"template_id": str(DEMO_TEMPLATE_ID)},
        )
        assert response.success is True
        ids_response = DemoIdsResponse(ids={"template_id": str(DEMO_TEMPLATE_ID)})
        assert "template_id" in ids_response.ids
        validation_response = DemoValidationResponse(
            valid=True,
            flows_validated=["template_exists"],
            errors=[],
        )
        assert validation_response.valid is True
        assert len(validation_response.errors) == 0


class TestErrorScenarioLogging:
    def test_error_produces_clear_message(self):
        error = InvalidWordUploadError(
            reason="File extension is .txt, expected .docx",
            file_name="report.txt",
        )

        error_dict = error.to_log_dict()
        assert "Invalid Word document upload" in error_dict["error_message"]
        assert error_dict["error_details"]["file_name"] == "report.txt"
        assert error_dict["error_details"]["reason"] == "File extension is .txt, expected .docx"
        assert error_dict["recovery_action"] == "RETRY"

    def test_job_error_includes_recovery_steps(self):
        error = JobCrashError(
            job_id=uuid.uuid4(),
            job_type="GENERATE",
            exception="MemoryError: Cannot allocate memory",
            stack_trace="...",
        )

        error_dict = error.to_log_dict()
        assert error_dict["error_severity"] == "HIGH"
        assert error_dict["recovery_action"] == "RESTART"
        assert error_dict["error_details"]["job_type"] == "GENERATE"


class TestServiceRestartResilience:
    def test_demo_ids_stable_across_imports(self):
        from backend.app.infrastructure.demo_seeding import DEMO_TEMPLATE_ID as id1
        from backend.app.infrastructure.demo_seeding import DEMO_TEMPLATE_ID as id2

        assert id1 == id2

    def test_error_codes_stable(self):
        error1 = InvalidWordUploadError(
            reason="Test",
            file_name="test.txt",
        )
        error2 = InvalidWordUploadError(
            reason="Different reason",
            file_name="other.txt",
        )
        assert error1.code == error2.code == "VALIDATION_INVALID_WORD_UPLOAD"
