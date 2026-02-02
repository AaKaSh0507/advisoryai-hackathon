import pytest

from backend.app.domains.parsing.schemas import (
    BlockType,
    HeaderFooterBlock,
    HeadingBlock,
    ParagraphBlock,
    TextRun,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
)
from backend.app.domains.section.rule_based_classifier import RuleBasedClassifier


class TestRuleBasedClassifierInitialization:
    def test_classifier_is_importable(self):
        classifier = RuleBasedClassifier()
        assert classifier is not None

    def test_classifier_has_default_confidence_threshold(self):
        classifier = RuleBasedClassifier()
        assert classifier.confidence_threshold == 0.85

    def test_classifier_accepts_custom_threshold(self):
        classifier = RuleBasedClassifier(confidence_threshold=0.90)
        assert classifier.confidence_threshold == 0.90


class TestStaticPatternClassification:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.85)

    def test_legal_disclaimer_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0001_abc123",
            sequence=1,
            runs=[TextRun(text="This document contains confidential and privileged information.")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.90
        assert result.method == ClassificationMethod.RULE_BASED
        assert (
            "confidential" in result.justification.lower()
            or "legal" in result.justification.lower()
        )

    def test_copyright_notice_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0002_def456",
            sequence=2,
            runs=[TextRun(text="© 2026 Advisory Corp. All Rights Reserved.")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.90

    def test_boilerplate_text_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0003_ghi789",
            sequence=3,
            runs=[TextRun(text="This document was prepared by our professional advisory team.")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.85

    def test_contact_information_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0004_jkl012",
            sequence=4,
            runs=[TextRun(text="Tel: +1-555-0123 | Email: info@advisory.com")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.85

    def test_page_number_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0005_mno345",
            sequence=5,
            runs=[TextRun(text="Page 1 of 10")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.90

    def test_internal_use_only_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0006_pqr678",
            sequence=6,
            runs=[TextRun(text="INTERNAL USE ONLY - PROPRIETARY")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"


class TestDynamicPatternClassification:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.85)

    def test_placeholder_curly_braces_classified_as_dynamic(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0010_abc123",
            sequence=10,
            runs=[TextRun(text="Dear {client_name}, we are pleased to present...")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"
        assert result.confidence_score >= 0.90
        assert result.method == ClassificationMethod.RULE_BASED

    def test_placeholder_square_brackets_classified_as_dynamic(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0011_def456",
            sequence=11,
            runs=[TextRun(text="Project Duration: [INSERT DURATION]")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"
        assert result.confidence_score >= 0.90

    def test_placeholder_angle_brackets_classified_as_dynamic(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0012_ghi789",
            sequence=12,
            runs=[TextRun(text="Amount: <amount_value> USD")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"

    def test_explicit_customization_marker_classified_as_dynamic(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0013_jkl012",
            sequence=13,
            runs=[TextRun(text="[To be completed by advisor based on client requirements]")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"
        assert result.confidence_score >= 0.85

    def test_client_specific_reference_classified_as_dynamic(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0014_mno345",
            sequence=14,
            runs=[TextRun(text="Based on our analysis for Client Name, we recommend...")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"

    def test_narrative_recommendation_classified_as_dynamic(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0015_pqr678",
            sequence=15,
            runs=[TextRun(text="Our analysis indicates that we recommend a tailored approach...")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"


class TestStructuralIndicatorClassification:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.70)

    def test_header_block_classified_as_static(self, classifier):
        block = HeaderFooterBlock(
            block_type=BlockType.HEADER,
            block_id="blk_hdr_0001_xyz",
            sequence=0,
            header_footer_type="default",
            content=[],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.90

    def test_footer_block_classified_as_static(self, classifier):
        block = HeaderFooterBlock(
            block_type=BlockType.FOOTER,
            block_id="blk_ftr_0001_xyz",
            sequence=0,
            header_footer_type="default",
            content=[],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"
        assert result.confidence_score >= 0.90

    def test_level_one_heading_classified_as_static(self, classifier):
        block = HeadingBlock(
            block_id="blk_hdg_0001_abc",
            sequence=1,
            level=1,
            runs=[TextRun(text="Executive Summary")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"


class TestContentHeuristicClassification:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.70)

    def test_very_short_content_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0020_abc",
            sequence=20,
            runs=[TextRun(text="Proprietary")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"

    def test_all_caps_short_text_classified_as_static(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0021_def",
            sequence=21,
            runs=[TextRun(text="APPENDIX A")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "STATIC"

    def test_long_narrative_classified_as_dynamic(self, classifier):
        long_text = (
            "Based on our comprehensive analysis of the current market conditions and "
            "the specific requirements outlined by the client, we have developed a "
            "tailored strategy that addresses the key challenges identified during "
            "our initial assessment. The recommended approach takes into consideration "
            "the unique circumstances of the engagement and provides actionable insights "
            "that can be implemented in phases to achieve optimal results."
        )
        block = ParagraphBlock(
            block_id="blk_par_0022_ghi",
            sequence=22,
            runs=[TextRun(text=long_text)],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.section_type == "DYNAMIC"


class TestClassificationDeterminism:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.85)

    def test_same_input_produces_identical_results(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0030_xyz",
            sequence=30,
            runs=[TextRun(text="This document is confidential and privileged.")],
        )
        result1 = classifier.classify(block, {})
        result2 = classifier.classify(block, {})
        result3 = classifier.classify(block, {})
        assert result1.section_type == result2.section_type == result3.section_type
        assert result1.confidence_score == result2.confidence_score == result3.confidence_score
        assert result1.method == result2.method == result3.method
        assert result1.section_id == result2.section_id == result3.section_id

    def test_different_blocks_same_content_consistent(self, classifier):
        content = "All rights reserved. Copyright 2026."
        block1 = ParagraphBlock(
            block_id="blk_par_0031_aaa",
            sequence=31,
            runs=[TextRun(text=content)],
        )
        block2 = ParagraphBlock(
            block_id="blk_par_0032_bbb",
            sequence=32,
            runs=[TextRun(text=content)],
        )
        result1 = classifier.classify(block1, {})
        result2 = classifier.classify(block2, {})
        assert result1.section_type == result2.section_type
        assert result1.confidence_score == result2.confidence_score

    def test_classification_order_does_not_matter(self, classifier):
        blocks = [
            ParagraphBlock(
                block_id=f"blk_par_{i:04d}_xyz",
                sequence=i,
                runs=[TextRun(text="This is confidential information.")],
            )
            for i in range(5)
        ]
        results_forward = [classifier.classify(b, {}) for b in blocks]
        results_reverse = [classifier.classify(b, {}) for b in reversed(blocks)]
        results_reverse.reverse()
        for r1, r2 in zip(results_forward, results_reverse):
            assert r1.section_type == r2.section_type
            assert r1.confidence_score == r2.confidence_score


class TestNoMatchReturnsNone:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.90)

    def test_ambiguous_content_returns_none(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0040_xyz",
            sequence=40,
            runs=[TextRun(text="The meeting was held on Tuesday afternoon.")],
        )

        result = classifier.classify(block, {})
        if result is not None:
            assert result.confidence_score < 0.90

    def test_generic_paragraph_not_confidently_classified(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0041_xyz",
            sequence=41,
            runs=[TextRun(text="The weather was sunny and the team enjoyed the outdoor event.")],
        )
        result = classifier.classify(block, {})
        if result is not None:
            assert result.confidence_score < 0.90


class TestConfidenceLevels:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier(confidence_threshold=0.70)

    def test_high_confidence_level_assignment(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0050_xyz",
            sequence=50,
            runs=[TextRun(text="CONFIDENTIAL - All rights reserved")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        if result.confidence_score >= 0.9:
            assert result.confidence_level == ClassificationConfidence.HIGH

    def test_medium_confidence_level_assignment(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0051_xyz",
            sequence=51,
            runs=[TextRun(text="APPENDIX")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        if 0.7 <= result.confidence_score < 0.9:
            assert result.confidence_level == ClassificationConfidence.MEDIUM

    def test_classification_result_has_justification(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0052_xyz",
            sequence=52,
            runs=[TextRun(text="This is confidential information.")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.justification is not None
        assert len(result.justification) > 0

    def test_classification_result_has_metadata(self, classifier):
        block = ParagraphBlock(
            block_id="blk_par_0053_xyz",
            sequence=53,
            runs=[TextRun(text="Copyright 2026 - All rights reserved.")],
        )
        result = classifier.classify(block, {})
        assert result is not None
        assert result.metadata is not None
        assert isinstance(result.metadata, dict)
