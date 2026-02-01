"""
Tests for Template repository.

Verifies:
- Entity creation
- Read by ID
- Listing
- Version management
- Parsing status updates
"""

from uuid import uuid4

import pytest


class TestTemplateRepository:
    """Tests for TemplateRepository."""

    @pytest.mark.asyncio
    async def test_create_template(self, template_repository):
        """Should create a template and return it with ID."""
        from backend.app.domains.template.models import Template

        template = Template(name="Test Template")
        created = await template_repository.create(template)

        assert created.id is not None
        assert created.name == "Test Template"
        assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_template_by_id(self, template_repository):
        """Should retrieve template by ID."""
        from backend.app.domains.template.models import Template

        template = Template(name="Test Template")
        created = await template_repository.create(template)

        retrieved = await template_repository.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    @pytest.mark.asyncio
    async def test_get_template_by_id_not_found(self, template_repository):
        """Should return None for non-existent template."""
        result = await template_repository.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_templates(self, template_repository):
        """Should list all templates with pagination."""
        from backend.app.domains.template.models import Template

        # Create multiple templates
        for i in range(5):
            template = Template(name=f"Template {i}")
            await template_repository.create(template)

        # List all
        templates = await template_repository.list_all()
        assert len(templates) == 5

        # Test pagination
        paginated = await template_repository.list_all(skip=2, limit=2)
        assert len(paginated) == 2

    @pytest.mark.asyncio
    async def test_delete_template(self, template_repository):
        """Should delete a template."""
        from backend.app.domains.template.models import Template

        template = Template(name="To Delete")
        created = await template_repository.create(template)

        await template_repository.delete(created)

        retrieved = await template_repository.get_by_id(created.id)
        assert retrieved is None


class TestTemplateVersionRepository:
    """Tests for template version operations in TemplateRepository."""

    @pytest.mark.asyncio
    async def test_create_template_version(self, template_repository):
        """Should create a template version."""
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        created = await template_repository.create_version(version)

        assert created.id is not None
        assert created.template_id == template.id
        assert created.version_number == 1

    @pytest.mark.asyncio
    async def test_get_version(self, template_repository):
        """Should retrieve version by template_id and version_number."""
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        retrieved = await template_repository.get_version(template.id, 1)

        assert retrieved is not None
        assert retrieved.version_number == 1

    @pytest.mark.asyncio
    async def test_get_version_by_id(self, template_repository):
        """Should retrieve version by its ID."""
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        created = await template_repository.create_version(version)

        retrieved = await template_repository.get_version_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    @pytest.mark.asyncio
    async def test_get_latest_version(self, template_repository):
        """Should retrieve the latest version number."""
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        # Create multiple versions
        for i in range(1, 4):
            version = TemplateVersion(
                template_id=template.id,
                version_number=i,
                source_doc_path=f"templates/test/{i}/source.docx",
            )
            await template_repository.create_version(version)

        latest = await template_repository.get_latest_version(template.id)

        assert latest is not None
        assert latest.version_number == 3

    @pytest.mark.asyncio
    async def test_list_versions(self, template_repository):
        """Should list all versions for a template."""
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        for i in range(1, 4):
            version = TemplateVersion(
                template_id=template.id,
                version_number=i,
                source_doc_path=f"templates/test/{i}/source.docx",
            )
            await template_repository.create_version(version)

        versions = await template_repository.list_versions(template.id)

        assert len(versions) == 3
        # Should be ordered by version_number desc
        assert versions[0].version_number == 3
        assert versions[1].version_number == 2
        assert versions[2].version_number == 1


class TestParsingStatusUpdates:
    """Tests for parsing status management."""

    @pytest.mark.asyncio
    async def test_mark_parsing_in_progress(self, template_repository):
        """Should mark parsing as in progress."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        updated = await template_repository.mark_parsing_in_progress(version.id)

        assert updated is not None
        assert updated.parsing_status == ParsingStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_mark_parsing_completed(self, template_repository):
        """Should mark parsing as completed with path and hash."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        updated = await template_repository.mark_parsing_completed(
            version.id, parsed_path="templates/test/1/parsed.json", content_hash="abc123hash"
        )

        assert updated is not None
        assert updated.parsing_status == ParsingStatus.COMPLETED
        assert updated.parsed_representation_path == "templates/test/1/parsed.json"
        assert updated.content_hash == "abc123hash"
        assert updated.parsed_at is not None

    @pytest.mark.asyncio
    async def test_mark_parsing_failed(self, template_repository):
        """Should mark parsing as failed with error message."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        updated = await template_repository.mark_parsing_failed(
            version.id, error="Parse error: Invalid document structure"
        )

        assert updated is not None
        assert updated.parsing_status == ParsingStatus.FAILED
        assert updated.parsing_error == "Parse error: Invalid document structure"
