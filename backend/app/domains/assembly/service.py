import hashlib
import time
from typing import Any, Sequence
from uuid import UUID

from backend.app.domains.assembly.models import AssembledDocument
from backend.app.domains.assembly.repository import AssembledDocumentRepository
from backend.app.domains.assembly.schemas import (
    AssembledBlockSchema,
    AssembledDocumentSchema,
    AssemblyErrorCode,
    AssemblyRequest,
    AssemblyResult,
    AssemblyValidationResult,
    SectionInjectionResult,
    compute_block_content_hash,
    compute_text_hash,
)
from backend.app.domains.audit.generation_audit_service import GenerationAuditService
from backend.app.domains.generation.section_output_models import SectionOutput
from backend.app.domains.generation.section_output_repository import SectionOutputRepository
from backend.app.domains.parsing.repository import ParsedDocumentRepository
from backend.app.domains.parsing.schemas import (
    BlockType,
    DocumentBlock,
    DocumentMetadata,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    ParsedDocument,
    TableBlock,
)
from backend.app.domains.section.models import Section, SectionType
from backend.app.domains.section.repository import SectionRepository
from backend.app.logging_config import get_logger

logger = get_logger("app.domains.assembly.service")


class StructuralIntegrityValidator:
    def validate_block_preservation(
        self,
        original_blocks: list[DocumentBlock],
        assembled_blocks: list[dict[str, Any]],
    ) -> AssemblyValidationResult:
        result = AssemblyValidationResult()

        if len(original_blocks) != len(assembled_blocks):
            result.add_error(
                AssemblyErrorCode.BLOCK_COUNT_MISMATCH,
                f"Block count mismatch: original={len(original_blocks)}, assembled={len(assembled_blocks)}",
            )
            return result

        original_ids = {b.block_id for b in original_blocks}
        assembled_ids = {b["block_id"] for b in assembled_blocks}

        missing_ids = original_ids - assembled_ids
        extra_ids = assembled_ids - original_ids

        if missing_ids:
            result.add_error(
                AssemblyErrorCode.ORPHANED_BLOCK,
                f"Missing blocks after assembly: {missing_ids}",
            )

        if extra_ids:
            result.add_error(
                AssemblyErrorCode.STRUCTURAL_MISMATCH,
                f"Unexpected blocks introduced: {extra_ids}",
            )

        for i, (orig, assembled) in enumerate(zip(original_blocks, assembled_blocks)):
            if orig.block_id != assembled["block_id"]:
                result.add_error(
                    AssemblyErrorCode.BLOCK_ORDER_MISMATCH,
                    f"Block order mismatch at position {i}: expected {orig.block_id}, got {assembled['block_id']}",
                )
            if orig.block_type.value != assembled.get("block_type"):
                result.add_error(
                    AssemblyErrorCode.STRUCTURAL_MISMATCH,
                    f"Block type mismatch for {orig.block_id}: expected {orig.block_type}, got {assembled.get('block_type')}",
                )

        return result

    def validate_static_sections_unchanged(
        self,
        original_blocks: list[DocumentBlock],
        assembled_blocks: list[dict[str, Any]],
        static_block_ids: set[str],
    ) -> AssemblyValidationResult:
        result = AssemblyValidationResult()

        original_map = {b.block_id: b for b in original_blocks}
        assembled_map = {b["block_id"]: b for b in assembled_blocks}

        for block_id in static_block_ids:
            if block_id not in original_map or block_id not in assembled_map:
                continue

            orig = original_map[block_id]
            assembled = assembled_map[block_id]

            original_hash = compute_block_content_hash(orig)
            assembled_hash = assembled.get("assembled_content_hash", "")

            if original_hash != assembled_hash:
                result.add_error(
                    AssemblyErrorCode.STATIC_SECTION_MODIFIED,
                    f"Static block {block_id} was modified during assembly",
                )

        return result


class ContentInjector:
    def inject_into_paragraph(
        self,
        block: ParagraphBlock,
        content: str,
    ) -> tuple[dict[str, Any], str]:
        new_block_data = {
            "block_type": block.block_type.value,
            "block_id": block.block_id,
            "sequence": block.sequence,
            "runs": [
                {
                    "text": content,
                    "bold": False,
                    "italic": False,
                    "underline": False,
                    "strike": False,
                }
            ],
            "alignment": block.alignment,
            "indent_left": block.indent_left,
            "indent_right": block.indent_right,
            "indent_first_line": block.indent_first_line,
            "spacing_before": block.spacing_before,
            "spacing_after": block.spacing_after,
            "style_name": block.style_name,
        }
        content_hash = compute_text_hash(content)
        return new_block_data, content_hash

    def inject_into_heading(
        self,
        block: HeadingBlock,
        content: str,
    ) -> tuple[dict[str, Any], str]:
        new_block_data = {
            "block_type": block.block_type.value,
            "block_id": block.block_id,
            "sequence": block.sequence,
            "level": block.level,
            "runs": [
                {
                    "text": content,
                    "bold": False,
                    "italic": False,
                    "underline": False,
                    "strike": False,
                }
            ],
            "alignment": block.alignment,
            "style_name": block.style_name,
        }
        content_hash = compute_text_hash(content)
        return new_block_data, content_hash

    def preserve_block(self, block: DocumentBlock) -> tuple[dict[str, Any], str]:
        block_data = self._serialize_block(block)
        content_hash = compute_block_content_hash(block)
        return block_data, content_hash

    def _serialize_block(self, block: DocumentBlock) -> dict[str, Any]:
        if isinstance(block, ParagraphBlock):
            return {
                "block_type": block.block_type.value,
                "block_id": block.block_id,
                "sequence": block.sequence,
                "runs": [
                    {
                        "text": run.text,
                        "bold": run.bold,
                        "italic": run.italic,
                        "underline": run.underline,
                        "strike": run.strike,
                        "font_name": run.font_name,
                        "font_size": run.font_size,
                        "color": run.color,
                        "highlight": run.highlight,
                    }
                    for run in block.runs
                ],
                "alignment": block.alignment,
                "indent_left": block.indent_left,
                "indent_right": block.indent_right,
                "indent_first_line": block.indent_first_line,
                "spacing_before": block.spacing_before,
                "spacing_after": block.spacing_after,
                "style_name": block.style_name,
            }
        elif isinstance(block, HeadingBlock):
            return {
                "block_type": block.block_type.value,
                "block_id": block.block_id,
                "sequence": block.sequence,
                "level": block.level,
                "runs": [
                    {
                        "text": run.text,
                        "bold": run.bold,
                        "italic": run.italic,
                        "underline": run.underline,
                        "strike": run.strike,
                        "font_name": run.font_name,
                        "font_size": run.font_size,
                        "color": run.color,
                        "highlight": run.highlight,
                    }
                    for run in block.runs
                ],
                "alignment": block.alignment,
                "style_name": block.style_name,
            }
        elif isinstance(block, TableBlock):
            return {
                "block_type": block.block_type.value,
                "block_id": block.block_id,
                "sequence": block.sequence,
                "rows": [
                    {
                        "row_id": row.row_id,
                        "row_index": row.row_index,
                        "is_header": row.is_header,
                        "height": row.height,
                        "cells": [
                            {
                                "cell_id": cell.cell_id,
                                "row_index": cell.row_index,
                                "col_index": cell.col_index,
                                "row_span": cell.row_span,
                                "col_span": cell.col_span,
                                "width": cell.width,
                                "vertical_alignment": cell.vertical_alignment,
                                "content": [self._serialize_block(c) for c in cell.content],
                            }
                            for cell in row.cells
                        ],
                    }
                    for row in block.rows
                ],
                "column_count": block.column_count,
                "style_name": block.style_name,
            }
        elif isinstance(block, ListBlock):
            return {
                "block_type": block.block_type.value,
                "block_id": block.block_id,
                "sequence": block.sequence,
                "list_type": block.list_type,
                "items": [
                    {
                        "item_id": item.item_id,
                        "level": item.level,
                        "runs": [
                            {
                                "text": run.text,
                                "bold": run.bold,
                                "italic": run.italic,
                                "underline": run.underline,
                                "strike": run.strike,
                            }
                            for run in item.runs
                        ],
                        "bullet_char": item.bullet_char,
                        "number_format": item.number_format,
                        "number_value": item.number_value,
                    }
                    for item in block.items
                ],
                "style_name": block.style_name,
            }
        else:
            return {
                "block_type": block.block_type.value,
                "block_id": block.block_id,
                "sequence": block.sequence,
            }


class DocumentAssemblyService:
    def __init__(
        self,
        repository: AssembledDocumentRepository,
        section_output_repository: SectionOutputRepository,
        parsed_document_repository: ParsedDocumentRepository,
        section_repository: SectionRepository,
        generation_audit_service: GenerationAuditService | None = None,
    ):
        self.repository = repository
        self.section_output_repository = section_output_repository
        self.parsed_document_repository = parsed_document_repository
        self.section_repository = section_repository
        self.integrity_validator = StructuralIntegrityValidator()
        self.content_injector = ContentInjector()
        self.generation_audit_service = generation_audit_service

    async def assemble_document(self, request: AssemblyRequest) -> AssemblyResult:
        start_time = time.time()

        existing = await self.repository.get_by_section_output_batch(
            request.section_output_batch_id
        )
        if existing and existing.is_immutable and not request.force_reassembly:
            return AssemblyResult(
                success=False,
                error_code=AssemblyErrorCode.ASSEMBLY_ALREADY_EXISTS,
                error_message=f"Assembly already exists for batch {request.section_output_batch_id}",
            )

        parsed_doc = await self.parsed_document_repository.get_by_template_version_id(
            request.template_version_id
        )
        if not parsed_doc:
            return AssemblyResult(
                success=False,
                error_code=AssemblyErrorCode.MISSING_PARSED_TEMPLATE,
                error_message=f"No parsed template found for version {request.template_version_id}",
            )

        section_outputs = await self.section_output_repository.get_validated_outputs(
            request.section_output_batch_id
        )

        sections = await self.section_repository.get_by_template_version_id(
            request.template_version_id
        )

        validation_result = self._validate_assembly_inputs(sections, section_outputs)
        if not validation_result.is_valid:
            return AssemblyResult(
                success=False,
                validation_result=validation_result,
                error_code=(
                    validation_result.error_codes[0] if validation_result.error_codes else None
                ),
                error_message=(
                    validation_result.error_messages[0]
                    if validation_result.error_messages
                    else None
                ),
            )

        initial_hash = self._compute_initial_hash(request)
        assembled_doc = await self.repository.create(
            document_id=request.document_id,
            template_version_id=request.template_version_id,
            version_intent=request.version_intent,
            section_output_batch_id=request.section_output_batch_id,
            assembly_hash=initial_hash,
        )

        await self.repository.mark_in_progress(assembled_doc.id)

        try:
            assembly_result = self._perform_assembly(
                parsed_doc=parsed_doc,
                sections=sections,
                section_outputs=section_outputs,
            )

            if not assembly_result["validation_result"].is_valid:
                await self.repository.mark_failed(
                    assembled_doc.id,
                    assembly_result["validation_result"].error_codes[0].value,
                    assembly_result["validation_result"].error_messages[0],
                )
                elapsed_ms = (time.time() - start_time) * 1000
                return AssemblyResult(
                    success=False,
                    validation_result=assembly_result["validation_result"],
                    error_code=assembly_result["validation_result"].error_codes[0],
                    error_message=assembly_result["validation_result"].error_messages[0],
                    assembly_duration_ms=elapsed_ms,
                )

            elapsed_ms = (time.time() - start_time) * 1000

            final_hash = self._compute_final_hash(request, assembly_result["assembled_blocks"])

            await self.repository.mark_completed(
                assembled_doc_id=assembled_doc.id,
                assembled_structure={"blocks": assembly_result["assembled_blocks"]},
                injection_results=[r.model_dump() for r in assembly_result["injection_results"]],
                validation_result=assembly_result["validation_result"].model_dump(),
                metadata=parsed_doc.metadata.model_dump() if parsed_doc.metadata else {},
                headers=[self.content_injector._serialize_block(h) for h in parsed_doc.headers],
                footers=[self.content_injector._serialize_block(f) for f in parsed_doc.footers],
                total_blocks=len(assembly_result["assembled_blocks"]),
                dynamic_blocks_count=assembly_result["dynamic_count"],
                static_blocks_count=assembly_result["static_count"],
                injected_sections_count=len(
                    [r for r in assembly_result["injection_results"] if r.was_injected]
                ),
                assembly_duration_ms=elapsed_ms,
                assembly_hash=final_hash,
            )

            await self.repository.mark_validated(assembled_doc.id)

            refreshed_doc = await self.repository.get_by_id(assembled_doc.id)
            if not refreshed_doc:
                raise RuntimeError(f"Failed to retrieve assembled document {assembled_doc.id}")

            assembled_schema = self._build_assembled_schema(
                assembled_doc=refreshed_doc,
                assembled_blocks=assembly_result["assembled_blocks"],
                injection_results=assembly_result["injection_results"],
                validation_result=assembly_result["validation_result"],
                metadata=parsed_doc.metadata,
            )

            if self.generation_audit_service:
                await self.generation_audit_service.log_document_assembly_completed(
                    assembled_document_id=refreshed_doc.id,
                    document_id=request.document_id,
                    template_version_id=request.template_version_id,
                    version_intent=request.version_intent,
                    total_blocks=len(assembly_result["assembled_blocks"]),
                    dynamic_blocks_count=assembly_result["dynamic_count"],
                    static_blocks_count=assembly_result["static_count"],
                    injected_sections_count=len(
                        [r for r in assembly_result["injection_results"] if r.was_injected]
                    ),
                    assembly_hash=final_hash,
                )

            return AssemblyResult(
                success=True,
                assembled_document=assembled_schema,
                validation_result=assembly_result["validation_result"],
                injection_results=assembly_result["injection_results"],
                assembly_duration_ms=elapsed_ms,
            )

        except Exception as e:
            logger.error(f"Assembly failed: {e}", exc_info=True)
            if self.generation_audit_service:
                await self.generation_audit_service.log_document_assembly_failed(
                    assembled_document_id=assembled_doc.id,
                    document_id=request.document_id,
                    template_version_id=request.template_version_id,
                    version_intent=request.version_intent,
                    error_code="ASSEMBLY_EXCEPTION",
                    error_message=str(e),
                )
            await self.repository.mark_failed(
                assembled_doc.id,
                AssemblyErrorCode.STRUCTURAL_MISMATCH.value,
                str(e),
            )
            elapsed_ms = (time.time() - start_time) * 1000
            return AssemblyResult(
                success=False,
                error_code=AssemblyErrorCode.STRUCTURAL_MISMATCH,
                error_message=str(e),
                assembly_duration_ms=elapsed_ms,
            )

    def _validate_assembly_inputs(
        self,
        sections: Sequence[Section],
        section_outputs: Sequence[SectionOutput],
    ) -> AssemblyValidationResult:
        result = AssemblyValidationResult()

        dynamic_sections = [s for s in sections if s.section_type == SectionType.DYNAMIC]
        output_section_ids = {o.section_id for o in section_outputs}

        for section in dynamic_sections:
            if section.id not in output_section_ids:
                result.add_error(
                    AssemblyErrorCode.MISSING_VALIDATED_CONTENT,
                    f"Dynamic section {section.id} lacks validated content",
                )

        for output in section_outputs:
            if not output.is_validated:
                result.add_error(
                    AssemblyErrorCode.INVALID_SECTION_OUTPUT,
                    f"Section output {output.id} is not validated",
                )
            if not output.generated_content:
                result.add_error(
                    AssemblyErrorCode.MISSING_VALIDATED_CONTENT,
                    f"Section output {output.id} has no content",
                )

        return result

    def _perform_assembly(
        self,
        parsed_doc: ParsedDocument,
        sections: Sequence[Section],
        section_outputs: Sequence[SectionOutput],
    ) -> dict[str, Any]:
        output_map = {o.section_id: o for o in section_outputs}

        path_to_section: dict[str, Section] = {}
        for section in sections:
            path_to_section[section.structural_path] = section

        assembled_blocks: list[dict[str, Any]] = []
        injection_results: list[SectionInjectionResult] = []
        dynamic_count = 0
        static_count = 0
        static_block_ids: set[str] = set()

        for block in parsed_doc.blocks:
            block_path = f"body/block/{block.sequence}"
            maybe_section = path_to_section.get(block_path)

            if maybe_section and maybe_section.section_type == SectionType.DYNAMIC:
                dynamic_count += 1
                output = output_map.get(maybe_section.id)

                if output and output.generated_content:
                    if isinstance(block, ParagraphBlock):
                        block_data, content_hash = self.content_injector.inject_into_paragraph(
                            block, output.generated_content
                        )
                    elif isinstance(block, HeadingBlock):
                        block_data, content_hash = self.content_injector.inject_into_heading(
                            block, output.generated_content
                        )
                    else:
                        block_data, content_hash = self.content_injector.preserve_block(block)
                        injection_results.append(
                            SectionInjectionResult(
                                section_id=maybe_section.id,
                                structural_path=maybe_section.structural_path,
                                was_injected=False,
                                error_message=f"Unsupported block type for injection: {block.block_type}",
                            )
                        )
                        assembled_blocks.append(
                            {
                                **block_data,
                                "is_dynamic": True,
                                "section_id": maybe_section.id,
                                "original_content_hash": compute_block_content_hash(block),
                                "assembled_content_hash": content_hash,
                                "was_modified": False,
                            }
                        )
                        continue

                    injection_results.append(
                        SectionInjectionResult(
                            section_id=maybe_section.id,
                            structural_path=maybe_section.structural_path,
                            was_injected=True,
                            original_content_hash=compute_block_content_hash(block),
                            injected_content_hash=content_hash,
                            content_length=len(output.generated_content),
                            is_static=False,
                        )
                    )

                    assembled_blocks.append(
                        {
                            **block_data,
                            "is_dynamic": True,
                            "section_id": maybe_section.id,
                            "original_content_hash": compute_block_content_hash(block),
                            "assembled_content_hash": content_hash,
                            "was_modified": True,
                        }
                    )
                else:
                    block_data, content_hash = self.content_injector.preserve_block(block)
                    assembled_blocks.append(
                        {
                            **block_data,
                            "is_dynamic": True,
                            "section_id": maybe_section.id,
                            "original_content_hash": content_hash,
                            "assembled_content_hash": content_hash,
                            "was_modified": False,
                        }
                    )
            else:
                static_count += 1
                block_data, content_hash = self.content_injector.preserve_block(block)
                static_block_ids.add(block.block_id)
                assembled_blocks.append(
                    {
                        **block_data,
                        "is_dynamic": False,
                        "section_id": maybe_section.id if maybe_section else None,
                        "original_content_hash": content_hash,
                        "assembled_content_hash": content_hash,
                        "was_modified": False,
                    }
                )

        block_validation = self.integrity_validator.validate_block_preservation(
            parsed_doc.blocks, assembled_blocks
        )

        static_validation = self.integrity_validator.validate_static_sections_unchanged(
            parsed_doc.blocks, assembled_blocks, static_block_ids
        )

        combined_validation = AssemblyValidationResult()
        for code, msg in zip(block_validation.error_codes, block_validation.error_messages):
            combined_validation.add_error(code, msg)
        for code, msg in zip(static_validation.error_codes, static_validation.error_messages):
            combined_validation.add_error(code, msg)

        return {
            "assembled_blocks": assembled_blocks,
            "injection_results": injection_results,
            "validation_result": combined_validation,
            "dynamic_count": dynamic_count,
            "static_count": static_count,
        }

    def _compute_initial_hash(self, request: AssemblyRequest) -> str:
        content = f"{request.document_id}|{request.template_version_id}|{request.version_intent}|{request.section_output_batch_id}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_final_hash(
        self,
        request: AssemblyRequest,
        assembled_blocks: list[dict[str, Any]],
    ) -> str:
        content_parts = [
            str(request.document_id),
            str(request.template_version_id),
            str(request.version_intent),
            str(request.section_output_batch_id),
        ]
        for block in sorted(assembled_blocks, key=lambda b: b.get("sequence", 0)):
            content_parts.append(f"{block['block_id']}:{block.get('assembled_content_hash', '')}")
        combined = "|".join(content_parts)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _build_assembled_schema(
        self,
        assembled_doc: AssembledDocument,
        assembled_blocks: list[dict[str, Any]],
        injection_results: list[SectionInjectionResult],
        validation_result: AssemblyValidationResult,
        metadata: DocumentMetadata | None,
    ) -> AssembledDocumentSchema:
        block_schemas = [
            AssembledBlockSchema(
                block_id=b["block_id"],
                block_type=BlockType(b["block_type"]),
                sequence=b.get("sequence", 0),
                is_dynamic=b.get("is_dynamic", False),
                section_id=b.get("section_id"),
                original_content_hash=b.get("original_content_hash"),
                assembled_content_hash=b.get("assembled_content_hash"),
                was_modified=b.get("was_modified", False),
                block_data=b,
            )
            for b in assembled_blocks
        ]

        return AssembledDocumentSchema(
            id=assembled_doc.id,
            document_id=assembled_doc.document_id,
            template_version_id=assembled_doc.template_version_id,
            version_intent=assembled_doc.version_intent,
            section_output_batch_id=assembled_doc.section_output_batch_id,
            assembly_hash=assembled_doc.assembly_hash,
            total_blocks=assembled_doc.total_blocks,
            dynamic_blocks_count=assembled_doc.dynamic_blocks_count,
            static_blocks_count=assembled_doc.static_blocks_count,
            injected_sections_count=assembled_doc.injected_sections_count,
            metadata=metadata,
            blocks=block_schemas,
            headers=assembled_doc.headers,
            footers=assembled_doc.footers,
            injection_results=injection_results,
            validation_result=validation_result,
            is_immutable=assembled_doc.is_immutable,
            assembled_at=assembled_doc.assembled_at or assembled_doc.created_at,
        )

    async def get_assembled_document(
        self, document_id: UUID, version_intent: int
    ) -> AssembledDocument | None:
        return await self.repository.get_by_document_and_version(document_id, version_intent)

    async def get_renderable_document(
        self, document_id: UUID, version_intent: int
    ) -> AssembledDocument | None:
        return await self.repository.get_renderable_document(document_id, version_intent)

    def validate_determinism(
        self,
        first_result: AssemblyResult,
        second_result: AssemblyResult,
    ) -> bool:
        if not first_result.assembled_document or not second_result.assembled_document:
            return False

        if (
            first_result.assembled_document.assembly_hash
            != second_result.assembled_document.assembly_hash
        ):
            return False

        first_blocks = first_result.assembled_document.blocks
        second_blocks = second_result.assembled_document.blocks

        if len(first_blocks) != len(second_blocks):
            return False

        for b1, b2 in zip(first_blocks, second_blocks):
            if b1.block_id != b2.block_id:
                return False
            if b1.assembled_content_hash != b2.assembled_content_hash:
                return False

        return True
