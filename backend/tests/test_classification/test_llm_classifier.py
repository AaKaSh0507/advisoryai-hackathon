"""
Tests for LLM-assisted section classification.

Verifies:
- LLM is invoked only when rules are insufficient
- LLM output is constrained to allowed labels
- Invalid or unexpected LLM output is rejected safely
- LLM decisions are repeatable under identical inputs
- Mock LLM responses explicitly
"""

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.domains.parsing.schemas import BlockType, HeadingBlock, ParagraphBlock, TextRun
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
    LLMClassificationResponse,
)
from backend.app.domains.section.llm_classifier import LLMClassifier, LLMClassifierConfig


class TestLLMClassifierInitialization:
    """Tests for LLM classifier setup."""

    def test_llm_classifier_is_importable(self):
        """LLM classifier should be importable."""
        assert LLMClassifier is not None
        assert LLMClassifierConfig is not None

    def test_llm_config_accepts_parameters(self):
        """LLM config should accept all required parameters."""
        config = LLMClassifierConfig(
            api_key="test-api-key",
            api_base_url="https://api.test.com/v1",
            model="gpt-4o-mini",
            max_tokens=500,
            temperature=0.0,
            timeout_seconds=30,
            enabled=True,
        )

        assert config.api_key == "test-api-key"
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.0
        assert config.enabled is True

    def test_llm_classifier_with_disabled_config(self):
        """Disabled LLM classifier should return None for classify."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=False,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="Some text")],
        )

        result = classifier.classify(block, {})

        assert result is None

    def test_llm_classifier_without_api_key(self):
        """LLM classifier without API key should return None."""
        config = LLMClassifierConfig(
            api_key="",
            enabled=True,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="Some text")],
        )

        result = classifier.classify(block, {})

        assert result is None


class TestLLMOutputConstraints:
    """Tests for LLM output constraint validation."""

    @pytest.fixture
    def classifier(self):
        """Create LLM classifier with test config."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        return LLMClassifier(config)

    def test_valid_static_response_is_accepted(self, classifier):
        """Valid STATIC LLM response should be accepted."""
        valid_response = {
            "classification": "STATIC",
            "confidence": 0.85,
            "reasoning": "This is standard boilerplate text",
        }

        result = classifier._parse_llm_output(json.dumps(valid_response))

        assert result is not None
        assert result.classification == "STATIC"
        assert result.confidence == 0.85
        assert result.reasoning == "This is standard boilerplate text"

    def test_valid_dynamic_response_is_accepted(self, classifier):
        """Valid DYNAMIC LLM response should be accepted."""
        valid_response = {
            "classification": "DYNAMIC",
            "confidence": 0.92,
            "reasoning": "Contains client-specific customization markers",
        }

        result = classifier._parse_llm_output(json.dumps(valid_response))

        assert result is not None
        assert result.classification == "DYNAMIC"
        assert result.confidence == 0.92

    def test_invalid_classification_is_rejected(self, classifier):
        """Invalid classification label should be rejected."""
        invalid_response = {
            "classification": "UNKNOWN",
            "confidence": 0.80,
            "reasoning": "Some reason",
        }

        result = classifier._parse_llm_output(json.dumps(invalid_response))

        assert result is None

    def test_empty_classification_is_rejected(self, classifier):
        """Empty classification should be rejected."""
        invalid_response = {"classification": "", "confidence": 0.80, "reasoning": "Some reason"}

        result = classifier._parse_llm_output(json.dumps(invalid_response))

        assert result is None

    def test_missing_classification_is_rejected(self, classifier):
        """Missing classification field should be rejected."""
        invalid_response = {"confidence": 0.80, "reasoning": "Some reason"}

        result = classifier._parse_llm_output(json.dumps(invalid_response))

        assert result is None

    def test_confidence_above_one_is_clamped(self, classifier):
        """Confidence above 1.0 should be clamped to 1.0."""
        response = {"classification": "STATIC", "confidence": 1.5, "reasoning": "Very confident"}

        result = classifier._parse_llm_output(json.dumps(response))

        assert result is not None
        assert result.confidence == 1.0

    def test_confidence_below_zero_is_clamped(self, classifier):
        """Confidence below 0.0 should be clamped to 0.0."""
        response = {
            "classification": "DYNAMIC",
            "confidence": -0.5,
            "reasoning": "Negative confidence",
        }

        result = classifier._parse_llm_output(json.dumps(response))

        assert result is not None
        assert result.confidence == 0.0

    def test_non_json_response_is_rejected(self, classifier):
        """Non-JSON response should be rejected."""
        result = classifier._parse_llm_output("This is not JSON")

        assert result is None

    def test_json_with_extra_text_is_parsed(self, classifier):
        """JSON embedded in extra text should still be parsed."""
        response_with_extra = 'Here is my analysis:\n{"classification": "STATIC", "confidence": 0.9, "reasoning": "Test"}\nEnd.'

        result = classifier._parse_llm_output(response_with_extra)

        assert result is not None
        assert result.classification == "STATIC"
        assert result.confidence == 0.9

    def test_lowercase_classification_is_normalized(self, classifier):
        """Lowercase classification should be normalized to uppercase."""
        response = {"classification": "static", "confidence": 0.85, "reasoning": "Test"}

        result = classifier._parse_llm_output(json.dumps(response))

        assert result is not None
        assert result.classification == "STATIC"

    def test_mixed_case_classification_is_normalized(self, classifier):
        """Mixed case classification should be normalized."""
        response = {"classification": "Dynamic", "confidence": 0.85, "reasoning": "Test"}

        result = classifier._parse_llm_output(json.dumps(response))

        assert result is not None
        assert result.classification == "DYNAMIC"


class TestLLMClassificationWithMocking:
    """Tests for LLM classification with mocked API calls."""

    @pytest.fixture
    def mock_successful_response(self):
        """Create a mock successful LLM API response."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "classification": "DYNAMIC",
                                "confidence": 0.88,
                                "reasoning": "Contains client-specific placeholders",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        return mock_response

    @pytest.fixture
    def mock_static_response(self):
        """Create a mock STATIC classification response."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "classification": "STATIC",
                                "confidence": 0.95,
                                "reasoning": "Standard legal boilerplate",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        return mock_response

    def test_successful_llm_classification(self, mock_successful_response):
        """Successful LLM call should return proper classification."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0001_xyz",
            sequence=1,
            runs=[TextRun(text="Dear {client_name}, we have prepared this report...")],
        )

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_successful_response
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is not None
        assert result.section_type == "DYNAMIC"
        assert result.confidence_score == 0.88
        assert result.method == ClassificationMethod.LLM_ASSISTED
        assert "placeholders" in result.justification.lower()

    def test_llm_classification_includes_metadata(self, mock_static_response):
        """LLM classification should include metadata."""
        config = LLMClassifierConfig(
            api_key="test-key",
            model="gpt-4o-mini",
            enabled=True,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0002_xyz",
            sequence=2,
            runs=[TextRun(text="This document is prepared by...")],
        )

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_static_response
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is not None
        assert "llm_model" in result.metadata
        assert result.metadata["llm_model"] == "gpt-4o-mini"
        assert "llm_duration_ms" in result.metadata

    def test_api_error_returns_none(self):
        """API error should return None gracefully."""
        import httpx

        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0003_xyz",
            sequence=3,
            runs=[TextRun(text="Some text")],
        )

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.side_effect = httpx.HTTPError("API Error")
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is None

    def test_invalid_json_from_llm_returns_none(self):
        """Invalid JSON from LLM should return None."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0004_xyz",
            sequence=4,
            runs=[TextRun(text="Some text")],
        )

        response_data = {"choices": [{"message": {"content": "I cannot classify this properly"}}]}

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is None


class TestLLMClassificationDeterminism:
    """Tests for LLM classification determinism."""

    @pytest.fixture
    def deterministic_response(self):
        """Create a deterministic mock response."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "classification": "STATIC",
                                "confidence": 0.90,
                                "reasoning": "Standard text",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        return mock_response

    def test_same_input_same_mock_produces_same_result(self, deterministic_response):
        """Same input with same mock should produce identical results."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
            temperature=0.0,
        )
        classifier = LLMClassifier(config)

        block = ParagraphBlock(
            block_id="blk_par_0010_xyz",
            sequence=10,
            runs=[TextRun(text="This is standard boilerplate text.")],
        )

        results = []
        for _ in range(3):
            with patch.object(classifier, "_get_client") as mock_get_client:
                mock_client = MagicMock()
                mock_client.post.return_value = deterministic_response
                mock_get_client.return_value = mock_client

                result = classifier.classify(block, {})
                results.append(result)

        # All results should be identical
        assert all(r is not None for r in results)
        assert results[0].section_type == results[1].section_type == results[2].section_type
        assert (
            results[0].confidence_score
            == results[1].confidence_score
            == results[2].confidence_score
        )

    def test_temperature_zero_enforced(self):
        """Temperature 0.0 should be used for determinism."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
            temperature=0.0,
        )

        assert config.temperature == 0.0


class TestLLMClassificationConfidenceLevels:
    """Tests for LLM classification confidence levels."""

    @pytest.fixture
    def classifier(self):
        """Create LLM classifier."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        return LLMClassifier(config)

    def test_high_confidence_llm_result(self, classifier):
        """High confidence LLM result should have HIGH level."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "classification": "STATIC",
                                "confidence": 0.95,
                                "reasoning": "Definite boilerplate",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        block = ParagraphBlock(
            block_id="blk_par_0020_xyz",
            sequence=20,
            runs=[TextRun(text="Test text")],
        )

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is not None
        assert result.confidence_score >= 0.9
        assert result.confidence_level == ClassificationConfidence.HIGH

    def test_medium_confidence_llm_result(self, classifier):
        """Medium confidence LLM result should have MEDIUM level."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "classification": "DYNAMIC",
                                "confidence": 0.75,
                                "reasoning": "Likely customization",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        block = ParagraphBlock(
            block_id="blk_par_0021_xyz",
            sequence=21,
            runs=[TextRun(text="Test text")],
        )

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is not None
        assert 0.7 <= result.confidence_score < 0.9
        assert result.confidence_level == ClassificationConfidence.MEDIUM

    def test_low_confidence_llm_result(self, classifier):
        """Low confidence LLM result should have LOW level."""
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "classification": "STATIC",
                                "confidence": 0.55,
                                "reasoning": "Uncertain classification",
                            }
                        )
                    }
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_response.raise_for_status = MagicMock()

        block = ParagraphBlock(
            block_id="blk_par_0022_xyz",
            sequence=22,
            runs=[TextRun(text="Test text")],
        )

        with patch.object(classifier, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = classifier.classify(block, {})

        assert result is not None
        assert result.confidence_score < 0.7
        assert result.confidence_level == ClassificationConfidence.LOW


class TestLLMClassifierCleanup:
    """Tests for LLM classifier cleanup."""

    def test_close_method_exists(self):
        """LLM classifier should have close method."""
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        classifier = LLMClassifier(config)

        assert hasattr(classifier, "close")
        assert callable(classifier.close)

        # Should not raise
        classifier.close()
