from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.domains.assembly.repository import AssembledDocumentRepository
from backend.app.domains.assembly.schemas import AssemblyRequest
from backend.app.domains.assembly.service import (
    ContentInjector,
    DocumentAssemblyService,
    StructuralIntegrityValidator,
)
from backend.app.domains.generation.section_output_models import (
    SectionGenerationStatus,
    SectionOutput,
)
from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    HeadingBlock,
    ListBlock,
    ListItem,
    ParagraphBlock,
    ParsedDocument,
    TableBlock,
    TableCell,
    TableRow,
    TextRun,
)
from backend.app.domains.section.models import Section, SectionType


@pytest.fixture
def document_id() -> UUID:
    return uuid4()


@pytest.fixture
def template_version_id() -> UUID:
    return uuid4()


@pytest.fixture
def template_id() -> UUID:
    return uuid4()


@pytest.fixture
def section_output_batch_id() -> UUID:
    return uuid4()


@pytest.fixture
def input_batch_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_text_run() -> TextRun:
    return TextRun(
        text="Sample text content",
        bold=False,
        italic=False,
        underline=False,
    )


@pytest.fixture
def static_paragraph_block() -> ParagraphBlock:
    return ParagraphBlock(
        block_id="blk_par_0001_abc123",
        sequence=0,
        runs=[TextRun(text="This is static content that should not change.")],
        alignment="left",
        style_name="Normal",
    )


@pytest.fixture
def dynamic_paragraph_block() -> ParagraphBlock:
    return ParagraphBlock(
        block_id="blk_par_0002_def456",
        sequence=1,
        runs=[TextRun(text="[DYNAMIC PLACEHOLDER]")],
        alignment="justify",
        style_name="BodyText",
    )


@pytest.fixture
def heading_block() -> HeadingBlock:
    return HeadingBlock(
        block_id="blk_hea_0003_ghi789",
        sequence=2,
        level=1,
        runs=[TextRun(text="Executive Summary", bold=True)],
        style_name="Heading1",
    )


@pytest.fixture
def table_block() -> TableBlock:
    return TableBlock(
        block_id="blk_tab_0004_jkl012",
        sequence=3,
        column_count=2,
        rows=[
            TableRow(
                row_id="row_001",
                row_index=0,
                is_header=True,
                cells=[
                    TableCell(
                        cell_id="cell_001",
                        row_index=0,
                        col_index=0,
                        content=[
                            ParagraphBlock(
                                block_id="blk_par_cell_001",
                                sequence=0,
                                runs=[TextRun(text="Header 1")],
                            )
                        ],
                    ),
                    TableCell(
                        cell_id="cell_002",
                        row_index=0,
                        col_index=1,
                        content=[
                            ParagraphBlock(
                                block_id="blk_par_cell_002",
                                sequence=0,
                                runs=[TextRun(text="Header 2")],
                            )
                        ],
                    ),
                ],
            )
        ],
        style_name="TableGrid",
    )


@pytest.fixture
def list_block() -> ListBlock:
    return ListBlock(
        block_id="blk_lst_0005_mno345",
        sequence=4,
        list_type="bullet",
        items=[
            ListItem(
                item_id="item_001",
                level=0,
                runs=[TextRun(text="First item")],
                bullet_char="•",
            ),
            ListItem(
                item_id="item_002",
                level=0,
                runs=[TextRun(text="Second item")],
                bullet_char="•",
            ),
        ],
        style_name="ListBullet",
    )


@pytest.fixture
def document_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        title="Advisory Report",
        author="AdvisoryAI",
        created=datetime.utcnow(),
        word_count=1500,
        page_count=5,
    )


@pytest.fixture
def parsed_document(
    template_version_id: UUID,
    template_id: UUID,
    static_paragraph_block: ParagraphBlock,
    dynamic_paragraph_block: ParagraphBlock,
    heading_block: HeadingBlock,
    document_metadata: DocumentMetadata,
) -> ParsedDocument:
    return ParsedDocument(
        template_version_id=template_version_id,
        template_id=template_id,
        version_number=1,
        content_hash="abc123def456",
        metadata=document_metadata,
        blocks=[static_paragraph_block, dynamic_paragraph_block, heading_block],
        headers=[],
        footers=[],
    )


@pytest.fixture
def static_section(template_version_id: UUID) -> Section:
    section = MagicMock(spec=Section)
    section.id = 1
    section.template_version_id = template_version_id
    section.section_type = SectionType.STATIC
    section.structural_path = "body/block/0"
    section.prompt_config = None
    return section


@pytest.fixture
def dynamic_section(template_version_id: UUID) -> Section:
    section = MagicMock(spec=Section)
    section.id = 2
    section.template_version_id = template_version_id
    section.section_type = SectionType.DYNAMIC
    section.structural_path = "body/block/1"
    section.prompt_config = {"type": "executive_summary"}
    return section


@pytest.fixture
def heading_section(template_version_id: UUID) -> Section:
    section = MagicMock(spec=Section)
    section.id = 3
    section.template_version_id = template_version_id
    section.section_type = SectionType.STATIC
    section.structural_path = "body/block/2"
    section.prompt_config = None
    return section


@pytest.fixture
def validated_section_output(
    section_output_batch_id: UUID,
    dynamic_section: Section,
    input_batch_id: UUID,
) -> SectionOutput:
    output = MagicMock(spec=SectionOutput)
    output.id = uuid4()
    output.batch_id = section_output_batch_id
    output.generation_input_id = uuid4()
    output.section_id = dynamic_section.id
    output.sequence_order = 1
    output.status = SectionGenerationStatus.VALIDATED
    output.generated_content = (
        "This is the generated executive summary content that replaces the placeholder."
    )
    output.content_length = len(output.generated_content)
    output.content_hash = "generated_hash_123"
    output.is_validated = True
    output.is_immutable = True
    output.is_ready_for_assembly = True
    return output


@pytest.fixture
def assembly_request(
    document_id: UUID,
    template_version_id: UUID,
    section_output_batch_id: UUID,
) -> AssemblyRequest:
    return AssemblyRequest(
        document_id=document_id,
        template_version_id=template_version_id,
        version_intent=1,
        section_output_batch_id=section_output_batch_id,
    )


@pytest.fixture
def mock_repository() -> AsyncMock:
    repo = AsyncMock(spec=AssembledDocumentRepository)
    repo.get_by_section_output_batch.return_value = None
    repo.exists_for_batch.return_value = False
    return repo


@pytest.fixture
def mock_section_output_repository() -> AsyncMock:
    repo = AsyncMock()
    repo.get_validated_outputs_by_batch = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_parsed_document_repository(parsed_document: ParsedDocument) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_template_version_id = AsyncMock(return_value=parsed_document)
    return repo


@pytest.fixture
def mock_section_repository(
    static_section: Section,
    dynamic_section: Section,
    heading_section: Section,
) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_template_version_id = AsyncMock(
        return_value=[static_section, dynamic_section, heading_section]
    )
    return repo


@pytest.fixture
def structural_validator() -> StructuralIntegrityValidator:
    return StructuralIntegrityValidator()


@pytest.fixture
def content_injector() -> ContentInjector:
    return ContentInjector()


@pytest.fixture
def assembly_service(
    mock_repository: AsyncMock,
    mock_section_output_repository: AsyncMock,
    mock_parsed_document_repository: AsyncMock,
    mock_section_repository: AsyncMock,
) -> DocumentAssemblyService:
    return DocumentAssemblyService(
        repository=mock_repository,
        section_output_repository=mock_section_output_repository,
        parsed_document_repository=mock_parsed_document_repository,
        section_repository=mock_section_repository,
    )
