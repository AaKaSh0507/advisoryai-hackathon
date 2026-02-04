import json
import time
from typing import Any

import httpx
from pydantic import ValidationError

from backend.app.domains.parsing.schemas import DocumentBlock
from backend.app.domains.section.classification_schemas import (
    ClassificationConfidence,
    ClassificationMethod,
    LLMClassificationRequest,
    LLMClassificationResponse,
    SectionClassificationResult,
)
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.section.llm_classifier")


class LLMClassifierConfig:
    def __init__(
        self,
        api_key: str,
        api_base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        max_tokens: int = 500,
        temperature: float = 0.0,  # Deterministic
        timeout_seconds: int = 30,
        enabled: bool = True,
    ):
        self.api_key = api_key
        self.api_base_url = api_base_url
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled


class LLMClassifier:
    SYSTEM_PROMPT = """You are a document section classifier for a template generation system. Your task is to classify sections as either STATIC or DYNAMIC.

DEFINITIONS:
- STATIC: Boilerplate content that stays EXACTLY the same for every document generated from this template. Examples: company disclaimers, standard terms, fixed instructional headers like "Meeting Notes" or "Action Items".
- DYNAMIC: Content that MUST be customized or filled in for each new document. This includes:
  * Person names (e.g., "Sarah Williams", "John Smith")
  * Dates and times (e.g., "January 15, 2024", "10:30 AM")
  * Meeting details, attendees, discussion points
  * Client-specific information, recommendations, analysis
  * Action items, tasks, follow-ups with specific details
  * Any data in tables that represents actual records (not headers)
  * Numerical data, statistics, financial figures
  * Specific project or case details
  * Email addresses, phone numbers, addresses

CLASSIFICATION RULES:
1. If the section contains ANY specific person name, date, or client data, classify as DYNAMIC
2. If the section contains placeholder-like content or sample data that would need to change, classify as DYNAMIC
3. Table data rows (not headers) are typically DYNAMIC
4. Meeting notes, action items with specific details are DYNAMIC
5. Only classify as STATIC if the content is truly generic boilerplate that never changes
6. When in doubt, prefer DYNAMIC - it's better to regenerate static content than miss dynamic content

OUTPUT FORMAT (valid JSON only):
{
  "classification": "STATIC" or "DYNAMIC",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation of the decision"
}

Only output valid JSON. No other text."""

    def __init__(self, config: LLMClassifierConfig):
        self.config = config
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.config.timeout_seconds)
        return self._client

    def classify(
        self, block: DocumentBlock, context: dict[str, Any]
    ) -> SectionClassificationResult | None:
        if not self.config.enabled:
            logger.debug("LLM classification disabled")
            return None

        if not self.config.api_key:
            logger.warning("LLM API key not configured")
            return None

        block_id = getattr(block, "block_id", "unknown")

        try:
            request = self._prepare_request(block, context)
            start_time = time.time()
            response = self._call_llm(request)
            duration_ms = (time.time() - start_time) * 1000

            if not response:
                logger.warning(f"No LLM response for block {block_id}")
                return None

            result = self._create_result(
                block_id=block_id, llm_response=response, duration_ms=duration_ms, request=request
            )

            logger.info(
                f"LLM classified block {block_id} as {result.section_type} "
                f"(confidence: {result.confidence_score:.2f}, duration: {duration_ms:.0f}ms)"
            )
            return result

        except Exception as e:
            logger.error(f"LLM classification failed for block {block_id}: {e}", exc_info=True)
            return None

    def _prepare_request(
        self, block: DocumentBlock, context: dict[str, Any]
    ) -> LLMClassificationRequest:
        block_id = getattr(block, "block_id", "unknown")
        block_type = getattr(block, "block_type", "unknown")
        text = self._extract_text(block)
        structural_metadata = {
            "block_type": str(block_type),
            "sequence": getattr(block, "sequence", -1),
            "text_length": len(text),
        }
        if hasattr(block, "level"):
            structural_metadata["heading_level"] = block.level
        if hasattr(block, "style_name"):
            structural_metadata["style_name"] = block.style_name
        structural_metadata.update(
            {
                "previous_block_type": context.get("previous_block_type"),
                "next_block_type": context.get("next_block_type"),
                "position_in_document": context.get("position_in_document"),
            }
        )

        return LLMClassificationRequest(
            block_id=block_id,
            block_type=str(block_type),
            content=text[:1000],
            structural_metadata=structural_metadata,
        )

    def _call_llm(self, request: LLMClassificationRequest) -> LLMClassificationResponse | None:
        try:
            client = self._get_client()
            user_prompt = f"""Classify this section:

BLOCK TYPE: {request.block_type}
CONTENT: {request.content}

STRUCTURAL CONTEXT:
{json.dumps(request.structural_metadata, indent=2)}

Classify as STATIC or DYNAMIC with confidence and reasoning."""

            response = client.post(
                f"{self.config.api_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
            )

            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = self._parse_llm_output(content)

            return parsed

        except httpx.HTTPError as e:
            logger.error(f"LLM API error: {e}")
            return None
        except (KeyError, json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None

    def _parse_llm_output(self, content: str) -> LLMClassificationResponse | None:
        try:
            start = content.find("{")
            end = content.rfind("}") + 1

            if start == -1 or end == 0:
                logger.error(f"No JSON found in LLM response: {content}")
                return None

            json_str = content[start:end]
            data = json.loads(json_str)
            classification = data.get("classification", "").upper()
            if classification not in ["STATIC", "DYNAMIC"]:
                logger.error(f"Invalid classification: {classification}")
                return None

            confidence = float(data.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

            reasoning = data.get("reasoning", "No reasoning provided")

            return LLMClassificationResponse(
                classification=classification, confidence=confidence, reasoning=reasoning
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse LLM output: {e}, content: {content}")
            return None

    def _extract_text(self, block: DocumentBlock) -> str:
        if hasattr(block, "text"):
            return block.text
        if hasattr(block, "runs"):
            return "".join(run.text for run in block.runs)
        return ""

    def _create_result(
        self,
        block_id: str,
        llm_response: LLMClassificationResponse,
        duration_ms: float,
        request: LLMClassificationRequest,
    ) -> SectionClassificationResult:
        confidence = llm_response.confidence
        if confidence >= 0.9:
            confidence_level = ClassificationConfidence.HIGH
        elif confidence >= 0.7:
            confidence_level = ClassificationConfidence.MEDIUM
        else:
            confidence_level = ClassificationConfidence.LOW

        return SectionClassificationResult(
            section_id=block_id,
            section_type=llm_response.classification,
            confidence_score=confidence,
            confidence_level=confidence_level,
            method=ClassificationMethod.LLM_ASSISTED,
            justification=f"LLM-assisted: {llm_response.reasoning}",
            metadata={
                "llm_model": self.config.model,
                "llm_duration_ms": duration_ms,
                "block_type": request.block_type,
                "content_sample": request.content[:100],
            },
        )

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
