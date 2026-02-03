import time
from typing import Any
from uuid import UUID

from backend.app.domains.parsing.schemas import DocumentBlock, ParsedDocument
from backend.app.domains.section.classification_schemas import (
    ClassificationBatchResult,
    ClassificationConfidence,
    ClassificationMethod,
    SectionClassificationResult,
)
from backend.app.domains.section.llm_classifier import LLMClassifier, LLMClassifierConfig
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository
from backend.app.domains.section.rule_based_classifier import RuleBasedClassifier
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.section.classification_service")


class ClassificationService:
    def __init__(
        self,
        rule_classifier: RuleBasedClassifier,
        llm_classifier: LLMClassifier | None = None,
        confidence_threshold: float = 0.85,
    ):
        self.rule_classifier = rule_classifier
        self.llm_classifier = llm_classifier
        self.confidence_threshold = confidence_threshold

    async def classify_template_sections(
        self,
        parsed_document: ParsedDocument,
        section_repo: SectionRepository,
    ) -> ClassificationBatchResult:
        start_time = time.time()
        template_version_id = parsed_document.template_version_id

        logger.info(
            f"Starting classification for template version {template_version_id}, "
            f"{len(parsed_document.blocks)} blocks"
        )
        classifications: list[SectionClassificationResult] = []
        errors: list[str] = []

        for i, block in enumerate(parsed_document.blocks):
            try:
                context = self._build_context(i, parsed_document.blocks)
                result = self._classify_block(block, context)
                classifications.append(result)

            except Exception as e:
                block_id = getattr(block, "block_id", f"block_{i}")
                error_msg = f"Failed to classify block {block_id}: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                fallback_result = self._create_fallback_classification(block)
                classifications.append(fallback_result)
        await self._persist_classifications(
            template_version_id=template_version_id,
            classifications=classifications,
            section_repo=section_repo,
        )
        duration_ms = (time.time() - start_time) * 1000
        result = self._compute_batch_result(
            template_version_id=str(template_version_id),
            classifications=classifications,
            duration_ms=duration_ms,
            errors=errors,
        )

        logger.info(
            f"Classification completed for {result.total_sections} sections: "
            f"{result.static_sections} STATIC, {result.dynamic_sections} DYNAMIC "
            f"({result.high_confidence_count} high confidence) in {duration_ms:.2f}ms"
        )

        return result

    def _classify_block(
        self, block: DocumentBlock, context: dict[str, Any]
    ) -> SectionClassificationResult:
        block_id = getattr(block, "block_id", "unknown")
        rule_result = self.rule_classifier.classify(block, context)
        if rule_result and rule_result.confidence_score >= self.confidence_threshold:
            logger.debug(f"Block {block_id} classified by rules: {rule_result.section_type}")
            return rule_result
        if self.llm_classifier:
            llm_result = self.llm_classifier.classify(block, context)
            if llm_result and llm_result.confidence_score >= self.confidence_threshold:
                logger.debug(f"Block {block_id} classified by LLM: {llm_result.section_type}")
                return llm_result

            if llm_result:
                logger.debug(
                    f"Block {block_id} LLM classification low confidence "
                    f"({llm_result.confidence_score:.2f}), using fallback"
                )
        logger.debug(f"Block {block_id} using conservative fallback (STATIC)")
        return self._create_fallback_classification(block)

    def _create_fallback_classification(self, block: DocumentBlock) -> SectionClassificationResult:
        block_id = getattr(block, "block_id", "unknown")

        return SectionClassificationResult(
            section_id=block_id,
            section_type="STATIC",
            confidence_score=0.5,
            confidence_level=ClassificationConfidence.LOW,
            method=ClassificationMethod.FALLBACK,
            justification="Conservative fallback: defaulting to STATIC when classification inconclusive",
            metadata={"fallback_reason": "no_confident_classification"},
        )

    def _build_context(self, index: int, blocks: list[DocumentBlock]) -> dict[str, Any]:
        context: dict[str, Any] = {
            "position_in_document": index,
            "total_blocks": len(blocks),
        }
        if index > 0:
            prev_block = blocks[index - 1]
            context["previous_block_type"] = str(getattr(prev_block, "block_type", "unknown"))
        if index < len(blocks) - 1:
            next_block = blocks[index + 1]
            context["next_block_type"] = str(getattr(next_block, "block_type", "unknown"))

        return context

    async def _persist_classifications(
        self,
        template_version_id: UUID,
        classifications: list[SectionClassificationResult],
        section_repo: SectionRepository,
    ) -> list[Section]:
        sections = []

        for classification in classifications:
            prompt_config = None
            if classification.is_dynamic:
                prompt_config = {
                    "classification_confidence": classification.confidence_score,
                    "classification_method": classification.method.value,
                    "justification": classification.justification,
                    "metadata": classification.metadata,
                }
            section = Section(
                template_version_id=template_version_id,
                section_type=SectionType(classification.section_type),
                structural_path=classification.section_id,
                prompt_config=prompt_config,
            )
            sections.append(section)
        created_sections = await section_repo.create_batch(sections)
        logger.info(f"Persisted {len(created_sections)} section classifications")

        return created_sections

    def _compute_batch_result(
        self,
        template_version_id: str,
        classifications: list[SectionClassificationResult],
        duration_ms: float,
        errors: list[str],
    ) -> ClassificationBatchResult:
        total = len(classifications)
        static_count = sum(1 for c in classifications if c.section_type == "STATIC")
        dynamic_count = sum(1 for c in classifications if c.section_type == "DYNAMIC")
        high_conf = sum(
            1 for c in classifications if c.confidence_level == ClassificationConfidence.HIGH
        )
        medium_conf = sum(
            1 for c in classifications if c.confidence_level == ClassificationConfidence.MEDIUM
        )
        low_conf = sum(
            1 for c in classifications if c.confidence_level == ClassificationConfidence.LOW
        )
        rule_based = sum(1 for c in classifications if c.method == ClassificationMethod.RULE_BASED)
        llm_assisted = sum(
            1 for c in classifications if c.method == ClassificationMethod.LLM_ASSISTED
        )
        fallback = sum(1 for c in classifications if c.method == ClassificationMethod.FALLBACK)

        return ClassificationBatchResult(
            template_version_id=template_version_id,
            total_sections=total,
            static_sections=static_count,
            dynamic_sections=dynamic_count,
            high_confidence_count=high_conf,
            medium_confidence_count=medium_conf,
            low_confidence_count=low_conf,
            rule_based_count=rule_based,
            llm_assisted_count=llm_assisted,
            fallback_count=fallback,
            classifications=classifications,
            duration_ms=duration_ms,
            errors=errors,
        )


def create_classification_service(
    llm_config: LLMClassifierConfig | None = None,
    confidence_threshold: float = 0.85,
) -> ClassificationService:
    rule_classifier = RuleBasedClassifier(confidence_threshold=confidence_threshold)

    llm_classifier = None
    if llm_config and llm_config.enabled and llm_config.api_key:
        llm_classifier = LLMClassifier(config=llm_config)

    return ClassificationService(
        rule_classifier=rule_classifier,
        llm_classifier=llm_classifier,
        confidence_threshold=confidence_threshold,
    )
