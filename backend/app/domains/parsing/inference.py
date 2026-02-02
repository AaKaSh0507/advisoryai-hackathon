import json
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

from backend.app.domains.parsing.schemas import (
    BlockType,
    HeadingBlock,
    ParagraphBlock,
    ParsedDocument,
)
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.parsing.inference")


class StructureSuggestion(BaseModel):
    block_id: str
    suggestion_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    new_level: int | None = None
    reason: str


class InferenceResult(BaseModel):
    suggestions: list[StructureSuggestion] = Field(default_factory=list)
    applied_count: int = 0
    skipped_count: int = 0
    duration_ms: float = 0.0
    errors: list[str] = Field(default_factory=list)


@dataclass
class LLMConfig:
    api_key: str
    api_base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    max_tokens: int = 2000
    temperature: float = 0.0
    timeout_seconds: int = 30
    enabled: bool = True
    confidence_threshold: float = 0.85


class StructureInferenceService:
    SYSTEM_PROMPT = """You are a document structure analyzer. Your task is to identify potential structural inconsistencies in parsed Word documents.

IMPORTANT RULES:
1. You can ONLY suggest changes to existing blocks - never add or remove blocks
2. You can only suggest: promoting paragraphs to headings, adjusting heading levels, or marking list continuations
3. Each suggestion must have a confidence score (0.0-1.0)
4. Only suggest changes where the structural pattern is clearly inconsistent
5. Be conservative - when in doubt, do not suggest changes

Output format (JSON array):
[
  {
    "block_id": "blk_xxx_xxxx_xxxx",
    "suggestion_type": "promote_to_heading",
    "confidence": 0.9,
    "new_level": 2,
    "reason": "This paragraph follows a clear heading pattern (all caps, short, followed by body text)"
  }
]

Valid suggestion_types:
- "promote_to_heading": A paragraph should be a heading
- "adjust_level": A heading level should be adjusted
- "merge_list": Consecutive paragraphs are actually a single list

Only return the JSON array, no other text."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.config.timeout_seconds if self.config else 30)
        return self._client

    def infer_structure(self, document: ParsedDocument) -> InferenceResult:
        start_time = time.time()
        if not self.config or not self.config.enabled:
            logger.info("LLM inference disabled, skipping structure analysis")
            return InferenceResult(duration_ms=(time.time() - start_time) * 1000)

        if not self.config.api_key:
            logger.warning("LLM API key not configured, skipping structure analysis")
            return InferenceResult(
                errors=["LLM API key not configured"], duration_ms=(time.time() - start_time) * 1000
            )

        try:
            doc_summary = self._prepare_document_summary(document)
            suggestions = self._call_llm(doc_summary)
            valid_suggestions = self._validate_suggestions(suggestions, document)
            applied, skipped = self._apply_suggestions(valid_suggestions, document)
            end_time = time.time()

            return InferenceResult(
                suggestions=valid_suggestions,
                applied_count=applied,
                skipped_count=skipped,
                duration_ms=(end_time - start_time) * 1000,
            )

        except Exception as e:
            logger.error(f"Structure inference failed: {e}", exc_info=True)
            end_time = time.time()
            return InferenceResult(
                errors=[str(e)],
                duration_ms=(end_time - start_time) * 1000,
            )

    def _prepare_document_summary(self, document: ParsedDocument) -> str:
        lines = []
        lines.append(f"Document has {document.total_blocks} blocks:")
        lines.append(f"- {document.heading_count} headings")
        lines.append(f"- {document.paragraph_count} paragraphs")
        lines.append(f"- {document.table_count} tables")
        lines.append(f"- {document.list_count} lists")
        lines.append("")
        lines.append("Block structure (first 50 blocks):")

        for _, block in enumerate(document.blocks[:50]):
            block_type = block.block_type if hasattr(block, "block_type") else "unknown"

            if isinstance(block, HeadingBlock):
                text = block.text[:60] if block.text else ""
                lines.append(f"  [{block.block_id}] HEADING L{block.level}: {text}")
            elif isinstance(block, ParagraphBlock):
                text = block.text[:60] if block.text else ""
                lines.append(f"  [{block.block_id}] PARAGRAPH: {text}")
            else:
                lines.append(f"  [{block.block_id}] {block_type.upper()}")

        if len(document.blocks) > 50:
            lines.append(f"  ... and {len(document.blocks) - 50} more blocks")

        return "\n".join(lines)

    def _call_llm(self, doc_summary: str) -> list[StructureSuggestion]:
        if not self.config:
            return []

        client = self._get_client()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": doc_summary},
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        response = client.post(
            f"{self.config.api_base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            suggestions_data = json.loads(content)

            suggestions = []
            for item in suggestions_data:
                try:
                    suggestion = StructureSuggestion(
                        block_id=item["block_id"],
                        suggestion_type=item["suggestion_type"],
                        confidence=item.get("confidence", 0.5),
                        new_level=item.get("new_level"),
                        reason=item.get("reason", ""),
                    )
                    suggestions.append(suggestion)
                except Exception as e:
                    logger.warning(f"Invalid suggestion from LLM: {e}")

            return suggestions

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return []

    def _validate_suggestions(
        self,
        suggestions: list[StructureSuggestion],
        document: ParsedDocument,
    ) -> list[StructureSuggestion]:
        valid_suggestions = []
        block_ids = {block.block_id for block in document.blocks if hasattr(block, "block_id")}

        for suggestion in suggestions:
            if suggestion.block_id not in block_ids:
                logger.warning(f"Suggestion references non-existent block: {suggestion.block_id}")
                continue
            valid_types = {"promote_to_heading", "adjust_level", "merge_list"}
            if suggestion.suggestion_type not in valid_types:
                logger.warning(f"Invalid suggestion type: {suggestion.suggestion_type}")
                continue
            if suggestion.new_level is not None and not (1 <= suggestion.new_level <= 9):
                logger.warning(f"Invalid heading level: {suggestion.new_level}")
                continue

            valid_suggestions.append(suggestion)

        return valid_suggestions

    def _apply_suggestions(
        self,
        suggestions: list[StructureSuggestion],
        document: ParsedDocument,
    ) -> tuple[int, int]:
        if not self.config:
            return 0, len(suggestions)

        threshold = self.config.confidence_threshold
        applied = 0
        skipped = 0
        block_index = {
            block.block_id: (i, block)
            for i, block in enumerate(document.blocks)
            if hasattr(block, "block_id")
        }

        for suggestion in suggestions:
            if suggestion.confidence < threshold:
                logger.debug(
                    f"Skipping low-confidence suggestion ({suggestion.confidence:.2f}): "
                    f"{suggestion.suggestion_type} for {suggestion.block_id}"
                )
                skipped += 1
                continue

            if suggestion.block_id not in block_index:
                skipped += 1
                continue

            index, block = block_index[suggestion.block_id]

            try:
                if suggestion.suggestion_type == "promote_to_heading":
                    if isinstance(block, ParagraphBlock):
                        new_block = HeadingBlock(
                            block_type=BlockType.HEADING,
                            block_id=block.block_id,
                            sequence=block.sequence,
                            level=suggestion.new_level or 2,
                            runs=block.runs,
                            alignment=block.alignment,
                            style_name=block.style_name,
                        )
                        document.blocks[index] = new_block
                        applied += 1
                        logger.info(
                            f"Applied suggestion: promoted {block.block_id} to heading L{suggestion.new_level}"
                        )
                    else:
                        skipped += 1

                elif suggestion.suggestion_type == "adjust_level":
                    if isinstance(block, HeadingBlock) and suggestion.new_level:
                        block.level = suggestion.new_level
                        applied += 1
                        logger.info(
                            f"Applied suggestion: adjusted {block.block_id} to level {suggestion.new_level}"
                        )
                    else:
                        skipped += 1

                else:
                    skipped += 1

            except Exception as e:
                logger.warning(f"Failed to apply suggestion: {e}")
                skipped += 1

        if applied > 0:
            document.compute_statistics()

        return applied, skipped

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
