import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.domains.parsing.schemas import ParagraphBlock, TextRun
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
)
from backend.app.domains.section.llm_classifier import LLMClassifier, LLMClassifierConfig


class TestLLMClassifierInitialization:
    def test_llm_classifier_is_importable(self):
        assert LLMClassifier is not None
        assert LLMClassifierConfig is not None

    def test_llm_config_accepts_parameters(self):
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
    @pytest.fixture
    def classifier(self):
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        return LLMClassifier(config)

    def test_valid_static_response_is_accepted(self, classifier):
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
        invalid_response = {
            "classification": "UNKNOWN",
            "confidence": 0.80,
            "reasoning": "Some reason",
        }
        result = classifier._parse_llm_output(json.dumps(invalid_response))
        assert result is None

    def test_empty_classification_is_rejected(self, classifier):
        invalid_response = {"classification": "", "confidence": 0.80, "reasoning": "Some reason"}
        result = classifier._parse_llm_output(json.dumps(invalid_response))
        assert result is None

    def test_missing_classification_is_rejected(self, classifier):
        invalid_response = {"confidence": 0.80, "reasoning": "Some reason"}
        result = classifier._parse_llm_output(json.dumps(invalid_response))
        assert result is None

    def test_confidence_above_one_is_clamped(self, classifier):
        response = {"classification": "STATIC", "confidence": 1.5, "reasoning": "Very confident"}
        result = classifier._parse_llm_output(json.dumps(response))
        assert result is not None
        assert result.confidence == 1.0

    def test_confidence_below_zero_is_clamped(self, classifier):
        response = {
            "classification": "DYNAMIC",
            "confidence": -0.5,
            "reasoning": "Negative confidence",
        }
        result = classifier._parse_llm_output(json.dumps(response))
        assert result is not None
        assert result.confidence == 0.0

    def test_non_json_response_is_rejected(self, classifier):
        result = classifier._parse_llm_output("This is not JSON")
        assert result is None

    def test_json_with_extra_text_is_parsed(self, classifier):
        response_with_extra = 'Here is my analysis:\n{"classification": "STATIC", "confidence": 0.9, "reasoning": "Test"}\nEnd.'
        result = classifier._parse_llm_output(response_with_extra)
        assert result is not None
        assert result.classification == "STATIC"
        assert result.confidence == 0.9

    def test_lowercase_classification_is_normalized(self, classifier):
        response = {"classification": "static", "confidence": 0.85, "reasoning": "Test"}
        result = classifier._parse_llm_output(json.dumps(response))
        assert result is not None
        assert result.classification == "STATIC"

    def test_mixed_case_classification_is_normalized(self, classifier):
        response = {"classification": "Dynamic", "confidence": 0.85, "reasoning": "Test"}
        result = classifier._parse_llm_output(json.dumps(response))
        assert result is not None
        assert result.classification == "DYNAMIC"


class TestLLMClassificationWithMocking:
    @pytest.fixture
    def mock_successful_response(self):
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
    @pytest.fixture
    def deterministic_response(self):
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
        assert all(r is not None for r in results)
        assert results[0].section_type == results[1].section_type == results[2].section_type
        assert (
            results[0].confidence_score
            == results[1].confidence_score
            == results[2].confidence_score
        )

    def test_temperature_zero_enforced(self):
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
            temperature=0.0,
        )
        assert config.temperature == 0.0


class TestLLMClassificationConfidenceLevels:
    @pytest.fixture
    def classifier(self):
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        return LLMClassifier(config)

    def test_high_confidence_llm_result(self, classifier):
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
    def test_close_method_exists(self):
        config = LLMClassifierConfig(
            api_key="test-key",
            enabled=True,
        )
        classifier = LLMClassifier(config)
        assert hasattr(classifier, "close")
        assert callable(classifier.close)
        classifier.close()
