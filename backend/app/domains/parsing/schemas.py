import hashlib
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.app.infrastructure.datetime_utils import utc_now


class BlockType(str, Enum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_BREAK = "page_break"
    SECTION_BREAK = "section_break"


class TextRun(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_name: str | None = None
    font_size: float | None = None
    color: str | None = None
    highlight: str | None = None


class ParagraphBlock(BaseModel):
    block_type: BlockType = BlockType.PARAGRAPH
    block_id: str
    sequence: int
    runs: list[TextRun] = Field(default_factory=list)
    alignment: str | None = None
    indent_left: float | None = None
    indent_right: float | None = None
    indent_first_line: float | None = None
    spacing_before: float | None = None
    spacing_after: float | None = None
    style_name: str | None = None

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


class HeadingBlock(BaseModel):
    block_type: BlockType = BlockType.HEADING
    block_id: str
    sequence: int
    level: int
    runs: list[TextRun] = Field(default_factory=list)
    alignment: str | None = None
    style_name: str | None = None

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


class TableCell(BaseModel):
    cell_id: str
    row_index: int
    col_index: int
    row_span: int = 1
    col_span: int = 1
    content: list["DocumentBlock"] = Field(default_factory=list)
    width: float | None = None
    vertical_alignment: str | None = None


class TableRow(BaseModel):
    row_id: str
    row_index: int
    cells: list[TableCell] = Field(default_factory=list)
    is_header: bool = False
    height: float | None = None


class TableBlock(BaseModel):
    block_type: BlockType = BlockType.TABLE
    block_id: str
    sequence: int
    rows: list[TableRow] = Field(default_factory=list)
    column_count: int = 0
    style_name: str | None = None

    @property
    def row_count(self) -> int:
        return len(self.rows)


class ListItem(BaseModel):
    item_id: str
    level: int
    runs: list[TextRun] = Field(default_factory=list)
    bullet_char: str | None = None
    number_format: str | None = None
    number_value: int | None = None

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


class ListBlock(BaseModel):
    block_type: BlockType = BlockType.LIST
    block_id: str
    sequence: int
    list_type: str
    items: list[ListItem] = Field(default_factory=list)
    style_name: str | None = None


class HeaderFooterBlock(BaseModel):
    block_type: BlockType
    block_id: str
    sequence: int
    header_footer_type: str
    content: list["DocumentBlock"] = Field(default_factory=list)


class PageBreakBlock(BaseModel):
    block_type: BlockType = BlockType.PAGE_BREAK
    block_id: str
    sequence: int


class SectionBreakBlock(BaseModel):
    block_type: BlockType = BlockType.SECTION_BREAK
    block_id: str
    sequence: int
    break_type: str
    page_width: float | None = None
    page_height: float | None = None
    orientation: str | None = None


DocumentBlock = (
    ParagraphBlock
    | HeadingBlock
    | TableBlock
    | ListBlock
    | HeaderFooterBlock
    | PageBreakBlock
    | SectionBreakBlock
)
TableCell.model_rebuild()
HeaderFooterBlock.model_rebuild()


class DocumentMetadata(BaseModel):
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: str | None = None
    created: datetime | None = None
    modified: datetime | None = None
    revision: int | None = None
    word_count: int | None = None
    page_count: int | None = None
    paragraph_count: int | None = None
    character_count: int | None = None


class ParsedDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    template_version_id: UUID
    template_id: UUID
    version_number: int
    content_hash: str
    parsed_at: datetime = Field(default_factory=utc_now)
    parser_version: str = "1.0.0"
    metadata: DocumentMetadata
    blocks: list[DocumentBlock] = Field(default_factory=list)
    headers: list[HeaderFooterBlock] = Field(default_factory=list)
    footers: list[HeaderFooterBlock] = Field(default_factory=list)
    total_blocks: int = 0
    heading_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    list_count: int = 0

    def compute_statistics(self) -> None:
        self.total_blocks = len(self.blocks)
        self.heading_count = sum(
            1
            for b in self.blocks
            if isinstance(b, HeadingBlock)
            or (hasattr(b, "block_type") and b.block_type == BlockType.HEADING)
        )
        self.paragraph_count = sum(
            1
            for b in self.blocks
            if isinstance(b, ParagraphBlock)
            or (hasattr(b, "block_type") and b.block_type == BlockType.PARAGRAPH)
        )
        self.table_count = sum(
            1
            for b in self.blocks
            if isinstance(b, TableBlock)
            or (hasattr(b, "block_type") and b.block_type == BlockType.TABLE)
        )
        self.list_count = sum(
            1
            for b in self.blocks
            if isinstance(b, ListBlock)
            or (hasattr(b, "block_type") and b.block_type == BlockType.LIST)
        )


class ParsingError(BaseModel):
    error_type: str
    message: str
    block_index: int | None = None
    recoverable: bool = False
    details: dict[str, Any] | None = None


class ParsingResult(BaseModel):
    success: bool
    document: ParsedDocument | None = None
    errors: list[ParsingError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    parse_duration_ms: float | None = None
    inference_duration_ms: float | None = None
    total_duration_ms: float | None = None


def generate_block_id(block_type: str, sequence: int, content_hint: str = "") -> str:
    content = f"{block_type}:{sequence}:{content_hint}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"blk_{block_type[:3]}_{sequence:04d}_{hash_digest}"


def generate_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
