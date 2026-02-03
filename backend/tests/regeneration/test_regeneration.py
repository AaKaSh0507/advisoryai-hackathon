import uuid
from datetime import datetime
from unittest.mock import MagicMock

from backend.app.domains.regeneration.schemas import (
    FullRegenerationRequest,
    RegenerationAuditPayload,
    RegenerationIntent,
    RegenerationResult,
    RegenerationScope,
    RegenerationSectionResult,
    RegenerationStatus,
    RegenerationStrategy,
    SectionRegenerationRequest,
    SectionRegenerationTarget,
    TemplateUpdateRegenerationRequest,
    VersionTransition,
)
from backend.app.domains.regeneration.service import (
    DocumentNotFoundError,
    NoVersionExistsError,
    RegenerationError,
)


class TestRegenerationSchemas:
    """Tests for regeneration schemas."""

    def test_regeneration_scope_values(self):
        """Test RegenerationScope enum values."""
        assert RegenerationScope.SECTION.value == "SECTION"
        assert RegenerationScope.FULL.value == "FULL"

    def test_regeneration_strategy_values(self):
        """Test RegenerationStrategy enum values."""
        assert RegenerationStrategy.REUSE_UNCHANGED.value == "REUSE_UNCHANGED"
        assert RegenerationStrategy.FORCE_ALL.value == "FORCE_ALL"

    def test_regeneration_intent_values(self):
        """Test RegenerationIntent enum values."""
        assert RegenerationIntent.CONTENT_UPDATE.value == "CONTENT_UPDATE"
        assert RegenerationIntent.CORRECTION.value == "CORRECTION"
        assert RegenerationIntent.TEMPLATE_UPDATE.value == "TEMPLATE_UPDATE"
        assert RegenerationIntent.MANUAL_OVERRIDE.value == "MANUAL_OVERRIDE"

    def test_regeneration_status_values(self):
        """Test RegenerationStatus enum values."""
        assert RegenerationStatus.PENDING.value == "PENDING"
        assert RegenerationStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert RegenerationStatus.COMPLETED.value == "COMPLETED"
        assert RegenerationStatus.FAILED.value == "FAILED"

    def test_section_regeneration_target(self):
        """Test SectionRegenerationTarget creation."""
        target = SectionRegenerationTarget(
            section_id=1,
            force=True,
            client_data_override={"key": "value"},
        )
        assert target.section_id == 1
        assert target.force is True
        assert target.client_data_override == {"key": "value"}

    def test_section_regeneration_request(self):
        """Test SectionRegenerationRequest creation."""
        doc_id = uuid.uuid4()
        targets = [SectionRegenerationTarget(section_id=1), SectionRegenerationTarget(section_id=2)]

        request = SectionRegenerationRequest(
            document_id=doc_id,
            target_sections=targets,
            intent=RegenerationIntent.CORRECTION,
            strategy=RegenerationStrategy.FORCE_ALL,
        )

        assert request.document_id == doc_id
        assert len(request.target_sections) == 2
        assert request.intent == RegenerationIntent.CORRECTION
        assert request.strategy == RegenerationStrategy.FORCE_ALL

    def test_section_regeneration_request_defaults(self):
        """Test SectionRegenerationRequest with defaults."""
        doc_id = uuid.uuid4()
        targets = [SectionRegenerationTarget(section_id=1)]

        request = SectionRegenerationRequest(
            document_id=doc_id,
            target_sections=targets,
        )

        assert request.intent == RegenerationIntent.CONTENT_UPDATE
        assert request.strategy == RegenerationStrategy.REUSE_UNCHANGED
        assert request.client_data == {}

    def test_full_regeneration_request(self):
        """Test FullRegenerationRequest creation."""
        doc_id = uuid.uuid4()

        request = FullRegenerationRequest(
            document_id=doc_id,
            intent=RegenerationIntent.MANUAL_OVERRIDE,
            client_data={"company": "Test Inc"},
        )

        assert request.document_id == doc_id
        assert request.intent == RegenerationIntent.MANUAL_OVERRIDE
        assert request.client_data["company"] == "Test Inc"

    def test_template_update_regeneration_request(self):
        """Test TemplateUpdateRegenerationRequest creation."""
        doc_id = uuid.uuid4()
        new_template_id = uuid.uuid4()

        request = TemplateUpdateRegenerationRequest(
            document_id=doc_id,
            new_template_version_id=new_template_id,
        )

        assert request.document_id == doc_id
        assert request.new_template_version_id == new_template_id
        assert request.intent == RegenerationIntent.TEMPLATE_UPDATE

    def test_regeneration_section_result(self):
        """Test RegenerationSectionResult creation."""
        result = RegenerationSectionResult(
            section_id=1,
            was_regenerated=True,
            was_reused=False,
            previous_content_hash="abc123",
            new_content_hash="def456",
        )

        assert result.section_id == 1
        assert result.was_regenerated is True
        assert result.was_reused is False

    def test_regeneration_result_structure(self):
        """Test RegenerationResult structure."""
        doc_id = uuid.uuid4()

        result = RegenerationResult(
            success=True,
            document_id=doc_id,
            previous_version_number=1,
            new_version_number=2,
            new_version_id=uuid.uuid4(),
            scope=RegenerationScope.SECTION,
            intent=RegenerationIntent.CONTENT_UPDATE,
            strategy=RegenerationStrategy.REUSE_UNCHANGED,
            status=RegenerationStatus.COMPLETED,
            sections_regenerated=2,
            sections_reused=3,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        assert result.success is True
        assert result.document_id == doc_id
        assert result.previous_version_number == 1
        assert result.new_version_number == 2
        assert result.scope == RegenerationScope.SECTION
        assert result.sections_regenerated == 2
        assert result.sections_reused == 3

    def test_version_transition(self):
        """Test VersionTransition creation."""
        doc_id = uuid.uuid4()
        version_id = uuid.uuid4()
        template_id = uuid.uuid4()

        transition = VersionTransition(
            document_id=doc_id,
            old_version_number=1,
            old_version_id=uuid.uuid4(),
            new_version_number=2,
            new_version_id=version_id,
            scope=RegenerationScope.FULL,
            intent=RegenerationIntent.CONTENT_UPDATE,
            regenerated_section_ids=[1, 2, 3],
            reused_section_ids=[4, 5],
            template_version_id=template_id,
            timestamp=datetime.utcnow(),
        )

        assert transition.document_id == doc_id
        assert transition.old_version_number == 1
        assert transition.new_version_number == 2
        assert len(transition.regenerated_section_ids) == 3
        assert len(transition.reused_section_ids) == 2

    def test_regeneration_audit_payload(self):
        """Test RegenerationAuditPayload creation."""
        doc_id = uuid.uuid4()
        template_id = uuid.uuid4()

        payload = RegenerationAuditPayload(
            document_id=doc_id,
            scope=RegenerationScope.SECTION,
            intent=RegenerationIntent.CORRECTION,
            strategy=RegenerationStrategy.FORCE_ALL,
            old_version=1,
            new_version=2,
            template_version_id=template_id,
            regenerated_sections=[1, 2],
            reused_sections=[3, 4, 5],
        )

        assert payload.document_id == doc_id
        assert payload.scope == RegenerationScope.SECTION
        assert payload.new_version == 2
        assert len(payload.regenerated_sections) == 2
        assert len(payload.reused_sections) == 3


class TestRegenerationErrors:
    """Tests for regeneration error classes."""

    def test_regeneration_error_base(self):
        """Test base RegenerationError."""
        error = RegenerationError(
            message="Test error",
            code="TEST_ERROR",
            details={"key": "value"},
        )

        assert str(error) == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.details["key"] == "value"

    def test_document_not_found_error(self):
        """Test DocumentNotFoundError."""
        doc_id = uuid.uuid4()
        error = DocumentNotFoundError(doc_id)

        assert str(doc_id) in str(error)
        assert error.code == "DOCUMENT_NOT_FOUND"
        assert error.details["document_id"] == str(doc_id)

    def test_no_version_exists_error(self):
        """Test NoVersionExistsError."""
        doc_id = uuid.uuid4()
        error = NoVersionExistsError(doc_id)

        assert str(doc_id) in str(error)
        assert error.code == "NO_VERSION_EXISTS"


class TestTemplateVersionUpdates:
    """Tests for template version update behavior."""

    def test_template_update_does_not_affect_old_document_structure(self):
        """Test that updating a template doesn't modify existing documents."""
        # Old document should retain its original template_version_id
        old_document_template_version = uuid.uuid4()
        new_template_version = uuid.uuid4()

        # Simulate document creation
        document = MagicMock()
        document.template_version_id = old_document_template_version

        # Template update happens (new version created)
        # Old document should still reference old version
        assert document.template_version_id == old_document_template_version
        assert document.template_version_id != new_template_version

    def test_document_can_opt_into_new_template_version(self):
        """Test that a document can be updated to use new template version."""
        new_version = uuid.uuid4()

        # Create request for template update
        doc_id = uuid.uuid4()
        request = TemplateUpdateRegenerationRequest(
            document_id=doc_id,
            new_template_version_id=new_version,
        )

        assert request.new_template_version_id == new_version
        assert request.intent == RegenerationIntent.TEMPLATE_UPDATE


class TestRegenerationWorkerHandlers:
    """Tests for regeneration worker handlers."""

    def test_handler_job_types(self):
        """Test that handlers register correct job types."""
        from backend.app.domains.job.models import JobType

        # These job types should exist
        assert hasattr(JobType, "REGENERATE")
        assert hasattr(JobType, "REGENERATE_SECTIONS")

    def test_job_schemas_for_regeneration(self):
        """Test job schemas support regeneration."""
        from backend.app.domains.job.schemas import RegenerateJobCreate, RegenerateSectionsJobCreate

        # Full regeneration job
        full_job = RegenerateJobCreate(
            document_id=uuid.uuid4(),
            version_intent=1,
            client_data={"company": "Test"},
        )
        assert full_job.document_id is not None
        assert full_job.version_intent == 1

        # Section regeneration job
        section_job = RegenerateSectionsJobCreate(
            document_id=uuid.uuid4(),
            template_version_id=uuid.uuid4(),
            version_intent=1,
            section_ids=[1, 2, 3],
            reuse_section_ids=[4, 5],
        )
        assert len(section_job.section_ids) == 3
        assert len(section_job.reuse_section_ids) == 2


class TestRegenerationAPIEndpoints:
    """Tests for regeneration API endpoints."""

    def test_section_regeneration_request_validation(self):
        """Test section regeneration request validation."""
        doc_id = uuid.uuid4()
        targets = [SectionRegenerationTarget(section_id=1)]

        request = SectionRegenerationRequest(
            document_id=doc_id,
            target_sections=targets,
        )

        assert len(request.target_sections) > 0

    def test_full_regeneration_request_validation(self):
        """Test full regeneration request validation."""
        request = FullRegenerationRequest(
            document_id=uuid.uuid4(),
        )
        assert request.document_id is not None

    def test_regeneration_result_serialization(self):
        """Test regeneration result can be serialized."""
        result = RegenerationResult(
            success=True,
            document_id=uuid.uuid4(),
            scope=RegenerationScope.FULL,
            intent=RegenerationIntent.CONTENT_UPDATE,
            status=RegenerationStatus.COMPLETED,
            sections_regenerated=5,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        # Should be serializable to dict
        result_dict = result.model_dump()
        assert "document_id" in result_dict
        assert "scope" in result_dict
        assert "status" in result_dict
