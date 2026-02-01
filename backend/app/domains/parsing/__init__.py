"""
Parsing domain module.

This module handles Word document parsing and structure extraction.
"""

from backend.app.domains.parsing.inference import (
    InferenceResult,
    LLMConfig,
    StructureInferenceService,
    StructureSuggestion,
)
from backend.app.domains.parsing.parser import WordDocumentParser
from backend.app.domains.parsing.schemas import (
    BlockType,
    DocumentBlock,
    DocumentMetadata,
    HeaderFooterBlock,
    HeadingBlock,
    ListBlock,
    ListItem,
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
from backend.app.domains.parsing.validator import DocumentValidator, ValidationResult

__all__ = [
    # Schemas
    "ParsedDocument",
    "DocumentBlock",
    "BlockType",
    "ParagraphBlock",
    "HeadingBlock",
    "TableBlock",
    "TableRow",
    "TableCell",
    "ListBlock",
    "ListItem",
    "HeaderFooterBlock",
    "DocumentMetadata",
    "ParsingResult",
    "ParsingError",
    "TextRun",
    "generate_block_id",
    "generate_content_hash",
    # Parser
    "WordDocumentParser",
    # Validator
    "DocumentValidator",
    "ValidationResult",
    # Inference
    "StructureInferenceService",
    "LLMConfig",
    "StructureSuggestion",
    "InferenceResult",
]
