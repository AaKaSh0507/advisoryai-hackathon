"""
Tests for Document repository.

Verifies:
- Document creation
- Read by ID
- Document version management
"""

from uuid import uuid4

import pytest


class TestDocumentRepository:
    """Tests for DocumentRepository."""

    @pytest.mark.asyncio
    async def test_create_document(self, document_repository, template_repository):
        """Should create a document linked to a template version."""
        from backend.app.domains.document.models import Document
        from backend.app.domains.template.models import Template, TemplateVersion

        # Create template and version first
        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        # Create document
        document = Document(template_version_id=version.id)
        created = await document_repository.create(document)

        assert created.id is not None
        assert created.template_version_id == version.id
        assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, document_repository, template_repository):
        """Should retrieve document by ID."""
        from backend.app.domains.document.models import Document
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
        created = await document_repository.create(document)

        retrieved = await document_repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, document_repository):
        """Should return None for non-existent document."""
        result = await document_repository.get_by_id(uuid4())
        assert result is None


class TestDocumentVersionRepository:
    """Tests for document version operations."""

    @pytest.mark.asyncio
    async def test_create_document_version(self, document_repository, template_repository):
        """Should create a document version."""
        from backend.app.domains.document.models import Document, DocumentVersion
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        template_version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(template_version)

        document = Document(template_version_id=template_version.id)
        await document_repository.create(document)

        doc_version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            output_doc_path="documents/test/1/output.docx",
            generation_metadata={"status": "completed"},
        )
        created = await document_repository.create_version(doc_version)

        assert created.id is not None
        assert created.document_id == document.id
        assert created.version_number == 1

    @pytest.mark.asyncio
    async def test_get_document_version(self, document_repository, template_repository):
        """Should retrieve version by document_id and version_number."""
        from backend.app.domains.document.models import Document, DocumentVersion
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        template_version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(template_version)

        document = Document(template_version_id=template_version.id)
        await document_repository.create(document)

        doc_version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            output_doc_path="documents/test/1/output.docx",
            generation_metadata={"status": "completed"},
        )
        await document_repository.create_version(doc_version)

        retrieved = await document_repository.get_version(document.id, 1)

        assert retrieved is not None
        assert retrieved.version_number == 1

    @pytest.mark.asyncio
    async def test_list_document_versions(self, document_repository, template_repository):
        """Should list all versions for a document."""
        from backend.app.domains.document.models import Document, DocumentVersion
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        template_version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(template_version)

        document = Document(template_version_id=template_version.id)
        await document_repository.create(document)

        # Create multiple versions
        for i in range(1, 4):
            doc_version = DocumentVersion(
                document_id=document.id,
                version_number=i,
                output_doc_path=f"documents/test/{i}/output.docx",
                generation_metadata={"version": i},
            )
            await document_repository.create_version(doc_version)

        versions = await document_repository.list_versions(document.id)

        assert len(versions) == 3
        # Should be ordered by version_number desc
        assert versions[0].version_number == 3

    @pytest.mark.asyncio
    async def test_get_latest_document_version(self, document_repository, template_repository):
        """Should retrieve the latest document version."""
        from backend.app.domains.document.models import Document, DocumentVersion
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        template_version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(template_version)

        document = Document(template_version_id=template_version.id)
        await document_repository.create(document)

        for i in range(1, 4):
            doc_version = DocumentVersion(
                document_id=document.id,
                version_number=i,
                output_doc_path=f"documents/test/{i}/output.docx",
                generation_metadata={"version": i},
            )
            await document_repository.create_version(doc_version)

        latest = await document_repository.get_latest_version(document.id)

        assert latest is not None
        assert latest.version_number == 3
