"""
Tests for Job System.

Verifies:
- Job lifecycle (creation, status transitions, completion)
- Job status state machine
- Job claiming for workers
- Job result storage
"""

from uuid import uuid4

import pytest


class TestJobLifecycle:
    """Tests for job lifecycle management."""

    @pytest.mark.asyncio
    async def test_job_created_with_pending_status(self, job_repository, template_repository):
        """Jobs should start with PENDING status."""
        from backend.app.domains.job.models import Job, JobStatus, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        # Create prerequisites
        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        # Create job
        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        created = await job_repository.create(job)

        assert created.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_job_transition_to_running(self, job_repository, template_repository):
        """Job should transition from PENDING to RUNNING when claimed."""
        from backend.app.domains.job.models import Job, JobStatus, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        await job_repository.create(job)

        # Claim the job
        claimed = await job_repository.claim_pending_job("worker-1")

        assert claimed is not None
        assert claimed.status == JobStatus.RUNNING
        assert claimed.worker_id == "worker-1"
        assert claimed.started_at is not None

    @pytest.mark.asyncio
    async def test_job_transition_to_completed(self, job_repository, template_repository):
        """Job should transition from RUNNING to COMPLETED."""
        from backend.app.domains.job.models import Job, JobStatus, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        await job_repository.create(job)

        # Claim and complete
        claimed = await job_repository.claim_pending_job("worker-1")
        completed = await job_repository.complete_job(claimed.id, result={"sections_parsed": 5})

        assert completed.status == JobStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.result == {"sections_parsed": 5}

    @pytest.mark.asyncio
    async def test_job_transition_to_failed(self, job_repository, template_repository):
        """Job should transition from RUNNING to FAILED with error message."""
        from backend.app.domains.job.models import Job, JobStatus, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        await job_repository.create(job)

        # Claim and fail
        claimed = await job_repository.claim_pending_job("worker-1")
        failed = await job_repository.fail_job(
            claimed.id, error="Document parsing failed: invalid format"
        )

        assert failed.status == JobStatus.FAILED
        assert failed.completed_at is not None
        assert failed.error == "Document parsing failed: invalid format"


class TestJobClaiming:
    """Tests for job claiming mechanism."""

    @pytest.mark.asyncio
    async def test_claim_returns_oldest_pending_job(self, job_repository, template_repository):
        """Should claim the oldest pending job first."""
        import asyncio

        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        # Create jobs with slight delay to ensure ordering
        job_ids = []
        for i in range(3):
            job = Job(
                job_type=JobType.PARSE, payload={"template_version_id": str(version.id), "order": i}
            )
            created = await job_repository.create(job)
            job_ids.append(created.id)
            await asyncio.sleep(0.01)

        # Claim should return the first job
        claimed = await job_repository.claim_pending_job("worker-1")

        assert claimed is not None
        assert claimed.id == job_ids[0]

    @pytest.mark.asyncio
    async def test_claim_returns_none_when_no_pending_jobs(self, job_repository):
        """Should return None when no pending jobs exist."""
        claimed = await job_repository.claim_pending_job("worker-1")

        assert claimed is None

    @pytest.mark.asyncio
    async def test_claimed_job_not_claimable_again(self, job_repository, template_repository):
        """A claimed job should not be claimable by another worker."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        # Create single job
        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        await job_repository.create(job)

        # First worker claims
        claimed1 = await job_repository.claim_pending_job("worker-1")
        assert claimed1 is not None

        # Second worker shouldn't be able to claim (no more pending)
        claimed2 = await job_repository.claim_pending_job("worker-2")
        assert claimed2 is None


class TestJobTypeHandling:
    """Tests for different job types."""

    @pytest.mark.asyncio
    async def test_parse_job_type(self, job_repository, template_repository):
        """Should handle PARSE job type."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        created = await job_repository.create(job)

        assert created.job_type == JobType.PARSE

    @pytest.mark.asyncio
    async def test_classify_job_type(self, job_repository, template_repository):
        """Should handle CLASSIFY job type."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(job_type=JobType.CLASSIFY, payload={"template_version_id": str(version.id)})
        created = await job_repository.create(job)

        assert created.job_type == JobType.CLASSIFY

    @pytest.mark.asyncio
    async def test_generate_job_type(self, job_repository, template_repository):
        """Should handle GENERATE job type."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(
            job_type=JobType.GENERATE,
            payload={"template_version_id": str(version.id), "document_id": str(uuid4())},
        )
        created = await job_repository.create(job)

        assert created.job_type == JobType.GENERATE


class TestJobFiltering:
    """Tests for job listing and filtering."""

    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, job_repository, template_repository):
        """Should filter jobs by status."""
        from backend.app.domains.job.models import Job, JobStatus, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        # Create jobs
        for _ in range(3):
            job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
            await job_repository.create(job)

        # Claim one job to make it RUNNING
        await job_repository.claim_pending_job("worker-1")

        # Filter by PENDING
        pending_jobs = await job_repository.list_all(status_filter=JobStatus.PENDING)
        assert len(pending_jobs) == 2

        # Filter by RUNNING
        running_jobs = await job_repository.list_all(status_filter=JobStatus.RUNNING)
        assert len(running_jobs) == 1

    @pytest.mark.asyncio
    async def test_list_jobs_by_type(self, job_repository, template_repository):
        """Should filter jobs by job type."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        # Create different job types
        for job_type in [JobType.PARSE, JobType.PARSE, JobType.CLASSIFY]:
            job = Job(job_type=job_type, payload={"template_version_id": str(version.id)})
            await job_repository.create(job)

        parse_jobs = await job_repository.list_all(job_type=JobType.PARSE)
        classify_jobs = await job_repository.list_all(job_type=JobType.CLASSIFY)

        assert len(parse_jobs) == 2
        assert len(classify_jobs) == 1


class TestJobPayload:
    """Tests for job payload handling."""

    @pytest.mark.asyncio
    async def test_job_payload_stored_correctly(self, job_repository, template_repository):
        """Job payload should be stored and retrieved correctly."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        payload = {
            "template_version_id": str(version.id),
            "options": {"llm_enabled": True, "confidence_threshold": 0.85},
        }

        job = Job(job_type=JobType.PARSE, payload=payload)
        created = await job_repository.create(job)

        retrieved = await job_repository.get_by_id(created.id)

        assert retrieved.payload == payload
        assert retrieved.payload["options"]["llm_enabled"] is True

    @pytest.mark.asyncio
    async def test_job_result_stored_correctly(self, job_repository, template_repository):
        """Job result should be stored correctly on completion."""
        from backend.app.domains.job.models import Job, JobType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
        await job_repository.create(job)

        claimed = await job_repository.claim_pending_job("worker-1")

        result = {
            "sections_parsed": 10,
            "section_types": {"STATIC": 7, "DYNAMIC": 3},
            "duration_ms": 1500,
        }

        completed = await job_repository.complete_job(claimed.id, result=result)

        assert completed.result == result
        assert completed.result["section_types"]["STATIC"] == 7


class TestJobHandlers:
    """Tests for job handler registration."""

    def test_parse_handler_registered(self):
        """PARSE handler should be registered."""
        from backend.app.domains.job.models import JobType
        from backend.app.worker.handlers import get_handler_for_job_type

        handler = get_handler_for_job_type(JobType.PARSE)

        assert handler is not None
        assert handler.name == "ParsingHandler"

    def test_classify_handler_registered(self):
        """CLASSIFY handler should be registered."""
        from backend.app.domains.job.models import JobType
        from backend.app.worker.handlers import get_handler_for_job_type

        handler = get_handler_for_job_type(JobType.CLASSIFY)

        assert handler is not None
        assert handler.name == "ClassificationHandler"

    def test_generate_handler_registered(self):
        """GENERATE handler should be registered."""
        from backend.app.domains.job.models import JobType
        from backend.app.worker.handlers import get_handler_for_job_type

        handler = get_handler_for_job_type(JobType.GENERATE)

        assert handler is not None
        assert handler.name == "GenerationPipelineHandler"

    def test_unknown_job_type_raises_error(self):
        """Unknown job type should raise ValueError."""
        from backend.app.worker.handlers import get_handler_for_job_type

        with pytest.raises(ValueError, match="No handler registered"):
            get_handler_for_job_type("UNKNOWN_TYPE")
