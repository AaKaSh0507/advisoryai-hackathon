"""
Tests for classification determinism and idempotency.

Verifies:
- Same input yields identical classification results
- No randomness in classification decisions
- Repeated classifications produce same output
- Order of blocks does not affect individual classifications
"""

import hashlib
from datetime import datetime
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
from backend.app.domains.section.rule_based_classifier import RuleBasedClassifier


class TestRuleBasedDeterminism:
    """Tests for rule-based classifier determinism."""

    @pytest.fixture
    def classifier(self):
        """Create rule-based classifier."""
        return RuleBasedClassifier()

    @pytest.fixture
    def sample_blocks(self):
        """Create sample blocks for testing."""
        return [
            # Static - legal
            ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text="This document is confidential and privileged.")],
            ),
            # Dynamic - placeholder
            ParagraphBlock(
                block_id="blk_par_0002_xyz",
                sequence=2,
                runs=[TextRun(text="Dear {client_name}, thank you for choosing us.")],
            ),
            # Static - copyright
            ParagraphBlock(
                block_id="blk_par_0003_xyz",
                sequence=3,
                runs=[TextRun(text="Copyright 2024. All rights reserved.")],
            ),
        ]

    def test_same_block_same_result_multiple_times(self, classifier, sample_blocks):
        """Same block should produce same result across multiple classifications."""
        block = sample_blocks[0]

        results = []
        for _ in range(10):
            result = classifier.classify(block, {})
            results.append(result)

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result.section_type == first_result.section_type
            assert result.confidence_score == first_result.confidence_score
            assert result.method == first_result.method

    def test_different_blocks_classified_consistently(self, classifier, sample_blocks):
        """Different blocks should be classified consistently across runs."""
        for _ in range(5):
            for block in sample_blocks:
                result1 = classifier.classify(block, {})
                result2 = classifier.classify(block, {})

                assert result1.section_type == result2.section_type
                assert result1.confidence_score == result2.confidence_score

    def test_classifier_is_stateless(self, classifier, sample_blocks):
        """Classifier should be stateless - order doesn't affect results."""
        # Classify in original order
        results_forward = [classifier.classify(b, {}) for b in sample_blocks]

        # Classify in reverse order
        results_reverse = [classifier.classify(b, {}) for b in reversed(sample_blocks)]
        results_reverse.reverse()  # Put back in original order for comparison

        # Results should be identical regardless of order
        for r1, r2 in zip(results_forward, results_reverse):
            assert r1.section_type == r2.section_type
            assert r1.confidence_score == r2.confidence_score

    def test_new_classifier_instance_same_results(self, sample_blocks):
        """New classifier instances should produce same results."""
        classifier1 = RuleBasedClassifier()
        classifier2 = RuleBasedClassifier()

        for block in sample_blocks:
            result1 = classifier1.classify(block, {})
            result2 = classifier2.classify(block, {})

            assert result1.section_type == result2.section_type
            assert result1.confidence_score == result2.confidence_score


class TestServiceDeterminism:
    """Tests for classification service determinism."""

    @pytest.fixture
    def mock_section_repo(self):
        """Create mock section repository."""
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        return mock_repo

    @pytest.fixture
    def sample_document(self):
        """Create sample document."""
        return ParsedDocument(
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
                    runs=[TextRun(text="Dear {name}")],
                ),
                ParagraphBlock(
                    block_id="blk_par_0003_xyz",
                    sequence=3,
                    runs=[TextRun(text="Copyright 2024.")],
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_service_produces_identical_results(self, mock_section_repo, sample_document):
        """Service should produce identical results for same input."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        # Create fresh mock for each call
        mock_repo1 = MagicMock()
        mock_repo1.create_batch = AsyncMock(return_value=[])

        mock_repo2 = MagicMock()
        mock_repo2.create_batch = AsyncMock(return_value=[])

        result1 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo1,
        )

        result2 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo2,
        )

        # Statistics should be identical
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections
        assert result1.rule_based_count == result2.rule_based_count

    @pytest.mark.asyncio
    async def test_classifications_match_exactly(self, sample_document):
        """Individual classifications should match exactly."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        mock_repo1 = MagicMock()
        mock_repo1.create_batch = AsyncMock(return_value=[])

        mock_repo2 = MagicMock()
        mock_repo2.create_batch = AsyncMock(return_value=[])

        result1 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo1,
        )

        result2 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo2,
        )

        # Each classification should match
        for c1, c2 in zip(result1.classifications, result2.classifications):
            assert c1.section_id == c2.section_id
            assert c1.section_type == c2.section_type
            assert c1.confidence_score == c2.confidence_score
            assert c1.method == c2.method


class TestContentHashDeterminism:
    """Tests for content hash determinism."""

    def test_same_content_same_hash(self):
        """Same content should produce same hash."""
        content = "This is confidential and privileged."

        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()

        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Different content should produce different hash."""
        content1 = "This is confidential."
        content2 = "This is not confidential."

        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        assert hash1 != hash2


class TestIdempotentClassification:
    """Tests for idempotent classification behavior."""

    @pytest.fixture
    def sample_document(self):
        """Create sample document."""
        template_version_id = uuid4()
        return ParsedDocument(
            template_version_id=template_version_id,
            template_id=uuid4(),
            version_number=1,
            content_hash="fixed_hash_for_test",
            metadata=DocumentMetadata(),
            blocks=[
                ParagraphBlock(
                    block_id="blk_par_0001_xyz",
                    sequence=1,
                    runs=[TextRun(text="CONFIDENTIAL")],
                ),
                ParagraphBlock(
                    block_id="blk_par_0002_xyz",
                    sequence=2,
                    runs=[TextRun(text="{customer_name}")],
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_idempotent_classification_no_state_change(self, sample_document):
        """Classification should be idempotent - no state change on repeated runs."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])

        # First classification
        result1 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo,
        )

        # Second classification (simulating re-run)
        mock_repo2 = MagicMock()
        mock_repo2.create_batch = AsyncMock(return_value=[])

        result2 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo2,
        )

        # Results should be functionally identical
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections

    def test_block_classification_is_pure_function(self):
        """Block classification should be a pure function."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="This is confidential and privileged.")],
        )

        # Same input should always produce same output
        context = {}

        result1 = service._classify_block(block, context)
        result2 = service._classify_block(block, context)
        result3 = service._classify_block(block, context)

        assert result1.section_type == result2.section_type == result3.section_type
        assert result1.confidence_score == result2.confidence_score == result3.confidence_score


class TestNoRandomness:
    """Tests ensuring no randomness in classification."""

    def test_confidence_scores_are_deterministic(self):
        """Confidence scores should be deterministic."""
        classifier = RuleBasedClassifier()

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="Dear {client_name}, thank you.")],
        )

        scores = []
        for _ in range(100):
            result = classifier.classify(block, {})
            scores.append(result.confidence_score)

        # All scores should be identical
        assert len(set(scores)) == 1

    def test_section_types_are_deterministic(self):
        """Section types should be deterministic."""
        classifier = RuleBasedClassifier()

        blocks = [
            ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text="CONFIDENTIAL")],
            ),
            ParagraphBlock(
                block_id="blk_par_0002_xyz",
                sequence=2,
                runs=[TextRun(text="{variable}")],
            ),
        ]

        for block in blocks:
            types = []
            for _ in range(50):
                result = classifier.classify(block, {})
                types.append(result.section_type)

            # All types should be identical
            assert len(set(types)) == 1

    def test_method_attribution_is_deterministic(self):
        """Method attribution should be deterministic."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="Copyright 2024. All rights reserved.")],
        )

        methods = []
        for _ in range(20):
            result = service._classify_block(block, {})
            methods.append(result.method)

        # All methods should be identical
        assert len(set(methods)) == 1


class TestPatternMatchingDeterminism:
    """Tests for pattern matching determinism."""

    def test_static_patterns_match_consistently(self):
        """Static patterns should match consistently."""
        classifier = RuleBasedClassifier()

        # Use patterns that are clearly identified as STATIC
        static_texts = [
            "This document is confidential.",
            "Copyright 2024. All rights reserved.",
            "DISCLAIMER: This content is privileged.",
        ]

        for text in static_texts:
            block = ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text=text)],
            )

            results = [classifier.classify(block, {}) for _ in range(10)]

            # All results should be non-None and same type
            assert all(r is not None for r in results), f"Pattern '{text}' should match STATIC"
            types = [r.section_type for r in results]

            # All should be the same
            assert len(set(types)) == 1

    def test_dynamic_patterns_match_consistently(self):
        """Dynamic patterns should match consistently."""
        classifier = RuleBasedClassifier()

        dynamic_texts = [
            "Dear {client_name}",
            "{{company_address}}",
            "[INSERT_DATE]",
            "<<customer_id>>",
        ]

        for text in dynamic_texts:
            block = ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text=text)],
            )

            results = [classifier.classify(block, {}) for _ in range(10)]
            types = [r.section_type for r in results]

            # All should be DYNAMIC
            assert all(t == "DYNAMIC" for t in types)


class TestBatchProcessingDeterminism:
    """Tests for batch processing determinism."""

    @pytest.fixture
    def large_document(self):
        """Create larger document for batch testing."""
        blocks = []
        for i in range(50):
            if i % 3 == 0:
                text = f"Section {i}: This is confidential information."
            elif i % 3 == 1:
                text = f"Section {i}: Dear {{customer_{i}}}"
            else:
                text = f"Section {i}: General content about topic {i}."

            blocks.append(
                ParagraphBlock(
                    block_id=f"blk_par_{i:04d}_xyz",
                    sequence=i,
                    runs=[TextRun(text=text)],
                )
            )

        return ParsedDocument(
            template_version_id=uuid4(),
            template_id=uuid4(),
            version_number=1,
            content_hash="large_doc_hash",
            metadata=DocumentMetadata(),
            blocks=blocks,
        )

    @pytest.mark.asyncio
    async def test_batch_results_are_deterministic(self, large_document):
        """Batch processing should produce deterministic results."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        mock_repo1 = MagicMock()
        mock_repo1.create_batch = AsyncMock(return_value=[])

        mock_repo2 = MagicMock()
        mock_repo2.create_batch = AsyncMock(return_value=[])

        result1 = await service.classify_template_sections(
            parsed_document=large_document,
            section_repo=mock_repo1,
        )

        result2 = await service.classify_template_sections(
            parsed_document=large_document,
            section_repo=mock_repo2,
        )

        # All statistics should match
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections
        assert result1.rule_based_count == result2.rule_based_count
        assert result1.llm_assisted_count == result2.llm_assisted_count
        assert result1.fallback_count == result2.fallback_count
        assert result1.high_confidence_count == result2.high_confidence_count
        assert result1.medium_confidence_count == result2.medium_confidence_count
        assert result1.low_confidence_count == result2.low_confidence_count

    @pytest.mark.asyncio
    async def test_all_classifications_match_in_batch(self, large_document):
        """All individual classifications in batch should match."""
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )

        mock_repo1 = MagicMock()
        mock_repo1.create_batch = AsyncMock(return_value=[])

        mock_repo2 = MagicMock()
        mock_repo2.create_batch = AsyncMock(return_value=[])

        result1 = await service.classify_template_sections(
            parsed_document=large_document,
            section_repo=mock_repo1,
        )

        result2 = await service.classify_template_sections(
            parsed_document=large_document,
            section_repo=mock_repo2,
        )

        # Every classification should match
        for c1, c2 in zip(result1.classifications, result2.classifications):
            assert (
                c1.section_id == c2.section_id
            ), f"Section ID mismatch: {c1.section_id} vs {c2.section_id}"
            assert c1.section_type == c2.section_type, f"Type mismatch for {c1.section_id}"
            assert c1.confidence_score == c2.confidence_score, f"Score mismatch for {c1.section_id}"
            assert c1.method == c2.method, f"Method mismatch for {c1.section_id}"
