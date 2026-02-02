from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.domains.job.models import JobType
from backend.app.domains.job.schemas import JobCreate, JobResponse
from backend.app.domains.template.schemas import (
    TemplateCreate,
    TemplateResponse,
    TemplateVersionResponse,
)


class TestTemplateSchemas:
    def test_template_create_schema(self):
        data = TemplateCreate(name="Test Template")
        assert data.name == "Test Template"

    def test_template_create_validation(self):
        with pytest.raises(ValidationError):
            TemplateCreate()

    def test_template_response_schema(self):
        data = TemplateResponse(
            id=uuid4(),
            name="Test Template",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        assert data.name == "Test Template"
        assert data.id is not None

    def test_template_version_response_schema(self):
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
    def test_job_response_schema(self):
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
        data = JobCreate(job_type=JobType.PARSE, payload={"template_version_id": str(uuid4())})
        assert data.job_type == JobType.PARSE


class TestDocumentSchemas:
    def test_document_response_schema(self):
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
    def test_section_response_schema(self):
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
    def test_audit_log_response_schema(self):
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

    def test_audit_query_schema(self):
        from backend.app.domains.audit.schemas import AuditQuery

        query = AuditQuery(entity_type="template", entity_id=uuid4(), skip=0, limit=50)
        assert query.entity_type == "template"
        assert query.limit == 50


class TestAPIRouterRegistration:
    def test_templates_router_exists(self):
        from backend.app.api.v1 import templates

        assert templates.router is not None

    def test_documents_router_exists(self):
        from backend.app.api.v1 import documents

        assert documents.router is not None

    def test_jobs_router_exists(self):
        from backend.app.api.v1 import jobs

        assert jobs.router is not None

    def test_sections_router_exists(self):
        from backend.app.api.v1 import sections

        assert sections.router is not None

    def test_audit_router_exists(self):
        from backend.app.api.v1 import audit

        assert audit.router is not None


class TestDependencies:

    def test_get_db_dependency_exists(self):
        from backend.app.api import deps

        assert hasattr(deps, "get_db")
        assert callable(deps.get_db)


class TestErrorHandling:
    def test_http_exception_structure(self):
        from fastapi import HTTPException

        error = HTTPException(status_code=404, detail="Not found")
        assert error.status_code == 404
        assert error.detail == "Not found"
