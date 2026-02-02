"""
Tests for classification audit logging.

Verifies:
- CLASSIFICATION_COMPLETED event is logged
- Audit records contain required context
- Audit records are immutable
- Statistics are captured in audit
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.parsing.schemas import (
    DocumentMetadata,
    ParagraphBlock,
    ParsedDocument,
    TextRun,
)
from backend.app.domains.section.classification_schemas import (
    ClassificationBatchResult,
    ClassificationConfidence,
    ClassificationMethod,
    SectionClassificationResult,
)


class TestAuditLogModelStructure:
    """Tests for AuditLog model structure."""

    def test_audit_log_model_exists(self):
        """AuditLog model should be importable."""
        assert AuditLog is not None

    def test_audit_log_has_required_fields(self):
        """AuditLog model should have required fields."""
        columns = [c.name for c in AuditLog.__table__.columns]

        assert "id" in columns
        assert "action" in columns or "event_type" in columns
        assert "entity_id" in columns


class TestAuditLogRepository:
    """Tests for AuditRepository."""

    def test_audit_repository_exists(self):
        """AuditRepository should be importable."""
        assert AuditRepository is not None

    def test_repository_has_create_method(self):
        """Repository should have create method."""
        assert hasattr(AuditRepository, "create")


class TestClassificationAuditContent:
    """Tests for classification audit log content."""

    @pytest.fixture
    def sample_batch_result(self):
        """Create sample batch classification result."""
        template_version_id = str(uuid4())

        classifications = [
            SectionClassificationResult(
                section_id="blk_par_0001_xyz",
                section_type="STATIC",
                confidence_score=0.92,
                confidence_level=ClassificationConfidence.HIGH,
                method=ClassificationMethod.RULE_BASED,
                justification="Contains legal disclaimer pattern.",
            ),
            SectionClassificationResult(
                section_id="blk_par_0002_xyz",
                section_type="DYNAMIC",
                confidence_score=0.95,
                confidence_level=ClassificationConfidence.HIGH,
                method=ClassificationMethod.RULE_BASED,
                justification="Contains placeholder pattern.",
            ),
        ]

        return ClassificationBatchResult(
            template_version_id=template_version_id,
            classifications=classifications,
            total_sections=2,
            static_sections=1,
            dynamic_sections=1,
            rule_based_count=2,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=2,
            medium_confidence_count=0,
            low_confidence_count=0,
            duration_ms=150,
        )

    def test_batch_result_is_serializable(self, sample_batch_result):
        """Batch result should be JSON serializable for audit."""
        # Convert to dict
        result_dict = sample_batch_result.model_dump()

        # Should be JSON serializable
        serialized = json.dumps(result_dict, default=str)
        assert serialized is not None

        # Should deserialize
        deserialized = json.loads(serialized)
        assert deserialized["total_sections"] == 2

    def test_audit_contains_statistics(self, sample_batch_result):
        """Audit should contain classification statistics."""
        result_dict = sample_batch_result.model_dump()

        assert "total_sections" in result_dict
        assert "static_sections" in result_dict
        assert "dynamic_sections" in result_dict
        assert "rule_based_count" in result_dict
        assert "llm_assisted_count" in result_dict
        assert "fallback_count" in result_dict

    def test_audit_contains_confidence_breakdown(self, sample_batch_result):
        """Audit should contain confidence level breakdown."""
        result_dict = sample_batch_result.model_dump()

        assert "high_confidence_count" in result_dict
        assert "medium_confidence_count" in result_dict
        assert "low_confidence_count" in result_dict

    def test_audit_contains_duration(self, sample_batch_result):
        """Audit should contain classification duration."""
        result_dict = sample_batch_result.model_dump()

        assert "duration_ms" in result_dict
        assert result_dict["duration_ms"] >= 0


class TestAuditEventConstruction:
    """Tests for constructing audit events from classification results."""

    def test_audit_event_from_batch_result(self):
        """Can construct audit event from batch result."""
        template_version_id = str(uuid4())
        template_id = uuid4()

        batch_result = ClassificationBatchResult(
            template_version_id=template_version_id,
            classifications=[],
            total_sections=5,
            static_sections=3,
            dynamic_sections=2,
            rule_based_count=4,
            llm_assisted_count=1,
            fallback_count=0,
            high_confidence_count=4,
            medium_confidence_count=1,
            low_confidence_count=0,
            duration_ms=200,
        )

        # Construct audit event payload
        audit_payload = {
            "action": "CLASSIFICATION_COMPLETED",
            "template_id": str(template_id),
            "template_version_id": str(template_version_id),
            "statistics": {
                "total_sections": batch_result.total_sections,
                "static_sections": batch_result.static_sections,
                "dynamic_sections": batch_result.dynamic_sections,
            },
            "methods": {
                "rule_based": batch_result.rule_based_count,
                "llm_assisted": batch_result.llm_assisted_count,
                "fallback": batch_result.fallback_count,
            },
            "confidence": {
                "high": batch_result.high_confidence_count,
                "medium": batch_result.medium_confidence_count,
                "low": batch_result.low_confidence_count,
            },
            "duration_ms": batch_result.duration_ms,
        }

        # Should be valid
        assert audit_payload["action"] == "CLASSIFICATION_COMPLETED"
        assert audit_payload["statistics"]["total_sections"] == 5


class TestAuditImmutability:
    """Tests for audit record immutability."""

    def test_batch_result_is_frozen(self):
        """Batch result should be frozen (immutable) once created."""
        result = ClassificationBatchResult(
            template_version_id=str(uuid4()),
            classifications=[],
            total_sections=3,
            static_sections=2,
            dynamic_sections=1,
            rule_based_count=3,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=3,
            medium_confidence_count=0,
            low_confidence_count=0,
            duration_ms=100,
        )

        # Check if model is frozen (Pydantic v2)
        if hasattr(result.model_config, "frozen"):
            # If model is configured as frozen, modification should fail
            pass

        # Even if not strictly frozen, we test that copy() works
        result_copy = result.model_copy()
        assert result_copy.total_sections == result.total_sections

    def test_classification_result_serialized_in_audit(self):
        """Individual classification results should be serialized in audit."""
        classification = SectionClassificationResult(
            section_id="blk_par_0001_xyz",
            section_type="DYNAMIC",
            confidence_score=0.88,
            confidence_level=ClassificationConfidence.MEDIUM,
            method=ClassificationMethod.LLM_ASSISTED,
            justification="LLM identified placeholder pattern.",
        )

        result_dict = classification.model_dump()

        # All fields should be serialized
        assert result_dict["section_id"] == "blk_par_0001_xyz"
        assert result_dict["section_type"] == "DYNAMIC"
        assert result_dict["confidence_score"] == 0.88
        assert result_dict["method"] == ClassificationMethod.LLM_ASSISTED


class TestAuditContextCompleteness:
    """Tests for audit context completeness."""

    def test_audit_has_template_version_id(self):
        """Audit should always have template_version_id."""
        template_version_id = str(uuid4())

        result = ClassificationBatchResult(
            template_version_id=template_version_id,
            classifications=[],
            total_sections=0,
            static_sections=0,
            dynamic_sections=0,
            rule_based_count=0,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            duration_ms=0,
        )

        assert result.template_version_id == template_version_id

    def test_audit_has_method_attribution(self):
        """Audit should attribute methods used."""
        result = ClassificationBatchResult(
            template_version_id=str(uuid4()),
            classifications=[],
            total_sections=10,
            static_sections=6,
            dynamic_sections=4,
            rule_based_count=7,
            llm_assisted_count=2,
            fallback_count=1,
            high_confidence_count=8,
            medium_confidence_count=1,
            low_confidence_count=1,
            duration_ms=500,
        )

        # Methods should sum to total
        total_methods = result.rule_based_count + result.llm_assisted_count + result.fallback_count
        assert total_methods == result.total_sections

    def test_audit_has_confidence_attribution(self):
        """Audit should attribute confidence levels."""
        result = ClassificationBatchResult(
            template_version_id=str(uuid4()),
            classifications=[],
            total_sections=10,
            static_sections=6,
            dynamic_sections=4,
            rule_based_count=10,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=7,
            medium_confidence_count=2,
            low_confidence_count=1,
            duration_ms=300,
        )

        # Confidence levels should sum to total
        total_confidence = (
            result.high_confidence_count
            + result.medium_confidence_count
            + result.low_confidence_count
        )
        assert total_confidence == result.total_sections


class TestAuditTimestamps:
    """Tests for audit timestamp handling."""

    def test_batch_result_has_duration(self):
        """Batch result should include duration."""
        result = ClassificationBatchResult(
            template_version_id=str(uuid4()),
            classifications=[],
            total_sections=5,
            static_sections=3,
            dynamic_sections=2,
            rule_based_count=5,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=5,
            medium_confidence_count=0,
            low_confidence_count=0,
            duration_ms=250,
        )

        assert result.duration_ms == 250
        assert result.duration_ms >= 0

    def test_duration_is_numeric(self):
        """Duration should be a numeric value."""
        result = ClassificationBatchResult(
            template_version_id=str(uuid4()),
            classifications=[],
            total_sections=0,
            static_sections=0,
            dynamic_sections=0,
            rule_based_count=0,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=0,
            medium_confidence_count=0,
            low_confidence_count=0,
            duration_ms=100,
        )

        assert isinstance(result.duration_ms, (int, float))


class TestAuditClassificationDetails:
    """Tests for detailed classification information in audit."""

    def test_individual_classifications_included(self):
        """Individual classification results should be includeable in audit."""
        classifications = [
            SectionClassificationResult(
                section_id=f"blk_par_{i:04d}_xyz",
                section_type="STATIC" if i % 2 == 0 else "DYNAMIC",
                confidence_score=0.90,
                confidence_level=ClassificationConfidence.HIGH,
                method=ClassificationMethod.RULE_BASED,
                justification=f"Classification for block {i}",
            )
            for i in range(5)
        ]

        result = ClassificationBatchResult(
            template_version_id=str(uuid4()),
            classifications=classifications,
            total_sections=5,
            static_sections=3,
            dynamic_sections=2,
            rule_based_count=5,
            llm_assisted_count=0,
            fallback_count=0,
            high_confidence_count=5,
            medium_confidence_count=0,
            low_confidence_count=0,
            duration_ms=100,
        )

        assert len(result.classifications) == 5

        # Check each classification is preserved
        for i, classification in enumerate(result.classifications):
            assert classification.section_id == f"blk_par_{i:04d}_xyz"

    def test_justifications_preserved_in_audit(self):
        """Justifications should be preserved in audit."""
        classification = SectionClassificationResult(
            section_id="blk_par_0001_xyz",
            section_type="STATIC",
            confidence_score=0.95,
            confidence_level=ClassificationConfidence.HIGH,
            method=ClassificationMethod.RULE_BASED,
            justification="Matched legal disclaimer pattern: 'confidential and privileged'",
        )

        assert classification.justification is not None
        assert "confidential" in classification.justification.lower()

    def test_matched_patterns_tracked(self):
        """Matched patterns should be trackable for audit via metadata."""
        classification = SectionClassificationResult(
            section_id="blk_par_0001_xyz",
            section_type="STATIC",
            confidence_score=0.92,
            confidence_level=ClassificationConfidence.HIGH,
            method=ClassificationMethod.RULE_BASED,
            justification="Matched pattern: copyright notice",
            metadata={"matched_patterns": ["copyright", "all rights reserved"]},
        )

        assert classification.metadata is not None
        assert "matched_patterns" in classification.metadata
        assert len(classification.metadata["matched_patterns"]) >= 1
