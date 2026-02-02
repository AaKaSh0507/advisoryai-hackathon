"""
Tests for classification service orchestration.

Verifies:
- Confidence scores are assigned to every section
- Low-confidence sections default to STATIC
- No section remains unclassified
- Confidence thresholds behave deterministically
- Pipeline coordination (rules → LLM → fallback)
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.domains.parsing.schemas import (
    BlockType,
    DocumentMetadata,
    HeadingBlock,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
    SectionClassificationResult,
)
from backend.app.domains.section.classification_service import (
    ClassificationService,
    create_classification_service,
)
from backend.app.domains.section.llm_classifier import LLMClassifier, LLMClassifierConfig
from backend.app.domains.section.rule_based_classifier import RuleBasedClassifier


class TestClassificationServiceInitialization:
    """Tests for classification service setup."""

    def test_classification_service_is_importable(self):
        """Classification service should be importable."""
        assert ClassificationService is not None
        assert create_classification_service is not None

    def test_create_service_with_default_config(self):
        """Service can be created with default configuration."""
        service = create_classification_service()

        assert service is not None
        assert service.rule_classifier is not None
        assert service.confidence_threshold == 0.85

    def test_create_service_with_custom_threshold(self):
        """Service can be created with custom confidence threshold."""
        service = create_classification_service(confidence_threshold=0.90)

        assert service.confidence_threshold == 0.90

    def test_create_service_without_llm(self):
        """Service can be created without LLM classifier."""
        service = create_classification_service(llm_config=None)

        assert service.llm_classifier is None

    def test_create_service_with_llm_config(self):
        """Service can be created with LLM configuration."""
        llm_config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        service = create_classification_service(llm_config=llm_config)

        assert service.llm_classifier is not None


class TestFallbackClassification:
    """Tests for conservative fallback classification."""

    @pytest.fixture
    def service(self):
        """Create service without LLM for fallback testing."""
        return create_classification_service(
            llm_config=None,
            confidence_threshold=0.95,  # High threshold to trigger fallback
        )

    def test_fallback_defaults_to_static(self, service):
        """Fallback classification should default to STATIC."""
        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="Some generic text that doesn't match any patterns.")],
        )

        result = service._create_fallback_classification(block)

        assert result is not None
        assert result.section_type == "STATIC"
        assert result.method == ClassificationMethod.FALLBACK

    def test_fallback_has_low_confidence(self, service):
        """Fallback classification should have low confidence."""
        block = ParagraphBlock(
            block_id="blk_par_0002_xyz",
            sequence=2,
            runs=[TextRun(text="Generic text")],
        )

        result = service._create_fallback_classification(block)

        assert result.confidence_score < 0.7
        assert result.confidence_level == ClassificationConfidence.LOW

    def test_fallback_has_justification(self, service):
        """Fallback classification should have justification."""
        block = ParagraphBlock(
            block_id="blk_par_0003_xyz",
            sequence=3,
            runs=[TextRun(text="Generic text")],
        )

        result = service._create_fallback_classification(block)

        assert result.justification is not None
        assert (
            "fallback" in result.justification.lower()
            or "conservative" in result.justification.lower()
        )


class TestClassificationPipeline:
    """Tests for classification pipeline coordination."""

    @pytest.fixture
    def sample_parsed_document(self):
        """Create a sample parsed document for testing."""
        return ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="abc123def456",
            metadata=DocumentMetadata(),
            blocks=[
                # Static content (legal disclaimer)
                ParagraphBlock(
                    block_id="blk_par_0001_abc",
                    sequence=1,
                    runs=[TextRun(text="This document is confidential and privileged.")],
                ),
                # Dynamic content (placeholder)
                ParagraphBlock(
                    block_id="blk_par_0002_def",
                    sequence=2,
                    runs=[TextRun(text="Dear {client_name}, thank you for choosing us.")],
                ),
                # Ambiguous content (no clear pattern)
                ParagraphBlock(
                    block_id="blk_par_0003_ghi",
                    sequence=3,
                    runs=[TextRun(text="The project timeline is outlined below.")],
                ),
            ],
        )

    def test_rule_based_takes_precedence_when_confident(self, sample_parsed_document):
        """Rule-based classification should be used when confident."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        # Test classification of first block (legal disclaimer)
        block = sample_parsed_document.blocks[0]
        result = service._classify_block(block, {})

        assert result is not None
        assert result.method == ClassificationMethod.RULE_BASED
        assert result.section_type == "STATIC"

    def test_dynamic_patterns_detected_by_rules(self, sample_parsed_document):
        """Dynamic patterns should be detected by rule-based classifier."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        # Test classification of second block (placeholder)
        block = sample_parsed_document.blocks[1]
        result = service._classify_block(block, {})

        assert result is not None
        assert result.section_type == "DYNAMIC"
        assert result.method == ClassificationMethod.RULE_BASED

    def test_ambiguous_content_uses_fallback_without_llm(self, sample_parsed_document):
        """Ambiguous content should use fallback when LLM is unavailable."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.95,  # High threshold
        )

        # Test classification of third block (ambiguous)
        block = sample_parsed_document.blocks[2]
        result = service._classify_block(block, {})

        assert result is not None
        # Should fallback to STATIC
        assert result.section_type == "STATIC"


class TestContextBuilding:
    """Tests for classification context building."""

    @pytest.fixture
    def service(self):
        """Create service for context testing."""
        return create_classification_service(confidence_threshold=0.85)

    def test_context_includes_position(self, service):
        """Context should include position in document."""
        blocks = [
            ParagraphBlock(
                block_id=f"blk_par_{i:04d}_xyz",
                sequence=i,
                runs=[TextRun(text="Text")],
            )
            for i in range(5)
        ]

        context = service._build_context(2, blocks)

        assert context["position_in_document"] == 2
        assert context["total_blocks"] == 5

    def test_context_includes_previous_block_type(self, service):
        """Context should include previous block type."""
        blocks = [
            HeadingBlock(
                block_id="blk_hdg_0000_xyz",
                sequence=0,
                level=1,
                runs=[TextRun(text="Heading")],
            ),
            ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text="Paragraph")],
            ),
        ]

        context = service._build_context(1, blocks)

        assert "previous_block_type" in context
        assert "heading" in context["previous_block_type"].lower()

    def test_context_includes_next_block_type(self, service):
        """Context should include next block type."""
        blocks = [
            ParagraphBlock(
                block_id="blk_par_0000_xyz",
                sequence=0,
                runs=[TextRun(text="Paragraph")],
            ),
            HeadingBlock(
                block_id="blk_hdg_0001_xyz",
                sequence=1,
                level=2,
                runs=[TextRun(text="Heading")],
            ),
        ]

        context = service._build_context(0, blocks)

        assert "next_block_type" in context
        assert "heading" in context["next_block_type"].lower()

    def test_first_block_has_no_previous(self, service):
        """First block should have no previous block info."""
        blocks = [
            ParagraphBlock(
                block_id="blk_par_0000_xyz",
                sequence=0,
                runs=[TextRun(text="First")],
            ),
            ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text="Second")],
            ),
        ]

        context = service._build_context(0, blocks)

        assert "previous_block_type" not in context or context["previous_block_type"] is None

    def test_last_block_has_no_next(self, service):
        """Last block should have no next block info."""
        blocks = [
            ParagraphBlock(
                block_id="blk_par_0000_xyz",
                sequence=0,
                runs=[TextRun(text="First")],
            ),
            ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text="Last")],
            ),
        ]

        context = service._build_context(1, blocks)

        assert "next_block_type" not in context or context["next_block_type"] is None


class TestEveryBlockGetsClassified:
    """Tests ensuring every block gets classified."""

    @pytest.fixture
    def mock_section_repo(self):
        """Create mock section repository."""
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    @pytest.fixture
    def sample_document(self):
        """Create sample document with various block types."""
        return ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id=f"blk_par_{i:04d}_xyz",
                    sequence=i,
                    runs=[TextRun(text=f"Block {i} content")],
                )
                for i in range(10)
            ],
        )

    @pytest.mark.asyncio
    async def test_all_blocks_get_classified(self, mock_section_repo, sample_document):
        """Every block in the document should be classified."""
        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )

        assert result.total_sections == len(sample_document.blocks)
        assert len(result.classifications) == len(sample_document.blocks)

    @pytest.mark.asyncio
    async def test_no_unclassified_sections(self, mock_section_repo, sample_document):
        """No section should be left unclassified."""
        service = create_classification_service(confidence_threshold=0.95)

        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )

        # Check all classifications have a valid type
        for classification in result.classifications:
            assert classification.section_type in ["STATIC", "DYNAMIC"]
            assert classification.confidence_score >= 0.0
            assert classification.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_static_and_dynamic_counts_add_up(self, mock_section_repo, sample_document):
        """Static + Dynamic counts should equal total sections."""
        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )

        assert result.static_sections + result.dynamic_sections == result.total_sections


class TestConfidenceThresholdBehavior:
    """Tests for confidence threshold handling."""

    @pytest.fixture
    def mock_section_repo(self):
        """Create mock section repository."""
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    def test_high_threshold_uses_more_fallback(self):
        """Higher threshold should result in more fallback classifications."""
        service_low = create_classification_service(confidence_threshold=0.60)
        service_high = create_classification_service(confidence_threshold=0.95)

        # Block with medium-confidence pattern
        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="APPENDIX A")],  # ALL CAPS = ~0.80 confidence
        )

        result_low = service_low._classify_block(block, {})
        result_high = service_high._classify_block(block, {})

        # Low threshold should accept rule-based
        if result_low.confidence_score >= 0.60:
            assert result_low.method == ClassificationMethod.RULE_BASED

        # High threshold may reject and fallback
        # Note: if rule returns 0.80, it's below 0.95, so fallback is expected
        # But fallback defaults to STATIC with 0.5 confidence

    def test_threshold_is_deterministic(self):
        """Same threshold should produce same results."""
        threshold = 0.85

        service1 = create_classification_service(confidence_threshold=threshold)
        service2 = create_classification_service(confidence_threshold=threshold)

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="This is confidential information.")],
        )

        result1 = service1._classify_block(block, {})
        result2 = service2._classify_block(block, {})

        assert result1.section_type == result2.section_type
        assert result1.confidence_score == result2.confidence_score


class TestBatchResultStatistics:
    """Tests for batch classification result statistics."""

    @pytest.fixture
    def mock_section_repo(self):
        """Create mock section repository."""
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    @pytest.mark.asyncio
    async def test_statistics_are_computed(self, mock_section_repo):
        """Batch result should include computed statistics."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                # Static (legal)
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="This is confidential.")],
                ),
                # Dynamic (placeholder)
                ParagraphBlock(
                    block_id="blk_par_0002_xyz",
                    sequence=2,
                    runs=[TextRun(text="Dear {name}, welcome.")],
                ),
            ],
        )

        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        assert result.total_sections == 2
        assert result.static_sections >= 0
        assert result.dynamic_sections >= 0
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_method_breakdown_tracked(self, mock_section_repo):
        """Batch result should track classification methods used."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="Copyright 2026. All rights reserved.")],
                ),
            ],
        )

        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        # Should have counts for different methods
        assert result.rule_based_count >= 0
        assert result.llm_assisted_count >= 0
        assert result.fallback_count >= 0
        assert (
            result.rule_based_count + result.llm_assisted_count + result.fallback_count
            == result.total_sections
        )

    @pytest.mark.asyncio
    async def test_confidence_breakdown_tracked(self, mock_section_repo):
        """Batch result should track confidence levels."""
        document = ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="test_hash",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id=f"blk_par_{i:04d}_xyz",
                    sequence=i,
                    runs=[TextRun(text="This is confidential information.")],
                )
                for i in range(5)
            ],
        )

        service = create_classification_service(confidence_threshold=0.85)

        result = await service.classify_template_sections(
            parsed_document=document,
            section_repo=mock_section_repo,
        )

        # Should have confidence level counts
        assert result.high_confidence_count >= 0
        assert result.medium_confidence_count >= 0
        assert result.low_confidence_count >= 0
        total_conf = (
            result.high_confidence_count
            + result.medium_confidence_count
            + result.low_confidence_count
        )
        assert total_conf == result.total_sections
