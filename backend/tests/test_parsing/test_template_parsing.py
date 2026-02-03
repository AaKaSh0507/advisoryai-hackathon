"""
Tests for Template Parsing.

Verifies:
- Parsing handler exists and is configured
- Parsing handler validates input
- Document structure parsing utilities
"""

import pytest


class TestParsingHandlerConfiguration:
    """Tests for parsing handler setup."""

    def test_parsing_handler_exists(self):
        """Parsing handler should be importable."""
        from backend.app.worker.handlers.parsing import ParsingHandler

        handler = ParsingHandler()
        assert handler.name == "ParsingHandler"

    def test_handler_has_handle_method(self):
        """Handler should have async handle method."""
        from backend.app.worker.handlers.parsing import ParsingHandler

        handler = ParsingHandler()
        assert hasattr(handler, "handle")
        assert callable(handler.handle)


class TestHandlerContext:
    """Tests for handler context and result types."""

    def test_handler_context_importable(self):
        """HandlerContext should be importable."""
        from backend.app.worker.handlers import HandlerContext

        assert HandlerContext is not None

    def test_handler_result_importable(self):
        """HandlerResult should be importable."""
        from backend.app.worker.handlers import HandlerResult

        assert HandlerResult is not None

    def test_handler_result_success(self):
        """HandlerResult should support success state."""
        from backend.app.worker.handlers import HandlerResult

        result = HandlerResult(success=True, data={"sections": 5}, should_advance_pipeline=True)

        assert result.success is True
        assert result.data == {"sections": 5}
        assert result.should_advance_pipeline is True

    def test_handler_result_failure(self):
        """HandlerResult should support failure state."""
        from backend.app.worker.handlers import HandlerResult

        result = HandlerResult(
            success=False, error="Document parsing failed", should_advance_pipeline=False
        )

        assert result.success is False
        assert result.error == "Document parsing failed"
        assert result.should_advance_pipeline is False


class TestParsingDomainComponents:
    """Tests for parsing domain components."""

    def test_word_document_parser_exists(self):
        """WordDocumentParser should be importable."""
        from backend.app.domains.parsing import WordDocumentParser

        parser = WordDocumentParser()
        assert parser is not None

    def test_document_validator_exists(self):
        """DocumentValidator should be importable."""
        from backend.app.domains.parsing import DocumentValidator

        validator = DocumentValidator()
        assert validator is not None

    def test_structure_inference_service_exists(self):
        """StructureInferenceService should be importable."""
        from backend.app.domains.parsing import StructureInferenceService

        # Note: This may require LLM config, so just check importability
        assert StructureInferenceService is not None


class TestDocumentValidator:
    """Tests for document validation."""

    def test_validator_has_validate_method(self):
        """Validator should have validate method."""
        from backend.app.domains.parsing import DocumentValidator

        validator = DocumentValidator()
        assert hasattr(validator, "validate")
        assert callable(validator.validate)

    def test_validator_returns_validation_result(self):
        """Validator should return a validation result object."""
        from backend.app.domains.parsing import DocumentValidator

        validator = DocumentValidator()

        # Test with invalid (empty) content
        result = validator.validate(b"")

        # Result should have valid property (note: it's 'valid' not 'is_valid')
        assert hasattr(result, "valid")
        assert result.valid is False  # Empty file should be invalid


class TestWordDocumentParser:
    """Tests for Word document parsing."""

    def test_parser_has_parse_method(self):
        """Parser should have parse method."""
        from backend.app.domains.parsing import WordDocumentParser

        parser = WordDocumentParser()
        assert hasattr(parser, "parse")
        assert callable(parser.parse)


class TestParsingStatus:
    """Tests for parsing status tracking."""

    @pytest.mark.asyncio
    async def test_template_version_parsing_status_enum(self):
        """ParsingStatus enum should have expected values."""
        from backend.app.domains.template.models import ParsingStatus

        assert ParsingStatus.PENDING is not None
        assert ParsingStatus.IN_PROGRESS is not None
        assert ParsingStatus.COMPLETED is not None
        assert ParsingStatus.FAILED is not None

    @pytest.mark.asyncio
    async def test_new_template_version_has_pending_status(self, template_repository):
        """New template versions should have PENDING parsing status."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        created = await template_repository.create_version(version)

        assert created.parsing_status == ParsingStatus.PENDING

    @pytest.mark.asyncio
    async def test_mark_parsing_in_progress(self, template_repository):
        """Should be able to mark parsing as in progress."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        await template_repository.mark_parsing_in_progress(version.id)

        updated = await template_repository.get_version_by_id(version.id)
        assert updated.parsing_status == ParsingStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_mark_parsing_completed(self, template_repository):
        """Should be able to mark parsing as completed."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        await template_repository.mark_parsing_completed(
            version.id, parsed_path="templates/test/1/parsed.json", content_hash="abc123"
        )

        updated = await template_repository.get_version_by_id(version.id)
        assert updated.parsing_status == ParsingStatus.COMPLETED
        assert updated.parsed_representation_path == "templates/test/1/parsed.json"
        assert updated.content_hash == "abc123"
        assert updated.parsed_at is not None

    @pytest.mark.asyncio
    async def test_mark_parsing_failed(self, template_repository):
        """Should be able to mark parsing as failed with error."""
        from backend.app.domains.template.models import ParsingStatus, Template, TemplateVersion

        template = Template(name="Test Template")
        await template_repository.create(template)

        version = TemplateVersion(
            template_id=template.id,
            version_number=1,
            source_doc_path="templates/test/1/source.docx",
        )
        await template_repository.create_version(version)

        await template_repository.mark_parsing_failed(version.id, error="Invalid document format")

        updated = await template_repository.get_version_by_id(version.id)
        assert updated.parsing_status == ParsingStatus.FAILED
        assert updated.parsing_error == "Invalid document format"


class TestClassificationHandler:
    """Tests for classification handler."""

    def test_classification_handler_exists(self):
        """Classification handler should be importable."""
        from backend.app.worker.handlers.classification import ClassificationHandler

        handler = ClassificationHandler()
        assert handler.name == "ClassificationHandler"

    def test_classification_handler_has_handle_method(self):
        """Handler should have async handle method."""
        from backend.app.worker.handlers.classification import ClassificationHandler

        handler = ClassificationHandler()
        assert hasattr(handler, "handle")
        assert callable(handler.handle)


class TestGenerationPipelineHandler:
    """Tests for generation pipeline handler."""

    def test_generation_pipeline_handler_exists(self):
        """Generation pipeline handler should be importable."""
        from backend.app.worker.handlers.generation_pipeline import GenerationPipelineHandler

        handler = GenerationPipelineHandler()
        assert handler.name == "GenerationPipelineHandler"

    def test_generation_pipeline_handler_has_handle_method(self):
        """Handler should have async handle method."""
        from backend.app.worker.handlers.generation_pipeline import GenerationPipelineHandler

        handler = GenerationPipelineHandler()
        assert hasattr(handler, "handle")
        assert callable(handler.handle)


class TestSectionTypes:
    """Tests for section type definitions."""

    def test_section_type_enum_exists(self):
        """SectionType enum should exist."""
        from backend.app.domains.section.models import SectionType

        assert SectionType.STATIC is not None
        assert SectionType.DYNAMIC is not None

    @pytest.mark.asyncio
    async def test_create_static_section(self, section_repository, template_repository):
        """Should be able to create STATIC section."""
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
            structural_path="/document/header",
        )

        # SectionRepository uses create_batch
        created_sections = await section_repository.create_batch([section])

        assert len(created_sections) == 1
        assert created_sections[0].section_type == SectionType.STATIC

    @pytest.mark.asyncio
    async def test_create_dynamic_section(self, section_repository, template_repository):
        """Should be able to create DYNAMIC section."""
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
            structural_path="/document/executive_summary",
            prompt_config={"prompt": "Write an executive summary"},
        )

        # SectionRepository uses create_batch
        created_sections = await section_repository.create_batch([section])

        assert len(created_sections) == 1
        assert created_sections[0].section_type == SectionType.DYNAMIC
        assert created_sections[0].prompt_config is not None
