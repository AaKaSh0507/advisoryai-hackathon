"""
Deterministic Word document parser.

Extracts structural information from Word documents (.docx) while
preserving ordering, nesting, and stable identifiers.
"""

import io
import re
import time
from datetime import datetime
from uuid import UUID

from backend.app.domains.parsing.schemas import (
    BlockType,
    DocumentBlock,
    DocumentMetadata,
    HeaderFooterBlock,
    HeadingBlock,
    ListBlock,
    ListItem,
    PageBreakBlock,
    ParagraphBlock,
    ParsedDocument,
    ParsingError,
    ParsingResult,
    TableBlock,
    TableCell,
    TableRow,
    TextRun,
    generate_block_id,
    generate_content_hash,
)
from backend.app.logging_config import get_logger
from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

logger = get_logger("app.domains.parsing.parser")


class WordDocumentParser:
    """
    Deterministic parser for Word documents.

    Guarantees:
    - Same input always produces identical output
    - Block ordering matches document structure
    - Stable identifiers for all blocks
    - No semantic interpretation (structure only)
    """

    # Heading style patterns
    HEADING_PATTERNS = [
        re.compile(r"^Heading\s*(\d)$", re.IGNORECASE),
        re.compile(r"^Title$", re.IGNORECASE),
        re.compile(r"^Subtitle$", re.IGNORECASE),
    ]

    # List style patterns
    LIST_STYLE_PATTERNS = [
        re.compile(r"List", re.IGNORECASE),
        re.compile(r"Bullet", re.IGNORECASE),
    ]

    def __init__(self):
        self._sequence = 0
        self._list_buffer: list[ListItem] = []
        self._current_list_style: str | None = None

    def parse(
        self,
        content: bytes,
        template_id: UUID,
        template_version_id: UUID,
        version_number: int,
    ) -> ParsingResult:
        """
        Parse a Word document into structured representation.

        Args:
            content: Raw bytes of the .docx file
            template_id: ID of the parent template
            template_version_id: ID of this template version
            version_number: Version number

        Returns:
            ParsingResult with parsed document or errors
        """
        start_time = time.time()
        errors: list[ParsingError] = []
        warnings: list[str] = []

        # Reset state
        self._sequence = 0
        self._list_buffer = []
        self._current_list_style = None

        try:
            # Generate content hash for determinism verification
            content_hash = generate_content_hash(content)

            # Load document
            doc = Document(io.BytesIO(content))

            # Extract metadata
            metadata = self._extract_metadata(doc)

            # Parse body content
            blocks = self._parse_body(doc, errors, warnings)

            # Parse headers and footers
            headers, footers = self._parse_headers_footers(doc, errors, warnings)

            # Create parsed document
            parsed_doc = ParsedDocument(
                template_version_id=template_version_id,
                template_id=template_id,
                version_number=version_number,
                content_hash=content_hash,
                parsed_at=datetime.utcnow(),
                metadata=metadata,
                blocks=blocks,
                headers=headers,
                footers=footers,
            )

            # Compute statistics
            parsed_doc.compute_statistics()

            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            logger.info(
                f"Parsed document successfully: {parsed_doc.total_blocks} blocks "
                f"({parsed_doc.heading_count} headings, {parsed_doc.paragraph_count} paragraphs, "
                f"{parsed_doc.table_count} tables, {parsed_doc.list_count} lists) in {duration_ms:.2f}ms"
            )

            return ParsingResult(
                success=True,
                document=parsed_doc,
                errors=errors,
                warnings=warnings,
                parse_duration_ms=duration_ms,
                total_duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"Failed to parse document: {e}", exc_info=True)
            errors.append(
                ParsingError(
                    error_type="parse_failure",
                    message=str(e),
                    recoverable=False,
                )
            )

            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000

            return ParsingResult(
                success=False,
                errors=errors,
                warnings=warnings,
                total_duration_ms=duration_ms,
            )

    def _extract_metadata(self, doc: DocxDocument) -> DocumentMetadata:
        """Extract document metadata from core properties."""
        props = doc.core_properties

        return DocumentMetadata(
            title=props.title,
            author=props.author,
            subject=props.subject,
            keywords=props.keywords,
            created=props.created,
            modified=props.modified,
            revision=props.revision,
        )

    def _parse_body(
        self,
        doc: DocxDocument,
        errors: list[ParsingError],
        warnings: list[str],
    ) -> list[DocumentBlock]:
        """
        Parse document body content in order.

        Iterates through the document body XML to maintain exact ordering
        of paragraphs and tables.
        """
        blocks: list[DocumentBlock] = []

        # Get the body element to iterate in document order
        body = doc.element.body

        for element in body.iterchildren():
            try:
                if isinstance(element, CT_P):
                    # Paragraph or heading
                    paragraph = Paragraph(element, doc)
                    block = self._parse_paragraph(paragraph, errors, warnings)
                    if block:
                        # Check if we need to flush list buffer
                        if self._list_buffer and not self._is_list_item(paragraph):
                            list_block = self._flush_list_buffer()
                            if list_block:
                                blocks.append(list_block)

                        # Check if this is a list item
                        if self._is_list_item(paragraph):
                            self._add_to_list_buffer(paragraph)
                        else:
                            blocks.append(block)

                elif isinstance(element, CT_Tbl):
                    # Flush any pending list
                    if self._list_buffer:
                        list_block = self._flush_list_buffer()
                        if list_block:
                            blocks.append(list_block)

                    # Table
                    table = Table(element, doc)
                    block = self._parse_table(table, errors, warnings)
                    if block:
                        blocks.append(block)

            except Exception as e:
                logger.warning(f"Error parsing element at sequence {self._sequence}: {e}")
                errors.append(
                    ParsingError(
                        error_type="element_parse_error",
                        message=str(e),
                        block_index=self._sequence,
                        recoverable=True,
                    )
                )

        # Flush any remaining list buffer
        if self._list_buffer:
            list_block = self._flush_list_buffer()
            if list_block:
                blocks.append(list_block)

        return blocks

    def _parse_paragraph(
        self,
        para: Paragraph,
        _errors: list[ParsingError],
        _warnings: list[str],
    ) -> DocumentBlock | None:
        """Parse a paragraph into a block (paragraph, heading, or list item indicator)."""
        # Skip empty paragraphs without any content
        text = para.text.strip()
        if not text and not para.runs:
            return None

        # Check for page break
        if self._has_page_break(para):
            self._sequence += 1
            return PageBreakBlock(
                block_id=generate_block_id("page_break", self._sequence),
                sequence=self._sequence,
            )

        # Extract text runs
        runs = self._extract_runs(para)

        # Determine block type
        heading_level = self._get_heading_level(para)

        self._sequence += 1

        if heading_level:
            return HeadingBlock(
                block_id=generate_block_id("heading", self._sequence, text[:50]),
                sequence=self._sequence,
                level=heading_level,
                runs=runs,
                alignment=self._get_alignment(para),
                style_name=para.style.name if para.style else None,
            )
        else:
            return ParagraphBlock(
                block_id=generate_block_id("paragraph", self._sequence, text[:50]),
                sequence=self._sequence,
                runs=runs,
                alignment=self._get_alignment(para),
                indent_left=self._get_indent(para, "left"),
                indent_right=self._get_indent(para, "right"),
                indent_first_line=self._get_indent(para, "first_line"),
                spacing_before=self._get_spacing(para, "before"),
                spacing_after=self._get_spacing(para, "after"),
                style_name=para.style.name if para.style else None,
            )

    def _extract_runs(self, para: Paragraph) -> list[TextRun]:
        """Extract text runs with formatting from paragraph."""
        runs: list[TextRun] = []

        for run in para.runs:
            if not run.text:
                continue

            text_run = TextRun(
                text=run.text,
                bold=run.bold or False,
                italic=run.italic or False,
                underline=bool(run.underline),
                strike=run.font.strike or False if run.font else False,
                font_name=run.font.name if run.font else None,
                font_size=run.font.size.pt if run.font and run.font.size else None,
            )

            # Extract color if present
            if run.font and run.font.color and run.font.color.rgb:
                text_run.color = str(run.font.color.rgb)

            runs.append(text_run)

        return runs

    def _get_heading_level(self, para: Paragraph) -> int | None:
        """Determine if paragraph is a heading and return its level."""
        if not para.style:
            return None

        style_name = para.style.name

        # Check for standard heading styles
        for pattern in self.HEADING_PATTERNS:
            match = pattern.match(style_name)
            if match:
                if "Title" in style_name:
                    return 1
                if "Subtitle" in style_name:
                    return 2
                try:
                    return int(match.group(1))
                except (IndexError, ValueError):
                    return 1

        # Check outline level in style
        if hasattr(para.style, "paragraph_format") and para.style.paragraph_format:
            outline_level = para.style.paragraph_format.outline_level
            if outline_level is not None and outline_level < 9:
                return outline_level + 1

        return None

    def _is_list_item(self, para: Paragraph) -> bool:
        """Check if paragraph is a list item."""
        # Check for numbering
        pPr = para._p.pPr
        if pPr is not None:
            numPr = pPr.find(qn("w:numPr"))
            if numPr is not None:
                return True

        # Check style name for list indicators
        if para.style:
            for pattern in self.LIST_STYLE_PATTERNS:
                if pattern.search(para.style.name):
                    return True

        return False

    def _add_to_list_buffer(self, para: Paragraph) -> None:
        """Add a paragraph to the list buffer."""
        runs = self._extract_runs(para)
        text = para.text.strip()

        # Determine list level
        level = 0
        pPr = para._p.pPr
        if pPr is not None:
            numPr = pPr.find(qn("w:numPr"))
            if numPr is not None:
                ilvl = numPr.find(qn("w:ilvl"))
                if ilvl is not None:
                    try:
                        level = int(ilvl.get(qn("w:val")))
                    except (ValueError, TypeError):
                        level = 0

        # Determine list type from style
        style_name = para.style.name if para.style else ""
        if not self._current_list_style:
            if "bullet" in style_name.lower() or "•" in text:
                self._current_list_style = "bullet"
            else:
                self._current_list_style = "numbered"

        item = ListItem(
            item_id=generate_block_id("list_item", len(self._list_buffer), text[:30]),
            level=level,
            runs=runs,
        )

        self._list_buffer.append(item)

    def _flush_list_buffer(self) -> ListBlock | None:
        """Create a ListBlock from the current buffer and reset."""
        if not self._list_buffer:
            return None

        self._sequence += 1
        list_block = ListBlock(
            block_id=generate_block_id("list", self._sequence),
            sequence=self._sequence,
            list_type=self._current_list_style or "bullet",
            items=self._list_buffer.copy(),
        )

        self._list_buffer = []
        self._current_list_style = None

        return list_block

    def _parse_table(
        self,
        table: Table,
        errors: list[ParsingError],
        warnings: list[str],
    ) -> TableBlock | None:
        """Parse a table into a TableBlock."""
        self._sequence += 1

        rows: list[TableRow] = []
        max_cols = 0

        for row_idx, row in enumerate(table.rows):
            cells: list[TableCell] = []

            for col_idx, cell in enumerate(row.cells):
                # Parse cell content as nested blocks
                cell_content = self._parse_cell_content(cell, errors, warnings)

                table_cell = TableCell(
                    cell_id=generate_block_id("cell", row_idx * 100 + col_idx),
                    row_index=row_idx,
                    col_index=col_idx,
                    content=cell_content,
                )

                cells.append(table_cell)

            max_cols = max(max_cols, len(cells))

            table_row = TableRow(
                row_id=generate_block_id("row", row_idx),
                row_index=row_idx,
                cells=cells,
                is_header=row_idx == 0,  # Assume first row is header
            )

            rows.append(table_row)

        return TableBlock(
            block_id=generate_block_id("table", self._sequence),
            sequence=self._sequence,
            rows=rows,
            column_count=max_cols,
        )

    def _parse_cell_content(
        self,
        cell: _Cell,
        _errors: list[ParsingError],
        _warnings: list[str],
    ) -> list[DocumentBlock]:
        """Parse content within a table cell as nested blocks."""
        blocks: list[DocumentBlock] = []

        for para in cell.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            runs = self._extract_runs(para)

            block = ParagraphBlock(
                block_id=generate_block_id("cell_para", len(blocks), text[:30]),
                sequence=len(blocks),
                runs=runs,
                alignment=self._get_alignment(para),
                style_name=para.style.name if para.style else None,
            )

            blocks.append(block)

        return blocks

    def _parse_headers_footers(
        self,
        doc: DocxDocument,
        _errors: list[ParsingError],
        _warnings: list[str],
    ) -> tuple[list[HeaderFooterBlock], list[HeaderFooterBlock]]:
        """Parse document headers and footers."""
        headers: list[HeaderFooterBlock] = []
        footers: list[HeaderFooterBlock] = []

        for section in doc.sections:
            # Parse headers
            for header_type, header in [
                ("default", section.header),
                ("first", section.first_page_header),
                ("even", section.even_page_header),
            ]:
                if header and header.paragraphs:
                    content = []
                    for para in header.paragraphs:
                        text = para.text.strip()
                        if text:
                            runs = self._extract_runs(para)
                            content.append(
                                ParagraphBlock(
                                    block_id=generate_block_id(
                                        "header_para", len(content), text[:30]
                                    ),
                                    sequence=len(content),
                                    runs=runs,
                                )
                            )

                    if content:
                        self._sequence += 1
                        headers.append(
                            HeaderFooterBlock(
                                block_type=BlockType.HEADER,
                                block_id=generate_block_id("header", self._sequence),
                                sequence=self._sequence,
                                header_footer_type=header_type,
                                content=content,
                            )
                        )

            # Parse footers
            for footer_type, footer in [
                ("default", section.footer),
                ("first", section.first_page_footer),
                ("even", section.even_page_footer),
            ]:
                if footer and footer.paragraphs:
                    content = []
                    for para in footer.paragraphs:
                        text = para.text.strip()
                        if text:
                            runs = self._extract_runs(para)
                            content.append(
                                ParagraphBlock(
                                    block_id=generate_block_id(
                                        "footer_para", len(content), text[:30]
                                    ),
                                    sequence=len(content),
                                    runs=runs,
                                )
                            )

                    if content:
                        self._sequence += 1
                        footers.append(
                            HeaderFooterBlock(
                                block_type=BlockType.FOOTER,
                                block_id=generate_block_id("footer", self._sequence),
                                sequence=self._sequence,
                                header_footer_type=footer_type,
                                content=content,
                            )
                        )

        return headers, footers

    def _has_page_break(self, para: Paragraph) -> bool:
        """Check if paragraph contains a page break."""
        for run in para.runs:
            if run._r.xml and "w:br" in run._r.xml and 'w:type="page"' in run._r.xml:
                return True
        return False

    def _get_alignment(self, para: Paragraph) -> str | None:
        """Get paragraph alignment."""
        if para.alignment is None:
            return None
        return str(para.alignment).replace("WD_PARAGRAPH_ALIGNMENT.", "").lower()

    def _get_indent(self, para: Paragraph, indent_type: str) -> float | None:
        """Get paragraph indentation in points."""
        pf = para.paragraph_format
        if not pf:
            return None

        if indent_type == "left" and pf.left_indent:
            return pf.left_indent.pt
        elif indent_type == "right" and pf.right_indent:
            return pf.right_indent.pt
        elif indent_type == "first_line" and pf.first_line_indent:
            return pf.first_line_indent.pt

        return None

    def _get_spacing(self, para: Paragraph, spacing_type: str) -> float | None:
        """Get paragraph spacing in points."""
        pf = para.paragraph_format
        if not pf:
            return None

        if spacing_type == "before" and pf.space_before:
            return pf.space_before.pt
        elif spacing_type == "after" and pf.space_after:
            return pf.space_after.pt

        return None
