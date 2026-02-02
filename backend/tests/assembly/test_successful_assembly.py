from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.domains.assembly.models import AssembledDocument
from backend.app.domains.assembly.schemas import AssemblyRequest
from backend.app.domains.assembly.service import DocumentAssemblyService
from backend.app.domains.parsing.schemas import (
    HeadingBlock,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.models import Section, SectionType


def create_mock_assembled_document(assembly_request, **overrides):
    mock_assembled = MagicMock(spec=AssembledDocument)
    mock_assembled.id = overrides.get("id", uuid4())
    mock_assembled.document_id = assembly_request.document_id
    mock_assembled.template_version_id = assembly_request.template_version_id
    mock_assembled.version_intent = assembly_request.version_intent
    mock_assembled.section_output_batch_id = assembly_request.section_output_batch_id
    mock_assembled.assembly_hash = overrides.get("assembly_hash", "test_hash")
    mock_assembled.total_blocks = overrides.get("total_blocks", 3)
    mock_assembled.dynamic_blocks_count = overrides.get("dynamic_blocks_count", 1)
    mock_assembled.static_blocks_count = overrides.get("static_blocks_count", 2)
    mock_assembled.injected_sections_count = overrides.get("injected_sections_count", 1)
    mock_assembled.headers = overrides.get("headers", [])
    mock_assembled.footers = overrides.get("footers", [])
    mock_assembled.is_immutable = overrides.get("is_immutable", True)
    mock_assembled.assembled_at = overrides.get("assembled_at", datetime.utcnow())
    mock_assembled.created_at = overrides.get("created_at", datetime.utcnow())
    return mock_assembled


class TestDynamicSectionsContainGeneratedContent:
    async def test_dynamic_section_receives_generated_content(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        validated_section_output,
        dynamic_section: Section,
    ):
        mock_assembled = create_mock_assembled_document(assembly_request)

        assembly_service.repository.create.return_value = mock_assembled
        assembly_service.repository.mark_in_progress.return_value = mock_assembled
        assembly_service.repository.mark_completed.return_value = mock_assembled
        assembly_service.repository.mark_validated.return_value = mock_assembled
        assembly_service.repository.get_by_id.return_value = mock_assembled
        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            validated_section_output
        ]

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is True
        assert result.injection_results is not None
        injected = [r for r in result.injection_results if r.was_injected]
        assert len(injected) == 1
        assert injected[0].section_id == dynamic_section.id

    async def test_multiple_dynamic_sections_all_injected(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        template_version_id,
        document_metadata,
    ):
        dynamic_block_1 = ParagraphBlock(
            block_id="blk_par_0001_dyn1",
            sequence=0,
            runs=[TextRun(text="[PLACEHOLDER 1]")],
        )
        dynamic_block_2 = ParagraphBlock(
            block_id="blk_par_0002_dyn2",
            sequence=1,
            runs=[TextRun(text="[PLACEHOLDER 2]")],
        )

        parsed_doc = ParsedDocument(
            template_version_id=template_version_id,
            template_id=uuid4(),
            version_number=1,
            content_hash="multi_dynamic_hash",
            metadata=document_metadata,
            blocks=[dynamic_block_1, dynamic_block_2],
            headers=[],
            footers=[],
        )

        section_1 = MagicMock(spec=Section)
        section_1.id = 10
        section_1.section_type = SectionType.DYNAMIC
        section_1.structural_path = "body/block/0"

        section_2 = MagicMock(spec=Section)
        section_2.id = 11
        section_2.section_type = SectionType.DYNAMIC
        section_2.structural_path = "body/block/1"

        output_1 = MagicMock()
        output_1.id = uuid4()
        output_1.section_id = 10
        output_1.generated_content = "Generated content for section 1"
        output_1.is_validated = True

        output_2 = MagicMock()
        output_2.id = uuid4()
        output_2.section_id = 11
        output_2.generated_content = "Generated content for section 2"
        output_2.is_validated = True

        assembly_service.parsed_document_repository.get_by_template_version_id.return_value = (
            parsed_doc
        )
        assembly_service.section_repository.get_by_template_version_id.return_value = [
            section_1,
            section_2,
        ]
        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            output_1,
            output_2,
        ]

        mock_assembled = create_mock_assembled_document(
            assembly_request,
            total_blocks=2,
            dynamic_blocks_count=2,
            static_blocks_count=0,
            injected_sections_count=2,
        )

        assembly_service.repository.create.return_value = mock_assembled
        assembly_service.repository.mark_in_progress.return_value = mock_assembled
        assembly_service.repository.mark_completed.return_value = mock_assembled
        assembly_service.repository.mark_validated.return_value = mock_assembled
        assembly_service.repository.get_by_id.return_value = mock_assembled

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is True
        injected = [r for r in result.injection_results if r.was_injected]
        assert len(injected) == 2


class TestStaticSectionsRemainUnchanged:
    async def test_static_section_content_preserved(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        validated_section_output,
        static_paragraph_block: ParagraphBlock,
    ):
        mock_assembled = create_mock_assembled_document(assembly_request)

        assembly_service.repository.create.return_value = mock_assembled
        assembly_service.repository.mark_in_progress.return_value = mock_assembled
        assembly_service.repository.mark_completed.return_value = mock_assembled
        assembly_service.repository.mark_validated.return_value = mock_assembled
        assembly_service.repository.get_by_id.return_value = mock_assembled
        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            validated_section_output
        ]

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is True
        assert result.assembled_document is not None
        static_blocks = [b for b in result.assembled_document.blocks if not b.is_dynamic]
        for static_block in static_blocks:
            assert static_block.was_modified is False
            assert static_block.original_content_hash == static_block.assembled_content_hash

    async def test_static_section_formatting_preserved(
        self,
        content_injector,
        static_paragraph_block: ParagraphBlock,
    ):
        block_data, content_hash = content_injector.preserve_block(static_paragraph_block)

        assert block_data["alignment"] == static_paragraph_block.alignment
        assert block_data["style_name"] == static_paragraph_block.style_name
        assert block_data["runs"][0]["text"] == static_paragraph_block.runs[0].text


class TestOrderingAndHierarchyPreserved:
    async def test_block_sequence_preserved(
        self,
        assembly_service: DocumentAssemblyService,
        assembly_request: AssemblyRequest,
        validated_section_output,
    ):
        mock_assembled = create_mock_assembled_document(assembly_request)

        assembly_service.repository.create.return_value = mock_assembled
        assembly_service.repository.mark_in_progress.return_value = mock_assembled
        assembly_service.repository.mark_completed.return_value = mock_assembled
        assembly_service.repository.mark_validated.return_value = mock_assembled
        assembly_service.repository.get_by_id.return_value = mock_assembled
        assembly_service.section_output_repository.get_validated_outputs_by_batch.return_value = [
            validated_section_output
        ]

        result = await assembly_service.assemble_document(assembly_request)

        assert result.success is True
        blocks = result.assembled_document.blocks
        sequences = [b.sequence for b in blocks]
        assert sequences == sorted(sequences)

    async def test_heading_levels_preserved(
        self,
        content_injector,
        heading_block: HeadingBlock,
    ):
        block_data, _ = content_injector.preserve_block(heading_block)

        assert block_data["level"] == heading_block.level
        assert block_data["style_name"] == heading_block.style_name


class TestBlockTypeIntegrity:
    def test_paragraph_block_injection(
        self,
        content_injector,
        dynamic_paragraph_block: ParagraphBlock,
    ):
        new_content = "Injected paragraph content"
        block_data, content_hash = content_injector.inject_into_paragraph(
            dynamic_paragraph_block, new_content
        )

        assert block_data["block_type"] == "paragraph"
        assert block_data["runs"][0]["text"] == new_content
        assert block_data["style_name"] == dynamic_paragraph_block.style_name

    def test_heading_block_injection(
        self,
        content_injector,
        heading_block: HeadingBlock,
    ):
        new_content = "Injected heading content"
        block_data, content_hash = content_injector.inject_into_heading(heading_block, new_content)

        assert block_data["block_type"] == "heading"
        assert block_data["level"] == heading_block.level
        assert block_data["runs"][0]["text"] == new_content

    def test_table_block_preserved(
        self,
        content_injector,
        table_block,
    ):
        block_data, content_hash = content_injector.preserve_block(table_block)

        assert block_data["block_type"] == "table"
        assert block_data["column_count"] == table_block.column_count
        assert len(block_data["rows"]) == len(table_block.rows)

    def test_list_block_preserved(
        self,
        content_injector,
        list_block,
    ):
        block_data, content_hash = content_injector.preserve_block(list_block)

        assert block_data["block_type"] == "list"
        assert block_data["list_type"] == list_block.list_type
        assert len(block_data["items"]) == len(list_block.items)
