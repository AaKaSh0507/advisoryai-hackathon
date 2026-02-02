import re
from typing import Any

from backend.app.domains.parsing.schemas import (
    BlockType,
    DocumentBlock,
    HeadingBlock,
    ParagraphBlock,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
    SectionClassificationResult,
)
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.section.rule_based_classifier")


class RuleBasedClassifier:
    STATIC_PATTERNS = [
        (
            re.compile(
                r"\b(disclaimer|confidential|privileged|copyright|all rights reserved)\b",
                re.IGNORECASE,
            ),
            0.95,
            "Legal disclaimer or confidentiality notice",
        ),
        (
            re.compile(
                r"\b(this document|prepared by|professional advice|should not be construed)\b",
                re.IGNORECASE,
            ),
            0.92,
            "Standard boilerplate text",
        ),
        (
            re.compile(r"^(page \d+|proprietary|internal use only)", re.IGNORECASE),
            0.95,
            "Fixed header or footer content",
        ),
        (
            re.compile(r"\b(tel:|email:|address:|phone:|fax:)", re.IGNORECASE),
            0.90,
            "Fixed contact information",
        ),
    ]
    DYNAMIC_PATTERNS = [
        (
            re.compile(r"\{[^}]+\}|\[[^\]]+\]|<[^>]+>|\$\{[^}]+\}"),
            0.95,
            "Contains placeholder syntax",
        ),
        (
            re.compile(
                r"\b(to be completed|insert|customize|client-specific|personalized)\b",
                re.IGNORECASE,
            ),
            0.92,
            "Explicit customization marker",
        ),
        (
            re.compile(
                r"\b(client name|company name|project name|date|amount|percentage)\b", re.IGNORECASE
            ),
            0.88,
            "Contains variable references",
        ),
        (
            re.compile(
                r"\b(our analysis|we recommend|specific to|tailored|customized approach)\b",
                re.IGNORECASE,
            ),
            0.85,
            "Client-specific narrative content",
        ),
    ]
    STATIC_STRUCTURAL_INDICATORS = {
        "header": 0.95,
        "footer": 0.95,
        "heading_level_1": 0.70,  # Top-level headings often static
    }

    DYNAMIC_STRUCTURAL_INDICATORS = {
        "short_paragraph_after_heading": 0.75,  # Likely data or customization
        "table_cell": 0.80,  # Tables often contain dynamic data
    }

    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold

    def classify(
        self, block: DocumentBlock, context: dict[str, Any]
    ) -> SectionClassificationResult | None:
        block_id = getattr(block, "block_id", "unknown")
        text = self._extract_text(block)
        for pattern, confidence, reason in self.STATIC_PATTERNS:
            if pattern.search(text):
                return self._create_result(
                    block_id=block_id,
                    section_type="STATIC",
                    confidence=confidence,
                    justification=f"Rule-based: {reason}",
                    metadata={"pattern": pattern.pattern, "text_sample": text[:100]},
                )
        for pattern, confidence, reason in self.DYNAMIC_PATTERNS:
            if pattern.search(text):
                return self._create_result(
                    block_id=block_id,
                    section_type="DYNAMIC",
                    confidence=confidence,
                    justification=f"Rule-based: {reason}",
                    metadata={"pattern": pattern.pattern, "text_sample": text[:100]},
                )
        structural_result = self._check_structural_indicators(block, context)
        if structural_result and structural_result.confidence_score >= self.confidence_threshold:
            return structural_result
        heuristic_result = self._apply_heuristics(block, text, context)
        if heuristic_result and heuristic_result.confidence_score >= self.confidence_threshold:
            return heuristic_result
        logger.debug(f"No confident rule-based classification for block {block_id}")
        return None

    def _check_structural_indicators(
        self, block: DocumentBlock, context: dict[str, Any]
    ) -> SectionClassificationResult | None:
        """Check structural patterns for classification hints."""
        block_id = getattr(block, "block_id", "unknown")
        block_type = getattr(block, "block_type", BlockType.PARAGRAPH)
        if block_type in [BlockType.HEADER, BlockType.FOOTER]:
            return self._create_result(
                block_id=block_id,
                section_type="STATIC",
                confidence=0.95,
                justification="Header or footer block type",
                metadata={"block_type": block_type.value},
            )
        if isinstance(block, HeadingBlock) and block.level == 1:
            return self._create_result(
                block_id=block_id,
                section_type="STATIC",
                confidence=0.70,
                justification="Top-level heading typically structural",
                metadata={"heading_level": block.level},
            )

        return None

    def _apply_heuristics(
        self, block: DocumentBlock, text: str, context: dict[str, Any]
    ) -> SectionClassificationResult | None:
        block_id = getattr(block, "block_id", "unknown")
        if len(text.strip()) < 10:
            return self._create_result(
                block_id=block_id,
                section_type="STATIC",
                confidence=0.75,
                justification="Very short content, likely structural label",
                metadata={"text_length": len(text)},
            )
        if text.isupper() and len(text) < 50:
            return self._create_result(
                block_id=block_id,
                section_type="STATIC",
                confidence=0.80,
                justification="ALL CAPS short text, likely static header",
                metadata={"text_sample": text},
            )
        if isinstance(block, ParagraphBlock) and len(text) > 200:
            word_count = len(text.split())
            if word_count > 50:
                return self._create_result(
                    block_id=block_id,
                    section_type="DYNAMIC",
                    confidence=0.72,
                    justification="Long narrative paragraph, likely client-specific content",
                    metadata={"word_count": word_count},
                )

        return None

    def _extract_text(self, block: DocumentBlock) -> str:
        if hasattr(block, "text"):
            return block.text
        if hasattr(block, "runs"):
            return "".join(run.text for run in block.runs)
        return ""

    def _create_result(
        self,
        block_id: str,
        section_type: str,
        confidence: float,
        justification: str,
        metadata: dict[str, Any],
    ) -> SectionClassificationResult:
        if confidence >= 0.9:
            confidence_level = ClassificationConfidence.HIGH
        elif confidence >= 0.7:
            confidence_level = ClassificationConfidence.MEDIUM
        else:
            confidence_level = ClassificationConfidence.LOW

        return SectionClassificationResult(
            section_id=block_id,
            section_type=section_type,
            confidence_score=confidence,
            confidence_level=confidence_level,
            method=ClassificationMethod.RULE_BASED,
            justification=justification,
            metadata=metadata,
        )
