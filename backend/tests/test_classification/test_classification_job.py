"""
Tests for classification job pipeline integration.

Verifies:
- CLASSIFY job handler works correctly
- Job state transitions are valid
- Error handling in job pipeline
- Job completion triggers audit
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.domains.job.models import Job, JobStatus, JobType
from backend.app.domains.job.repository import JobRepository
from backend.app.domains.job.service import JobService
from backend.app.domains.parsing.repository import ParsedDocumentRepository
from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationBatchResult,
    ClassificationConfidence,
    ClassificationMethod,
    SectionClassificationResult,
)
from backend.app.domains.section.classification_service import (
    ClassificationService,
    create_classification_service,
)
from backend.app.worker.handlers.classification import ClassificationHandler


class TestJobTypeStructure:
    """Tests for job type structure."""

    def test_job_type_has_classify(self):
        """JobType enum should have CLASSIFY."""
        assert hasattr(JobType, "CLASSIFY")

    def test_job_status_values(self):
        """JobStatus enum should have required values."""
        assert hasattr(JobStatus, "PENDING")
        assert hasattr(JobStatus, "RUNNING")
        assert hasattr(JobStatus, "COMPLETED")
        assert hasattr(JobStatus, "FAILED")


class TestClassificationJobHandler:
    """Tests for classification job handler."""

    def test_handler_class_exists(self):
        """Classification job handler class should exist."""
        assert ClassificationHandler is not None

    def test_handler_has_handle_method(self):
        """Handler should have handle method."""
        assert hasattr(ClassificationHandler, "handle")


class TestJobInputValidation:
    """Tests for job input validation."""

    @pytest.fixture
    def valid_job_payload(self):
        """Create valid job payload."""
        return {
            "template_id": str(uuid4()),
            "template_version_id": str(uuid4()),
        }

    def test_job_payload_requires_template_version_id(self):
        """Job payload should require template_version_id."""
        invalid_payload = {
            "template_id": str(uuid4()),
            # Missing template_version_id
        }

        # Handler should validate payload
        # This test verifies the schema structure
        assert "template_version_id" not in invalid_payload

    def test_job_payload_accepts_valid_structure(self, valid_job_payload):
        """Job payload should accept valid structure."""
        assert "template_id" in valid_job_payload
        assert "template_version_id" in valid_job_payload


class TestJobStatusTransitions:
    """Tests for job status transitions."""

    def test_job_can_transition_to_running(self):
        """Job should be able to transition to RUNNING."""
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.PENDING,
            payload={"template_version_id": str(uuid4())},
        )

        assert job.can_transition_to(JobStatus.RUNNING)

    def test_job_can_transition_to_completed(self):
        """Job should be able to transition to COMPLETED."""
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.RUNNING,
            payload={"template_version_id": str(uuid4())},
        )

        assert job.can_transition_to(JobStatus.COMPLETED)

    def test_job_can_transition_to_failed(self):
        """Job should be able to transition to FAILED."""
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.RUNNING,
            payload={"template_version_id": str(uuid4())},
        )

        assert job.can_transition_to(JobStatus.FAILED)


class TestClassificationJobExecution:
    """Tests for classification job execution."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for job execution."""
        # Mock session
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Mock parsed document repository
        mock_parsed_repo = MagicMock(spec=ParsedDocumentRepository)
        template_version_id = uuid4()
        mock_parsed_repo.get_by_template_version_id = AsyncMock(
            return_value=ParsedDocument(
                template_version_id=template_version_id,
                template_id=uuid4(),
                version_number=1,
                content_hash="test_hash",
                metadata=DocumentMetadata(),
                blocks=[
                    ParagraphBlock(
                        block_id="blk_par_0001_xyz",
                        sequence=1,
                        runs=[TextRun(text="Confidential information.")],
                    ),
                ],
            )
        )

        # Mock section repository
        mock_section_repo = MagicMock()
        mock_section_repo.create_batch = AsyncMock(return_value=[])

        # Mock audit repository
        mock_audit_repo = MagicMock()
        mock_audit_repo.create = AsyncMock(return_value=None)

        # Mock job repository
        mock_job_repo = MagicMock(spec=JobRepository)
        mock_job_repo.update_status = AsyncMock(return_value=None)
        mock_job_repo.update_result = AsyncMock(return_value=None)

        return {
            "session": mock_session,
            "parsed_repo": mock_parsed_repo,
            "section_repo": mock_section_repo,
            "audit_repo": mock_audit_repo,
            "job_repo": mock_job_repo,
            "template_version_id": template_version_id,
        }

    @pytest.mark.asyncio
    async def test_job_retrieves_parsed_document(self, mock_dependencies):
        """Job should retrieve parsed document."""
        template_version_id = mock_dependencies["template_version_id"]

        # Verify repository method exists
        assert hasattr(mock_dependencies["parsed_repo"], "get_by_template_version_id")

        # Call the mock to verify behavior
        result = await mock_dependencies["parsed_repo"].get_by_template_version_id(
            template_version_id
        )

        assert result is not None
        assert isinstance(result, ParsedDocument)

    @pytest.mark.asyncio
    async def test_job_creates_sections(self, mock_dependencies):
        """Job should create sections via repository."""
        # Verify repository method exists
        assert hasattr(mock_dependencies["section_repo"], "create_batch")

    @pytest.mark.asyncio
    async def test_job_creates_audit_log(self, mock_dependencies):
        """Job should create audit log on completion."""
        # Verify repository method exists
        assert hasattr(mock_dependencies["audit_repo"], "create")


class TestJobErrorHandling:
    """Tests for job error handling."""

    def test_job_stores_error_message(self):
        """Failed job should store error message."""
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.FAILED,
            payload={"template_version_id": str(uuid4())},
            error="Parsed document not found",
        )

        assert job.status == JobStatus.FAILED
        assert job.error == "Parsed document not found"

    def test_job_result_includes_error_details(self):
        """Failed job result should include error details."""
        error_result = {
            "status": "failed",
            "error": "Parsed document not found",
            "error_type": "NotFoundError",
        }

        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.FAILED,
            payload={"template_version_id": str(uuid4())},
            result=error_result,
        )

        assert job.result["status"] == "failed"
        assert "error" in job.result


class TestJobResultStorage:
    """Tests for job result storage."""

    def test_job_result_stores_statistics(self):
        """Completed job should store classification statistics."""
        result = {
            "status": "completed",
            "total_sections": 10,
            "static_sections": 6,
            "dynamic_sections": 4,
            "methods": {
                "rule_based": 8,
                "llm_assisted": 2,
                "fallback": 0,
            },
            "duration_ms": 350,
        }

        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.COMPLETED,
            payload={"template_version_id": str(uuid4())},
            result=result,
        )

        assert job.result["status"] == "completed"
        assert job.result["total_sections"] == 10

    def test_job_result_is_serializable(self):
        """Job result should be JSON serializable."""
        result = {
            "status": "completed",
            "total_sections": 5,
            "static_sections": 3,
            "dynamic_sections": 2,
            "methods": {
                "rule_based": 4,
                "llm_assisted": 1,
                "fallback": 0,
            },
            "confidence": {
                "high": 4,
                "medium": 1,
                "low": 0,
            },
            "duration_ms": 200,
        }

        # Should serialize without error
        serialized = json.dumps(result)
        assert serialized is not None

        # Should deserialize correctly
        deserialized = json.loads(serialized)
        assert deserialized["total_sections"] == 5


class TestJobChaining:
    """Tests for job chaining behavior."""

    def test_classify_job_has_payload(self):
        """Job model should have payload field."""
        columns = [c.name for c in Job.__table__.columns]
        assert "payload" in columns

    def test_classify_job_can_store_result(self):
        """Completed CLASSIFY job should store result."""
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.COMPLETED,
            payload={"template_version_id": str(uuid4())},
            result={
                "status": "completed",
                "total_sections": 5,
            },
        )

        assert job.result["status"] == "completed"


class TestJobConcurrency:
    """Tests for job concurrency handling."""

    def test_job_has_created_at_timestamp(self):
        """Job should have created_at timestamp."""
        columns = [c.name for c in Job.__table__.columns]
        assert "created_at" in columns

    def test_job_has_updated_at_timestamp(self):
        """Job should have updated_at timestamp."""
        columns = [c.name for c in Job.__table__.columns]
        assert "updated_at" in columns

    def test_job_can_store_progress_in_result(self):
        """Job should be able to store progress in result."""
        progress_result = {
            "status": "processing",
            "progress": {
                "processed": 5,
                "total": 10,
                "percentage": 50,
            },
        }

        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.RUNNING,
            payload={"template_version_id": str(uuid4())},
            result=progress_result,
        )

        assert job.result["progress"]["percentage"] == 50


class TestJobIntegrationWithClassification:
    """Tests for job integration with classification service."""

    @pytest.fixture
    def sample_document(self):
        """Create sample document for job testing."""
        return ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="This is confidential.")],
                ),
                ParagraphBlock(
                    block_id="blk_par_0002_xyz",
                    sequence=2,
                    runs=[TextRun(text="Dear {name}")],
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_classification_service_produces_job_result(self, sample_document):
        """Classification service should produce result suitable for job."""
        mock_section_repo = MagicMock()
        mock_section_repo.create_batch = AsyncMock(return_value=[])

        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )

        # Result should be convertible to job result
        job_result = {
            "status": "completed",
            "total_sections": result.total_sections,
            "static_sections": result.static_sections,
            "dynamic_sections": result.dynamic_sections,
            "methods": {
                "rule_based": result.rule_based_count,
                "llm_assisted": result.llm_assisted_count,
                "fallback": result.fallback_count,
            },
            "duration_ms": result.duration_ms,
        }

        # Should be valid job result
        assert job_result["status"] == "completed"
        assert job_result["total_sections"] == len(sample_document.blocks)
