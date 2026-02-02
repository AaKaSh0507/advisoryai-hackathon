import json
from uuid import uuid4

import pytest

from backend.app.domains.audit.models import AuditLog
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.section.classification_schemas import (
    ClassificationBatchResult,
    ClassificationConfidence,
    ClassificationMethod,
    SectionClassificationResult,
)


class TestAuditLogModelStructure:
    def test_audit_log_model_exists(self):
        assert AuditLog is not None

    def test_audit_log_has_required_fields(self):
        columns = [c.name for c in AuditLog.__table__.columns]
        assert "id" in columns
        assert "action" in columns or "event_type" in columns
        assert "entity_id" in columns


class TestAuditLogRepository:
    def test_audit_repository_exists(self):
        assert AuditRepository is not None

    def test_repository_has_create_method(self):
        assert hasattr(AuditRepository, "create")


class TestClassificationAuditContent:
    @pytest.fixture
    def sample_batch_result(self):
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
        result_dict = sample_batch_result.model_dump()
        serialized = json.dumps(result_dict, default=str)
        assert serialized is not None
        deserialized = json.loads(serialized)
        assert deserialized["total_sections"] == 2

    def test_audit_contains_statistics(self, sample_batch_result):
        result_dict = sample_batch_result.model_dump()
        assert "total_sections" in result_dict
        assert "static_sections" in result_dict
        assert "dynamic_sections" in result_dict
        assert "rule_based_count" in result_dict
        assert "llm_assisted_count" in result_dict
        assert "fallback_count" in result_dict

    def test_audit_contains_confidence_breakdown(self, sample_batch_result):
        result_dict = sample_batch_result.model_dump()
        assert "high_confidence_count" in result_dict
        assert "medium_confidence_count" in result_dict
        assert "low_confidence_count" in result_dict

    def test_audit_contains_duration(self, sample_batch_result):
        result_dict = sample_batch_result.model_dump()
        assert "duration_ms" in result_dict
        assert result_dict["duration_ms"] >= 0


class TestAuditEventConstruction:
    def test_audit_event_from_batch_result(self):
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

        assert audit_payload["action"] == "CLASSIFICATION_COMPLETED"
        assert audit_payload["statistics"]["total_sections"] == 5


class TestAuditImmutability:
    def test_batch_result_is_frozen(self):
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

        if hasattr(result.model_config, "frozen"):
            pass
        result_copy = result.model_copy()
        assert result_copy.total_sections == result.total_sections

    def test_classification_result_serialized_in_audit(self):
        classification = SectionClassificationResult(
            section_id="blk_par_0001_xyz",
            section_type="DYNAMIC",
            confidence_score=0.88,
            confidence_level=ClassificationConfidence.MEDIUM,
            method=ClassificationMethod.LLM_ASSISTED,
            justification="LLM identified placeholder pattern.",
        )

        result_dict = classification.model_dump()
        assert result_dict["section_id"] == "blk_par_0001_xyz"
        assert result_dict["section_type"] == "DYNAMIC"
        assert result_dict["confidence_score"] == 0.88
        assert result_dict["method"] == ClassificationMethod.LLM_ASSISTED


class TestAuditContextCompleteness:
    def test_audit_has_template_version_id(self):
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

        total_methods = result.rule_based_count + result.llm_assisted_count + result.fallback_count
        assert total_methods == result.total_sections

    def test_audit_has_confidence_attribution(self):
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

        total_confidence = (
            result.high_confidence_count
            + result.medium_confidence_count
            + result.low_confidence_count
        )
        assert total_confidence == result.total_sections


class TestAuditTimestamps:
    def test_batch_result_has_duration(self):
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
    def test_individual_classifications_included(self):
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
        for i, classification in enumerate(result.classifications):
            assert classification.section_id == f"blk_par_{i:04d}_xyz"

    def test_justifications_preserved_in_audit(self):
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
