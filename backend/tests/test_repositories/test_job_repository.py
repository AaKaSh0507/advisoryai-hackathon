"""
Tests for Job repository.

Verifies:
- Job creation
- Job status transitions
- Listing by entity and status
- Job type validation
"""

from uuid import uuid4

import pytest


class TestJobRepository:
    """Tests for JobRepository."""

    @pytest.mark.asyncio
    async def test_create_job(self, job_repository, template_repository):
        """Should create a job."""
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
        created = await job_repository.create(job)

        assert created.id is not None
        assert created.job_type == JobType.PARSE
        assert created.status == JobStatus.PENDING
        assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_job_by_id(self, job_repository, template_repository):
        """Should retrieve job by ID."""
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

        retrieved = await job_repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_job_by_id_not_found(self, job_repository):
        """Should return None for non-existent job."""
        result = await job_repository.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="list_by_entity uses PostgreSQL JSONB astext which is not supported in SQLite"
    )
    async def test_list_jobs_by_entity(self, job_repository, template_repository):
        """Should list jobs for a specific entity.

        Note: This test is skipped because list_by_entity uses PostgreSQL-specific
        JSONB operations (payload[key].astext) that aren't compatible with SQLite.
        This functionality is tested in integration tests with PostgreSQL.
        """
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

        # Create multiple jobs for same entity
        for _ in range(3):
            job = Job(job_type=JobType.PARSE, payload={"template_version_id": str(version.id)})
            await job_repository.create(job)

        jobs = await job_repository.list_by_entity("template_version", version.id)

        assert len(jobs) == 3

    @pytest.mark.asyncio
    async def test_list_jobs_by_status(self, job_repository, template_repository):
        """Should list jobs by status."""
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

        pending_jobs = await job_repository.list_all(status_filter=JobStatus.PENDING)

        assert len(pending_jobs) == 3


class TestJobStatusTransitions:
    """Tests for job status transitions."""

    @pytest.mark.asyncio
    async def test_claim_pending_job(self, job_repository, template_repository):
        """Should claim a pending job and mark as RUNNING."""
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

        claimed = await job_repository.claim_pending_job("worker-1")

        assert claimed is not None
        assert claimed.status == JobStatus.RUNNING
        assert claimed.worker_id == "worker-1"
        assert claimed.started_at is not None

    @pytest.mark.asyncio
    async def test_complete_job(self, job_repository, template_repository):
        """Should mark a running job as completed."""
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
        await job_repository.claim_pending_job("worker-1")

        result_data = {"parsed": True, "sections": 5}
        completed = await job_repository.complete_job(job.id, result=result_data)

        assert completed is not None
        assert completed.status == JobStatus.COMPLETED
        assert completed.result == result_data
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_job(self, job_repository, template_repository):
        """Should mark a job as failed with error."""
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
        await job_repository.claim_pending_job("worker-1")

        failed = await job_repository.fail_job(job.id, error="Parse error: Invalid document")

        assert failed is not None
        assert failed.status == JobStatus.FAILED
        assert failed.error == "Parse error: Invalid document"
        assert failed.completed_at is not None


class TestJobTypes:
    """Tests for different job types."""

    @pytest.mark.asyncio
    async def test_create_parse_job(self, job_repository, template_repository):
        """Should create PARSE job."""
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
    async def test_create_classify_job(self, job_repository, template_repository):
        """Should create CLASSIFY job."""
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
    async def test_create_generate_job(
        self, job_repository, document_repository, template_repository
    ):
        """Should create GENERATE job."""
        from backend.app.domains.document.models import Document
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

        document = Document(template_version_id=version.id)
        await document_repository.create(document)

        job = Job(job_type=JobType.GENERATE, payload={"document_id": str(document.id)})
        created = await job_repository.create(job)

        assert created.job_type == JobType.GENERATE


class TestJobModelMethods:
    """Tests for Job model transition validation."""

    @pytest.mark.asyncio
    async def test_valid_transition_pending_to_running(self, job_repository, template_repository):
        """Job model should allow PENDING to RUNNING transition."""
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

        assert job.can_transition_to(JobStatus.RUNNING) is True

    @pytest.mark.asyncio
    async def test_invalid_transition_pending_to_completed(
        self, job_repository, template_repository
    ):
        """Job model should reject PENDING to COMPLETED transition."""
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

        assert job.can_transition_to(JobStatus.COMPLETED) is False

    @pytest.mark.asyncio
    async def test_transition_raises_on_invalid(self, job_repository, template_repository):
        """Job model transition_to should raise on invalid transition."""
        from backend.app.domains.job.models import (
            InvalidJobTransitionError,
            Job,
            JobStatus,
            JobType,
        )
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

        with pytest.raises(InvalidJobTransitionError):
            job.transition_to(JobStatus.COMPLETED)
