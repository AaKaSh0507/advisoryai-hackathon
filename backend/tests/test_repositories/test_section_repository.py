"""
Tests for Section repository.

Verifies:
- Section batch creation
- Listing by template version
"""

import pytest


class TestSectionRepository:
    """Tests for SectionRepository."""

    @pytest.mark.asyncio
    async def test_create_sections_batch(self, section_repository, template_repository):
        """Should create sections in batch."""
        from backend.app.domains.section.models import Section, SectionType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        sections = [
            Section(
                template_version_id=version.id,
                section_type=SectionType.STATIC,
                structural_path=f"/section/{i}",
            )
            for i in range(3)
        ]

        created = await section_repository.create_batch(sections)

        assert len(created) == 3
        for section in created:
            assert section.id is not None

    @pytest.mark.asyncio
    async def test_get_sections_by_template_version(self, section_repository, template_repository):
        """Should list sections for a template version."""
        from backend.app.domains.section.models import Section, SectionType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        sections = [
            Section(
                template_version_id=version.id,
                section_type=SectionType.STATIC if i % 2 == 0 else SectionType.DYNAMIC,
                structural_path=f"/section/{i}",
            )
            for i in range(5)
        ]
        await section_repository.create_batch(sections)

        retrieved = await section_repository.get_by_template_version_id(version.id)

        assert len(retrieved) == 5


class TestSectionTypes:
    """Tests for different section types."""

    @pytest.mark.asyncio
    async def test_create_static_section(self, section_repository, template_repository):
        """Should create a STATIC section."""
        from backend.app.domains.section.models import Section, SectionType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        section = Section(
            template_version_id=version.id,
            section_type=SectionType.STATIC,
            structural_path="/header",
        )
        created = await section_repository.create_batch([section])

        assert created[0].section_type == SectionType.STATIC

    @pytest.mark.asyncio
    async def test_create_dynamic_section_with_prompt(
        self, section_repository, template_repository
    ):
        """Should create a DYNAMIC section with prompt config."""
        from backend.app.domains.section.models import Section, SectionType
        from backend.app.domains.template.models import Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        section = Section(
            template_version_id=version.id,
            section_type=SectionType.DYNAMIC,
            structural_path="/project_description",
            prompt_config={
                "prompt_template": "Describe the project: {project_name}",
                "variables": ["project_name"],
            },
        )
        created = await section_repository.create_batch([section])

        assert created[0].section_type == SectionType.DYNAMIC
        assert created[0].prompt_config is not None
        assert "prompt_template" in created[0].prompt_config
