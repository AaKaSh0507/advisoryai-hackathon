"""
Tests for API schemas and contracts.

Verifies:
- API schemas are properly defined
- Request/response models are valid
- Serialization works correctly
"""

from datetime import datetime
from uuid import uuid4

import pytest


class TestTemplateSchemas:
    """Tests for template API schemas."""

    def test_template_create_schema(self):
        """TemplateCreate schema should accept valid data."""
        from backend.app.domains.template.schemas import TemplateCreate

        data = TemplateCreate(name="Test Template")

        assert data.name == "Test Template"

    def test_template_create_validation(self):
        """TemplateCreate should validate input."""
        from backend.app.domains.template.schemas import TemplateCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TemplateCreate()  # Missing required name

    def test_template_response_schema(self):
        """TemplateResponse schema should serialize correctly."""
        from backend.app.domains.template.schemas import TemplateResponse

        data = TemplateResponse(
            id=uuid4(),
            name="Test Template",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert data.name == "Test Template"
        assert data.id is not None

    def test_template_version_response_schema(self):
        """TemplateVersionResponse should serialize correctly."""
        from backend.app.domains.template.schemas import TemplateVersionResponse

        data = TemplateVersionResponse(
            id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            source_doc_path="templates/abc/1/source.docx",
            parsing_status="PENDING",
            created_at=datetime.utcnow(),
        )

        assert data.version_number == 1
        assert data.parsing_status == "PENDING"


class TestJobSchemas:
    """Tests for job API schemas."""

    def test_job_response_schema(self):
        """JobResponse schema should serialize correctly."""
        from backend.app.domains.job.schemas import JobResponse

        data = JobResponse(
            id=uuid4(),
            job_type="PARSE",
            status="PENDING",
            payload={"template_version_id": str(uuid4())},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert data.job_type == "PARSE"
        assert data.status == "PENDING"

    def test_job_create_schema(self):
        """JobCreate should accept valid data."""
        from backend.app.domains.job.models import JobType
        from backend.app.domains.job.schemas import JobCreate

        data = JobCreate(job_type=JobType.PARSE, payload={"template_version_id": str(uuid4())})

        assert data.job_type == JobType.PARSE


class TestDocumentSchemas:
    """Tests for document API schemas."""

    def test_document_response_schema(self):
        """DocumentResponse schema should serialize correctly."""
        from backend.app.domains.document.schemas import DocumentResponse

        data = DocumentResponse(
            id=uuid4(),
            template_version_id=uuid4(),
            current_version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert data.current_version == 1


class TestSectionSchemas:
    """Tests for section API schemas."""

    def test_section_response_schema(self):
        """SectionResponse schema should serialize correctly."""
        from backend.app.domains.section.schemas import SectionResponse

        data = SectionResponse(
            id=1,
            template_version_id=uuid4(),
            section_type="STATIC",
            structural_path="/document/header",
            prompt_config=None,
            created_at=datetime.utcnow(),
        )

        assert data.section_type == "STATIC"
        assert data.structural_path == "/document/header"

    def test_section_response_with_prompt_config(self):
        """SectionResponse should handle prompt_config."""
        from backend.app.domains.section.schemas import SectionResponse

        data = SectionResponse(
            id=1,
            template_version_id=uuid4(),
            section_type="DYNAMIC",
            structural_path="/document/summary",
            prompt_config={"prompt": "Write a summary"},
            created_at=datetime.utcnow(),
        )

        assert data.section_type == "DYNAMIC"
        assert data.prompt_config == {"prompt": "Write a summary"}


class TestAuditSchemas:
    """Tests for audit API schemas."""

    def test_audit_log_response_schema(self):
        """AuditLogResponse schema should serialize correctly."""
        from backend.app.domains.audit.schemas import AuditLogResponse

        data = AuditLogResponse(
            id=uuid4(),
            entity_type="template",
            entity_id=uuid4(),
            action="created",
            metadata={"name": "Test"},
            timestamp=datetime.utcnow(),
        )

        assert data.entity_type == "template"
        assert data.action == "created"
        # Note: uses alias, so access via metadata_ or model_dump with by_alias

    def test_audit_query_schema(self):
        """AuditQuery schema should accept query parameters."""
        from backend.app.domains.audit.schemas import AuditQuery

        query = AuditQuery(entity_type="template", entity_id=uuid4(), skip=0, limit=50)

        assert query.entity_type == "template"
        assert query.limit == 50


class TestAPIRouterRegistration:
    """Tests for API router structure."""

    def test_templates_router_exists(self):
        """Templates router should be importable."""
        from backend.app.api.v1 import templates

        assert templates.router is not None

    def test_documents_router_exists(self):
        """Documents router should be importable."""
        from backend.app.api.v1 import documents

        assert documents.router is not None

    def test_jobs_router_exists(self):
        """Jobs router should be importable."""
        from backend.app.api.v1 import jobs

        assert jobs.router is not None

    def test_sections_router_exists(self):
        """Sections router should be importable."""
        from backend.app.api.v1 import sections

        assert sections.router is not None

    def test_audit_router_exists(self):
        """Audit router should be importable."""
        from backend.app.api.v1 import audit

        assert audit.router is not None


class TestDependencies:
    """Tests for API dependency injection."""

    def test_get_db_dependency_exists(self):
        """get_db dependency should be defined."""
        from backend.app.api import deps

        assert hasattr(deps, "get_db")
        assert callable(deps.get_db)


class TestErrorHandling:
    """Tests for error schemas and handling."""

    def test_http_exception_structure(self):
        """HTTPException should be available."""
        from fastapi import HTTPException

        error = HTTPException(status_code=404, detail="Not found")

        assert error.status_code == 404
        assert error.detail == "Not found"
