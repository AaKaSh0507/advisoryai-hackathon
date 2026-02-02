import hashlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_service import create_classification_service
from backend.app.domains.section.rule_based_classifier import RuleBasedClassifier


class TestRuleBasedDeterminism:
    @pytest.fixture
    def classifier(self):
        return RuleBasedClassifier()

    @pytest.fixture
    def sample_blocks(self):
        return [
            ParagraphBlock(
                block_id="blk_par_0001_xyz",
                sequence=1,
                runs=[TextRun(text="This document is confidential and privileged.")],
            ),
            ParagraphBlock(
                block_id="blk_par_0002_xyz",
                sequence=2,
                runs=[TextRun(text="Dear {client_name}, thank you for choosing us.")],
            ),
            ParagraphBlock(
                block_id="blk_par_0003_xyz",
                sequence=3,
                runs=[TextRun(text="Copyright 2024. All rights reserved.")],
            ),
        ]

    def test_same_block_same_result_multiple_times(self, classifier, sample_blocks):
        block = sample_blocks[0]

        results = []
        for _ in range(10):
            result = classifier.classify(block, {})
            results.append(result)

        first_result = results[0]
        for result in results[1:]:
            assert result.section_type == first_result.section_type
            assert result.confidence_score == first_result.confidence_score
            assert result.method == first_result.method

    def test_different_blocks_classified_consistently(self, classifier, sample_blocks):
        for _ in range(5):
            for block in sample_blocks:
                result1 = classifier.classify(block, {})
                result2 = classifier.classify(block, {})

                assert result1.section_type == result2.section_type
                assert result1.confidence_score == result2.confidence_score

    def test_classifier_is_stateless(self, classifier, sample_blocks):
        results_forward = [classifier.classify(b, {}) for b in sample_blocks]
        results_reverse = [classifier.classify(b, {}) for b in reversed(sample_blocks)]
        for r1, r2 in zip(results_forward, results_reverse):
            assert r1.section_type == r2.section_type
            assert r1.confidence_score == r2.confidence_score

    def test_new_classifier_instance_same_results(self, sample_blocks):
        classifier1 = RuleBasedClassifier()
        classifier2 = RuleBasedClassifier()
        for block in sample_blocks:
            result1 = classifier1.classify(block, {})
            result2 = classifier2.classify(block, {})
            assert result1.section_type == result2.section_type
            assert result1.confidence_score == result2.confidence_score


class TestServiceDeterminism:
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
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections
        assert result1.rule_based_count == result2.rule_based_count

    @pytest.mark.asyncio
    async def test_classifications_match_exactly(self, sample_document):
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
        for c1, c2 in zip(result1.classifications, result2.classifications):
            assert c1.section_id == c2.section_id
            assert c1.section_type == c2.section_type
            assert c1.confidence_score == c2.confidence_score
            assert c1.method == c2.method


class TestContentHashDeterminism:
    def test_same_content_same_hash(self):
        content = "This is confidential and privileged."
        hash1 = hashlib.sha256(content.encode()).hexdigest()
        hash2 = hashlib.sha256(content.encode()).hexdigest()
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        content1 = "This is confidential."
        content2 = "This is not confidential."
        hash1 = hashlib.sha256(content1.encode()).hexdigest()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()
        assert hash1 != hash2


class TestIdempotentClassification:
    @pytest.fixture
    def sample_document(self):
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
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )
        mock_repo = MagicMock()
        mock_repo.create_batch = AsyncMock(return_value=[])
        result1 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo,
        )
        mock_repo2 = MagicMock()
        mock_repo2.create_batch = AsyncMock(return_value=[])
        result2 = await service.classify_template_sections(
            parsed_document=sample_document,
            section_repo=mock_repo2,
        )
        assert result1.total_sections == result2.total_sections
        assert result1.static_sections == result2.static_sections
        assert result1.dynamic_sections == result2.dynamic_sections

    def test_block_classification_is_pure_function(self):
        service = create_classification_service(
            llm_config=None,
            confidence_threshold=0.85,
        )
        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="This is confidential and privileged.")],
        )
        context = {}
        result1 = service._classify_block(block, context)
        result2 = service._classify_block(block, context)
        result3 = service._classify_block(block, context)
        assert result1.section_type == result2.section_type == result3.section_type
        assert result1.confidence_score == result2.confidence_score == result3.confidence_score


class TestNoRandomness:
    def test_confidence_scores_are_deterministic(self):
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
        assert len(set(scores)) == 1

    def test_section_types_are_deterministic(self):
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
            assert len(set(types)) == 1

    def test_method_attribution_is_deterministic(self):
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
        assert len(set(methods)) == 1


class TestPatternMatchingDeterminism:
    def test_static_patterns_match_consistently(self):
        classifier = RuleBasedClassifier()
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
            assert all(r is not None for r in results), f"Pattern '{text}' should match STATIC"
            types = [r.section_type for r in results]
            assert len(set(types)) == 1

    def test_dynamic_patterns_match_consistently(self):
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
            assert all(t == "DYNAMIC" for t in types)


class TestBatchProcessingDeterminism:
    @pytest.fixture
    def large_document(self):
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
        for c1, c2 in zip(result1.classifications, result2.classifications):
            assert (
                c1.section_id == c2.section_id
            ), f"Section ID mismatch: {c1.section_id} vs {c2.section_id}"
            assert c1.section_type == c2.section_type, f"Type mismatch for {c1.section_id}"
            assert c1.confidence_score == c2.confidence_score, f"Score mismatch for {c1.section_id}"
            assert c1.method == c2.method, f"Method mismatch for {c1.section_id}"
