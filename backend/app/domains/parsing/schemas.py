"""
Schemas for parsed document representation.

These schemas define the canonical parsed representation of Word documents.
The output is deterministic - same input always produces identical output.
"""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BlockType(str, Enum):
    """Types of structural blocks in a document."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE = "table"
    LIST = "list"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_BREAK = "page_break"
    SECTION_BREAK = "section_break"


class TextRun(BaseModel):
    """
    A run of text with consistent formatting.
    Preserves formatting information for accurate reconstruction.
    """

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    font_name: str | None = None
    font_size: float | None = None  # in points
    color: str | None = None  # hex color
    highlight: str | None = None


class ParagraphBlock(BaseModel):
    """A paragraph block with text content and formatting."""

    block_type: BlockType = BlockType.PARAGRAPH
    block_id: str
    sequence: int  # Position in document
    runs: list[TextRun] = Field(default_factory=list)
    alignment: str | None = None  # left, center, right, justify
    indent_left: float | None = None  # in points
    indent_right: float | None = None
    indent_first_line: float | None = None
    spacing_before: float | None = None
    spacing_after: float | None = None
    style_name: str | None = None

    @property
    def text(self) -> str:
        """Get plain text content."""
        return "".join(run.text for run in self.runs)


class HeadingBlock(BaseModel):
    """A heading block with level and text."""

    block_type: BlockType = BlockType.HEADING
    block_id: str
    sequence: int
    level: int  # 1-9 for Heading 1-9
    runs: list[TextRun] = Field(default_factory=list)
    alignment: str | None = None
    style_name: str | None = None

    @property
    def text(self) -> str:
        """Get plain text content."""
        return "".join(run.text for run in self.runs)


class TableCell(BaseModel):
    """A cell within a table."""

    cell_id: str
    row_index: int
    col_index: int
    row_span: int = 1
    col_span: int = 1
    content: list["DocumentBlock"] = Field(default_factory=list)  # Nested blocks
    width: float | None = None  # in points
    vertical_alignment: str | None = None


class TableRow(BaseModel):
    """A row within a table."""

    row_id: str
    row_index: int
    cells: list[TableCell] = Field(default_factory=list)
    is_header: bool = False
    height: float | None = None


class TableBlock(BaseModel):
    """A table block with rows and cells."""

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
    """An item in a list."""

    item_id: str
    level: int  # Nesting level (0-based)
    runs: list[TextRun] = Field(default_factory=list)
    bullet_char: str | None = None  # For bullet lists
    number_format: str | None = None  # For numbered lists
    number_value: int | None = None

    @property
    def text(self) -> str:
        """Get plain text content."""
        return "".join(run.text for run in self.runs)


class ListBlock(BaseModel):
    """A list block containing list items."""

    block_type: BlockType = BlockType.LIST
    block_id: str
    sequence: int
    list_type: str  # "bullet" or "numbered"
    items: list[ListItem] = Field(default_factory=list)
    style_name: str | None = None


class HeaderFooterBlock(BaseModel):
    """Header or footer content."""

    block_type: BlockType  # HEADER or FOOTER
    block_id: str
    sequence: int
    header_footer_type: str  # "default", "first", "even"
    content: list["DocumentBlock"] = Field(default_factory=list)  # Nested blocks


class PageBreakBlock(BaseModel):
    """Explicit page break."""

    block_type: BlockType = BlockType.PAGE_BREAK
    block_id: str
    sequence: int


class SectionBreakBlock(BaseModel):
    """Section break with section properties."""

    block_type: BlockType = BlockType.SECTION_BREAK
    block_id: str
    sequence: int
    break_type: str  # "continuous", "next_page", "even_page", "odd_page"
    page_width: float | None = None
    page_height: float | None = None
    orientation: str | None = None  # "portrait" or "landscape"


# Union type for all document blocks
DocumentBlock = (
    ParagraphBlock
    | HeadingBlock
    | TableBlock
    | ListBlock
    | HeaderFooterBlock
    | PageBreakBlock
    | SectionBreakBlock
)

# Required for forward references in TableCell
TableCell.model_rebuild()
HeaderFooterBlock.model_rebuild()


class DocumentMetadata(BaseModel):
    """Metadata extracted from the document."""

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
    """
    The canonical parsed representation of a Word document.

    This is the authoritative structure used by all downstream
    classification and generation stages.
    """

    model_config = ConfigDict(from_attributes=True)

    # Identification
    template_version_id: UUID
    template_id: UUID
    version_number: int

    # Content hash for determinism verification
    content_hash: str

    # Parsing metadata
    parsed_at: datetime = Field(default_factory=datetime.utcnow)
    parser_version: str = "1.0.0"

    # Document metadata
    metadata: DocumentMetadata

    # Structural content - ordered list of blocks
    blocks: list[DocumentBlock] = Field(default_factory=list)

    # Headers and footers (separate from main body)
    headers: list[HeaderFooterBlock] = Field(default_factory=list)
    footers: list[HeaderFooterBlock] = Field(default_factory=list)

    # Statistics
    total_blocks: int = 0
    heading_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    list_count: int = 0

    def compute_statistics(self) -> None:
        """Compute block statistics."""
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
    """Details of a parsing error."""

    error_type: str
    message: str
    block_index: int | None = None
    recoverable: bool = False
    details: dict[str, Any] | None = None


class ParsingResult(BaseModel):
    """Result of the parsing operation."""

    success: bool
    document: ParsedDocument | None = None
    errors: list[ParsingError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    # Timing information
    parse_duration_ms: float | None = None
    inference_duration_ms: float | None = None
    total_duration_ms: float | None = None


def generate_block_id(block_type: str, sequence: int, content_hint: str = "") -> str:
    """
    Generate a stable, deterministic block ID.

    The ID is based on block type, sequence, and a hash of content.
    This ensures the same document always produces the same IDs.
    """
    content = f"{block_type}:{sequence}:{content_hint}"
    hash_digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"blk_{block_type[:3]}_{sequence:04d}_{hash_digest}"


def generate_content_hash(content: bytes) -> str:
    """Generate a deterministic hash of document content."""
    return hashlib.sha256(content).hexdigest()
