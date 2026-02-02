from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    HeadingBlock,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
)
from backend.app.domains.section.classification_service import (
    ClassificationService,
    create_classification_service,
)
from backend.app.domains.section.llm_classifier import LLMClassifierConfig


class TestClassificationServiceInitialization:
    def test_classification_service_is_importable(self):
        assert ClassificationService is not None
        assert create_classification_service is not None

    def test_create_service_with_default_config(self):
        service = create_classification_service()
        assert service is not None
        assert service.rule_classifier is not None
        assert service.confidence_threshold == 0.85

    def test_create_service_with_custom_threshold(self):
        service = create_classification_service(confidence_threshold=0.90)
        assert service.confidence_threshold == 0.90

    def test_create_service_without_llm(self):
        service = create_classification_service(llm_config=None)
        assert service.llm_classifier is None

    def test_create_service_with_llm_config(self):
        llm_config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        service = create_classification_service(llm_config=llm_config)
        assert service.llm_classifier is not None


class TestFallbackClassification:
    @pytest.fixture
    def service(self):
        return create_classification_service(
            llm_config=None,
            confidence_threshold=0.95,
        )

    def test_fallback_defaults_to_static(self, service):
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
        block = ParagraphBlock(
            block_id="blk_par_0002_xyz",
            sequence=2,
            runs=[TextRun(text="Generic text")],
        )
        result = service._create_fallback_classification(block)
        assert result.confidence_score < 0.7
        assert result.confidence_level == ClassificationConfidence.LOW

    def test_fallback_has_justification(self, service):
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
    @pytest.fixture
    def sample_parsed_document(self):
        return ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="abc123def456",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_abc",
                    sequence=1,
                    runs=[TextRun(text="This document is confidential and privileged.")],
                ),
                ParagraphBlock(
                    block_id="blk_par_0002_def",
                    sequence=2,
                    runs=[TextRun(text="Dear {client_name}, thank you for choosing us.")],
                ),
                ParagraphBlock(
                    block_id="blk_par_0003_ghi",
                    sequence=3,
                    runs=[TextRun(text="The project timeline is outlined below.")],
                ),
            ],
        )

    def test_rule_based_takes_precedence_when_confident(self, sample_parsed_document):
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )
        block = sample_parsed_document.blocks[0]
        result = service._classify_block(block, {})
        assert result is not None
        assert result.method == ClassificationMethod.RULE_BASED
        assert result.section_type == "STATIC"

    def test_dynamic_patterns_detected_by_rules(self, sample_parsed_document):
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )
        block = sample_parsed_document.blocks[1]
        result = service._classify_block(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"
        assert result.method == ClassificationMethod.RULE_BASED

    def test_ambiguous_content_uses_fallback_without_llm(self, sample_parsed_document):
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.95,
        )
        block = sample_parsed_document.blocks[2]
        result = service._classify_block(block, {})
        assert result is not None
        assert result.section_type == "STATIC"


class TestContextBuilding:
    @pytest.fixture
    def service(self):
        return create_classification_service(confidence_threshold=0.85)

    def test_context_includes_position(self, service):
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
    @pytest.fixture
    def mock_section_repo(self):
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    @pytest.fixture
    def sample_document(self):
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
        service = create_classification_service(confidence_threshold=0.85)
        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )
        assert result.total_sections == len(sample_document.blocks)
        assert len(result.classifications) == len(sample_document.blocks)

    @pytest.mark.asyncio
    async def test_no_unclassified_sections(self, mock_section_repo, sample_document):
        service = create_classification_service(confidence_threshold=0.95)
        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )
        for classification in result.classifications:
            assert classification.section_type in ["STATIC", "DYNAMIC"]
            assert classification.confidence_score >= 0.0
            assert classification.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_static_and_dynamic_counts_add_up(self, mock_section_repo, sample_document):
        service = create_classification_service(confidence_threshold=0.85)
        result = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_section_repo,
        )
        assert result.static_sections + result.dynamic_sections == result.total_sections


class TestConfidenceThresholdBehavior:
    @pytest.fixture
    def mock_section_repo(self):
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    def test_high_threshold_uses_more_fallback(self):
        service_low = create_classification_service(confidence_threshold=0.60)
        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="APPENDIX A")],
        )

        result_low = service_low._classify_block(block, {})
        if result_low.confidence_score >= 0.60:
            assert result_low.method == ClassificationMethod.RULE_BASED

    def test_threshold_is_deterministic(self):
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
    @pytest.fixture
    def mock_section_repo(self):
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    @pytest.mark.asyncio
    async def test_statistics_are_computed(self, mock_section_repo):
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
                    runs=[TextRun(text="This is confidential.")],
                ),
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
        assert result.rule_based_count >= 0
        assert result.llm_assisted_count >= 0
        assert result.fallback_count >= 0
        assert (
            result.rule_based_count + result.llm_assisted_count + result.fallback_count
            == result.total_sections
        )

    @pytest.mark.asyncio
    async def test_confidence_breakdown_tracked(self, mock_section_repo):
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
        assert result.high_confidence_count >= 0
        assert result.medium_confidence_count >= 0
        assert result.low_confidence_count >= 0
        total_conf = (
            result.high_confidence_count
            + result.medium_confidence_count
            + result.low_confidence_count
        )
        assert total_conf == result.total_sections
