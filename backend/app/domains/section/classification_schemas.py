from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClassificationMethod(str, Enum):
    RULE_BASED = "rule_based"
    LLM_ASSISTED = "llm_assisted"
    FALLBACK = "fallback"


class ClassificationConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SectionClassificationResult(BaseModel):
    section_id: str = Field(..., description="Block ID from parsed document")
    section_type: str = Field(..., description="STATIC or DYNAMIC")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    confidence_level: ClassificationConfidence
    method: ClassificationMethod
    justification: str = Field(..., description="Explanation for the classification")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence_level == ClassificationConfidence.HIGH

    @property
    def is_dynamic(self) -> bool:
        return self.section_type == "DYNAMIC"


class ClassificationBatchResult(BaseModel):
    template_version_id: str
    total_sections: int
    static_sections: int
    dynamic_sections: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    rule_based_count: int
    llm_assisted_count: int
    fallback_count: int
    classifications: list[SectionClassificationResult]
    duration_ms: float
    errors: list[str] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_sections == 0:
            return 0.0
        return (self.high_confidence_count / self.total_sections) * 100


class LLMClassificationRequest(BaseModel):
    block_id: str
    block_type: str
    content: str
    structural_metadata: dict[str, Any]


class LLMClassificationResponse(BaseModel):
    classification: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
