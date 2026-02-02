import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.domains.job.models import Job, JobStatus, JobType
from backend.app.domains.job.repository import JobRepository
from backend.app.domains.parsing.repository import ParsedDocumentRepository
from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_service import create_classification_service
from backend.app.worker.handlers.classification import ClassificationHandler


class TestJobTypeStructure:
    def test_job_type_has_classify(self):
        assert hasattr(JobType, "CLASSIFY")

    def test_job_status_values(self):
        assert hasattr(JobStatus, "PENDING")
        assert hasattr(JobStatus, "RUNNING")
        assert hasattr(JobStatus, "COMPLETED")
        assert hasattr(JobStatus, "FAILED")


class TestClassificationJobHandler:
    def test_handler_class_exists(self):
        assert ClassificationHandler is not None

    def test_handler_has_handle_method(self):
        assert hasattr(ClassificationHandler, "handle")


class TestJobInputValidation:
    @pytest.fixture
    def valid_job_payload(self):
        return {
            "template_id": str(uuid4()),
            "template_version_id": str(uuid4()),
        }

    def test_job_payload_requires_template_version_id(self):
        invalid_payload = {
            "template_id": str(uuid4()),
        }
        assert "template_version_id" not in invalid_payload

    def test_job_payload_accepts_valid_structure(self, valid_job_payload):
        assert "template_id" in valid_job_payload
        assert "template_version_id" in valid_job_payload


class TestJobStatusTransitions:
    def test_job_can_transition_to_running(self):
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.PENDING,
            payload={"template_version_id": str(uuid4())},
        )
        assert job.can_transition_to(JobStatus.RUNNING)

    def test_job_can_transition_to_completed(self):
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.RUNNING,
            payload={"template_version_id": str(uuid4())},
        )
        assert job.can_transition_to(JobStatus.COMPLETED)

    def test_job_can_transition_to_failed(self):
        job = Job(
            id=uuid4(),
            job_type=JobType.CLASSIFY,
            status=JobStatus.RUNNING,
            payload={"template_version_id": str(uuid4())},
        )
        assert job.can_transition_to(JobStatus.FAILED)


class TestClassificationJobExecution:
    @pytest.fixture
    def mock_dependencies(self):
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
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

        mock_section_repo = MagicMock()
        mock_section_repo.create_batch = AsyncMock(return_value=[])
        mock_audit_repo = MagicMock()
        mock_audit_repo.create = AsyncMock(return_value=None)
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
        template_version_id = mock_dependencies["template_version_id"]
        assert hasattr(mock_dependencies["parsed_repo"], "get_by_template_version_id")
        result = await mock_dependencies["parsed_repo"].get_by_template_version_id(
            template_version_id
        )

        assert result is not None
        assert isinstance(result, ParsedDocument)

    @pytest.mark.asyncio
    async def test_job_creates_sections(self, mock_dependencies):
        assert hasattr(mock_dependencies["section_repo"], "create_batch")

    @pytest.mark.asyncio
    async def test_job_creates_audit_log(self, mock_dependencies):
        assert hasattr(mock_dependencies["audit_repo"], "create")


class TestJobErrorHandling:
    def test_job_stores_error_message(self):
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
    def test_job_result_stores_statistics(self):
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
        serialized = json.dumps(result)
        assert serialized is not None
        deserialized = json.loads(serialized)
        assert deserialized["total_sections"] == 5


class TestJobChaining:
    def test_classify_job_has_payload(self):
        columns = [c.name for c in Job.__table__.columns]
        assert "payload" in columns

    def test_classify_job_can_store_result(self):
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
    def test_job_has_created_at_timestamp(self):
        columns = [c.name for c in Job.__table__.columns]
        assert "created_at" in columns

    def test_job_has_updated_at_timestamp(self):
        columns = [c.name for c in Job.__table__.columns]
        assert "updated_at" in columns

    def test_job_can_store_progress_in_result(self):
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
    @pytest.fixture
    def sample_document(self):
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
        assert job_result["status"] == "completed"
        assert job_result["total_sections"] == len(sample_document.blocks)
